# Stage 05：政策已经会查了，订单总不能还靠用户自报吧？——把外部系统接进 Agent

> Language: [English](README.md) | **简体中文**

[上一章](../04-agentic-rag/README.zh-CN.md)，小林已经让助手学会了一件很重要的事：面对退款问题，先去找当前政策，再根据证据回答，而不是凭模型印象猜“30 天还是 45 天”。可那一章还有一个刻意保留的前提——顾客说“我 8 月 3 日下单、商品已经付款、现在是第 38 天”，程序只是把这些信息当成题设，并没有真的去订单系统核实。

产品准备把助手接到真实业务流程时，小林马上撞上了下一层问题。政策文件由文档团队维护，订单在订单服务里，物流状态在配送系统里，发票又是另一套服务。今天为了查订单写一个 HTTP adapter，明天为了查物流再写一个，后天工单团队又换了一套参数格式。Agent 还没变聪明，项目里已经先开起了“转接头专卖店”。

这一章仍然只处理同一笔教学订单 `ACME-1007`。我们会先让程序核实下单日期、付款金额和配送状态，再看看怎样把外部团队提供的能力接回前面的 Runtime。途中会出现一个很关键的能力：`create_support_case`。Server 会声明它存在，但默认情况下我们**不会把它交给模型**。这正好能说明 MCP 最容易被误解的一点：**能发现某项能力，不等于当前 Agent 有权使用它。**

先把故事记住，再看名词。MCP 的作用不是“让模型更聪明”，而是让 Host 与外部能力提供方之间有一套共同语言。

## 1. 先看眼前到底多了哪条边界

Stage 01 的天气 Tool 全都在同一个 Python 项目里。Runtime 拿到工具名以后，可以直接调用本地 handler：

```python
result = registry.execute(call.name, call.arguments)
```

这里没有网络，也没有另一个团队。Registry 知道有哪些函数，Python 进程直接执行它们。

现在换成订单查询。小林并不拥有订单服务的源码，她只得到另一支团队提供的一套接口。于是系统中多出了一条边界：

```text
模型
  ↓ 提出 Tool Call
Tiny-Agent Runtime
  ↓ 验证当前允许的能力
外部服务连接层
  ↓ 请求订单 / 物流 / 发票系统
业务服务
```

Function Calling 解决的是第一段：**模型怎样结构化地提出“我想调用某个能力”。** MCP 要解决的是后一段：**应用怎样用统一方式发现并调用另一个系统提供的能力和上下文。**

这两层不是竞争关系。模型完全可以先通过 Function Calling 请求 `support__get_order_summary`，Runtime 再通过 MCP Client 把这个请求送到外部 MCP Server。

如果把两件事混成一句“MCP 就是 Tool Calling”，后面很容易把权限也一起混掉：模型提出请求是一回事，Host 是否把这项远程能力暴露给模型，是另一回事。

## 2. 在写协议代码之前，先把客服要做的事情走一遍

顾客问：“我的 `ACME-1007` 订单是否符合退款条件？”

上一章已经能查政策，但真正回答之前，客服至少还想确认几件系统事实：订单是什么时候下的、是否已经支付、金额是多少、物流是否已经送达。需要时还可以看看发票信息。于是理想的数据流大概是：

```text
顾客问题
   ↓
读取当前退款政策        ← Stage 04 已经会做
   ↓
核实订单系统事实        ← 本章的新边界
   ↓
核实物流 / 发票
   ↓
把系统事实与政策证据放在一起解释
```

如果后面真的需要人工跟进，还可能“创建支持工单”。注意这个动作和前三个查询不一样：查询只是读取，创建工单会改变服务端状态。

本章的虚构 Acme Support Server 因此提供四个 Tool：

```text
get_order_summary
get_shipment_status
get_invoice_summary
create_support_case
```

前三个是只读查询，最后一个有副作用。我们故意把它们放在同一个 Server 里，因为真实外部系统往往也会同时提供“看”和“改”的能力。真正的安全边界不能建立在“这个 Server 看起来挺正规”上，而要建立在 Host 明确选择暴露什么。

这条区别会贯穿整章。

## 3. Host、Client、Server：把三个人先认清

在 MCP 里，经常出现 Host、Client、Server 三个角色。名字都很普通，所以最容易串台。

在我们的故事里，**Host** 就是 Tiny-Agent 应用。它管理模型、Runtime、上下文和权限。小林写的 Agent 跑在 Host 里。

**MCP Client** 是 Host 里负责和某个 MCP Server 说协议的连接组件。它知道怎样列出远程 Tool、读取 Resource、获取 Prompt，也知道怎样发送一次 Tool 调用。

**MCP Server** 是外部能力提供方。这里它模拟 Acme 的订单、物流、发票和客服系统。

```text
                    Tiny-Agent Host
       +-------------------------------------+
       | Model                               |
       | Runtime / Policy                    |
       | Local Tool Registry                 |
       |                ↓                    |
       |          MCP Client                 |
       +----------------|--------------------+
                        |
                        | MCP
                        v
              Acme Support MCP Server
             +-------------------------+
             | order / shipment / ... |
             +-------------------------+
```

这个图里最重要的不是方框数量，而是责任归属：**Server 声明自己能提供什么，Host 决定当前任务允许使用什么。**

先把这一句记牢，后面 discovery、Bridge 和权限过滤都会顺理成章。

## 4. 一个 Server 不只有 Tool：做事、读资料和给模板是三种不同语义

先看本章的教学 Server [`code/mcp_server.py`](code/mcp_server.py)。它除了四个 Tool，还提供 Resource 与 Prompt。

可以先用一句不正式但很好记的话区分：

```text
Tool     = 帮我做一件事
Resource = 给我读一份东西
Prompt   = 给我一套可复用的模型输入模板
```

### Tool：调用一个能力

订单查询是 Tool：

```python
@mcp.tool()
def get_order_summary(order_id: str) -> dict[str, object]:
    return _tool_call(order_record, order_id)
```

调用它会让 Server 执行业务函数，并返回结构化结果。

有副作用的工单创建也是 Tool：

```python
@mcp.tool()
def create_support_case(order_id: str, reason: str) -> dict[str, str]:
    return _tool_call(create_case_record, order_id, reason)
```

二者都属于 Tool，不代表二者风险一样。协议只告诉我们“这是一个可调用能力”，Host 仍要进一步决定谁能使用。

### Resource：读取一个地址对应的数据

客服操作指南更像资料，而不是动作：

```python
@mcp.resource("acme-support://guide/{topic}")
def support_guide(topic: str) -> str:
    return read_support_guide(topic)
```

例如：

```text
acme-support://guide/refund-evidence
```

表示“读取退款审核资料指南”。把它强行包装成 `get_refund_evidence_guide()` Tool 当然也能运行，但语义就开始模糊了。

### Prompt：复用一套模型输入模板

Server 还可以提供：

```python
@mcp.prompt()
def prepare_case_summary(order_id: str, audience: str = "customer") -> str:
    ...
```

它返回的是给模型使用的模板，不是业务动作，也不是事实查询结果。

Stage 04 刚刚把“证据”和“动作”分开，本章继续保留这条边界：**能读取的上下文不需要全部伪装成 Tool。**

## 5. 先把 Server 跑在同一个进程里，把网络噪音拿掉

第一次学习 MCP 时，最容易被端口、代理、子进程和 HTTP 抢走注意力。所以先让 Client 直接连接同一个 Python 进程里的 Server 对象：

```python
from mcp import Client
from mcp_server import mcp

async with Client(mcp) as client:
    tools = await client.list_tools()
```

这种 in-process 方式不经过网络，但 Client / Server 的 MCP 语义仍然存在。进入 `async with` 时，Client 会完成连接与协议协商；离开代码块时连接结束。官方 Python SDK v2 的 `Client` 就以这个生命周期为中心。

安装本章依赖后运行：

```bash
python -m pip install -r stages/05-mcp/code/requirements.txt
python stages/05-mcp/code/in_memory_client.py
```

程序首先列出 Server 提供的 Tools、Resources、Resource Templates 和 Prompts，然后真正读取 `ACME-1007` 的订单与物流。

你会看到类似这样的结构化数据：

```text
order: {'order_id': 'ACME-1007', 'placed_on': '2026-08-03', ...}
shipment: {'order_id': 'ACME-1007', 'shipment_status': 'delivered', ...}
```

这里终于补上了 Stage 04 明确缺失的那一环：`2026-08-03` 不再只是顾客自报的题设，而是这次教学 Server 返回的系统事实。

当然，这仍然是虚构数据。我们验证的是协议和数据流，不是在连接真实商店。

## 6. Discovery 只是“对方说自己有什么”，不是授权表

`list_tools()` 很方便：

```python
catalog = await client.list_tools()
```

它会告诉 Host 这个 Server 声明了哪些 Tool，以及各自的参数 Schema。

本章 Server 会列出四个名字，其中也包括：

```text
create_support_case
```

到这里千万不要自动得出：

> “既然发现了，那就把四个都放给模型吧。”

Discovery 回答的是：

> “Server 声称提供什么？”

授权回答的是：

> “当前用户、当前任务、当前模型究竟能使用什么？”

二者必须分开：

```text
discovered capability
        ≠
model-visible capability
        ≠
authorized execution
```

这和 Stage 04 的检索范围很像。向量库里“存在某篇文档”，不代表当前用户就应该检索到它；MCP Server 里“存在某个 Tool”，也不代表当前 Agent 就应该调用它。

这一点会在 Bridge 里真正落实，而不是停留在一句安全口号上。

## 7. Tool 调用返回的是结构，不必再从一句话里抠字段

Client 可以直接调用远程 Tool：

```python
result = await client.call_tool(
    "get_order_summary",
    {"order_id": "ACME-1007"},
)
```

MCP Tool result 常见有三部分需要区分：

```text
content             面向模型 / 人类的内容块
structured_content  适合程序继续处理的结构化结果
is_error            这次 Tool 执行是否失败
```

订单查询返回字典，所以程序可以直接读取：

```python
result.structured_content["placed_on"]
```

不必从“订单是在 2026 年 8 月 3 日下的”这句话里重新做字符串解析。

如果传入不存在的订单号，Server 会把业务异常转换成 `ToolError`。Client 收到的是一次正常完成的 MCP exchange，但：

```python
result.is_error is True
```

这和“网络根本连不上 Server”不是同一类错误。

```text
连接 / 协议失败
    → MCP 请求本身没有正常完成

Tool 执行失败
    → MCP 请求完成了，但业务操作失败
```

这种区分很重要。订单不存在时，重连十次不会让订单凭空出现；网络临时断开时，处理策略则可能完全不同。

## 8. Resource 和 Prompt 继续服务同一笔订单，而不是换一道例题

在同一个 `in_memory_client.py` 里，我们还读取：

```python
await client.read_resource("acme-support://guide/refund-evidence")
```

它返回一段客服审核指南，提醒应用核实订单、政策版本与必要材料。Resource 通过 URI 定位；Resource Template 则描述“一类 URI 怎么解析”。

Prompt 也围绕同一案件：

```python
await client.get_prompt(
    "prepare_case_summary",
    {"order_id": "ACME-1007", "audience": "customer"},
)
```

得到的是一段用于模型总结案件的模板。Server 没有因此获得 Host 内模型的控制权；Host 可以决定是否使用、什么时候用，以及还要配哪些上下文。

到这里，Tools、Resources、Prompts 的区别已经不再是三条定义，而是三件具体事情：

```text
查订单               → Tool
读退款审核指南        → Resource
准备案件摘要写作模板  → Prompt
```

这比背一句“Primitive 有三种”更容易在真实设计中做判断。

## 9. 先理解能力语义，再让消息跨进程、跨网络

进程内连接适合学习，但真实系统往往需要跨边界。MCP Python SDK 可以让同一套 Client 操作通过不同 transport 工作。

本章依次保留三种方式：

```text
in-process      同一个 Python 进程
stdio           Host 启动本地 Server 子进程
Streamable HTTP 独立运行的 HTTP MCP 服务
```

Primitive 的含义不变，变化的是消息怎么到达 Server。

### stdio：Host 启动一个本地子进程

[`code/stdio_client.py`](code/stdio_client.py) 用当前 Python 解释器启动 `mcp_server.py`：

```python
parameters = StdioServerParameters(
    command=sys.executable,
    args=[str(server_path)],
)

async with Client(stdio_client(parameters)) as client:
    ...
```

这时 MCP 请求通过子进程的 stdin 发送，响应从 stdout 返回。因此 **Server 子进程的 stdout 是协议通道**，不能随便拿来 `print("debug")`；诊断信息应写到 stderr 或正式日志系统。

运行：

```bash
python stages/05-mcp/code/stdio_client.py
```

它会真正从另一个 Python 进程读取 `ACME-1007` 的发票摘要。

### Streamable HTTP：Client 不负责启动 Server

HTTP 情况正好不同。Server 是一个独立运行的服务：

```bash
python stages/05-mcp/code/streamable_http_server.py
```

它监听本机 `127.0.0.1:8765`。然后在**另一个终端**运行 Client：

```bash
python stages/05-mcp/code/streamable_http_client.py
```

Client 只拿到 URL：

```python
async with Client("http://127.0.0.1:8765/mcp") as client:
    ...
```

它不会替你偷偷启动 `streamable_http_server.py`。这点和 stdio 完全不同：stdio Client 拥有子进程生命周期；HTTP Client 面对的是已经存在的服务。

先把这两个差异搞清楚，比一上来研究 HTTP header 更重要。

## 10. 协议版本由 Client 与 Server 协商，不要把一个版本号写进业务逻辑

进入 Client 生命周期以后，可以读取：

```python
client.protocol_version
client.server_capabilities
```

当前 MCP Python SDK v2 会处理协议探测与兼容逻辑，应用通常不需要为了普通业务调用手写“如果是某版本就走 A，否则走 B”。协议版本会继续演进，因此教学代码把它作为**可观察信息**打印出来，而不是作为订单业务分支条件。

同样，“协议本身可以无会话地处理现代请求”也不等于“订单系统没有状态”。`ACME-1007` 的订单信息仍然存放在业务服务里；是否创建过工单也仍然属于业务状态。

```text
protocol session semantics
        ≠
business state
```

这一点与 Stage 03 的 State 并不冲突。MCP 描述的是系统之间怎么交换请求，不是告诉你的业务“从今天开始禁止数据库”。

## 11. 现在把远程 Tool 接回 Stage 01 的 Runtime 形状

我们已经会直接用 MCP Client 调 Tool，但 Agent Runtime 并不应该到处知道 MCP SDK 的类型。更理想的方式，是把远程 Tool 翻译成 Runtime 已经理解的本地 Tool 形状。

[`code/tiny_agent_mcp_bridge.py`](code/tiny_agent_mcp_bridge.py) 中，远程 Tool 被包装成：

```python
@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    source: str
```

真正的 handler 最后仍然调用远程 Client：

```python
result = await self._client.call_tool(_remote_name, arguments)
```

于是整条链路变成：

```text
MCP Server
   ↓ list_tools()
MCP Client
   ↓ Bridge
Local Tool Registry
   ↓ schema
Model
   ↓ Tool Call proposal
Runtime
   ↓ registry.execute(...)
MCP Client
   ↓ call_tool(...)
MCP Server
   ↓ result
Runtime / Model
```

MCP 没有把 Stage 01 的 Runtime 推倒重写，它只是把一个本地 Tool handler 换成了远程 handler。这是比较健康的集成方式：新协议接入原有抽象，而不是让 Provider / MCP 类型一路渗透到业务控制代码。

## 12. Bridge 最重要的功能不是“自动注册全部 Tool”，而是过滤

这次 Bridge 和旧版最大的区别就在这里。

Server 发现了四个 Tool，但默认允许集合只有三个只读查询：

```python
DEFAULT_ALLOWED_TOOLS = frozenset(
    {"get_order_summary", "get_shipment_status", "get_invoice_summary"}
)
```

创建 Bridge 时必须显式提供 allowlist：

```python
bridge = MCPToolBridge(
    client,
    namespace="support",
    allowed_remote_tools=DEFAULT_ALLOWED_TOOLS,
)
```

`populate()` 先读取远程 catalog，然后只注册 allowlist 中的名称。若某个“应该存在”的允许 Tool 没有被 Server 发现，Bridge 会直接失败，而不是悄悄忽略：

```python
missing = self._allowed - discovered.keys()
if missing:
    raise RuntimeError(...)
```

所以模型最终看到的是：

```text
support__get_order_summary
support__get_shipment_status
support__get_invoice_summary
```

而不是：

```text
support__create_support_case
```

这就把前面的原则变成了代码：**Discovery 不是 Authorization。**

以后业务真的允许创建工单，也应该由新的策略明确把它加入当前任务的能力集合，而不是因为 Server 多发布了一个 Tool，模型第二天就自动多了一项写权限。

## 13. Namespace 解决的不只是重名，还保留来源

为什么本地名字要写成：

```text
support__get_order_summary
```

而不是继续叫：

```text
get_order_summary
```

因为 Host 很可能连接多个 Server。订单服务、ERP、CRM 都可能出现 `search`、`get_record` 这类名称。如果把来源抹掉，Registry 很快就不知道一个 Tool 究竟来自哪里。

Bridge 使用：

```python
local_name = f"{self._namespace}__{remote_name}"
```

namespace 一方面避免重名，另一方面给日志、策略与调试保留来源线索。它不是完整身份认证，但比把所有远程能力都扔进一个扁平名字空间更容易维护。

## 14. 为什么 Bridge 是异步的？因为远程调用不是普通函数调用

本地 Python 函数通常直接返回：

```python
result = handler(**arguments)
```

MCP Tool 可能要跨子进程或网络等待结果，所以 Bridge 的执行接口是：

```python
await registry.execute(name, arguments)
```

这里的 async 不代表“Agent 更智能”，只是表示调用可能等待 I/O。

还有一个容易踩坑的生命周期问题：Bridge 中创建的远程 handler 持有当前 MCP Client。它应该在：

```python
async with Client(...) as client:
    ...
```

这个生命周期内使用。离开代码块以后连接已经结束，不能把 Registry 保存到全局，过半小时再期待里面的远程 handler 还能使用已经关闭的 Client。

连接生命周期是资源管理问题，不是模型推理问题。

## 15. 接上真实 DeepSeek，完整链路才真正闭合

到这里，即使不调用模型，我们已经能验证 Server、Discovery、Bridge 和 Registry。现在再把真实 DeepSeek 接上，观察一条完整 Agent 路径。

[`code/deepseek_mcp_agent.py`](code/deepseek_mcp_agent.py) 仍然使用前几章相同的 DeepSeek Responses 接口。不同的是，发给模型的 function tools 来自 Bridge 过滤后的 Registry：

```python
def function_tools(registry: AsyncToolRegistry) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": schema["name"],
            "description": schema["description"],
            "parameters": schema["parameters"],
        }
        for schema in registry.schemas()
    ]
```

如果模型请求 `support__get_order_summary`，Runtime 先解析参数，再通过 Registry 调用远程 MCP Tool，把结构化结果作为 `function_call_output` 放回下一轮输入。

关键的是：**模型根本看不到 `support__create_support_case`。** 它没有机会仅靠“猜出一个函数名”绕过 Host 的 allowlist，因为 Registry 里也没有这项能力。

运行真实模型前配置：

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export DEEPSEEK_MODEL="your-available-model-id"
python stages/05-mcp/code/deepseek_mcp_agent.py
```

PowerShell 使用 `$env:DEEPSEEK_API_KEY=...` 与 `$env:DEEPSEEK_MODEL=...`。入口会明确打印 `live DeepSeek: API usage applies`。缺少 SDK、密钥或模型配置时会报错，不会偷偷换成脚本答案。

真实模型可能先查订单，再查物流，也可能顺便查发票；顺序和措辞都不保证和离线示例一致。我们真正关心的是三件事：它只能看见 allowlist 中的 Tool；系统事实来自远程结果；任务必须在模型轮数上限内结束。

## 16. MCP 返回的文本和 metadata 仍然属于外部输入

连接标准化以后，很容易产生一种危险的心理错觉：

> “这是 MCP Server 返回的，所以应该可信。”

不对。

MCP Resource 可能包含错误文字，Prompt 模板可能设计得很差，Tool description 也只是 Server 自己声明的 metadata。甚至远程 Tool 返回的业务数据也需要根据调用来源和业务规则解释。

所以这些等式都不成立：

```text
MCP Resource = system instruction          ❌
Tool annotation = 权限证明                 ❌
Tool 被发现 = 当前模型可以调用             ❌
Server description = 绝对可信事实          ❌
```

Stage 04 说“检索到的文本是数据，不是控制指令”，本章完全继承这条原则。协议统一了传输方式，不会替 Host 建立信任关系。

真正的权限、租户身份、审批和副作用策略仍然属于 Host / Runtime / 业务服务。

## 17. 到这里，哪些问题是 MCP 解决的，哪些不是？

现在回到开头那间“转接头专卖店”。MCP 确实替我们统一了不少事情：Host 可以用一致方式连接 Server，发现 Tools / Resources / Prompts，读取 Schema，调用 Tool，获得结构化结果和错误，并且同一套 Client 还能跑在进程内、stdio 或 Streamable HTTP 上。

但 MCP 没有替我们决定：

```text
当前用户能否看这份订单
模型该不该获得 create_support_case
创建工单是否需要审批
失败后该不该重试
跨租户数据怎样隔离
远程文本是否可信
外部副作用是否已经真正发生
```

这些问题没有“被协议自动解决”，反而因为系统真的接到了外部能力而变得更重要。

更准确的总结是：

> **MCP 标准化 Host 与外部能力提供方之间的互操作；Host 仍然拥有能力选择、权限和执行后果。**

## 18. 用检查把这些边界固定下来

离线环境即使没有 MCP SDK，也可以先运行本章的业务与 Bridge 检查：

```bash
python stages/05-mcp/code/checks.py
```

它会检查同一订单的订单、物流和发票数据能对应起来；未知订单会被拒绝；支持工单确实属于会改变状态的操作；Bridge 只注册 allowlist；允许的远程 Tool 缺失时会 fail closed；未知本地 Tool 不能执行。

安装 MCP SDK 后，同一文件还会额外跑真实 in-process MCP 检查，验证 Primitive discovery、结构化 Tool result、Tool error，以及真实 Client 经过 Bridge 后仍不会暴露 `create_support_case`。

然后再分别运行三种连接方式：

```bash
python stages/05-mcp/code/in_memory_client.py
python stages/05-mcp/code/stdio_client.py
```

HTTP 需要两个终端：

```bash
# 终端 A
python stages/05-mcp/code/streamable_http_server.py

# 终端 B
python stages/05-mcp/code/streamable_http_client.py
```

不要只看“最后有没有打印结果”，还要观察每个例子是谁启动 Server、连接什么时候存在、错误在哪一层出现。

## 19. 从 Stage 04 到 Stage 05，我们到底多了什么？

把两章接起来看，边界会非常清楚。

Stage 04 的核心是：

```text
外部文档
  ↓ 检索
证据
  ↓
模型回答
```

Stage 05 增加的是另一类外部来源：

```text
外部业务服务
  ↓ MCP
Tool / Resource / Prompt
  ↓ Host 过滤与适配
Agent Runtime
```

所以现在小林已经能做两件过去做不到的事：一边从当前政策中找依据，一边向外部系统核实 `ACME-1007` 的订单事实。政策解释和系统事实终于不需要都靠用户自己提供。

但我们又故意停在一个新的边界上：Server 已经有 `create_support_case`，Host 却默认没有把它交给模型。为什么？因为一旦动作开始产生长期副作用，就会出现“是否需要人审、执行到一半进程重启怎么办、哪些状态必须保存”这些问题。

这正是下一章的入口。

[Stage 06：Memory、Persistence 与 Human-in-the-Loop](../06-memory-persistence-hitl/README.zh-CN.md) 会从“查询已经能跨系统，真正要执行动作时怎么暂停、保存和恢复”继续。到了那里，我们才有理由让“长期存在的状态”和“人工审批”正式登场，而不是提前把所有复杂度塞进 MCP 这一章。
