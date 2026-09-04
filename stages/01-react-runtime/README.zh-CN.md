# Stage 01 — 把 Tool Calling 变成一个真正的 Agent Runtime

> Language: [English](README.md) | 简体中文

Stage 00 结束时，我们已经亲手写过一个最小 Tool loop：

```text
用户问题
   ↓
模型判断要不要调用 Tool
   ↓
Python 执行 Tool
   ↓
把结果交还给模型
   ↓
模型继续判断
```

它已经有一点 Agent 的味道了。

但如果你真的准备把这段代码继续往下写，很快会遇到一个问题：**那个 loop 里混进了越来越多彼此不同的职责。**

例如：

```text
怎么调用模型？
怎么把不同模型提供商的响应转成统一格式？
Tool 名字怎么查找？
谁真正执行 Python 函数？
Tool 执行失败后怎么办？
模型连续调用 Tool 时谁负责继续循环？
模型一直不结束怎么办？
我们怎么知道刚才到底执行了哪些步骤？
```

如果这些问题全部继续塞进一个 `while True`，代码当然也能跑，但它会越来越难理解、难测试，也很难扩展。

所以 Stage 01 不会从“这是 ReAct 的定义”开始。

我们先解决一个更工程化的问题：

> **怎样把 Stage 00 的手写 Tool loop 拆成一个小而清楚、以后还能继续扩展的 Agent Runtime？**

这就是本阶段的主线。

---

## 我们继续使用同一个旅行助手

Stage 00 一直用“小型旅行助手”串联知识；Stage 01 不换题目。

假设用户现在问：

```text
课程里的东京模拟天气是多少摄氏度？
再换算成华氏度，并解释这个温度大概是什么体感。
```

应用提供两个 Tool：

```text
get_mock_weather(city)
celsius_to_fahrenheit(temperature_c)
```

一个合理的运行轨迹可能是：

```text
USER
  查询东京课程模拟天气，并换算成华氏度

MODEL ACTION
  get_mock_weather(city="Tokyo")

RUNTIME
  真正执行 Python Tool

OBSERVATION
  {"temperature_c": 18.0, "condition": "cloudy"}

MODEL ACTION
  celsius_to_fahrenheit(temperature_c=18.0)

RUNTIME
  真正执行 Python Tool

OBSERVATION
  64.4

MODEL
  东京课程模拟天气为 18°C，约 64.4°F……
```

Stage 00 的写法已经能把它跑通。

Stage 01 要做的是把这条轨迹拆成清楚的职责：

```text
                         AgentRuntime
                              │
                  ┌───────────┴───────────┐
                  │                       │
                  ▼                       ▼
              Model 接口              ToolRegistry
                  │                       │
                  ▼                       ▼
          Provider Adapter            Python Tool
                  │                       │
                  ▼                       ▼
          OpenAI / Qwen ...           Observation
                  │                       │
                  └───────────┬───────────┘
                              ▼
                         下一轮决策
```

真正需要理解的不是这些类名，而是：**为什么它们应该分开。**

---

## Stage 01 的六个连续问题

不要把四篇理论文档当成四份互不相干的说明书。它们是在依次解决下面的问题：

```text
01  Stage 00 已经有 Tool loop 了，为什么还需要 Agent Runtime？
        ↓
02  一个最小 Runtime 到底应该拥有哪些职责？
        ↓
03  如何让 Runtime 不依赖 OpenAI / Qwen 等模型提供商的具体对象？
        ↓
04  当模型连续调用 Tool 时，call_id、Observation、step 又如何串起来？
        ↓
05  怎样不用真实 LLM，也能确定性地测试 Runtime？
        ↓
06  这套最小 Runtime 到底哪里还不够生产可用？
        ↓
Stage 02：什么时候应该让模型决定路径，什么时候应该写确定性 Workflow？
```

读完以后，你应该不只是“知道有 `AgentRuntime` 这个类”，而是能解释：

> **如果删掉其中任何一层，会具体坏在哪里。**

---

## 先准备运行环境

Stage 01 有三种不同的运行方式，不要把它们混在一起。

### 1. 只看最小 Runtime：不需要网络

```bash
python stages/01-react-runtime/code/minimal_react_runtime.py
```

这里使用 `ScriptedTravelModel`，不调用真实 LLM。它的作用是让你先把 Runtime 控制流程看清楚。

### 2. 运行确定性单元测试

先安装开发依赖：

```bash
python -m pip install -e ".[dev]"
```

然后：

```bash
pytest -q tests/test_runtime.py tests/test_runtime_edges.py
```

### 3. 接入真实 OpenAI 模型

安装 OpenAI 依赖：

```bash
python -m pip install -e ".[openai]"
```

设置 API Key：

```bash
export OPENAI_API_KEY="你的 API Key"
```

PowerShell：

```powershell
$env:OPENAI_API_KEY="你的 API Key"
```

模型默认使用当前课程配置中的 `gpt-5.6-luna`，也可以覆盖：

```bash
export OPENAI_MODEL="gpt-5.6-luna"
```

然后运行：

```bash
python stages/01-react-runtime/code/openai_multi_tool_agent.py
```

这里要观察的重点不是“模型回答得像不像 ChatGPT”，而是 **同一个 Runtime 在换成真实模型以后，控制边界有没有保持不变**。

---

## 推荐学习顺序

### 第一步：先看清楚 loop 本身

阅读：

1. [01 — 从 Tool loop 到 ReAct Runtime](theory/01-react-and-agent-loop.zh-CN.md)

然后运行：

```bash
python stages/01-react-runtime/code/minimal_react_runtime.py
```

这里先不要接真实模型。

我们故意使用 `ScriptedTravelModel`，因为现在要观察的是 Runtime 的控制逻辑，而不是模型随机性。

你应该能看着输出解释：

```text
为什么第一轮会出现 ToolCall？
为什么 Tool 结果要成为 Observation？
为什么 Observation 必须进入下一轮？
为什么最终答案和 ToolCall 是两种不同的 Runtime 结果？
```

### 第二步：从一坨 `while` 代码里拆出架构

阅读：

2. [02 — 从手写 loop 到 Core Runtime Architecture](theory/02-runtime-architecture.zh-CN.md)

这一章会按代码出现的顺序解释：

```text
ToolCall / ModelResponse
        ↓
Model Protocol
        ↓
Tool / ToolRegistry
        ↓
AgentResult
        ↓
AgentRuntime.run()
```

然后对照真正的测试：

```bash
pytest -q tests/test_runtime.py tests/test_runtime_edges.py
```

这里第一次建立一个非常重要的工程习惯：

> **LLM 可以是随机的，但 Runtime 的控制规则应该尽可能接受确定性测试。**

### 第三步：把真实 OpenAI 接进来

阅读：

3. [03 — Provider Adapter：让 Runtime 不绑定某一家模型](theory/03-model-provider-adapter.zh-CN.md)

然后读：

```text
src/tiny_agent/types.py
src/tiny_agent/models/openai.py
```

最后运行真实示例：

```bash
python stages/01-react-runtime/code/openai_multi_tool_agent.py
```

这里真正要验证的不是“OpenAI 能调用成功”，而是：

```text
ScriptedTravelModel
        ↓ 替换成
OpenAIResponsesModel

AgentRuntime 不需要重写
ToolRegistry 不需要重写
Tool handler 不需要重写
```

这才说明 Stage 00 学到的 Adapter 思想真正进入了 Runtime 架构。

### 第四步：学习 Tool 接口为什么会影响 Agent 表现

阅读：

4. [Advanced — Tool / Agent-Computer Interface Design](advanced/tool-interface-design.zh-CN.md)

同一个 Python 函数，如果 Tool 名字、描述、参数 schema 写得模糊，模型就可能稳定地选错。

因此：

```text
Tool implementation 正确
!=
Tool interface 对 Agent 友好
```

### 第五步：主动看这版 Runtime 会在哪里失败

阅读：

5. [04 — 这版 Runtime 哪里还会坏？](theory/04-scope-and-production-limitations.zh-CN.md)

这一章不会用一句“生产环境还需要很多能力”草草带过，而会用具体失败场景说明：

```text
无限循环
非法参数
Tool 异常
权限
超时
重试
并发
Context / 状态
Tracing / Evaluation
```

哪些是 Stage 01 已经解决的，哪些是为了教学清晰而暂时没有加入。

### 第六步：通过练习把 Runtime 自己重新写一遍

最后完成：

6. [Stage 01 综合练习](exercises/review-questions.zh-CN.md)
7. [Provider Adapter 专项练习](exercises/provider-adapter-exercises.zh-CN.md)

不要只看答案。Stage 01 的结课标准是：**离开 Tiny-Agent 源码，你也能重新写出一个小型 Runtime。**

---

## 先记住一个核心边界

整个 Stage 01 最重要的关系可以压缩成一句话：

> **模型负责提出下一步；Runtime 负责决定这一步怎样进入真实世界。**

例如模型返回：

```text
get_mock_weather(city="Tokyo")
```

这只是一个提议。

后面至少还有：

```text
模型 ToolCall
    ↓
Runtime 解析
    ↓
ToolRegistry 查找
    ↓
参数边界检查（后续继续加强）
    ↓
Python handler 执行
    ↓
Observation
    ↓
Runtime 记录
    ↓
下一轮 model.generate(...)
```

模型没有偷偷伸出一只手去执行 Python。

如果这一点一直清楚，后面学权限、HITL、MCP、Sandbox、Multi-Agent 时会轻松很多。

---

## 为什么本阶段第一次认真讲 FakeModel？

很多初学者看到：

```python
class ScriptedModel:
    ...
```

会觉得：

> “我明明在学大模型，怎么又给我一个假的？”

其实 FakeModel 是理解 Agent Runtime 的利器。

假设我们想验证：

```text
Runtime 收到 ToolCall 后是否真的执行 Tool？
Observation 是否追加正确？
call_id 是否保留？
max_steps 是否能阻止死循环？
空 ModelResponse 是否会被拒绝？
```

这些都是**程序控制逻辑**。

如果每次测试都调用真实模型，那么测试结果同时受到：

```text
网络
API Key
模型采样
模型升级
服务故障
费用
```

影响。

这就像测试汽车刹车时，每次都先问一位随机司机“你今天想不想踩刹车”。

Stage 01 要建立的习惯是：

```text
Runtime 规则
    -> 确定性单元测试

真实 Agent 效果
    -> 真实模型集成测试 / Evaluation
```

两者都需要，但不要混成一件事。

---

## 教学快照和 `src/` 为什么不完全一样？

你会看到两个版本：

```text
stages/01-react-runtime/code/minimal_react_runtime.py
src/tiny_agent/runtime.py
```

它们不是重复代码。

前者是**教学快照**：

- 自包含；
- 一口气可以读完；
- 只保留这一阶段需要理解的机制；
- 每个设计都尽量在同一个文件里看见。

后者是**持续演化的项目实现**：

- Stage 07 已经给错误返回加上安全脱敏；
- 后续 Stage 又加入了更多异步、策略和集成能力；
- 它代表“学完整门课之后，这个 Runtime 会长成什么样”。

因此不要问：

> “为什么两份代码不是逐字一致？”

应该问：

> **哪一部分是 Stage 01 的核心不变量，哪一部分是后续 Stage 增加的工程能力？**

这正是 [04 — 这版 Runtime 哪里还会坏？](theory/04-scope-and-production-limitations.zh-CN.md) 要解决的问题。

---

## 完成本阶段后，你应该能自己画出这张图

```text
                    User Task
                       │
                       ▼
                ┌──────────────┐
                │ AgentRuntime │
                └──────┬───────┘
                       │
                normalized protocol
                       │
              ┌────────┴────────┐
              ▼                 ▼
        Model.generate()    ToolRegistry
              │                 │
              ▼                 ▼
      Provider Adapter       Tool handler
              │                 │
              ▼                 ▼
       OpenAI / Qwen ...    Observation
              │                 │
              └────────┬────────┘
                       ▼
                 Runtime state
                       │
                ┌──────┴──────┐
                ▼             ▼
             next step    final answer
```

并且能够解释每条箭头是谁负责的。

---

## Stage 01 的结课检查

如果下面这些问题还需要翻文档，建议不要急着进 Stage 02：

1. Tool Calling demo 和 Agent Runtime 的真正差别是什么？
2. 为什么 `Model.generate()` 应该只代表**一次模型决策**，而不是偷偷完成整个 Agent run？
3. `ToolCall.id` / provider `call_id` 为什么必须穿过 Tool 执行再回来？
4. 为什么 `ToolRegistry` 比 `if tool_name == ...` 更重要？
5. 为什么真实 OpenAI provider 接入后 `AgentRuntime` 不应该发生变化？
6. 为什么同一轮返回多个 ToolCall，不等于 Python Tool 已经并发执行？
7. 为什么 FakeModel 对 Agent 工程非常重要？
8. `max_steps` 能防什么，又防不了什么？
9. Stage 01 哪些设计是长期**架构原则**，哪些只是**教学简化**？
10. 为什么 Stage 02 还需要继续讨论 Agent 与 Workflow 的边界？

如果你能不用术语堆砌、而是结合代码把这些问题讲清楚，那么 Stage 01 才算真正学完。