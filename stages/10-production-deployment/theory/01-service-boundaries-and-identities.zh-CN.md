# 01 — Service Boundary、Request Identity 与 Thin Transport Adapter

> Language: [English](01-service-boundaries-and-identities.md) | 简体中文

本地 Agent 可以像函数一样调用：

```python
result = await agent.run(request)
```

部署后多了一条 network/service boundary：

```text
client
  -> gateway/network
  -> HTTP/A2A transport
  -> authentication + validation + admission
  -> Agent service
  -> model/tools/state
```

Network boundary 会改变 failure mode 和 identity semantics，但它**不应该变成第二套 Agent implementation**。

---

## 1. HTTP Adapter 要 Thin

坏：所有 authentication/routing/planning/retry/Tool permission/DB/model/tracing/business rule 都塞进 route handler。

好：

```python
@app.post("/run")
async def run(body):
    service_request = to_service_request(body)
    return await service.run(service_request)
```

这样同一套 Agent semantics 可以从 HTTP、CLI、worker、test、A2A adapter、scheduled job 调用。

FastAPI 应负责 transport translation，不应该变成“所有不知道放哪的逻辑最后都堆进去”的架构地下室。

---

## 2. 四个不同 Identity/Correlation Handle

```text
request_id
    = 一次 transport request

run_id
    = 一次 logical Agent execution/job

thread_id
    = 可 resume 的 conversation/workflow state

subject/user identity
    = 已认证 caller principal
```

一次 logical run 可以被多个 HTTP retry 观察；一个 thread 可以包含多个 run；一个 user 可以拥有多个 thread；streaming connection 断开后 durable run 仍可继续。

不要拿一个方便的 UUID 同时扮演四种语义，再期待系统未来自己悟出区别。

---

## 3. ID 是 Handle，不是 Credential

知道：

```text
thread_id = abc123
```

并不能证明 ownership。

正确流程：

```text
credential
-> trusted authenticator
-> AuthenticatedIdentity(subject, tenant, roles)
-> load resource metadata
-> require_owner / authorization
-> read/resume/update
```

随机 ID 只能降低猜中概率，不能替代 authorization。

---

## 4. Body Identity 不是 Authenticated Identity

如果 request body 可以自报：

```json
{
  "user_id": "admin",
  "tenant_id": "tenant-A",
  "roles": ["superuser"]
}
```

然后 server 直接相信，那么 authentication 就退化成了一场“创意写作比赛”。

Tiny-Agent 使用 server-owned binding：

```python
identity = authenticate(request)
metadata = bind_trusted_identity(client_metadata, identity)
```

保留字段由 server 注入，client 不能覆盖。

---

## 5. `ServiceRequest` 分离 Transport 与 Execution

```python
service = BoundedAgentService(agent_handler)
result = await service.run(
    ServiceRequest(
        input="research this question",
        metadata={"tenant_id": "server-bound-value"},
    )
)
```

Service 创建明确的 `request_id`/`run_id` 并拥有 admission/deadline 语义；Agent handler 接收 normalized request，而不是 FastAPI `Request` object。

---

## 6. Validation 有多个层

HTTP/Pydantic 可以验证 string length/metadata shape。

Runtime 仍然要检查 Tool exists、arguments schema、caller permission、approval、workspace path、budget。

```text
transport validation != runtime/domain governance
```

---

## 7. Public Error vs Internal Diagnostic

不要：

```python
except Exception as exc:
    return {"error": str(exc)}
```

raw exception 可能含 SQL/hostname/path/prompt/provider payload/secret。

对外返回稳定错误：

```text
service_at_capacity
run_timeout
invalid_request
authentication_failed
```

详细诊断留在 privacy-governed log/trace。

---

## 8. Idempotency 属于 Service Contract

Client timeout 后 retry，而 server side effect 其实已经完成，是典型重复执行风险。

若 API 承诺 retry-safe，就需要稳定的 idempotency/run key 把多个 transport retry 对应到同一个 logical work。

不要因为 HTTP method 或 UUID “看起来很正规”就自动推导 exactly-once。

---

## 9. Worked Request

```text
POST /v1/research
Authorization: Bearer ...
body: {question, preferred_style}
        ↓
auth resolver
        ↓
AuthenticatedIdentity(subject=u17, tenant=t9)
        ↓
body validation
        ↓
bind trusted identity
        ↓
ServiceRequest(request_id, run_id)
        ↓
BoundedAgentService
        ↓
OpenScholar
```

整个路径里都不会出现：

```text
body says "I am tenant t1 admin"
-> server believes it
```

---

## Completion Test

你应该能解释：thin transport；request/run/thread/identity；ID 为什么不授权；identity 为什么必须来自 trusted auth；HTTP validation 与 runtime validation；public error contract 与 private diagnostic；idempotent retry 应放在哪里。

核心 invariant：

> **Network adapter 只负责翻译 request；Agent service 拥有 execution semantics；authenticated identity 与 authorization 始终由 server-owned boundary 决定。**
