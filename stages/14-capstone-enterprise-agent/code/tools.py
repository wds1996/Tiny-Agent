"""Application-owned schemas and dispatch: discovery never grants authority."""
from __future__ import annotations

import json

from domain import DATA, BoundaryError, Identity, encode, fields, refund_quote, text
from mcp_bridge import READ_TOOLS
from retrieval import KnowledgeBase
from skills import SkillLibrary

# MCP write tools deliberately do not appear in this model-facing registry.
SPECS = {
    "list_orders": ("List accessible orders; ask the user to choose instead of guessing.", {}),
    "get_order": ("Read authoritative facts for the order in this request.", {"order_id": "string"}),
    "get_shipment": ("Read recorded fictional shipment events.", {"order_id": "string"}),
    "get_invoice": ("Read the original invoice, not the refundable balance.", {"order_id": "string"}),
    "get_product": ("Read a catalog SKU and warranty duration.", {"sku": "string"}),
    "get_ticket": ("Read a service ticket belonging to this customer.", {"ticket_id": "string"}),
    "search_knowledge": ("Search effective merchant policy passages with a focused query.", {"query": "string"}),
    "read_knowledge": ("Read an exact passage ID returned by search, not a path.", {"passage_id": "string"}),
    "load_skill": ("Load a registered support procedure. It cannot add tools.", {"name": "string"}),
    "calculate_refund": ("Compute eligibility and net CNY cents; NEVER execute payment.", {"order_id": "string"}),
    "read_preferences": ("Read only this customer's consented language preference.", {}),
    "save_case_note": ("Save a short case-only note, not an external ticket.", {"note": "string"}),
}


def definitions() -> list[dict]:
    tools = []
    for name, (description, parameters) in SPECS.items():
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {key: {"type": kind} for key, kind in parameters.items()},
                    "required": list(parameters),
                    "additionalProperties": False,
                },
            },
        })
    return tools


class ToolRouter:
    def __init__(self, state: dict, bridge, kb: KnowledgeBase, skills: SkillLibrary, budget):
        self.state = state
        self.bridge = bridge
        self.kb = kb
        self.skills = skills
        self.budget = budget
        self.identity = Identity(**state["identity"])
        self.rules = json.loads((DATA / "refund_rules.json").read_text(encoding="utf-8"))
        self.as_of = json.loads((DATA / "business.json").read_text(encoding="utf-8"))["as_of"]

    def scope(self) -> dict:
        return {
            "tenant": self.identity.tenant,
            "language": self.state["language"],
            "as_of": self.as_of,
        }

    def add_evidence(self, results: list[dict]):
        for passage in results:
            self.state["evidence"][passage["id"]] = passage
        if len(self.state["evidence"]) > 32:
            raise BoundaryError("evidence_budget_exhausted")

    def order_scope(self, order_id: str):
        # The service also authorizes every read; this prevents accidental case switching.
        if order_id != self.state["plan"]["order_id"]:
            raise BoundaryError("order_not_bound_to_case")

    async def execute(self, name: str, arguments: dict) -> dict:
        self.budget("tool")
        if name not in SPECS:
            raise BoundaryError("model_tool_not_allowed")
        fields(arguments, set(SPECS[name][1]))
        for value in arguments.values():
            text(value, maximum=1500)
        if "order_id" in arguments:
            self.order_scope(arguments["order_id"])
        if name in READ_TOOLS:
            result = await self.bridge.call(name, arguments)
            if len(encode(result)) > 14_000:
                raise BoundaryError("tool_result_too_large")
            source = name + ":" + next(iter(arguments.values()), "current")
            self.state["facts"][source] = result
            return {"source_id": source, "data": result}
        if name == "search_knowledge":
            results = self.kb.search(arguments["query"], **self.scope())
            self.add_evidence(results)
            return {"passages": results}
        if name == "read_knowledge":
            passage = self.kb.read(arguments["passage_id"], **self.scope())
            self.add_evidence([passage])
            return passage
        if name == "load_skill":
            return {"procedure": self.skills.load(arguments["name"], self.state["language"])}
        if name == "read_preferences":
            return dict(self.state["preferences"])
        if name == "save_case_note":
            if len(self.state.setdefault("notes", [])) >= 3:
                raise BoundaryError("note_limit")
            self.state["notes"].append(arguments["note"])
            return {"saved": True, "scope": "case_only"}
        if name == "calculate_refund":
            return await self.calculate_refund(arguments["order_id"])
        raise BoundaryError("unimplemented_tool")

    async def calculate_refund(self, order_id: str) -> dict:
        order = await self.bridge.call("get_order", {"order_id": order_id})
        self.state["facts"]["get_order:" + order_id] = order
        full = {**order, "tenant": self.identity.tenant, "user": self.identity.user}
        quote = refund_quote(full, self.rules, self.as_of)
        if self.identity.tenant == self.rules["tenant"]:
            proof = []
            for page in self.rules["policy_pages"]:
                proof.extend(self.kb.page(page, **self.scope()))
            if any("returns-" + p["version"] != self.rules["version"] for p in proof):
                raise BoundaryError("rule_document_version_mismatch")
            self.add_evidence(proof)
            quote["evidence_ids"] = [p["id"] for p in proof]
        # Evidence IDs describe the quote, but are not its financial fingerprint.
        self.state["quote"] = quote
        return quote

    def context(self) -> dict:
        mandatory = set(self.state.get("quote", {}).get("evidence_ids", []))
        all_ids = list(self.state["evidence"])
        selected = [i for i in all_ids if i in mandatory]
        remaining = 12 - len(selected)
        if remaining < 0:
            raise BoundaryError("mandatory_context_exceeds_budget")
        if remaining:
            selected += [i for i in all_ids if i not in mandatory][-remaining:]
        evidence = [
            {key: self.state["evidence"][i][key]
             for key in ("id", "document", "page", "version", "title", "body")}
            for i in selected
        ]
        return {
            "question": self.state["question"],
            "language": self.state["language"],
            "plan": self.state["plan"],
            "procedure": self.state["procedure"],
            "facts": self.state["facts"],
            "evidence": evidence,
            "quote": self.state.get("quote"),
            "preferences": self.state["preferences"],
            "case_notes": self.state.get("notes", []),
        }
