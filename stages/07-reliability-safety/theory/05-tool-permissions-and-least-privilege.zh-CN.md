# 05 — Tool Permission、Least Privilege 与 Approval Binding

> Language: [English](05-tool-permissions-and-least-privilege.md) | 简体中文

Stage 05 通过 MCP 给 Tiny-Agent 接入了标准化 external capability。

Stage 06 又加入了 human approval。

Stage 07 接下来要问一个不那么舒服、但必须回答的问题：

> **Agent 能发现一个 Tool，凭什么就意味着它应该有权执行？**

答案是：除非 deterministic application policy 明确允许，否则就不应该。

---

## 1. Capability Discovery != Authorization

一个 MCP server 可能暴露：

```text
read_file
write_file
delete_file
send_email
run_query
```

这只能说明：

```text
these capabilities exist
```

并不能说明：

```text
the current user may execute all of them
```

Tiny-Agent 使用 default-deny allowlist。

未知 capability：

```text
not in policy
    -> deny
```

而不是：

```text
not in policy
    -> probably fine
```

---

## 2. `Principal`

Authorization 必须有 identity。

Stage 07 建模：

```python
Principal(
    subject_id="user-42",
    roles=frozenset({"analyst"}),
)
```

重要的不是 class 名，而是 architecture boundary：

```text
model
    !=
identity provider
```

永远不要问模型：

```text
"Does this user look like an admin?"
```

Identity 应来自 authenticated application context。

---

## 3. Tool Allowlist 用来缩小 Blast Radius

一个只读 research Agent 只需要：

```text
search_documents
read_document
```

就不要同时暴露：

```text
delete_document
send_email
run_shell
manage_users
```

然后把全部安全希望寄托在 system prompt 的一句：

```text
"Please do not use the scary tools."
```

OWASP 把这类问题归入 Excessive Agency：功能给得太多、权限给得太大，或者 autonomy 放得太宽。

很多时候，最安全的 Tool 就是**模型这一轮根本看不到的 Tool**。

---

## 4. Narrow Tool 通常优于 Open-ended Tool

比较：

```text
run_shell(command: str)
```

与：

```text
get_service_status(service_id)
restart_service(service_id)
```

前者 capability surface 极大；后者被 application semantics 限定得更清楚。

这不是说 shell Tool 永远不能用，而是说它需要：

- 更强的 sandbox；
- 更窄的 permission；
- 可能 mandatory HITL；
- 更严格的 output / side-effect audit；
- 在存在窄 API 时，不应成为默认方案。

---

## 5. Approval != Authorization

Stage 06 教了：

```text
approve / edit / reject
```

Stage 07 再加一层区分：

```text
human approval
    = reviewer 表达了一个决定

authorization
    = application policy 确认这个 action 真的允许执行
```

一个 intern 点了 Approve，并不会因此自动升级成 administrator。

Tiny-Agent 即使拿到了 approval object，也仍然会执行 role policy check。

---

## 6. Approval 应绑定到“准确被 Review 的 Action”

这是比 `approved=True` 更重要的一步。

糟糕表示：

```python
approved = True
```

问题是：批准了什么？

假设 reviewer 看到的是：

```json
{
  "tool": "deploy",
  "environment": "staging"
}
```

之后 arguments 被改成：

```json
{
  "tool": "deploy",
  "environment": "production"
}
```

如果 runtime 只记一个 boolean，旧 review 可能错误地授权新 action。

Stage 07 的 `ApprovalGrant` 会绑定：

```text
tool name + canonical JSON arguments
```

例如：

```python
grant = ApprovalGrant.issue(
    tool_name="deploy",
    arguments={"environment": "staging"},
    reviewer_id="reviewer-2",
)
```

拿它去执行 production 会失败。

---

## 7. 为什么 Fingerprint 需要 Canonicalization？

下面两个 JSON 应该代表同一个 action：

```json
{"a": 1, "b": 2}
```

```json
{"b": 2, "a": 1}
```

所以 Tiny-Agent 在 hashing 前会 canonicalize JSON。

这里不是要靠 hash 实现完整 cryptographic approval protocol，而是教授一个重要 invariant：

> **Review 必须绑定到 reviewer 真正看到的那次 action。**

生产环境还可能需要 signed approval record、workflow ID、reviewer identity claim、expiry、transaction 和 audit log。

---

## 8. Time-of-Check vs Time-of-Use

常见安全问题：

```text
check action A
    ↓
state/resource changes
    ↓
execute action B
```

Exact-action binding 能减少其中一类问题，但生产系统还应考虑：

- resource version 在 review 后变化；
- target ownership 发生变化；
- approval 已过期；
- reviewer 已失去权限；
- deployment artifact 被替换；
- price/account balance 已变化。

必要时应在 execution 前再次检查 application state。

---

## 9. Downstream Authorization 仍然必须存在

即使 Tiny-Agent policy 写得再漂亮，downstream API 自己也应该 enforcement permission。

这叫 defense in depth：

```text
Agent runtime allowlist
        ↓
service/API authorization
        ↓
database/storage permissions
```

不要让一个“read-only Agent”拿着 PostgreSQL superuser credential，然后因为 prompt 写了“只读”就宣布权限设计完成。

Least privilege 最终应该落实到真实 credential 上。

---

## 10. Permission Policy 属于 Application

模型可以提出：

```json
{
  "tool": "delete_report",
  "arguments": {"report_id": "r-7"}
}
```

但它不能提出：

```json
{
  "new_role": "admin",
  "policy": "allow everything"
}
```

然后指望 runtime 接受。

Security policy 不能放在 model-controlled state 里。这也是 Stage 06 对 procedural memory write 非常谨慎的原因之一。

---

## 11. 一个中文更好记的比喻

MCP discovery 像餐厅菜单：告诉你“店里有什么菜”。

Permission policy 像服务员核对你的套餐券到底能不能点龙虾。

Human approval 像同行朋友说：“可以，点吧。”

Authorization 则像最终刷卡时发卡机构确认这笔支付是否允许通过。

看起来都和“点菜”有关，但它们是完全不同的层。

---

## Code to Inspect

- `src/tiny_agent/governance.py`
- `code/permission_policy.py`

运行：

```bash
python stages/07-reliability-safety/code/permission_policy.py
```

---

## 完成检查

解释：

1. discovery vs authorization；
2. authenticated Principal vs model-inferred identity；
3. 为什么 default deny 比 default allow 更安全；
4. excessive functionality、permissions、autonomy 的区别；
5. narrow Tool vs open-ended shell Tool；
6. approval vs authorization；
7. 为什么 approval 要绑定准确 arguments；
8. 为什么 downstream service 仍需要自己的 authorization。
