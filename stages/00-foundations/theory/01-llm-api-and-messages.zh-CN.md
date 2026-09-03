# 01 — 先别急着写 Agent：从一次 LLM API 调用开始

> Language: [English](01-llm-api-and-messages.md) | 简体中文

很多 Agent 教程的第一行代码就是 `create_agent(...)`。

这对“快速跑起来”很方便，但对真正理解 Agent 不太友好。因为当第一层抽象就把请求、消息、模型响应、状态管理都藏起来时，你很容易把框架提供的能力误认为模型本身的能力。

所以这一章我们故意做一件很朴素的事：**只调用一次 OpenAI 模型，然后把这次调用拆开。**

等你真正看懂这一次调用，后面的 Tool Calling 和 Agent loop 才会有落脚点。

---

## 1. 先运行最小的完整例子

假设我们想问模型一个和本项目直接相关的问题：

> 为什么 Agent 不能简单理解成“一个 LLM”？

当前 OpenAI Python SDK 推荐用 Responses API 来完成这类调用：

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5.6-luna",
    instructions=(
        "你是一位耐心的 AI 工程老师。"
        "请用简洁但准确的中文解释概念。"
    ),
    input="为什么 Agent 不能简单理解成一个 LLM？",
)

print(response.output_text)
```

运行前需要设置：

```bash
export OPENAI_API_KEY="你的 API Key"
```

代码对应的可运行版本在：

[`../code/first_openai_call.py`](../code/first_openai_call.py)

### 预期输出

模型生成具有随机性，因此文字不会逐字一致。一个合理的输出大概是：

```text
LLM 主要负责根据输入进行语言理解和生成；
Agent 则是在 LLM 之外加入了 Runtime、Tool、状态、执行流程和控制策略。
LLM 可以提出“下一步做什么”，但真正执行 Tool、保存状态和限制权限的是应用程序。
```

先不要急着往下读。看着这段代码，问自己三个问题：

1. `OpenAI()` 做了什么？
2. `responses.create(...)` 发送了什么？
3. `response.output_text` 又是什么？

下面逐一拆开。

---

## 2. `OpenAI()` 不是模型，它只是客户端

```python
client = OpenAI()
```

这行代码创建的是 **API 客户端（API Client）**。

它负责和 OpenAI 的服务通信，例如：

```text
读取 API Key
    ↓
构造 HTTP 请求
    ↓
发送到 OpenAI API
    ↓
接收 HTTP 响应
    ↓
转换成 Python 对象
```

真正执行模型推理的并不是这个 Python 对象。

这就像你手机里的外卖 App 不是餐厅厨房。App 负责把订单送过去、把结果带回来；厨房才真正做饭。

这个区分以后非常重要，因为 Agent 运行时（Runtime）也不是 LLM。它同样是在**组织、调用和约束模型**。

---

## 3. 为什么“提供商专用客户端”不应该直接长进 Agent Runtime 里？

到这里很容易写出一种能跑、但不耐用的代码：

```python
from openai import OpenAI


def answer(prompt: str) -> str:
    client = OpenAI()
    response = client.responses.create(
        model="gpt-5.6-luna",
        input=prompt,
    )
    return response.output_text
```

如果这个程序永远只调用 OpenAI，这段代码没有什么罪过。

问题出现在第二天产品经理说：

> “我们也想测一下 Qwen。”

### 同样用 OpenAI SDK 调用 Qwen

阿里云 Model Studio 当前提供 OpenAI-compatible Responses API，因此 Qwen 也可以保持我们前面使用的 OpenAI 调用范式：

```python
import os
from openai import OpenAI

qwen_client = OpenAI(
    api_key=os.environ["DASHSCOPE_API_KEY"],
    base_url=os.environ["DASHSCOPE_BASE_URL"],
)

response = qwen_client.responses.create(
    model="qwen3.8-max",
    instructions="你是一位耐心的 AI 工程老师。",
    input="为什么 Agent Runtime 不应该和某一家模型提供商绑定？",
)

print(response.output_text)
```

其中 `DASHSCOPE_BASE_URL` 应该配置成与你的 Model Studio 工作空间和地域匹配的 OpenAI-compatible 地址，例如官方文档给出的形式：

```text
https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

不同地域使用不同地址，API Key 也必须和地域匹配，所以这里故意不把地址硬编码进 Runtime。

一个合理的模拟输出可能是：

```text
Agent Runtime 应该依赖稳定的内部接口，而不是某一家模型服务的具体 Response 类型。
这样更换模型提供商时，只需要修改边缘适配层，而不必重写 Tool loop、状态管理和控制逻辑。
```

你可能马上会问：

> “OpenAI 和 Qwen 的代码长得这么像，那我为什么还需要 Adapter？”

这正是最值得理解的地方。

### “OpenAI-compatible” 不等于“完全相同”

兼容接口确实降低了迁移成本，但 provider 差异仍然存在：

```text
API Key 来源不同
base_url 不同
model ID 不同
支持的参数和功能可能不同
Tool / Structured Output 的细节可能不同
usage 字段和扩展字段可能不同
错误码、限流、重试语义可能不同
某些未来 provider 甚至根本不兼容 OpenAI 协议
```

阿里云自己的 Responses API 文档也明确提醒：它虽然兼容 OpenAI，但参数、功能和行为并不保证完全一致。

所以真正应该隔离的是：

```text
                    provider-specific 世界
                 ┌─────────────────────────┐
OpenAI SDK ------>| OpenAI client / Response|
                 ├─────────────────────────┤
Qwen endpoint --->| Qwen config / behavior |
                 └────────────┬────────────┘
                              │
                           Adapter
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ ModelRequest            │
                 │ ModelReply              │
                 │ ToolCall（Stage 01）    │
                 └────────────┬────────────┘
                              │
                              ▼
                       Agent Runtime
```

Runtime 不应该关心：

```text
“这个 response 是 OpenAI SDK 的哪个 class？”
“Qwen 的 base_url 是什么？”
“这家 provider 的 usage 里多了什么扩展字段？”
```

它应该关心的是：

```text
“模型给了我什么文本？”
“模型是否提出了 ToolCall？”
“Token 使用是多少？”
“这次模型调用失败了吗？”
```

### 一个最小 Adapter 长什么样？

先定义 Runtime 自己认识的数据：

```python
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelRequest:
    instructions: str
    input: str


@dataclass(frozen=True)
class ModelReply:
    text: str
    response_id: str
    model: str


class ModelAdapter(Protocol):
    def generate(self, request: ModelRequest) -> ModelReply:
        ...
```

然后让 provider 适配层负责翻译：

```python
class OpenAICompatibleResponsesAdapter:
    def __init__(self, client, model: str):
        self.client = client
        self.model = model

    def generate(self, request: ModelRequest) -> ModelReply:
        response = self.client.responses.create(
            model=self.model,
            instructions=request.instructions,
            input=request.input,
        )
        return ModelReply(
            text=response.output_text,
            response_id=response.id,
            model=response.model,
        )
```

现在核心业务代码只依赖 `ModelAdapter`：

```python
def run_once(model: ModelAdapter, user_input: str) -> str:
    reply = model.generate(
        ModelRequest(
            instructions="你是旅行助手。",
            input=user_input,
        )
    )
    return reply.text
```

注意 `run_once()` 里面没有：

```python
if provider == "openai":
    ...
elif provider == "qwen":
    ...
```

这就是关键。

如果 provider 判断散落在 Tool loop、规划、状态机、重试逻辑和权限逻辑里，换一次模型就像在整栋楼里重新布电线。代码还能亮，但以后谁都不敢碰开关。

Adapter 的作用，就是把这些变化压在系统边缘。

本项目提供了完整可运行示例：

[`../code/provider_adapter_demo.py`](../code/provider_adapter_demo.py)

调用 OpenAI：

```bash
python stages/00-foundations/code/provider_adapter_demo.py --provider openai
```

调用 Qwen：

```bash
export DASHSCOPE_API_KEY="你的 Model Studio API Key"
export DASHSCOPE_BASE_URL="与你的地域和 Workspace 匹配的 compatible-mode/v1 地址"
export QWEN_MODEL="qwen3.8-max"

python stages/00-foundations/code/provider_adapter_demo.py --provider qwen
```

两种运行方式进入的是**同一个** `run_teacher_example()`。变化发生在 Adapter 和配置层，而不是 Runtime 核心逻辑里。

Stage 01 会继续把这个思路扩展到真正的 Agent 模型适配器：把 provider 原生的文本、Function Call、usage 和异常，归一化成 Runtime 自己的内部类型。

---

## 4. 一次模型请求里，我们到底给了模型什么？

回头看：

```python
response = client.responses.create(
    model="gpt-5.6-luna",
    instructions="你是一位耐心的 AI 工程老师……",
    input="为什么 Agent 不能简单理解成一个 LLM？",
)
```

这里至少包含三个不同概念。

### `model`

指定使用哪个模型。

```python
model="gpt-5.6-luna"
```

模型名称属于模型提供商（provider）的版本化配置。以后可能会更新，所以不要把某个 model ID 背成“Agent 原理”。

真正稳定的知识是：**应用选择一个模型，然后向它发送一次请求。**

### `instructions`

这是应用提供的高层指令：

```python
instructions="你是一位耐心的 AI 工程老师……"
```

它回答的是：

> 这次模型应该以什么规则、角色或风格工作？

例如你可以要求：

```text
回答使用中文
不要编造未知事实
给初学者解释
只根据提供的证据回答
```

在 Responses API 中，顶层 `instructions` 会作为具有系统/开发者指令语义的上下文进入模型请求。

### `input`

这是当前真正要处理的输入：

```python
input="为什么 Agent 不能简单理解成一个 LLM？"
```

最简单时，它就是一个字符串。

复杂时，它也可以是一组带角色的消息或其它输入项。

所以可以先把一次调用理解为：

```text
应用规则（instructions）
          +
当前任务（input）
          ↓
        模型
          ↓
        输出
```

这已经比“把所有东西拼成一个 prompt 字符串”更接近真实工程。

---

## 5. `response` 不是只有一段文字

初学时我们最常用：

```python
print(response.output_text)
```

`output_text` 是 SDK 提供的便利属性，用来取得最终文本。

但完整的 Response 对象还可能包含：

```text
response.id
response.model
response.output
response.usage
response.status
...
```

尤其重要的是 `response.output`。

为什么？

因为模型以后不一定只返回“文字”。它还可能返回：

```text
assistant message
function call
reasoning item
built-in tool call
...
```

到了 Tool Calling 章节，我们就不能再简单地假设：

```python
response.output[0] == 一段文本
```

所以普通问答时使用：

```python
response.output_text
```

很方便；但 Agent Runtime 必须学会处理不同类型的 output item。

这就是为什么我们现在先认识 Response，而不是等到 Stage 01 再突然面对一堆对象。

---

## 6. “消息角色”到底解决什么问题？

很多资料会直接让你背：

```text
system
user
assistant
tool
```

但只背名字没有意义。

角色真正解决的是一个问题：

> **同样都是文本，模型凭什么知道哪段是应用规则、哪段是用户要求、哪段是之前的模型回答、哪段是外部 Tool 返回的数据？**

例如在概念上，一段对话可能是：

```text
应用指令：你是旅行助手。
用户：我准备去东京。
助手：你想了解天气还是交通？
用户：天气。
```

这些内容如果被无脑拼成：

```text
你是旅行助手。我准备去东京。你想了解天气还是交通？天气。
```

人勉强还能猜出来，程序和模型面对复杂上下文时就会越来越混乱。

结构化消息能保留“这段内容是谁产生的、有什么语义作用”。

在 Responses API 中，普通消息可以写成：

```python
input=[
    {
        "role": "user",
        "content": "我准备去东京，18°C 需要穿厚外套吗？",
    }
]
```

而应用级规则可以继续放在 `instructions` 中。

---

## 7. `assistant` 历史是谁保存的？

这是 Stage 00 最容易形成错误直觉的地方。

你在 ChatGPT 产品里连续聊很多轮，很容易感觉：

> “模型自己记得前面的内容。”

但在 API 工程中，更准确的说法是：

> **模型当前能利用哪些过去信息，取决于应用或模型提供商的会话机制向这一轮提供了什么上下文。**

例如第一次调用：

```python
first = client.responses.create(
    model="gpt-5.6-luna",
    input="我的项目叫 Tiny-Agent。",
)
```

第二次如果只写：

```python
second = client.responses.create(
    model="gpt-5.6-luna",
    input="我的项目叫什么？",
)
```

你不应该假设第二个独立请求自动拥有第一个请求的全部上下文。

### 用 `previous_response_id` 继续一次对话

Responses API 提供了一种方便的连续调用方式：

```python
first = client.responses.create(
    model="gpt-5.6-luna",
    input="我的项目叫 Tiny-Agent。",
)

second = client.responses.create(
    model="gpt-5.6-luna",
    previous_response_id=first.id,
    input="我的项目叫什么？",
)

print(second.output_text)
```

### 预期输出

```text
你的项目叫 Tiny-Agent。
```

这里不是“模型突然获得永久记忆”，而是 API 使用前一个 Response 建立了连续上下文。

这是非常重要的区别。

因为以后你还会遇到：

```text
conversation history
checkpoint
short-term memory
long-term memory
RAG evidence
provider-managed conversation
```

它们都可能让模型“看起来记得东西”，但工程语义完全不同。

---

## 8. 一个很容易漏掉的细节：`instructions` 不等于永久状态

如果你通过 `previous_response_id` 继续对话，也不要形成另一个误解：

> “上一轮的所有配置以后都会自动继承。”

当前 Responses API 明确把 `instructions` 视为当前请求配置；在继续请求时，应用应该明确提供这一轮仍然需要的高层指令，而不是把控制策略建立在“应该还记得”上。

这背后对应一个很重要的 Agent 原则：

> **稳定行为应该由应用显式构造，而不是依赖隐含状态。**

后面写 Tool loop 时，你会看到我们每轮都明确提供需要的 Tool schema 和指令。

---

## 9. 模型“知道”什么，和应用“拥有”什么，不是一回事

假设你的 Python 程序里有：

```python
user_profile = {
    "name": "Alice",
    "city": "Tokyo",
    "budget": 8000,
}
```

只因为这个变量存在于 Python 内存中，不代表模型自动知道它。

只有当应用选择其中的信息并放进请求：

```python
response = client.responses.create(
    model="gpt-5.6-luna",
    input=f"用户资料：{user_profile}\n请给出旅行建议。",
)
```

模型才有机会利用这些数据。

同样：

```text
数据库里有 100 万条记录
!= 模型知道 100 万条记录

硬盘里有 10 GB 文档
!= 模型读过这些文档

Python 有一个函数
!= 模型已经执行这个函数
```

这一组“不等于”会贯穿整个 Tiny-Agent。

---

## 10. 为什么下一章马上要讲 Structured Output？

现在我们已经能完成最基本的流程：

```text
Python 程序
    ↓
调用模型
    ↓
得到自然语言
```

但如果下一步不是“把答案展示给人”，而是“让程序继续根据结果做事”，问题马上出现。

例如我们问：

> 从“我 2026 年 10 月 3 日去东京，预算 8000 元，还想查天气”中提取旅行信息。

模型可能回答：

```text
好的，这位用户准备在 10 月 3 日前往东京，预算约 8000 元，并且希望了解天气。
```

人看起来完全没问题。

但程序想要的是：

```json
{
  "city": "东京",
  "travel_date": "2026-10-03",
  "budget_cny": 8000,
  "needs_weather": true
}
```

于是下一章的问题自然出现：

> **当模型输出要被程序读取时，我们能不能不要再靠正则表达式和字符串猜测？**

这就是 Structured Output 要解决的事情。

---

## 11. 本章真正需要记住的五句话

如果这一章最后只记五句话，我希望是：

1. **API 客户端是调用模型的程序接口，不是模型本身。**
2. **模型只根据当前可用上下文推理，不要把“能连续聊天”误解成“模型天然拥有永久记忆”。**
3. **应用中的数据、函数和权限不会因为模型存在就自动进入模型能力范围。**
4. **模型提供商的 API、配置和 Response 类型应该停留在 Adapter 边缘，不要渗进 Agent Runtime。**
5. **Agent 的第一层边界，是模型负责生成，应用负责构造请求和处理结果。**

下一章，我们开始让模型的输出真正适合被程序消费。

---

## 官方参考

- OpenAI Responses API：<https://developers.openai.com/api/reference/resources/responses>
- OpenAI model guidance：<https://developers.openai.com/api/docs/guides/latest-model>
- 阿里云 Model Studio：Qwen OpenAI-compatible Responses API：<https://docs.modelstudio.console.alibabacloud.com/zh/model-studio/qwen-api-via-openai-responses>
