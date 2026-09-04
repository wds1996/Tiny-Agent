# Stage 02：别让模型什么都决定——Workflow、Routing 与 Planning

> Language: [English](README.md) | **简体中文**

上一章我们终于把一个真正的 Agent Runtime 跑起来了。模型可以看当前运行记录，决定是调用 Tool 还是直接回答；Runtime 负责执行 Tool、记录 Observation，再把新的状态交还给模型。到这里，很多人会自然产生一个想法：

> 既然模型已经会决定下一步，那干脆以后所有“下一步”都让模型决定，不就完了？

这个想法很诱人，也很危险。它有点像刚招到一位聪明的新同事，就决定从明天开始让他顺便负责门禁、财务审批、服务器发布和午饭点什么。聪明不等于每件事都应该交给他决定。

这一章我们要解决的问题，正好是 Stage 01 留下来的下一层问题：**Runtime 已经能承载模型决策了，但哪些决策真的值得交给模型？哪些应该继续由普通代码牢牢掌握？**

这会带出三个非常常用的控制模式：Workflow、Routing 和 Planning。它们并不是三个孤零零的名词，而是同一个问题的三种答案：**我们到底把多少控制权交给模型？**

---

## 1. 先纠正一个常见误区：Agent 不是“把 if/else 删掉”

先看一个完全不需要模型参与控制的任务：

```python
weather = get_weather("Tokyo")
fahrenheit = celsius_to_fahrenheit(weather["temperature_c"])
return format_answer(weather, fahrenheit)
```

这里的顺序很清楚：先查天气，再换算温度，最后格式化答案。步骤固定、依赖固定、失败位置也很容易判断。你当然可以硬塞一个模型进来，让它每一步都回答“接下来应该查天气”“接下来应该换算温度”，但这不会让系统更聪明，只会让一个本来三行能解释清楚的流程，多出延迟、成本和不确定性。

这类流程就是 **Workflow（工作流）**。它的核心不是“有没有 LLM”，而是**主要控制路径是否由程序预先定义**。

这一点值得说得更彻底一些。假设一个工作流里有一步是：

```python
summary = model.generate(report)
```

它仍然可以是 Workflow。模型只负责这一小步内容生成，至于“什么时候调用模型、调用之后去哪里”，仍然由程序决定。

所以判断一个系统是不是 Agent，不要先看它有没有模型，也不要先看有没有 `while` 循环。先问一句：

> **下一步主要由谁决定？**

如果答案是“代码提前写好了”，它更接近 Workflow；如果答案是“模型会根据当前观察决定下一步动作”，才真正出现 Agentic control。

---

## 2. 那什么时候才值得把决定交给模型？

普通代码最擅长处理边界清楚、规则稳定的问题。比如请求以 `weather:` 开头，就交给天气处理器；请求以 `account:` 开头，就交给账户处理器。这种规则根本不需要模型参与：

```python
def rule_route(request: str) -> Route | None:
    normalized = request.strip().lower()

    if normalized.startswith("weather:"):
        return Route.WEATHER
    if normalized.startswith("account:"):
        return Route.ACCOUNT

    return None
```

如果输入已经给了明确、可靠的信号，直接 `if/else` 通常就是最好的方案。规则可测试、可预测，而且不会某天心情一变把 `weather:` 分到财务部。

问题出在自然语言。

用户可能不会老老实实写：

```text
account: duplicate charge
```

他更可能写：

> 我这个月的账单好像被扣了两次，我也不知道应该找谁。

这时要判断它属于账户问题，程序需要理解自然语言语义。你可以继续堆关键词：

```python
if "invoice" in text or "charged" in text or "billing" in text:
    ...
```

一开始很好用，后来规则会慢慢长成一棵灌木丛：`charged twice`、`double payment`、`refund`、`money taken again`……你会发现自己正在用字符串规则偷偷手写一个很差的语言理解模型。

这就是 **Routing（路由）** 最适合引入模型的地方：**程序已经知道有哪些合法分支，但无法可靠地只靠固定规则理解用户想走哪一条。**

---

## 3. Router 的工作不是“执行”，而是“选路”

我们先把 Router 的职责压到最小。

假设系统只有三条合法路线：

```python
class Route(str, Enum):
    WEATHER = "weather"
    ACCOUNT = "account"
    GENERAL = "general"
```

模型需要做的，只是从三个选项里选一个。它不应该直接调用数据库，也不应该返回一段“我建议你现在运行 `delete_account()`”之类的自由发挥。最稳妥的结果是一份结构化决策：

```python
class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Route
    reason: str = Field(min_length=1)
```

注意这里的设计和 Stage 00 的 Structured Output 是连起来的。模型负责一个语义判断，但这个判断最终要进入程序控制流，所以它应该变成**程序可以验证的数据**，而不是一段散文。

模型给出：

```json
{
  "route": "account",
  "reason": "The request is about a duplicate charge."
}
```

应用拿到结果以后，再执行普通代码：

```python
handler = HANDLERS[routing.route]
return handler(request)
```

这里有一个非常重要的分工：

```text
模型：
    “我判断它应该去 account。”

应用：
    “account 是允许的路线之一，我现在调用 account handler。”
```

模型做语义判断，应用做真实分发。**决策和执行仍然是两层。**

这个边界和 Stage 00 的 Tool Calling 其实是同一个思想，只是换了一个层级。Stage 00 是“模型提议调用哪个 Tool”；这里是“模型提议走哪个分支”。无论提议看起来多合理，真正改变程序控制流的动作仍然由应用完成。

---

## 4. 最实用的 Router，往往不是“所有请求都问模型”

现在我们再往前一步。

如果一个请求已经明确写着：

```text
weather: Tokyo
```

还要不要发一次模型请求，问它“请判断这是不是天气问题”？

没有必要。那就像快递箱上已经印着“上海”，分拣员还专门打电话问寄件人：“您这个是不是想寄到上海？”——流程很认真，效率很感人。

更合理的方式是**规则优先，语义判断兜底**：

```python
class HybridRouter:
    def __init__(self, semantic_router: SemanticRouter) -> None:
        self.semantic_router = semantic_router

    def route(self, request: str) -> RoutingResult:
        deterministic = rule_route(request)
        if deterministic is not None:
            return RoutingResult(
                route=deterministic,
                source="rule",
                reason="The request contains an explicit route prefix.",
            )

        decision = self.semantic_router.decide(request)
        return RoutingResult(
            route=decision.route,
            source="semantic",
            reason=decision.reason,
        )
```

这段代码背后的思路比代码本身更重要：**先使用最便宜、最确定、最容易解释的信号；只有当这些信号不足时，才让模型介入。**

运行离线示例：

```bash
python stages/02-workflows-routing-planning/code/routing.py
```

你会看到三类请求：一个带显式 `weather:` 前缀，直接被规则分流；一个自然语言账单问题，需要语义 Router 判断；一个普通改写请求进入通用路线。

示例里的 `ScriptedSemanticRouter` 是确定性的模型替身，它并不假装自己是大模型。我们先用它确认“路由机制本身”没问题，再在后面换成真实模型。这和 Stage 01 用 `ScriptedWeatherModel` 测 Runtime 是同一种测试思路：先把控制逻辑和模型随机性分开。

---

## 5. 为什么 Router 最好返回有限集合，而不是自由文本？

假设你让模型回答：

> 这个请求应该交给哪个模块？

然后得到：

```text
I think the billing support team should probably handle this.
```

人类当然看得懂，但程序又回到了 Stage 00 的老问题：接下来是找 `"billing"` 关键词吗？如果模型改成 `"account support"` 呢？

所以 Route 应该是有限集合：

```python
class Route(str, Enum):
    WEATHER = "weather"
    ACCOUNT = "account"
    GENERAL = "general"
```

这相当于告诉模型：“你可以帮忙判断，但只能从这三个门里选一个，不能临时在墙上画第四扇门。”

这类设计有两个好处。

第一，模型输出可以直接验证。如果它返回 `"finance_super_team"`，Pydantic 会拒绝，而不是让程序猜它大概是什么意思。

第二，应用仍然拥有可执行分支。模型不能因为输出了一个新字符串，就凭空创造一个新的系统能力。

所以 Router 的一个好原则是：

> **让模型处理语义模糊，让程序保存控制边界。**

---

## 6. Routing 解决的是“走哪条路”，Planning 解决的是“这条路怎么走”

Router 很适合从有限分支中选一个方向，但它不擅长表达一个多步骤任务。

比如：

> 读取东京的教学天气，把摄氏度换成华氏度，然后生成一句简短说明。

如果只有两个互斥模块，Router 当然可以选“天气”。但进了天气模块以后，任务还没结束。你还要决定：

1. 先从哪里读取天气；
2. 再把哪个结果交给温度换算；
3. 最后怎样把两份结果组合起来。

这时我们需要的是 **Planning（规划）**。

Planner 的工作，不是直接执行任务，而是把目标拆成一个程序可以检查的步骤序列。我们在示例里定义了四种允许的操作：

```python
class Operation(str, Enum):
    READ_PRIMARY_WEATHER = "read_primary_weather"
    READ_BACKUP_WEATHER = "read_backup_weather"
    CONVERT_TEMPERATURE = "convert_temperature"
    WRITE_BRIEF = "write_brief"
```

注意，Planner 仍然没有“想写什么函数就写什么函数”的自由。它只能从应用明确允许的 Operation 中组合计划。

这点非常重要。一个靠谱的 Planner 不是拿到键盘以后自由写 Python，而更像一个项目经理：它可以决定“先查主数据源，再换算，再生成摘要”，但真正能执行的动作集合，仍然由系统提前定义。

---

## 7. Plan 不是一段作文，它应该是可验证的数据

很多 Planning 示例喜欢让模型输出：

```text
1. First search for the weather.
2. Then convert the temperature.
3. Finally summarize the result.
```

拿来展示当然很直观，但如果接下来真要由程序执行，这种自然语言计划还不够。

程序至少需要知道：每一步叫什么、做什么、依赖谁。于是我们用一个结构化 `PlanStep`：

```python
class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1)
    operation: Operation
    depends_on: list[str] = Field(default_factory=list)
    city: Literal["Tokyo", "Paris"] | None = None
    source_step: str | None = None
    conversion_step: str | None = None
```

一个实际计划大概长这样：

```text
weather
    operation = read_primary_weather

convert
    operation = convert_temperature
    source_step = weather

brief
    operation = write_brief
    source_step = weather
    conversion_step = convert
```

这样一来，“先后关系”不再只存在于模型文字里，而是成为程序能检查的依赖。

例如 `convert` 引用了 `weather`，那 `weather` 必须已经在前面完成；`brief` 要同时引用天气结果和换算结果，这两步就都必须先存在。

---

## 8. 为什么 Plan 必须在执行前检查？

这里很容易出现一个危险的错觉：

> 既然 Plan 是模型生成的，那模型应该已经知道自己在干什么吧？

不要这么乐观。模型生成的 Plan 仍然是外部输入。

它可能返回重复的 step ID：

```text
weather
weather
brief
```

也可能让第一步依赖第三步：

```text
convert depends_on weather
weather comes later
```

这种计划像一个会议通知：“请大家先根据会议结论准备材料，会议结论将在两小时后讨论。”语法完全通顺，执行起来很有哲学意味。

所以 `Plan` 本身要做结构检查：

```python
class Plan(BaseModel):
    goal: str = Field(min_length=1)
    steps: list[PlanStep] = Field(min_length=1, max_length=5)
```

并且验证：

- `step_id` 不能重复；
- 依赖只能指向已经出现的步骤；
- `source_step`、`conversion_step` 不能引用未来结果；
- 计划长度有上限。

这里其实又重复了一次我们整门课已经见过的原则：

> **模型输出是候选数据，应用在使用之前要验证。**

Stage 00 用在 Structured Output 和 Tool Arguments 上，Stage 01 用在 ToolCall 和 ModelTurn 上，现在 Stage 02 用在 Plan 上。你会发现真正稳定的 Agent 系统，往往不是因为模型从不出错，而是因为每一层都清楚知道“我接下来准备信任什么”。

---

## 9. Planner 和 Executor 要分开

当 Plan 验证通过以后，谁来执行？

不是 Planner 自己。

我们把执行交给 `PlanExecutor`：

```python
class PlanExecutor:
    def execute(self, plan: Plan) -> str:
        results: dict[str, Any] = {}

        for index, step in enumerate(plan.steps, start=1):
            if index > self.max_execution_steps:
                raise RuntimeError("execution step budget exhausted")

            results[step.step_id] = self._execute_step(step, results)

        ...
```

Planner 和 Executor 的分工可以这样理解：

```text
Planner：
    “我建议按 weather → convert → brief 执行。”

Executor：
    “我先检查这个计划是否合法，然后按允许的 Operation 真正执行。”
```

这和 Tool Calling 的边界非常相似。Planner 负责产生“怎么做”的建议；Executor 才拥有“真的做”的权限。

为什么要分开？因为一旦把两者揉在一起，你很难回答这些问题：

- 计划是否合法，是谁检查的？
- 某一步到底执行了几次？
- 模型能不能随手发明一个新操作？
- 计划说要执行五十步时，谁负责拒绝？
- 某一步失败后，是继续、结束还是重新规划？

这些都不应该靠“Planner 大概会处理好”来回答。

---

## 10. 计划中的结果从哪里来？

`PlanExecutor` 维护了一个很朴素的字典：

```python
results: dict[str, Any] = {}
```

每一步完成后，结果按 `step_id` 保存：

```python
results[step.step_id] = self._execute_step(step, results)
```

后续步骤再通过引用拿到前面的结果。

例如温度换算步骤：

```python
weather = results[step.source_step]
temperature_c = float(weather["temperature_c"])
return {"temperature_f": round(temperature_c * 9 / 5 + 32, 1)}
```

这说明 Plan 不是单纯的“任务清单”，它还是一个依赖关系。

```text
weather 产生数据
      ↓
convert 消费 weather
      ↓
brief 同时消费 weather 和 convert
```

如果把 Plan 想成菜谱，`depends_on` 不是“步骤编号好看一点”，而是在说：“面粉还没和好之前，先别把面包送进烤箱。”

这一章暂时用普通字典保存运行结果，已经足够看清依赖关系。等控制流程出现分支、循环和更复杂状态时，我们才需要更明确的状态编排方式。

---

## 11. Planning 并不意味着“一次计划永远正确”

计划验证通过，只能说明它在结构上能执行；现实世界仍然可能让它失败。

示例里，我们故意安排了一个非常普通的故障：主天气源不可用。

第一次计划是：

```text
weather = read_primary_weather
convert = convert_temperature(weather)
brief   = write_brief(weather, convert)
```

执行第一步时，Executor 得到：

```text
primary teaching weather source is unavailable
```

这时有两种极端做法都不理想。

第一种是“计划失败就彻底崩掉”，哪怕系统明明有备用源。第二种是“让模型无限重新想办法”，直到它自己满意为止。后者听起来很 Agent，实际可能只是把错误变成一个会循环的错误。

更稳妥的做法是 **bounded replanning（有界重新规划）**：只有观察到执行失败以后，才允许 Planner 根据这个新事实重新生成计划，而且重新规划次数由应用限制。

```python
for attempt in range(max_replans + 1):
    plan = planner.make_plan(task, failure=failure)

    try:
        return executor.execute(plan)
    except StepFailure as exc:
        failure = exc
        if attempt == max_replans:
            raise
```

第一次失败以后，`ScriptedPlanner` 会把主数据源替换成备用数据源：

```text
read_primary_weather
        ↓ failure
read_backup_weather
        ↓
convert_temperature
        ↓
write_brief
```

运行：

```bash
python stages/02-workflows-routing-planning/code/planning.py
```

你会看到两次 Plan attempt。第一次在天气读取处失败，第二次使用备用源并得到：

```text
Tokyo: 18.0°C / 64.4°F, cloudy.
```

这里最值得注意的不是“模型会反思”，而是另一件更工程化的事：

> **重新规划是由新的 Observation 触发的控制动作，而且它有明确次数上限。**

---

## 12. Replanning 和 Retry 不是一回事

这两个词很容易混。

Retry 通常表示：**同一个动作再做一次。**

```text
调用 primary weather
失败
再调用 primary weather
```

Replanning 表示：**根据新的观察修改后续方案。**

```text
调用 primary weather
失败
改计划：使用 backup weather
```

我们这章做的是后者。

这一区分非常实际。如果某一步是“读取数据”，重复执行往往问题不大；如果某一步是“扣款”或“发送邮件”，重复执行的代价就完全不同。Stage 02 暂时不展开副作用和重试策略，只需要把控制语义分清：**重新规划不是把原动作偷偷再执行一次。**

---

## 13. 为什么一定要有 Budget？

一旦 Planner 能生成步骤、还能 Replan，系统就拥有了“继续想办法”的能力。听起来很美好，但任何能“继续”的机制都应该问一句：

> 最多继续多久？

示例里有三层很简单的边界。

Plan 自己限制长度：

```python
steps: list[PlanStep] = Field(min_length=1, max_length=5)
```

Executor 限制最多执行多少步：

```python
if index > self.max_execution_steps:
    raise RuntimeError("execution step budget exhausted")
```

控制器限制最多重新规划多少次：

```python
for attempt in range(max_replans + 1):
    ...
```

这三种 Budget 管的是不同东西：计划有多长、实际执行多少步、失败后最多改几次计划。不要用一个模糊的 `max_iterations` 试图解释所有边界，否则出问题时你会不知道“到底是什么耗尽了”。

Budget 的价值也不只是省钱。它首先是在定义系统行为：**即使模型一直认为“我还能再想想”，应用也有权说到此为止。**

---

## 14. 接入真实模型时，控制结构不需要改

到目前为止，我们故意使用 `ScriptedSemanticRouter` 和 `ScriptedPlanner`。它们没有语言理解能力，只是为了把控制逻辑跑得可重复。

真正接入模型时，我们只替换“做语义判断”的部分，不改 Hybrid Router，不改 PlanExecutor，也不改 Budget。

运行真实示例前设置：

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="your-model-id"
python stages/02-workflows-routing-planning/code/openai_decisions.py
```

Router 使用 Structured Output：

```python
response = self.client.responses.parse(
    model=self.model,
    instructions=(
        "Classify the user's request into exactly one route. "
        "weather: weather or forecast questions. "
        "account: invoices, billing, refunds, or account records. "
        "general: everything else."
    ),
    input=request,
    text_format=RouteDecision,
)
```

Planner 同样返回结构化 `Plan`：

```python
response = self.client.responses.parse(
    model=self.model,
    instructions=(
        "Create a short executable plan using only these operations: ..."
    ),
    input=f"Task: {task}\n{failure_text}",
    text_format=Plan,
)
```

这就是 Provider Adapter 在本章最重要的意义：模型负责语义工作，但核心控制代码只认识 `RouteDecision` 和 `Plan`。

换句话说，我们不是让 OpenAI Response 对象一路渗透到业务控制逻辑，而是尽快把它翻译成应用自己的数据结构。

---

## 15. Workflow、Router、Planner、Agent Runtime 到底怎么选？

学到这里，最容易出现的新问题是：“这么多模式，我到底用哪个？”

不要按“哪个听起来更高级”选。按任务中真正存在的不确定性选。

| 情况 | 更合适的控制方式 |
|---|---|
| 步骤和顺序都稳定 | 确定性 Workflow |
| 路径有限，但自然语言决定走哪条 | Router |
| 目标明确，但需要先拆成多个依赖步骤 | Planner + Executor |
| 下一步必须根据每轮 Observation 动态决定 | Agent Runtime |

举个例子。

“每天 9 点读取固定报表，再生成摘要”通常是 Workflow。
“用户的问题属于退款、天气还是通用咨询”适合 Router。
“先规划需要查哪些资料，再按依赖执行多个步骤”适合 Planner。
“查了一步以后，下一步完全取决于刚得到的内容”更接近 Agent Runtime。

现实系统也可以组合这些模式，但组合之前先把每一种单独想清楚。不要一看到任务复杂，就把所有东西塞进一个“万能 Agent”。万能通常只是“所有责任都混在一起”的礼貌说法。

---

## 16. 一个成熟的控制策略，往往是“能不用模型就不用”

现在回头看这一章，真正想建立的不是三种设计模式，而是一种判断习惯：

如果规则已经确定，就写规则。
如果只有语义分类不确定，就让模型只做分类。
如果任务需要拆解，就让模型提出受约束的 Plan。
如果下一步真的必须随着 Observation 动态变化，再让 Runtime 把这个决策权交给模型。

这不是保守，而是把模型放在它真正有优势的位置：处理语义、不完整信息和开放式判断；把可验证、可重复、边界明确的控制逻辑留给普通程序。

一个好 Agent 系统通常不是“模型控制最多”的系统，而是“模型只控制必须由模型判断的那部分”的系统。

---

## 17. 运行本章检查

这章的离线检查不需要 API Key：

```bash
python stages/02-workflows-routing-planning/code/checks.py
```

它验证了几个关键边界：显式路由规则不会多余地调用语义 Router；自然语言请求会进入语义判断；Route 决定以后由普通代码完成 Dispatch；Plan 会拒绝未来依赖和重复 ID；关闭 Replanning 时失败会直接结束；只允许一次 Replan 时可以从主源失败切换到备用源；执行步数 Budget 由应用强制执行。

真正值得你看的是失败用例。成功路径只能证明“它能跑一次”，失败用例才在说明“它不会偷偷做什么”。

---

## 18. 动手练习

先改 `routing.py`。给系统增加一个 `DOCUMENT` Route，并设计一个**可靠的确定性信号**，让某些请求不必经过语义 Router。然后再写一句没有显式标记的自然语言，让 Semantic Router 决定是否进入文档路线。做完以后问自己：哪些规则应该硬编码，哪些规则开始变成了脆弱的关键词堆砌？

接着改 `planning.py`。增加一个 `CHECK_UNIT` Operation，放在温度换算之前。要求 Planner 生成的计划必须先确认天气温度单位是 Celsius，再允许转换。不要修改 `PlanExecutor.execute()` 的整体循环，只增加新的受控操作。如果你为了加一个操作不得不把 Executor 的主循环推倒重写，说明抽象还不够稳定。

然后故意写一个坏 Plan，让 `brief` 引用一个不存在的步骤。不要先改验证器，先观察 Pydantic 在哪里拒绝它，再解释为什么这个错误应该在执行前发现。

最后把 `max_replans` 改成 `0`、`1`、`2` 分别运行。你会发现“允许更多 Replan”并不自动提高结果质量，只是扩大了系统继续尝试的空间。控制空间越大，边界就越重要。

---

## 19. 本章收尾：Runtime 会循环，还不等于系统已经会编排

Stage 01 解决了“怎样让模型根据 Observation 一轮一轮决定下一步”。Stage 02 又往前走了一步：我们开始主动设计**哪些决定由模型做，哪些由程序做**。

现在我们已经有了四种控制手段：

```text
固定 Workflow
语义 Router
Planner + Executor
Agent Runtime
```

它们都能处理多步骤任务，但表达复杂控制流时，我们仍然主要靠 Python 函数、局部变量和循环。只要流程再多一些分支、条件和中间状态，代码会开始变得难以看清“现在到底走到哪一步了”。

下一章就从这个问题开始：把运行中的状态和状态转移明确写出来。

➡️ [Stage 03：显式 State 与 Stateful Orchestration](../03-stateful-orchestration/README.zh-CN.md)
