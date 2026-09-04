# 03 — Just-in-Time Context and Capability Exposure

An Agent may have access to hundreds of Tools, Skills, memories, documents, and files. The model rarely needs all of them on every turn.

**Progressive disclosure** means exposing detail only when the current decision requires it.

```text
large capability/data universe
        ↓ discover metadata
small relevant subset
        ↓ activate/read
current model context
```

This principle connects RAG, dynamic Tool exposure, Agent Skills, workspace access, and multi-Agent context projection.

---

## 1. Installed != exposed

Suppose the Host can execute 200 Tools.

Bad default:

```text
all 200 schemas -> every model call
```

Problems:

- larger input cost;
- more Tool-selection confusion;
- larger attack surface;
- more accidental high-risk options;
- unstable prompt prefixes.

Better:

```text
Host owns 200 Tools
-> task/phase policy selects 8
-> model sees 8 schemas
-> runtime can only execute authorized calls
```

Note the two separate controls:

```text
exposure = what the model sees
permission = what the runtime may execute
```

Hiding a Tool is useful context policy. It is not an authorization mechanism by itself.

---

## 2. Dynamic Tool exposure

Conceptual policy:

```python
TOOL_GROUPS = {
    "research": {"search_papers", "read_document", "save_note"},
    "export": {"render_report", "write_report"},
}


def tools_for_phase(phase: str, all_tools):
    names = TOOL_GROUPS[phase]
    return [tool for tool in all_tools if tool.name in names]
```

The model is not asked:

> Which forbidden tools would you prefer to see?

The application first defines the candidate set.

---

## 3. RAG is just-in-time factual context

A vector store may contain millions of chunks.

The model receives perhaps five.

```text
corpus
-> query
-> candidate retrieval
-> rerank/filter/diversify
-> evidence subset
-> model
```

That is progressive disclosure applied to external knowledge.

The same idea works for historical conversation:

```text
full history stored
-> retrieve relevant prior decisions
-> include only selected pieces now
```

---

## 4. Skills are just-in-time procedural context

Stage 08 uses three levels:

```text
all Skills: name + description metadata
            ↓ choose relevant Skill
activated: SKILL.md instructions
            ↓ need detail
resource: one reference/script/asset
```

Tiny-Agent's `SkillCatalog.metadata_prompt()` deliberately avoids loading every full Skill:

```python
catalog = SkillCatalog("skills")
print(catalog.metadata_prompt())

# - code-review: Review code changes safely...
# - research-review: Check claims against evidence...
```

Then:

```python
skill = catalog.activate("research-review")
print(skill.instructions)
```

This is much cheaper than stuffing fifteen procedural manuals into every request.

---

## 5. Workspace files are context candidates, not automatic prompt content

A coding Agent may own a repository with 10,000 files.

Bad:

```text
read repository recursively
-> concatenate every file
-> ask model to fix one function
```

Better:

```text
search/list relevant paths
-> read target file
-> inspect neighboring definitions/tests
-> make change
-> run tests
```

The filesystem is external working state. The model reads slices of it as needed.

This matters for both token efficiency and data minimization.

---

## 6. Multi-Agent context should be projected, not cloned

Suppose a supervisor delegates "review citations" to a critic Agent.

Bad handoff:

```text
copy entire supervisor state
including secrets, unrelated tools, all memories, all user data
```

Better:

```text
subtask
+ relevant draft
+ cited evidence
+ critic-specific instructions/tools
```

A sub-Agent should receive the minimum context and authority needed for its role.

Stage 11 calls this context ownership/projection.

---

## 7. Context activation should be phase-aware

A research run might use:

```text
PLAN phase
  -> planner instructions
  -> user objective
  -> high-level memory
  -> no export Tool

RETRIEVE phase
  -> search/read Tools
  -> search Skill
  -> evidence budget

WRITE phase
  -> selected evidence
  -> style memory
  -> no open search Tool if research is complete

EXPORT phase
  -> approval state
  -> authorized write capability
```

Different phases need different action spaces.

This is a powerful reliability technique: reduce the number of invalid next actions the model can even propose.

---

## 8. Worked example: 80 Tools, 15 Skills

Question:

```text
"Compare two RAG reranking strategies and write a Markdown report."
```

Startup metadata:

```text
Skill catalog metadata: 15 short descriptions
Tool catalog metadata: application-owned registry
```

Planning selects:

```text
Skills: research-review
Tools: search_papers, read_document, save_note
```

After evidence is sufficient:

```text
remove search Tools from writer context
load selected evidence
load report-writing instructions
```

Only at export:

```text
write_report becomes eligible
HITL/policy still controls execution
```

The Agent remains capable without seeing the entire universe every turn.

---

## 9. Failure mode: relevance becomes authority

A dynamic selector may decide a Tool or Skill is relevant. That does not authorize it.

```text
semantic selector: "database_admin is relevant"
        ↓
application policy: caller lacks admin permission
        ↓
not exposed / not executable
```

The selector proposes context. Deterministic policy owns trust and permission.

---

## 10. Evaluate progressive disclosure

Compare:

```text
all-tools baseline
vs
phase-selected tools
```

Measure:

- task success;
- Tool precision (useful calls / calls);
- invalid Tool calls;
- tokens per turn;
- latency/cost;
- security exposure;
- selector recall (did it hide a capability that was actually needed?).

Too much exposure creates noise. Too aggressive selection creates capability starvation. Context engineering is the policy between those extremes.

---

## Core principle

> **Make large application capability/data spaces discoverable, but make model context small and just-in-time.**

Progressive disclosure is not about making the Agent weaker. It is about making the next decision clearer.