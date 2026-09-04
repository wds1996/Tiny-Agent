# 07 — Production Boundary、MCP 与 A2A

最终架构只有在真实 caller 能够访问它时才有产品意义。

因此 Stage 15 会通过多个边界暴露同一个 domain Agent，同时避免复制 research logic。

## Boundary 1 — HTTP Service

FastAPI adapter 暴露：

```text
POST /v1/research/base
POST /v1/research/langgraph
POST /v1/research/langgraph/{thread_id}/resume
GET  /livez
```

adapter 负责把 HTTP payload 转成 `ResearchRequest`，然后调用 domain agent。

route function 不实现 planning / retrieval：

```text
HTTP
  -> request validation
  -> OpenScholar domain core
  -> ResearchReport
  -> JSON
```

## Identity Warning

教学版 body 中包含 `user_id`，方便做 correlation 与 memory demo。

这个字段**不是 authenticated identity**。

错误的生产思路：

```json
{"user_id":"admin"}
```

然后服务端回答：

```text
太好了，你现在就是 admin。
```

production identity 必须来自可信 boundary，例如：

- authenticated middleware；
- gateway claims；
- workload identity；
- 其他 server-controlled authentication layer。

## Boundary 2 — MCP Capability

MCP 暴露的是系统的一项 capability：

```text
search_corpus(query)
```

host 可以发现并调用 corpus search Tool，而不需要采用 OpenScholar 内部 runtime。

这是 Stage 05 的 boundary：

```text
Agent / application
      -> MCP
      -> capability
```

MCP Tool 返回 evidence data。

host 仍然负责：

- authorization；
- 如何把 data 放进 model context；
- downstream policy。

## Boundary 3 — A2A Agent Service

A2A 把 OpenScholar 暴露成独立 Agent system：

```text
remote Agent
   -> A2A message / task
   -> OpenScholar Agent
   -> research result
```

remote caller 不需要知道 OpenScholar 内部究竟使用：

- LangGraph；
- local RAG；
- MCP；
- reviewer team。

可以把差别概括为：

```text
MCP: 使用我的 capability
A2A: 与我的 Agent 协作
```

## A2A 不会自动带来 Trust

Agent Card 可以 advertise capability。

但它不会证明：

- caller 被允许使用全部 capability；
- remote Agent 是安全的；
- remote output 是正确的。

production A2A 仍然需要：

- TLS；
- caller authentication；
- tenant binding；
- authorization；
- rate limits；
- request size limits；
- tracing / audit boundaries；
- downstream least privilege。

## Stage 13 Service Constraints 仍然存在

给 OpenScholar 套上 FastAPI，并不会让这些事实消失：

```text
process-local semaphore != cluster-wide limit
request timeout != hard kill
dict memory != distributed state
Docker != correctness
```

真实部署可以在 Agent 前面使用 `BoundedAgentService`，维持 queue / execution deadline。

## Durable Graph Backend

教学版 LangGraph 默认用：

```text
InMemorySaver
```

因为 example 应该不依赖外部 infra 也能运行。

production 应替换成 Stage 06 的 durable checkpointer backend。

同理：

```text
InMemoryResearchMemory
```

当跨 restart 的 user preference 有真实产品语义时，也应该换成 durable Store。

一个 API 能从网络访问，并不会让里面的 in-memory object 自动获得 durability。

## Container

Stage 15 Dockerfile 负责 package application，并启动 FastAPI example。

它是 deployment baseline，而不是“enterprise production completeness”声明。

真正环境仍然必须决定：

- secret delivery；
- persistence backend；
- replica / pool sizing；
- network egress；
- authentication；
- autoscaling；
- job durability；
- observability exporter；
- backup / retention；
- data licensing。

Container 更像运输箱。

它负责把东西送到运行环境，却不会替你检查箱子里的架构是否合理。

## Data Licensing 与 Paper Ingestion

仓库保存 open paper identifier / download URL manifest，而不是直接重新分发 PDF。

用户扩展 corpus 时仍然应该确认：

- license；
- source terms；
- redistribution / processing permissions；
- retention policy。

尤其不能因为“文件能下载”就自动推导出“任何训练/再分发方式都合法”。

## 建议的 Production Evolution

一个更真实的架构可能是：

```text
Gateway / Auth
      |
      v
OpenScholar API replicas
      |
      +---- Postgres checkpointer / Store
      |
      +---- Redis coordination / rate limit
      |
      +---- Qdrant corpus index
      |
      +---- Crossref / external scholarly services
      |
      +---- MCP capability servers
      |
      +---- A2A peer Agents
      |
      `---- OpenTelemetry / LangSmith
```

但每一个新 box 都必须解决一个可以说明、最好还能测量的 requirement。

学完十几个 Stage 之后，最重要的能力之一应该是知道**什么时候不要再加一个 box**。

## Production Checklist

在把 research Agent 称为 “production ready” 之前，至少确认：

```text
[ ] identity 来自 trusted auth boundary
[ ] request / run / thread / user ID 语义分开
[ ] local 与 external evidence 有明确 trust class
[ ] retrieval / evidence threshold 经过 evaluation
[ ] memory write 有 policy / consent
[ ] 高风险 side effect 需要 approval
[ ] approval 不绕过 authorization
[ ] retry safe / idempotent
[ ] durable HITL 使用 durable checkpointer
[ ] timeout / capacity limit 存在
[ ] secret 不进入不必要的 log / trace
[ ] citation 对 evidence inventory 做 evaluation
[ ] regression tests 覆盖 known failures
[ ] corpus / license / data-retention policy 明确
[ ] container / runtime health checks 存在
[ ] multi-Agent coordination 有 bound
```

Capstone 的完成标准不是 architecture diagram 有最多的箭头，而是：

> **你能解释清楚每一个 box 为什么存在，以及它具体不负责什么。**