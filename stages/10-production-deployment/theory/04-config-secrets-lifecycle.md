# 04 — Configuration, secrets, and resource lifecycle

## Configuration is not code editing

Do not deploy by changing:

```python
DATABASE_URL = "prod-db.internal"
```

between environments.

Use external configuration:

```text
TINY_AGENT_ENVIRONMENT
TINY_AGENT_DATABASE_URL
TINY_AGENT_REDIS_URL
TINY_AGENT_MAX_CONCURRENCY
```

Stage 10 uses `pydantic-settings` for typed environment loading.

## `.env` is convenient, not a secret vault

A local `.env` can improve developer ergonomics.

Production secrets should normally come from the deployment platform's secret mechanism, mounted secret files, workload identity, or a dedicated secret manager.

Never commit real credentials.

## `SecretStr`

Pydantic `SecretStr` helps reduce accidental repr/log leakage:

```python
model_api_key: SecretStr
```

But the application can still call:

```python
secret.get_secret_value()
```

Therefore:

```text
SecretStr = safer representation
          ≠ authorization
          ≠ encryption
          ≠ secret manager
```

## Safe configuration summaries

Operational logs often need to answer:

```text
Is Redis configured?
Which environment?
What concurrency limit?
```

They almost never need to print the actual API key.

Stage 10 exposes booleans such as:

```text
redis_configured = true
model_api_key_configured = true
```

instead of values.

## Lifespan

ASGI lifespan is the right place for long-lived resources:

```text
startup
  -> open Postgres pool
  -> create/ping Redis client
  -> initialize model clients
  -> validate required dependencies

serve requests

shutdown
  -> stop accepting work
  -> drain/finish according to policy
  -> close Redis
  -> close Postgres pool
  -> flush telemetry
```

Do not create a new pool inside every route.

## Readiness and startup

A process can be alive while still not ready:

```text
Python process running ✅
Postgres unavailable ❌
```

That distinction is why Stage 10 has both `/livez` and `/readyz`.
