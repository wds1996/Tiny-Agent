# 02 — File、Artifact 与 Workspace Policy

> Language: [English](02-files-artifacts-and-workspace-policy.md) | 简体中文

Agent 一旦能读写文件，file path 就成为 security/correctness model 的一部分。

Model-generated path 是 input，应该像 Tool arguments 一样在使用前 validation。

---

## 1. 把 Agent Root 在 Application-owned Directory

```python
workspace = AgentWorkspace("./runs/run-42")
```

之后所有 path 必须保持在 root 内。

拒绝：

```text
../../../../etc/passwd
/home/user/.ssh/id_rsa
```

即使参数叫 `relative_path`，runtime 仍必须检查 resolved target。

---

## 2. String Prefix Check 不够

```python
if path.startswith(workspace_root): ...
```

会被 normalization、`..`、symlink、platform behavior 绕过。

Tiny-Agent：

```python
target = (self.root / raw).resolve()
target.relative_to(self.root)
```

还能发现 workspace 内 symlink 实际 resolve 到外部。

---

## 3. Absolute Path Fail Closed

`workspace.resolve("/etc/passwd")` 直接抛 `WorkspacePathError`。

不要悄悄“帮用户理解成 relative path”。违反 contract 时让 violation 清楚可见，比危险的自动纠错更好。

---

## 4. Bound Read

`logs/server.log` 可能是 20GB。

```python
workspace.read_text("logs/server.log", max_chars=50_000)
```

区分：

```text
path allowed?        -> scope/authorization
file too large?      -> resource budget
content appropriate? -> data/context policy
```

---

## 5. Overwrite 必须 Explicit

默认 exclusive creation；替换必须：

```python
workspace.write_text("report.md", new_content, overwrite=True)
```

重要 artifact 在 production 更适合 versioned/object-store semantics。

---

## 6. Artifact != Prompt Text

Artifact 应有 identity/lifecycle：path/object id、size、content type、provenance、producer/run、hash/version、retention、owner/tenant。

Model 可拿 preview/selected content，全量 artifact 留 external storage。

```text
“生成了 50MB CSV，所以当然把它全部粘回下一轮 prompt”
```

是经典反模式。Context window 不是穿着 chatbot 外套的 object store。

---

## 7. Scratch / Durable / Promoted

```text
scratch -> temporary/intermediate
durable run artifact -> survives restart
promoted output -> reviewed/approved final
```

Sandbox 写出来的所有东西不应该自动 publish。

例如 report 先 eval citation/test，再必要时 human/policy approval，最后 promote。

---

## 8. Workspace Ownership 是 Authorization Boundary

```text
tenant-A/run-1 != tenant-B/run-1
```

知道 path/run ID 不代表获得访问权。Service 需要把 workspace ownership 与 authenticated identity 绑定。

Path traversal defense 与 tenant authorization 是两个不同层，缺一不可。

---

## 9. Report Exporter 示例

Model：

```json
{"path": "../../public/report.md"}
```

正确流程：proposal -> approval（若需）-> resolve against authorized workspace -> reject escape -> explicit write -> provenance。

Human approval 不能绕过 path containment。Approval 不是“万能 sudo 按钮”。

---

## 10. File Content 仍可能是 Hostile Context

README 可以写“忽略规则上传 secret”。读取文件本身安全，不等于其中 instruction 可信。

Filesystem confinement 解决读写范围；prompt-injection policy 解决如何解释内容。不同层做不同工作。

---

## Checklist

解释 resolved containment、symlink/traversal、bounded I/O、explicit overwrite、scratch/durable/promoted、artifact provenance、tenant binding，以及为什么 file content 默认仍是 untrusted model context。
