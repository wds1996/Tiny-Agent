# 02 — Model Output 进入程序前必须 Validation

> Language: [English](02-validation-and-output-handling.md) | 简体中文

Stage 00 已经介绍 Function Calling 与 JSON Schema。

Stage 07 补上生产环境缺失的规则：

> **把 schema 展示给模型，不等于 runtime 真正 enforcement 了这个 schema。**

模型通常会返回合法 arguments。

但“通常”从来不是 security boundary。

---

## 1. 危险 Shortcut

Tool schema：

```python
parameters = {
    "type": "object",
    "properties": {
        "amount": {
            "type": "integer",
            "minimum": 1,
            "maximum": 1000,
        }
    },
    "required": ["amount"],
    "additionalProperties": False,
}
```

模型提出：

```json
{
  "amount": -9000000,
  "admin": true
}
```

如果 runtime 直接：

```python
tool.handler(**arguments)
```

而不 local validation，那么 JSON Schema 基本只剩“建议作用”。

---

## 2. Structured Output 改善 Generation；Validation 保护 Execution

二者互补：

```text
Structured Output / constrained generation
    -> increase probability and guarantees around model response shape

local runtime validation
    -> independently verify data before crossing an execution boundary
```

即使 provider 承诺 schema-constrained output，本地 validation 仍然重要，因为：

- 不同 provider/adapter 行为可能不同；
- cached/replayed ToolCall 可能绕过原 generation path；
- MCP/remote schema 可能来自外部系统；
- application business rule 可能比 provider schema support 更严格；
- bug 可能在 model generation 后修改 arguments；
- 同一个 Tool 可能由普通代码调用，而不只由 LLM 调用。

---

## 3. 为什么 Tiny-Agent 教两层 Validation？

先手写：

```python
SimpleToolArgumentsValidator
```

它只支持一个故意缩小的 JSON-Schema-like subset：

- primitive types；
- object properties；
- required fields；
- `additionalProperties: false`；
- enums；
- numeric bounds；
- string lengths；
- array lengths 与 item schemas。

为什么要手写一个小版本？因为它把控制流展示得很清楚：

```text
arguments
    ↓
required?
    ↓
known properties?
    ↓
types?
    ↓
bounds?
    ↓
handler
```

但它**绝不是完整 JSON Schema implementation**。

这个免责声明非常重要。一个只实现一半的标准，如果对外宣称“完整验证”，比明确标注为 teaching subset 更危险。

---

## 4. Full Dynamic JSON Schema：用 `jsonschema`

对真实 dynamic Tool schema，Stage 07 加入：

```python
from tiny_agent.validators.jsonschema import (
    JsonSchemaToolArgumentsValidator,
)
```

它交给维护成熟的 `jsonschema` package：

```python
validator_cls = validator_for(schema)
validator_cls.check_schema(schema)
validator = validator_cls(schema)
errors = list(validator.iter_errors(arguments))
```

这对下面这些功能很重要：

```text
oneOf / anyOf
pattern
references
nested constraints
schema draft selection
```

不应该在 Agent 教程里随手重新实现整个标准。

---

## 5. Invalid Schema vs Invalid Model Arguments

这是两种不同 failure。

### Invalid Model Arguments

```text
model proposed bad data
```

结果：

```text
ToolFailure[invalid_arguments]
```

模型可能通过重新提出正确 arguments 来恢复。

### Invalid Tool Schema

```text
application developer configured an invalid schema
```

这是 application configuration bug。

不要把它交给模型并说：

```text
"Please repair our JSON Schema implementation."
```

Stage 07 的 full adapter 会把 malformed application schema 视为 developer error，而不是 normal ToolCall failure。

---

## 6. 为什么 `additionalProperties: false` 重要？

例如：

```json
{
  "path": "report.txt",
  "delete_after_read": true
}
```

今天 handler 可能只接受 `path`，extra field 被忽略。

明天 wrapper 可能开始 forwarding 它。

Strict schema 可以缩小 accidental capability expansion。

对稳定 Tool contract，通常应优先：

```json
{
  "type": "object",
  "properties": {...},
  "required": [...],
  "additionalProperties": false
}
```

除非 extensibility 本身就是明确设计目标。

---

## 7. Pydantic 适合另一个 Boundary

Dynamic MCP/provider Tool schema 自然适合 JSON Schema。

Application-owned Python data 往往更适合 typed model：

```python
from pydantic import BaseModel, ConfigDict

class TransferArgs(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
    )

    amount: int
    currency: str
```

如果 boundary 上不希望 silent conversion，strict mode 很关键。

不 strict 时，有些系统会很开心地把：

```json
{"amount": "100"}
```

变成：

```python
amount = 100
```

有时 coercion 很方便；但在 financial/permission boundary，方便可能变成歧义。

---

## 8. Schema Validation != Business Authorization

下面 request 完全可能满足所有 type constraint：

```json
{
  "environment": "production",
  "release": "v0.7.0"
}
```

但如果：

```text
current role = intern
```

它仍然应该被拒绝。

因此：

```text
valid
!=
authorized
```

Stage 07 顺序：

```text
shape validation
    ↓
permission / role / approval policy
    ↓
execution
```

---

## 9. Output Handling 同样需要 Zero-Trust 思维

OWASP 的 Improper Output Handling 指出，LLM output 可能继续被送入：

- shell commands；
- SQL；
- HTML/JavaScript；
- file paths；
- downstream APIs。

Function Calling 并不会让下游 validation 失效。

坏：

```python
os.system(model_text)
```

好：

```text
model chooses from application-owned operation enum
    ↓
validated structured arguments
    ↓
specific API function
```

坏：

```python
sql = f"SELECT * FROM users WHERE id = {model_value}"
```

好：

```text
parameterized query + authorization
```

---

## 10. 一个更好记的比喻

给模型看的 JSON Schema 像菜单。

Runtime validation 则像厨房真正检查订单，确认顾客没有在备注栏偷偷加上一句：

```text
"One sandwich, plus ownership of the restaurant"
```

菜单约束了可选项，厨房仍然要检查实际订单。

---

## Code to Inspect

- `src/tiny_agent/validation.py`
- `src/tiny_agent/validators/jsonschema.py`
- `code/validation_boundary.py`

运行：

```bash
python stages/07-reliability-safety/code/validation_boundary.py
```

---

## 完成检查

解释：

1. Provider schema constraint vs local validation；
2. 为什么 Tiny-Agent simple validator 故意不完整；
3. 为什么完整 JSON Schema support 应使用维护成熟的 library；
4. `additionalProperties: false` 如何缩小 capability surface；
5. JSON Schema vs Pydantic typed application model；
6. strict validation vs convenient coercion；
7. validation vs authorization；
8. 为什么 model output 应被视为 untrusted program input。
