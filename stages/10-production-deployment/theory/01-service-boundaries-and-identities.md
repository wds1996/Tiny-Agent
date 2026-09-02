# 01 — Service Boundaries, Request Identity, and Thin Transport Adapters

A local Agent can be called like a function:

```python
result = await agent.run(request)
```

A deployed Agent adds a network/service boundary:

```text
client
  -> gateway/network
  -> HTTP/A2A transport
  -> authentication + validation + admission
  -> Agent service
  -> model/tools/state
```

The network boundary changes failure modes and identity semantics. It should **not** become a second implementation of the Agent.

---

## 1. Keep HTTP thin

Bad:

```python
@app.post("/run")
async def run(body):
    # authenticate
    # route
    # plan
    # retry
    # Tool permissions
    # DB queries
    # model calls
    # tracing
    # business rules
    # everything lives here forever
```

Better:

```python
@app.post("/run")
async def run(body):
    service_request = to_service_request(body)
    return await service.run(service_request)
```

Why?

The same Agent semantics can now be invoked from:

```text
HTTP
CLI
worker
unit/integration tests
A2A adapter
scheduled job
```

FastAPI should translate transport concerns. It should not become your architectural basement where every forgotten piece of logic is stored.

---

## 2. Four identifiers with different meanings

```text
request_id
    = one transport request / correlation handle

run_id
    = one logical Agent execution/job

thread_id
    = resumable conversational/workflow state

subject/user identity
    = authenticated caller principal
```

A retry can produce:

```text
HTTP request A -> logical run 42
HTTP request B -> logical run 42
```

A thread can contain many runs. A user can own many threads. A streaming connection can disconnect while a durable run continues.

Do not use one convenient UUID for all four and hope semantics emerge later.

---

## 3. IDs are handles, not credentials

Knowing:

```text
thread_id = abc123
```

does not prove ownership.

Correct access path:

```text
credential
-> trusted authenticator
-> AuthenticatedIdentity(subject, tenant, roles)
-> load resource metadata
-> require_owner / authorization policy
-> read/resume/update
```

Bad:

```python
# insecure mental model
if thread_id_exists(thread_id):
    return resume(thread_id)
```

A random-looking ID may reduce guessability. It does not replace authorization.

---

## 4. Body identity is not authenticated identity

Bad request schema:

```json
{
  "question": "...",
  "user_id": "admin",
  "tenant_id": "tenant-A",
  "roles": ["superuser"]
}
```

If the server trusts those fields, authentication is a creative-writing exercise.

Tiny-Agent uses server-owned binding:

```python
identity = authenticate(request)
metadata = bind_trusted_identity(client_metadata, identity)
```

`bind_trusted_identity()` rejects body/client metadata that attempts to supply reserved identity fields.

---

## 5. ServiceRequest separates transport from execution

Tiny-Agent's framework-neutral boundary:

```python
from tiny_agent import BoundedAgentService, ServiceRequest

service = BoundedAgentService(agent_handler)

result = await service.run(
    ServiceRequest(
        input="research this question",
        metadata={"tenant_id": "server-bound-value"},
    )
)
```

The service creates explicit `request_id` and `run_id` values and owns admission/deadline behavior.

The Agent handler receives a normalized request rather than a FastAPI `Request` object.

---

## 6. Validation has layers

HTTP/Pydantic can validate:

```text
question is a string
max length
metadata shape
```

Runtime/tool validation still checks:

```text
Tool exists
arguments match schema
caller has permission
side effect needs approval
workspace/path is allowed
budget remains
```

Transport validation does not replace domain/runtime governance.

---

## 7. Public errors vs internal diagnostics

Bad:

```python
except Exception as exc:
    return {"error": str(exc)}
```

The exception may contain:

- SQL/hostnames;
- filesystem paths;
- internal prompts;
- provider payloads;
- secrets/tokens.

Prefer stable public errors:

```text
service_at_capacity
run_timeout
invalid_request
authentication_failed
```

and keep detailed diagnostics in privacy-governed logs/traces.

---

## 8. Idempotency belongs to the service contract

Suppose client times out after the server actually created an external side effect and retries.

```text
request A -> side effect succeeds -> response lost
request B -> retry
```

If the API promises retry-safe operation, a stable idempotency/run key must connect retries to logical work.

Do not infer idempotency from HTTP method names or UUID aesthetics.

Stage 07 explains side-effect retry safety; Stage 10 adds durable run ownership.

---

## 9. Worked production request

```text
POST /v1/research
Authorization: Bearer ...
body: {question, preferred_style}
        ↓
auth middleware/resolver
        ↓
AuthenticatedIdentity(subject=u17, tenant=t9)
        ↓
body schema validation
        ↓
bind trusted identity
        ↓
ServiceRequest(request_id, run_id)
        ↓
BoundedAgentService
        ↓
OpenScholar
```

Notice what never happens:

```text
body says "I am tenant t1 admin"
-> server believes it
```

---

## 10. Completion test

You should be able to explain:

1. why the transport adapter should remain thin;
2. request_id vs run_id vs thread_id vs identity;
3. why IDs do not authorize access;
4. why identity must come from a trusted authentication layer;
5. HTTP validation vs Tool/runtime validation;
6. public error contracts vs private diagnostics;
7. where idempotent retry semantics belong.

The invariant is:

> **The network adapter translates requests; the Agent service owns execution semantics; authenticated identity and authorization remain server-owned.**
