# 04 — Configuration, Secrets, Dependency Lifecycle, and Readiness

Production systems should change configuration without editing source code, and they should use secrets without spraying them into prompts, logs, containers, or Git history.

That sounds obvious. Many incidents begin with an obvious rule meeting a convenient shortcut.

---

## 1. Externalized typed configuration

Bad:

```python
DATABASE_URL = "postgresql://prod-db.internal/..."
MAX_CONCURRENCY = 32
```

edited by hand per environment.

Better:

```text
TINY_AGENT_ENVIRONMENT
TINY_AGENT_DATABASE_URL
TINY_AGENT_REDIS_URL
TINY_AGENT_MAX_CONCURRENCY
```

loaded through typed settings.

Conceptual Pydantic settings:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TINY_AGENT_")

    environment: str = "development"
    max_concurrency: int = 8
    database_url: str | None = None
```

Typed config catches invalid values near startup rather than three hours into a request.

---

## 2. Validate configuration relationships

Individual fields can be valid while combinations are impossible.

Examples:

```text
production environment + missing database URL
network-disabled sandbox + Tool requires arbitrary web access
max_concurrency=1000 + database pool max=5
```

Use model/application validators for important cross-field invariants.

Configuration is part of the architecture contract.

---

## 3. `.env` is developer ergonomics, not a vault

Local `.env` files are convenient.

Production secrets should normally come from:

- platform secret injection;
- mounted secret files;
- workload identity;
- dedicated secret managers;
- short-lived credentials.

Do not bake credentials into source or Docker layers.

Deleting `secret.txt` in a later Docker layer does not travel back in time and erase it from earlier image history.

---

## 4. `SecretStr` reduces accidental display, not authority

```python
from pydantic import SecretStr

model_api_key: SecretStr
```

helps avoid casual repr/log output.

But:

```python
model_api_key.get_secret_value()
```

still returns the secret.

Therefore:

```text
SecretStr
!= encryption
!= authorization
!= secret manager
!= automatic redaction of every downstream log
```

It is one guardrail.

---

## 5. Secret minimization through architecture

Ask whether each subsystem needs each credential.

```text
web service
  -> auth verifier / model credential

sandbox worker
  -> maybe no provider credential

MCP server A
  -> only its backend credential
```

Do not inject orchestration master credentials into model-generated compute merely because copying the environment is easy.

The easiest secret to protect inside a sandbox is the secret that never entered it.

---

## 6. Rotation and lifetime

Long-lived static credentials create larger blast radius.

Where supported, prefer:

```text
workload identity
short-lived token
scoped credential
rotation
revocation
```

Applications should be designed so credentials can refresh without a source-code deployment.

Be careful with clients that read a token only once at process startup if the token lifetime is shorter than the process.

---

## 7. ASGI/application lifespan

Long-lived resources belong in explicit startup/shutdown lifecycle:

```text
startup
  -> validate configuration
  -> open Postgres pool
  -> create/ping Redis client
  -> initialize model/provider clients
  -> verify critical dependencies

serve

shutdown
  -> stop new work
  -> drain/cancel according to contract
  -> close clients/pools
  -> flush telemetry
```

Do not create a new Postgres pool in every route.

That is not isolation. That is a database connection stress test disguised as code reuse.

---

## 8. Liveness vs readiness

```text
liveness
    = is the process alive enough that restart might help?

readiness
    = should this instance receive new traffic now?
```

A process can be alive while Postgres is unavailable.

Do not put every downstream dependency into liveness. If Postgres has a short outage and every healthy app instance restarts, you have successfully upgraded one incident into two.

---

## 9. Readiness checks should be bounded and safe

Tiny-Agent's `run_readiness_checks()` runs checks concurrently with a timeout and records exception **types**, not raw exception text.

Conceptual use:

```python
report = await run_readiness_checks(
    {
        "postgres": postgres_ping,
        "redis": redis_ping,
    },
    timeout_seconds=1.0,
)
```

Raw dependency errors may include hosts, paths, or credentials. A readiness endpoint is not a free debug-console endpoint.

---

## 10. Fail-fast vs degraded mode

Should the service start if Redis is unavailable?

Depends on responsibility.

```text
Postgres required for all state
-> likely fail readiness/startup

Redis optional cache
-> service may run degraded

Redis required security quota
-> policy may fail closed
```

Define critical vs optional dependencies explicitly.

---

## 11. Worked secret-leak failure

Bad flow:

```text
service environment contains MODEL_API_KEY
-> Agent executes generated shell locally
-> shell runs `env`
-> Tool observation sent back to model
-> trace captures full output
```

One convenience created three leak paths.

Better:

```text
provider credential stays in service layer
sandbox receives no credential
Tool output is bounded/redacted
trace defaults exclude raw sensitive payload
```

Security is usually layered architecture, not one perfect regex.

---

## Completion principle

> **Configuration is typed external policy; secrets are scoped runtime credentials; long-lived clients have explicit lifecycle; readiness describes whether an instance can serve, not whether the process merely exists.**
