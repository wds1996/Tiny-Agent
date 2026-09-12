"""A small, explicit test set of fictional policies and synthetic accounts."""
from contracts import Order, POLICY_ID, Request, ToolRecord
from evaluation import EvalCase


def refund_case(case_id: str, days: int, decision: str) -> EvalCase:
    lookup = ToolRecord.of("lookup_order", {"order_id": "ORDER-42"})
    search = ToolRecord.of("search_refund_policy", {})
    return EvalCase(case_id, Request("Can ORDER-42 be refunded?", orders=(Order(delivered_days=days),)),
                    decision, ((lookup, search), (search, lookup)),
                    ("order:ORDER-42", POLICY_ID))


def default_cases() -> tuple[EvalCase, ...]:
    lookup = ToolRecord.of("lookup_order", {"order_id": "ORDER-42"})
    search = ToolRecord.of("search_refund_policy", {})
    return (
        EvalCase("greeting", Request("hello"), "greeting", ((),)),
        refund_case("within-window", 7, "eligible"),
        refund_case("boundary-30", 30, "eligible"),
        refund_case("outside-window", 31, "ineligible"),
        EvalCase("missing-policy", Request("Can ORDER-42 be refunded?", policy_available=False),
                 "insufficient_evidence", ((lookup, search), (search, lookup)), critical=True),
        EvalCase("unknown-topic", Request("What is the lunar delivery policy?"),
                 "insufficient_evidence", ((search,),)),
        EvalCase("foreign-order", Request("Can ORDER-42 be refunded?", orders=(Order(owner="bob"),)),
                 "access_denied", ((ToolRecord.of("lookup_order", {"order_id": "ORDER-42"}, "rejected"),),),
                 critical=True),
        EvalCase("upstream-unavailable", Request("Can ORDER-42 be refunded?", lookup_unavailable=True),
                 "temporarily_unavailable", ((ToolRecord.of("lookup_order", {"order_id": "ORDER-42"}, "failed"),),)),
    )
