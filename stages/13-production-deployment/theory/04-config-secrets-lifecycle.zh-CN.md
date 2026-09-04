# 04 — Configuration、Secret、Dependency Lifecycle 与 Readiness

> Language: [English](04-config-secrets-lifecycle.md) | 简体中文

生产系统应该能在不修改源码的情况下改变 configuration，也应该能够使用 secret，而不是把 secret 到处喷进 prompt、log、container 和 Git history。

这听起来理所当然。很多事故恰恰发生在“大家都知道的规则”遇到“这次先图个方便”的时候。

---

## 1. Externalized Typed Configuration

坏：

```python
DATABASE_URL = "postgresql://prod-db.internal/..."
MAX_CONCURRENCY = 32
```

然后每个环境手工改代码。

更好：

```text
TINY_AGENT_ENVIRONMENT
TINY_AGENT_DATABASE_URL
TINY_AGENT_REDIS_URL
TINY_AGENT_MAX_CONCURRENCY
```

通过 typed settings 加载。

Pydantic settings 的概念示例：

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TINY_AGENT_")

    environment: str = "development"
    max_concurrency: int = 8
    database_url: str | None = None
```

Typed config 的价值，是让错误尽量在 startup 就暴露，而不是服务运行三小时、某个请求走到冷门路径时才发现。

---

## 2. 还要 Validate Configuration 之间的关系

单个字段都合法，组合起来仍可能不成立：

```text
production + missing database URL
network-disabled sandbox + Tool requires arbitrary web access
max_concurrency=1000 + DB pool max=5
```

重要 cross-field invariant 应通过 model/application validator enforcement。

Configuration 本身就是 architecture contract 的一部分。

---

## 3. `.env` 是开发便利，不是保险柜

本地 `.env` 很方便。

生产 secret 更适合来自：

- platform secret injection；
- mounted secret file；
- workload identity；
- secret manager；
- short-lived credential。

不要把 credential 烘进 source 或 Docker layer。

即使后续 Docker layer 执行：

```text
rm secret.txt
```

也不会穿越时间，把早先 image layer 里的 secret 一并抹掉。

---

## 4. `SecretStr` 只减少意外展示，不提供 Authority

```python
from pydantic import SecretStr

model_api_key: SecretStr
```

有助于避免 casual repr/log 泄露。

但：

```python
model_api_key.get_secret_value()
```

仍能取出真实 secret。

所以：

```text
SecretStr
!= encryption
!= authorization
!= secret manager
!= automatic redaction everywhere
```

它只是一层 guardrail。

---

## 5. 通过 Architecture 做 Secret Minimization

问清楚每个 subsystem 到底需要哪些 credential：

```text
web service
  -> auth verifier / model credential

sandbox worker
  -> 也许完全不需要 provider credential

MCP server A
  -> 只拿自己的 backend credential
```

不要因为“复制整个 environment 最省事”，就把 orchestration master credential 送进 model-generated compute。

Sandbox 里最好保护的 secret，就是**从来没有进入 sandbox 的 secret**。

---

## 6. Rotation 与 Lifetime

Long-lived static credential 会放大 blast radius。

能用时优先：

```text
workload identity
short-lived token
scoped credential
rotation
revocation
```

应用应该允许 credential refresh，而不是每次 rotation 都必须重新部署源码。

如果 token lifetime 短于 process lifetime，也要注意某些 client 是否只在 startup 读一次 token。

---

## 7. ASGI / Application Lifespan

Long-lived resource 应进入明确 lifecycle：

```text
startup
  -> validate configuration
  -> open Postgres pool
  -> create/ping Redis client
  -> initialize provider clients
  -> verify critical dependencies

serve

shutdown
  -> stop new work
  -> drain/cancel per contract
  -> close clients/pools
  -> flush telemetry
```

不要每个 route 都重新建一个 Postgres pool。

那不是 isolation，而是把数据库连接压力测试伪装成“代码简单”。

---

## 8. Liveness vs Readiness

```text
liveness
    = 进程是否还活着，失败时 restart 是否可能有帮助？

readiness
    = 这个 instance 此刻是否应该继续接收新流量？
```

进程完全活着，但 Postgres 暂时不可用，readiness 可能失败。

不要把所有 dependency 都塞进 liveness。否则 Postgres 短暂故障时，orchestrator 可能顺手把所有健康 app instance 全重启一遍——非常高效地把一个事故升级成两个。

---

## 9. Readiness Check 要 Bounded 且 Safe

Tiny-Agent 的 `run_readiness_checks()` 并发运行 check，并设 timeout；异常只记录 exception **type**，不回传 raw message。

```python
report = await run_readiness_checks(
    {
        "postgres": postgres_ping,
        "redis": redis_ping,
    },
    timeout_seconds=1.0,
)
```

Dependency error 可能含 hostname/path/credential。Readiness endpoint 不是免费开放的 debug console。

---

## 10. Fail-fast vs Degraded Mode

Redis down 时是否允许 service 启动？取决于职责：

```text
Postgres 是所有 state 必需
-> 通常 fail readiness/startup

Redis 只是 optional cache
-> 可以 degraded mode

Redis 承担强制 security quota
-> policy 可能 fail closed
```

Critical dependency 与 optional dependency 必须明确分类。

---

## 11. Secret Leak 失败链

坏流程：

```text
service env contains MODEL_API_KEY
-> Agent executes generated shell locally
-> shell runs `env`
-> Tool observation goes to model
-> trace captures full output
```

一个“方便复制环境”的决定，制造了三条 leak path。

更好：provider credential 留 service layer；sandbox 不拿它；Tool output bounded/redacted；trace 默认不抓 raw sensitive payload。

安全通常来自 layered architecture，而不是一条完美 regex。

---

## Completion Principle

> **Configuration 是 typed external policy；secret 是 scoped runtime credential；long-lived client 有明确 lifecycle；readiness 描述 instance 是否能服务，而不只是 process 是否还活着。**
