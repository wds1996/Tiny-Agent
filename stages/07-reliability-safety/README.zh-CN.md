# Stage 07 — Reliability、Safety 与 Tool Governance

> Language: [English](README.md) | 简体中文

Stage 07 要把 Tiny-Agent 从一个“**能够执行**”的系统，升级成一个能够**明确拒绝、限制资源、超时、重试，并以可预测方式治理执行**的系统。

Stage 00–06 先逐步把能力加进来：

```text
LLM decisions
    -> Tool execution
    -> planning / graph state
    -> RAG
    -> MCP external capabilities
    -> durable memory / HITL
```

Stage 07 开始追问 control plane 层面真正关键的问题：

> **一个 LLM 到底应该拥有多少 authority？哪些 authority 必须始终留在确定性的 application policy 手里？**

本阶段最重要的原则是：

> **把模型输出当成不可信的程序输入。先验证 proposal，尽量缩小它的 authority，限制它消耗的资源，并且让所有 side effect 都经过模型之外的运行时治理。**

---

# 为什么需要这一阶段？

Agent demo 经常默认：

```text
valid arguments
healthy network
well-behaved model
safe tool
unlimited budget
honest retrieved content
```

真实系统会遇到：

```text
malformed ToolCalls
provider/network failures
timeouts and cancellation
repeated loops
expensive runaway trajectories
permission boundaries
stale or mismatched approvals
indirect prompt injection
secret-bearing exceptions
unsafe downstream output
untrusted code/processes
```

目标不是让 failure 永远消失。

目标是让 failure **可分类、可限制、可观察，并且在恢复过程中绝不偷偷扩大权限**。

---

# 前置知识

完成 Stage 00–06，或者已经理解：

- Structured Output / Function Calling；
- `Tool` / `ToolRegistry` 与 ReAct execution；
- workflow 与 Agent budgets；
- explicit graph state；
- RAG external-evidence trust boundary；
- MCP Host/Client/Server 与 remote capability；
- durable checkpoint 与 long-term memory；
- approve/edit/reject HITL；
- Python `async` / `await` 基础。

Stage 06 尤其重要，因为 Stage 07 直接建立在下面三个结论上：

```text
approval != authorization
external content != authority
durable execution != exactly-once side effect
```

---

# 先修复现有集成 Runtime 的两个生产缺口

Stage 07 在加入新能力前，先修正两个已有问题。

## 1. Arbitrary exception text 不再进入模型 transcript

早期 Stage 01 风格的处理：

```python
except Exception as exc:
    return f"ToolError[{type(exc).__name__}]: {exc}"
```

可能把这些内容送进模型：

```text
connection strings
internal paths
provider response bodies
secret fragments
implementation details
```

新的可复用 runtime 会把 unexpected exception 转成 model-safe failure：

```text
ToolFailure[internal_error]: Tool execution failed.
```

同时保留 internal exception type，供后续 logging/observability 使用。

## 2. `ToolRegistry` 增加 `get()`

Stage 07 的 policy code 需要在 execution 前检查 Tool schema/handler，而不应该直接访问私有 `_tools` 字典。

因此 registry 增加一个很小的 public lookup method，同时保留 Stage 01 原有 execution API。

---

# 学习路径

```text
failure taxonomy + safe redaction
        ↓
local argument validation
        ↓
jsonschema + Pydantic strict boundaries
        ↓
timeout / cancellation
        ↓
retryable failure vs retry-safe operation
        ↓
backoff / jitter / Tenacity comparison
        ↓
run-wide budgets
        ↓
exact repeated-call detection
        ↓
default-deny Tool permissions
        ↓
exact-action approval binding
        ↓
prompt-injection trust boundaries
        ↓
process vs sandbox concepts
        ↓
GuardedToolExecutor
```

不要直接跳到最终 executor。前面的每一个机制，都对应最终 policy pipeline 中的一条明确控制。

---

# 学习目标

完成 Stage 07 后，你应该能够：

1. 区分 safe operational error 与 arbitrary internal exception；
2. 解释为什么 raw `str(exc)` 不应进入 model context；
3. 在 handler invocation 前本地验证动态 Tool arguments；
4. 比较手写 JSON Schema subset 与维护成熟的 `jsonschema` package；
5. 用 Pydantic strict mode 建立稳定的 application-owned typed boundary；
6. 区分 validation 与 authorization；
7. 区分 async timeout 与 cancellation；
8. 解释为什么超时返回的 worker thread 可能仍在后台运行；
9. 区分 retryable failure 与 retry-safe/idempotent action；
10. 实现 bounded exponential backoff 并解释 jitter；
11. 对比手写 retry mechanism 与 Tenacity；
12. 维护 run-wide tool/retry/time/token/cost budgets；
13. 在全局 cap 耗尽前检测 exact repeated ToolCall；
14. 解释为什么 exact repetition 不是万能 loop detector；
15. 使用 default-deny Tool allowlist 与 authenticated `Principal`；
16. 区分 discovery 与 authorization；
17. 把 human approval 绑定到**准确的 Tool + arguments**；
18. 解释 approval 为什么仍不能替代 role/downstream authorization；
19. 识别 excessive functionality、permissions 与 autonomy；
20. 区分 direct 与 indirect prompt injection；
21. 把 external content 留在 data plane，而不是允许它重写 control policy；
22. 解释为什么 RAG 或 prompt delimiter 本身解决不了 prompt injection；
23. 把 injection detector 当成 signal，而不是 permission system；
24. 解释为什么 narrow Tool 通常比 generic shell/API proxy Tool 更安全；
25. 区分 in-process function、worker thread、child process、container 与 security sandbox；
26. 从 model proposal 到真实 side effect 画出完整 guarded execution pipeline。

---

# Part A — 安全地失败

阅读：

1. [`theory/01-agent-failure-modes.zh-CN.md`](theory/01-agent-failure-modes.zh-CN.md)

运行：

```bash
python stages/07-reliability-safety/code/error_model.py
```

记住：

```text
known + deliberately sanitized failure
    -> may cross model boundary

unexpected exception
    -> generic model-safe failure
    -> detailed diagnostics remain internal
```

---

# Part B — 执行前先 Validation

阅读：

2. [`theory/02-validation-and-output-handling.zh-CN.md`](theory/02-validation-and-output-handling.zh-CN.md)

运行：

```bash
python stages/07-reliability-safety/code/validation_boundary.py
```

教学顺序：

```text
SimpleToolArgumentsValidator
    -> inspect validation mechanics

JsonSchemaToolArgumentsValidator
    -> mature dynamic JSON Schema validation

Pydantic strict model
    -> stable application-owned Python boundary
```

三个边界必须分开：

```text
provider constrained generation
    !=
local runtime validation
    !=
authorization
```

---

# Part C — Timeout、Cancellation 与 Retry

阅读：

3. [`theory/03-timeout-retry-cancellation.zh-CN.md`](theory/03-timeout-retry-cancellation.zh-CN.md)

运行：

```bash
python stages/07-reliability-safety/code/retry_policy.py
```

必须记住的规则：

```text
retryable failure
AND
retry-safe operation
AND
attempts remain
AND
global retry budget remains
    ↓
retry
```

而不是：

```text
exception happened
    ↓
retry everything forever
```

---

# Part D — Bound Autonomy

阅读：

4. [`theory/04-execution-budgets-and-loops.zh-CN.md`](theory/04-execution-budgets-and-loops.zh-CN.md)

运行：

```bash
python stages/07-reliability-safety/code/execution_budget.py
python stages/07-reliability-safety/code/loop_detection.py
```

Tiny-Agent 现在显式建模：

```text
tool-call budget
retry budget
elapsed-time budget
token budget
cost budget
```

当 provider usage metadata 可用时记录 token/cost；Stage 08 会继续把这些变成可观察、可评估的数据。

---

# Part E — Minimize Authority

阅读：

5. [`theory/05-tool-permissions-and-least-privilege.zh-CN.md`](theory/05-tool-permissions-and-least-privilege.zh-CN.md)

运行：

```bash
python stages/07-reliability-safety/code/permission_policy.py
```

关键链路：

```text
authenticated application Principal
        ↓
default-deny Tool allowlist
        ↓
role check
        ↓
exact-action approval if required
        ↓
downstream authorization
```

`ApprovalGrant` 会绑定：

```text
tool name + canonical JSON arguments
```

所以 staging 的 approval 不会在 arguments 改成 production 后继续有效。

---

# Part F — Prompt Injection 与 Trust Boundary

阅读：

6. [`theory/06-prompt-injection-and-sandboxing.zh-CN.md`](theory/06-prompt-injection-and-sandboxing.zh-CN.md)

运行：

```bash
python stages/07-reliability-safety/code/prompt_injection_boundary.py
python stages/07-reliability-safety/code/sandbox_boundary.py
```

最重要的架构：

```text
DATA PLANE
user/retrieved/web/MCP/tool-result text
        ↓
model may be influenced
        ↓
model proposes action
        ↓

CONTROL PLANE
validation
permissions
approval
budgets
credentials
sandbox policy
        ↓
allow / deny
```

示例中的 tiny injection detector **故意不是** authorization boundary。

---

# Part G — 组合 Guarded Runtime

阅读：

7. [`theory/07-guarded-runtime-and-production.zh-CN.md`](theory/07-guarded-runtime-and-production.zh-CN.md)

运行：

```bash
python stages/07-reliability-safety/code/guarded_tool_runtime.py
```

`GuardedToolExecutor` 强制执行：

```text
budget
  -> validation
  -> permission
  -> exact approval binding
  -> loop detection
  -> timeout
  -> execute
  -> safe failure classification
  -> bounded retry when safe
```

Stage 01 `AgentRuntime` 仍然保持小而透明。Stage 07 是在 `ToolRegistry` 外面增加更强的 execution layer，而不是把初学者 runtime 改造成 500 行安全框架。

---

# Code Map

```text
code/
├── error_model.py
├── validation_boundary.py
├── retry_policy.py
├── execution_budget.py
├── permission_policy.py
├── loop_detection.py
├── guarded_tool_runtime.py
├── prompt_injection_boundary.py
└── sandbox_boundary.py
```

按上面的顺序运行。

---

# Theory Map

```text
theory/
├── 01-agent-failure-modes.md
├── 02-validation-and-output-handling.md
├── 03-timeout-retry-cancellation.md
├── 04-execution-budgets-and-loops.md
├── 05-tool-permissions-and-least-privilege.md
├── 06-prompt-injection-and-sandboxing.md
└── 07-guarded-runtime-and-production.md
```

中文版本使用同名 `*.zh-CN.md` 文件，并复用完全相同的 Python 代码。

---

# 安装

核心 reliability/governance mechanism 继续保持轻依赖。

安装成熟 Stage 07 对比库以及完整 tests/examples：

```bash
python -m pip install -e ".[dev,stage07]"
```

额外依赖：

```text
jsonschema >= 4.25, < 5
Tenacity   >= 9, < 10
Pydantic   >= 2.11, < 3
```

早期 Stage 不需要这些包。

---

# Tests

Core：

```bash
pytest -q \
  tests/test_reliability.py \
  tests/test_validation.py \
  tests/test_governance.py \
  tests/test_guarded_runtime.py \
  tests/test_trust.py
```

Optional integration：

```bash
pytest -q tests/test_stage07_integrations.py
```

GitHub Actions 会在 Python 3.10 与 3.12 上运行 Stage 07 suite/examples，并继续保留 Stage 00–06 compatibility jobs。

---

# 外部学习资料

安全建议迭代很快，优先以当前官方/安全组织材料为准。

## 1. OWASP GenAI Security

- Prompt Injection — LLM01:2025  
  <https://genai.owasp.org/llmrisk/llm012025-prompt-injection/>
- Improper Output Handling — LLM05:2025  
  <https://genai.owasp.org/llmrisk/llm052025-improper-output-handling/>
- Excessive Agency — LLM06:2025  
  <https://genai.owasp.org/llmrisk/llm062025-excessive-agency/>
- Unbounded Consumption — LLM10:2025  
  <https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/>

对应 Tiny-Agent：

```text
Prompt Injection
    -> external content remains untrusted

Improper Output Handling
    -> validate before downstream execution

Excessive Agency
    -> narrow Tools + least privilege + HITL

Unbounded Consumption
    -> deterministic budgets / rate and action limits
```

## 2. Python async timeout/cancellation

- <https://docs.python.org/3/library/asyncio-task.html>

重点：

```text
wait_for
timeout
CancelledError
to_thread
```

然后再次思考：timing out a worker thread **不等于** kill underlying synchronous function。

## 3. JSON Schema

- <https://python-jsonschema.readthedocs.io/>
- <https://python-jsonschema.readthedocs.io/en/stable/validate/>

先理解手写 subset，再看 mature library。

## 4. Pydantic Strict Validation

- <https://docs.pydantic.dev/latest/concepts/strict_mode/>

用于比较 dynamic JSON-schema Tool contract 与 stable typed application model。

## 5. Tenacity

- <https://tenacity.readthedocs.io/>

重点：

```text
stop
wait
retry predicate
async retry
```

但永远再问一句：

> 这个 business operation 本身真的允许重复执行吗？

## 6. LangChain Middleware / Guardrails

在理解 first-principles guarded executor 后再看：

- <https://docs.langchain.com/oss/python/langchain/middleware/overview>
- <https://docs.langchain.com/oss/python/langchain/middleware/built-in>
- <https://docs.langchain.com/oss/python/langchain/guardrails>
- <https://docs.langchain.com/oss/python/langchain/human-in-the-loop>

这些成熟 abstraction 会把 tool/model call limit、fallback、retry、PII handling、HITL 等模式打包起来。Tiny-Agent 先拆开机制，是为了让这些高层 API 不再像“魔法装饰器”。

---

# 推荐阅读顺序

```text
1. Stage 01 production-limitations refresher
2. Stage 07 Theory 01 + error_model.py
3. Theory 02 + validation_boundary.py
4. jsonschema / Pydantic official docs
5. Theory 03 + retry_policy.py
6. Python asyncio + Tenacity docs
7. Theory 04 + budget / loop examples
8. OWASP Unbounded Consumption
9. Theory 05 + permission_policy.py
10. OWASP Excessive Agency
11. Theory 06 + injection / sandbox examples
12. OWASP Prompt Injection + Improper Output Handling
13. Theory 07 + guarded_tool_runtime.py
14. LangChain middleware / guardrails comparison
15. exercises/review-questions.zh-CN.md
```

---

# Stage Boundary

Stage 07 建立的是 **guarded runtime architecture**，不是“已经完成全部企业安全”的声明。

仍然属于 deployment-specific 或后续范围：

- enterprise IAM / RBAC / ABAC administration；
- signed/expiring approval workflows；
- distributed rate limiting and circuit breakers；
- exactly-once distributed side effects；
- hardened arbitrary-code sandboxing；
- secret-management systems；
- DLP / malware scanning / browser isolation；
- complete prompt-injection prevention；
- formal security verification；
- production audit retention/compliance；
- red-team automation；
- tracing/metrics/evaluation dashboards（Stage 08）；
- service deployment and infrastructure hardening（Stage 10）。

不要把 `asyncio.to_thread()` 叫 sandbox；不要把 substring detector 叫 prompt-injection prevention；不要把一次 human click 叫 authorization。

准确的名字，会逼着架构边界也变准确。

---

# Milestone

你应该能构建并解释：

```text
model proposal
    ↓
local validation
    ↓
least-privilege permission
    ↓
exact-action human approval when needed
    ↓
budget / loop controls
    ↓
timeout
    ↓
retry only when both failure and action are safe
    ↓
model-safe result/failure
```

问题不再是：

> Agent 能不能调用这个 Tool？

而是：

> **在什么 identity、validated arguments、permissions、approval、budget、retry semantics、trust boundary 和 isolation level 下，这个 Tool 才允许影响真实世界？**
