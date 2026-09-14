# Stage 05: The Policy Is Searchable—But the Order Cannot Still Be Self-Reported

> Language: **English** | [简体中文](README.zh-CN.md)

[Stage 04](../04-agentic-rag/README.md) taught Lin's assistant to stop guessing policy from model memory. It retrieves the current refund policy, checks whether the evidence is sufficient, and answers from that evidence. But the chapter deliberately left one assumption in place: when the customer said, “I ordered on August 3, the item is paid, and today is day 38,” the program treated those statements as supplied facts. It never verified the order in an order system.

The moment Lin tries to turn the demo into a real support workflow, a new boundary appears. The documentation team owns policy content. The order service owns order facts. Shipping lives in another system. Invoice data lives somewhere else. If the Agent team invents a separate discovery format, argument format, error model, and connection wrapper for every service, the repository soon becomes a museum of adapters.

This chapter keeps following one fictional teaching order, `ACME-1007`. We will verify its order date, paid amount, shipment status, and invoice data through an external service. That service also exposes a state-changing capability called `create_support_case`. The Host will discover it—but will **not expose it to the model by default**. That single difference captures one of the most important MCP boundaries:

> **A capability that exists on a server is not automatically a capability that this Agent may use.**

Start with the story. MCP is not a way to make a model smarter. It is a standardized way for a Host to communicate with external providers of capabilities and context.

## 1. What new boundary appeared after the local Tool loop?

The Stage 01 weather tools lived in the same Python application as the Runtime. Once the Registry resolved a Tool name, Python could call the local handler directly:

```python
result = registry.execute(call.name, call.arguments)
```

There was no separate team and no network boundary.

Order lookup is different. Lin does not own the order service's implementation. The Agent application receives an interface maintained by another system. The execution path now has another boundary:

```text
model
  ↓ proposes a Tool Call
Tiny-Agent Runtime
  ↓ validates allowed capability
external-service connection layer
  ↓ requests order / shipment / invoice data
business service
```

Function Calling addresses the first boundary: **how a model expresses a structured request to use a capability.** MCP addresses the later boundary: **how an application discovers and invokes capabilities and context provided by another system in a standard way.**

They can sit in the same path. A model may request `support__get_order_summary`; the Runtime can then execute that local Tool wrapper, whose handler calls a remote MCP Server.

That is why “MCP is Function Calling” is too imprecise. A model proposal and a Host-to-service protocol are different responsibilities.

## 2. Walk the support task before naming protocol primitives

The customer asks whether order `ACME-1007` qualifies for a refund.

Stage 04 can retrieve the relevant policy. Before applying that policy, support wants system facts: when was the order placed, what was paid, what is the shipment state, and what invoice record belongs to it?

The task therefore grows into:

```text
customer question
    ↓
retrieve current refund policy      ← Stage 04
    ↓
verify order-system facts           ← new boundary
    ↓
verify shipment / invoice data
    ↓
explain system facts with policy evidence
```

A later workflow may also create a support case. That is different from the first three operations: queries read state; creating a case changes state.

The fictional Acme Support Server therefore exposes four Tools:

```text
get_order_summary
get_shipment_status
get_invoice_summary
create_support_case
```

The first three are read-only teaching operations. The last has a side effect. Putting them on one Server is intentional: real services often offer both reads and writes. A trustworthy Agent cannot simply conclude, “all Tools from this server are equally safe.”

## 3. Host, Client, Server: keep the three jobs separate

In this story, the **Host** is Tiny-Agent. It owns the model, Runtime, context, and application policy.

The **MCP Client** is the component inside the Host that speaks MCP to one server. It lists Tools, reads Resources, renders Prompts, and sends Tool calls.

The **MCP Server** is the external provider. Our teaching server stands in for an Acme order/support service.

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

The important boundary is simple: **the Server declares what it offers; the Host decides what the current Agent is allowed to use.**

Everything later in the chapter—discovery, bridging, namespacing, and allowlists—follows from that sentence.

## 4. One Server can expose actions, data, and reusable prompts

The teaching Server lives in [`code/mcp_server.py`](code/mcp_server.py). It demonstrates the three core server primitives without switching to unrelated examples.

A useful plain-language memory aid is:

```text
Tool     = do something
Resource = let me read something
Prompt   = give me a reusable model-input template
```

### Tool: invoke a capability

Order lookup is a Tool:

```python
@mcp.tool()
def get_order_summary(order_id: str) -> dict[str, object]:
    return _tool_call(order_record, order_id)
```

So is the state-changing support action:

```python
@mcp.tool()
def create_support_case(order_id: str, reason: str) -> dict[str, str]:
    return _tool_call(create_case_record, order_id, reason)
```

Both are Tools. That does **not** mean they carry the same risk.

### Resource: read data addressed by a URI

The support guide is better modeled as a Resource:

```python
@mcp.resource("acme-support://guide/{topic}")
def support_guide(topic: str) -> str:
    return read_support_guide(topic)
```

For example:

```text
acme-support://guide/refund-evidence
```

means “read the refund-evidence guide.” Turning every readable object into a fake `get_*` Tool would erase a useful semantic distinction.

### Prompt: obtain a reusable message template

The Server also exposes:

```python
@mcp.prompt()
def prepare_case_summary(order_id: str, audience: str = "customer") -> str:
    ...
```

That returns model-facing instructions. It does not execute a business action and it is not itself evidence.

Stage 04 separated evidence from actions. MCP preserves that distinction instead of flattening every external thing into “a Tool.”

## 5. First connect in-process so networking does not steal the lesson

Ports, proxies, subprocesses, and HTTP can distract from the protocol semantics. The Python SDK can connect a `Client` directly to an `MCPServer` object:

```python
from mcp import Client
from mcp_server import mcp

async with Client(mcp) as client:
    tools = await client.list_tools()
```

This in-process connection has no subprocess and no TCP port, but the Client/Server MCP behavior still exists. Entering `async with` connects and negotiates; leaving the block disconnects.

Install the chapter dependencies and run:

```bash
python -m pip install -r stages/05-mcp/code/requirements.txt
python stages/05-mcp/code/in_memory_client.py
```

The program discovers every primitive, then calls `get_order_summary` and `get_shipment_status` for `ACME-1007`.

You should see structured facts such as:

```text
order: {'order_id': 'ACME-1007', 'placed_on': '2026-08-03', ...}
shipment: {'order_id': 'ACME-1007', 'shipment_status': 'delivered', ...}
```

That finally changes the meaning of the August 3 date from “customer-supplied scenario fact” to “fact returned by this teaching business service.”

It is still fictional data. We are verifying the protocol and control boundary, not a real store.

## 6. Discovery is a catalog, not an authorization table

The Client can discover remote Tools:

```python
catalog = await client.list_tools()
```

The catalog includes `create_support_case`.

Do not silently transform that into “therefore the model should receive this Tool.” Discovery answers:

> What does the Server claim to provide?

Authorization answers:

> Which capabilities may this user, task, and model use now?

Those are separate sets:

```text
discovered capability
        ≠
model-visible capability
        ≠
authorized execution
```

This should feel familiar from retrieval. A document existing in a store does not automatically make it eligible for every caller. A Tool existing on an MCP Server does not automatically make it eligible for every Agent.

## 7. Tool results are structured protocol results, not just strings

Call the order Tool:

```python
result = await client.call_tool(
    "get_order_summary",
    {"order_id": "ACME-1007"},
)
```

Three result concepts are useful to keep separate:

```text
content             human/model-oriented content blocks
structured_content  structured data for application code
is_error            whether Tool execution failed
```

Because the order Tool returns a dictionary, application code can read:

```python
result.structured_content["placed_on"]
```

without scraping a sentence.

If the caller requests an unknown order, the Server turns the expected business failure into an MCP Tool error. The MCP exchange can still complete normally while:

```python
result.is_error is True
```

That is different from the Client failing to connect or parse the protocol at all.

```text
transport / protocol failure
    → the MCP exchange itself did not complete normally

Tool execution failure
    → the exchange completed, but the requested business operation failed
```

Retry and recovery policy should care about that distinction. Reconnecting will not make a nonexistent order suddenly exist.

## 8. Resources and Prompts stay inside the same support story

The in-memory client also reads:

```python
await client.read_resource("acme-support://guide/refund-evidence")
```

This returns a support guide reminding the application to verify the order record, applicable policy, and approval material.

It can also render:

```python
await client.get_prompt(
    "prepare_case_summary",
    {"order_id": "ACME-1007", "audience": "customer"},
)
```

The result is a reusable model-input template. The Server still does not own the Host's model or decide when that prompt is used.

Now the three primitive types have concrete meanings in one task:

```text
verify an order                  → Tool
read the refund-evidence guide   → Resource
prepare a case-summary template  → Prompt
```

That distinction is more useful than memorizing a list of protocol nouns.

## 9. Once the semantics are clear, move the same protocol across boundaries

The same Client operations can cross different transports. The important difference is where the Server runs and who owns its lifecycle.

```text
in-process      same Python process
stdio           Host launches a local server subprocess
Streamable HTTP independently running MCP HTTP service
```

### stdio: the Host launches the Server subprocess

[`code/stdio_client.py`](code/stdio_client.py) launches `mcp_server.py` using the same Python interpreter:

```python
parameters = StdioServerParameters(
    command=sys.executable,
    args=[str(server_path)],
)

async with Client(stdio_client(parameters)) as client:
    ...
```

MCP requests travel through the child process's stdin and responses through its stdout. Therefore the **Server subprocess's stdout is the protocol channel**. Do not write arbitrary debug text there; use stderr or a proper logging destination.

Run:

```bash
python stages/05-mcp/code/stdio_client.py
```

This time invoice data comes from another Python process.

### Streamable HTTP: the Client does not launch the Server

HTTP has a different lifecycle. Start the service explicitly in one terminal:

```bash
python stages/05-mcp/code/streamable_http_server.py
```

Then run the Client in another:

```bash
python stages/05-mcp/code/streamable_http_client.py
```

The Client only knows a URL:

```python
async with Client("http://127.0.0.1:8765/mcp") as client:
    ...
```

It does **not** start `streamable_http_server.py` for you. That is the opposite of the stdio ownership model.

Understanding that lifecycle difference is more useful at this stage than memorizing transport headers.

## 10. Observe protocol negotiation; do not turn one version string into business logic

Inside a connected Client, you can inspect:

```python
client.protocol_version
client.server_capabilities
```

The current Python SDK v2 handles protocol discovery and compatibility behavior for you. The example prints the negotiated version as diagnostic information rather than branching order logic on one hard-coded string.

Protocol session semantics also do not erase application state. `ACME-1007` still exists in a business data store; support cases still have state.

```text
protocol session semantics
        ≠
business state
```

MCP explains how systems exchange requests. It does not outlaw databases or replace the explicit state ideas from Stage 03.

## 11. Bridge a remote MCP Tool into the local Runtime shape

Direct Client calls are useful for learning, but the core Agent Runtime should not have to understand MCP-specific response types everywhere.

[`code/tiny_agent_mcp_bridge.py`](code/tiny_agent_mcp_bridge.py) adapts a remote Tool into the same local shape the Runtime already understands:

```python
@dataclass(slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    source: str
```

The generated handler ultimately calls:

```python
result = await self._client.call_tool(_remote_name, arguments)
```

The complete path becomes:

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

Nothing about MCP requires throwing away the Stage 01 Runtime. It simply supplies a remote implementation behind an existing Tool boundary.

## 12. The Bridge must filter, not automatically expose everything it discovers

This is the most important change from a naive bridge.

The Server publishes four Tools, but the default model-visible allowlist contains only the three read operations:

```python
DEFAULT_ALLOWED_TOOLS = frozenset(
    {"get_order_summary", "get_shipment_status", "get_invoice_summary"}
)
```

The Bridge requires an explicit set:

```python
bridge = MCPToolBridge(
    client,
    namespace="support",
    allowed_remote_tools=DEFAULT_ALLOWED_TOOLS,
)
```

`populate()` compares that allowlist with the discovered catalog. If an expected allowed Tool is missing, it fails closed instead of silently pretending the capability exists.

The model therefore sees:

```text
support__get_order_summary
support__get_shipment_status
support__get_invoice_summary
```

and does not see:

```text
support__create_support_case
```

That is **Discovery != Authorization** implemented as code rather than left as a warning paragraph.

If a later workflow is allowed to create a case, a separate application policy can add that capability deliberately. A server deployment should not be able to grant every model a new side effect merely by publishing one more Tool tomorrow.

## 13. Namespaces preserve origin as well as avoiding collisions

Two servers may both expose names such as `search` or `get_record`. Registering every remote Tool into one flat local namespace makes provenance ambiguous.

The bridge builds local names with:

```python
local_name = f"{self._namespace}__{remote_name}"
```

`support__get_order_summary` tells logs and policy code where the capability came from. A namespace is not authentication, but preserving origin is much better than discarding it at the adapter boundary.

## 14. The bridge is async because remote execution is I/O

A local Python handler can often return immediately:

```python
result = handler(**arguments)
```

A remote MCP Tool may wait on a subprocess or network request, so the bridge exposes:

```python
await registry.execute(name, arguments)
```

Async here is an I/O boundary, not an intelligence feature.

The Client lifecycle matters too. Generated remote handlers refer to the current MCP Client. Use them inside:

```python
async with Client(...) as client:
    ...
```

Once the block exits, the connection is closed. Do not populate a global Registry and expect its remote handlers to keep using a dead Client later.

## 15. Add live DeepSeek only after the connection and policy boundary are clear

The protocol can be tested without a model. Once those mechanics are clear, [`code/deepseek_mcp_agent.py`](code/deepseek_mcp_agent.py) closes the full Agent loop using the same DeepSeek Responses style as earlier stages.

The model-facing function definitions come from the **filtered local Registry**:

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

If the model asks for `support__get_order_summary`, the Runtime parses its arguments, executes the Registry entry, receives the MCP result, and sends the structured output back as a `function_call_output` on the next model turn.

The critical security property is simpler: **the model cannot request `support__create_support_case` through this Runtime because that Tool was never registered or shown to it.** Guessing a name does not create a capability.

Configure a real account before running:

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export DEEPSEEK_MODEL="your-available-model-id"
python stages/05-mcp/code/deepseek_mcp_agent.py
```

PowerShell uses `$env:DEEPSEEK_API_KEY=...` and `$env:DEEPSEEK_MODEL=...`. The entry point prints `live DeepSeek: API usage applies`. Missing dependencies, credentials, or provider failures are reported; the program does not silently fall back to scripted answers.

A live model may query order, shipment, and invoice data in a different order. The important invariants are that only allowlisted Tools are visible, system facts come from Tool results, and the outer Runtime has a model-turn limit.

## 16. MCP content is still external input

A standard protocol can create a dangerous psychological shortcut: “it came from MCP, therefore it is trusted.”

That is false.

A Resource may contain malicious or incorrect text. A Prompt may be poorly designed. Tool descriptions and annotations are server-declared metadata. Even structured business results must still be interpreted under application identity and business rules.

None of these equations are valid:

```text
MCP Resource = system instruction           ✗
Tool annotation = authorization proof       ✗
Tool discovered = model may call it         ✗
Server description = absolute truth         ✗
```

Stage 04 said retrieved text is data, not control policy. The same principle applies here. MCP standardizes communication; it does not manufacture trust.

Authorization, tenant identity, approval rules, and side-effect policy remain Host/application responsibilities.

## 17. What did MCP solve, and what did it deliberately not solve?

MCP gives the Host a consistent way to connect to external services, discover Tools/Resources/Prompts, inspect schemas, call Tools, read structured results and errors, and reuse the same high-level Client across in-process, stdio, and Streamable HTTP transports.

It does **not** automatically decide:

```text
whether this user may read the order
whether the model should receive create_support_case
whether a write requires approval
whether a failed side effect is safe to retry
how tenants are isolated
whether remote text is trustworthy
whether an external action really completed exactly once
```

A useful summary is:

> **MCP standardizes interoperability between a Host and external providers; the Host still owns capability selection, authorization, and execution consequences.**

## 18. Turn the boundaries into executable checks

The chapter checks run even without the MCP SDK for the pure business and bridge logic:

```bash
python stages/05-mcp/code/checks.py
```

They verify that order, shipment, and invoice data refer to the same teaching order; unknown orders fail; case creation is explicitly state-changing; the bridge registers only an allowlist; missing allowed Tools fail closed; and unknown local Tools cannot execute.

When the MCP SDK is installed, the same test file also runs real in-process integration checks for primitive discovery, structured Tool results, Tool errors, and the real Client-to-Bridge path that still excludes `create_support_case`.

Then exercise the transports:

```bash
python stages/05-mcp/code/in_memory_client.py
python stages/05-mcp/code/stdio_client.py
```

Streamable HTTP needs two terminals:

```bash
# terminal A
python stages/05-mcp/code/streamable_http_server.py

# terminal B
python stages/05-mcp/code/streamable_http_client.py
```

Do not inspect only the final printed dictionary. Notice who starts the Server, when the connection exists, and whether a failure belongs to transport, protocol, or Tool execution.

## 19. The handoff to Stage 06 now follows from the story

Stage 04 added an external evidence path:

```text
external documents
  ↓ retrieval
selected evidence
  ↓
model answer
```

Stage 05 adds another external boundary:

```text
external business service
  ↓ MCP
Tool / Resource / Prompt
  ↓ Host filtering + adapter
Agent Runtime
```

Lin's assistant can now combine current policy evidence with verified system facts about `ACME-1007`. It no longer needs the customer to self-report every order fact.

But we deliberately stop before granting the model the state-changing `create_support_case` capability. The moment a workflow may create a case, issue a refund, or wait for approval, new questions appear: what survives a process restart, where does an interrupted run resume, and when must a human take control?

That is the natural next problem, not another MCP feature.

[Stage 06: Memory, Persistence, and Human-in-the-Loop](../06-memory-persistence-hitl/README.md) continues from that point: external reads now work, so the next step is making long-lived actions, pauses, and recovery explicit.
