# Stage 02：页面已经有开关，还要每一步都问模型吗？——工作流、路由与规划

> Language: [English](README.md) | **简体中文**

[上一章](../01-react-runtime/README.zh-CN.md)，小林的出行练习页面已经能先查 Tokyo 的教学天气，再把 18°C 换算成 64.4°F。模型根据刚拿到的结果提出下一步，运行时检查、执行，再把结果送回去。小林看完却提出一个很实在的问题：“页面上已经有‘同时显示华氏度’的开关了。用户勾上就换算，没勾就不换算，为什么还要问模型？”

这个问题没有推翻上一章的循环。会让模型选择，和每个选择都需要模型，是两回事。就像请了一位懂外语的同事，并不意味着电梯每到一层，都要请他翻译一下按钮上的数字。已经明确的事情，程序自己办，往往更合适。

这一章继续做小林的页面。先把开关交给普通代码处理；等页面增加文字输入，再让模型理解用户的表达；等用户希望先看一份两城简报的处理方案，再把步骤写成可检查的计划。中途我们会让一个数据源出故障，看看哪些结果可以保留、后面怎样改。所有天气数值来自本地固定记录，只有最后的 DeepSeek 入口会使用真实模型服务。

## 1. 开关已经告诉我们的事情，就不必再猜

先替小林按一次页面上的按钮：城市选择 Tokyo，勾选“显示华氏度”。此时程序已经知道要查谁、要不要换算。它不知道的是天气记录里的数值，而不是执行顺序。因此，最直接的做法就是读取记录，按开关决定是否换算，最后排成一段文字。

这里把城市、单位选项和输出语言放进一张 `WeatherTask` 任务单。`cities=("Tokyo",)` 表示只查一座城市，括号里的逗号让它成为一个元组；`fahrenheit=True` 表示同时显示华氏度。任务单使用前两章学过的 Pydantic 检查，只接受 Tokyo、Paris，不允许重复城市，也不把字符串 `"false"` 当成布尔开关。

看 [`workflow.py`](code/workflow.py) 中真正工作的这一小段：

```python
def run_workflow(task: WeatherTask, service: WeatherService) -> str:
    task = WeatherTask.model_validate(task)
    readings = []
    for city in task.cities:
        reading = service.read(city)
        if task.fahrenheit:
            reading = convert_temperature(reading)
        readings.append(reading)
    return render_brief(task, tuple(readings))
```

`service.read()` 读取固定记录，`convert_temperature()` 计算华氏度，`render_brief()` 根据实际结果组织文字。`reading` 始终携带城市、摄氏温度、天气状况和数据来源；换算只是增加一个华氏温度，不会把原始记录覆盖掉。这里的 `if` 不是一个需要被 Agent 淘汰的旧技术，它恰好表达了小林的产品规则。

这样一条由应用预先规定主要路线的处理过程，叫作 **Workflow（工作流）**。它可以有分支，也可以在某一步调用模型润色文字；是否用了模型，不是区分工作流与 Agent 循环的唯一标准。关键是，下一步的路线主要由固定代码决定，还是需要模型结合新信息决定。[工作流与 Agent 的设计讨论](https://www.anthropic.com/engineering/building-effective-agents)也强调先从满足需求的简单结构开始。

使用 Python 3.10 或更新版本，在仓库根目录安装本章依赖，再执行这条固定流程：

```bash
python -m pip install -r stages/02-workflows-routing-planning/code/requirements.txt
python stages/02-workflows-routing-planning/code/workflow.py --fahrenheit
```

结果包含 `Tokyo: 18.0°C / 64.4°F`，同时显示 `model calls: 0`。去掉 `--fahrenheit` 再运行，结果就只包含摄氏温度，不会先调用换算函数再把华氏度藏起来。`--cities Paris` 会读取 Paris；`--cities Tokyo Paris` 会处理两座城市并比较温度。它们都不需要语言理解。

开关这条路线已经清楚了。不过，小林随后加了一个输入框。有些用户不想找按钮，只想说一句“读一下东京的教学天气，顺便给我华氏度”。程序这回需要理解的，才真正是语言。

## 2. 加了输入框以后，先弄清用户要去哪一条路线

同一个页面可能收到三种很不同的话：“看一下东京的教学天气”“比较东京和巴黎”“这个页面能做什么”。还有一种更麻烦：“那里现在冷不冷？”最后一句既没有明确城市，又可能在问实时天气，而我们的页面只提供教学记录。

先不用想一个全能模型。页面已有几种处理能力，我们只是需要判断用户想使用哪一种；条件不足时先问清楚，而不是随手挑 Tokyo，热情地回答错问题。这种**从已知目的地中选一个**的工作，就是 **Routing（路由）**。负责提出选择的组件叫 Router，真正进入对应函数仍然是应用的工作。

我们约定四个目的地，名称只是给程序识别用的：

| 目的地 | 页面接下来做什么 |
| --- | --- |
| `weather` | 读取一座明确城市的教学记录，可按要求换算 |
| `compare` | 读取两座城市并比较，可同时显示华氏度 |
| `help` | 解释页面能力，不查询天气 |
| `clarify` | 要求补充或调整请求，不查询天气 |

`clarify` 不是故障逃生口。用户确实没说清楚，或者要求本系统没有的实时天气时，澄清本来就是正确的下一步。反过来，模型响应无法解析，不应伪装成“用户没说清楚”；那是另一类错误。

上一章的工具调用已经告诉我们，不能靠一句“我感觉可以查天气”驱动代码。选路也一样，要交回一张结构化任务单。在 [`routing.py`](code/routing.py) 中，主要字段是：

```python
class RouteDecision(Contract):
    route: Literal["weather", "compare", "help", "clarify"]
    cities: tuple[City, ...] = Field(default=(), max_length=2)
    fahrenheit: bool = False
    reason: str = Field(min_length=1, max_length=300)
```

`Literal` 限定目的地，`cities` 携带从请求识别出的城市，`fahrenheit` 携带单位要求。`reason` 用来解释这次分类，不是交给后续代码执行的新指令。比如 `compare` 对应两个不同城市；`weather` 对应一个；`help` 和 `clarify` 则不应该偷偷夹带查询城市。

`Contract` 是本章几类任务单共同使用的 Pydantic 配置：拒绝额外字段，严格检查类型，并在进入边界时重新验证实例。各个任务单自己的验证函数再检查字段之间的关系。可以把前者理解成检查表格栏目，后者理解成检查“勾了两城对照，是否真的填了两座城”。[Pydantic 的模型说明](https://docs.pydantic.dev/latest/concepts/models/)介绍了字段验证和实例重新验证的区别。

不过，页面还有原来的下拉框和开关。它们已经给出明确字段，不应该因为增加了输入框，所有请求就都绕道模型服务。

## 3. 能走表单就走表单，只有自由文字才请模型解释

我们把两个入口分清楚。表单入口接收经过验证的 `WeatherTask`；文字入口接收用户的一段话。一次请求只能选其中一个，不能同时给出“表单是 Tokyo、文字是 Paris”，再让代码暗中决定听谁的。无论从哪里来，非法输入都应该明确报错，不能在表单校验失败后自动送给模型“修一下”。

组合规则与模型的做法通常叫 **Hybrid Router（混合路由器）**。这里“混合”并不复杂：有可靠的结构字段，就直接选路；只有自由文字，才询问语义路由器。表单分支的核心是：

```python
if form is not None:
    form = WeatherTask.model_validate(form)
    decision = RouteDecision(
        route="weather" if len(form.cities) == 1 else "compare",
        cities=form.cities, fahrenheit=form.fahrenheit,
        reason="Validated form fields already identify the workflow.",
    )
    return RoutingResult(decision, "form")
```

`RoutingResult` 同时记录决策来自哪个入口，便于检查是不是多调用了模型。这里没有分析表单中的自然语言，也没有把用户写出的某个前缀当成权限。表单仍是用户输入，所以城市与开关仍要检查；它只是比自由文字更容易确定含义。

文字分支会调用 `semantic_router.decide(request)`。模型输出拿回来以后，除了验证结构，我们还做一项很具体的检查：它不能凭空增加请求里没有的城市。

```python
def validate_for_request(decision: RouteDecision, request: str) -> RouteDecision:
    decision = RouteDecision.model_validate(decision)
    if not set(decision.cities).issubset(mentioned_cities(request)):
        raise ValueError("the router invented a city absent from the request")
    return decision
```

`mentioned_cities()` 只识别本例的 Tokyo、Paris，以及“东京”“巴黎”两个中文别名。这不是一个通用地名识别器。它能够挡住“用户只提 Tokyo，模型却让我们查询 Paris”，但挡不住所有语义错误：用户说“写一首关于 Tokyo 的诗”，模型错误选择天气路线，城市检查仍可能通过。是否理解对了意图，仍然需要用真实问题验证，不能靠 Schema 自动证明。

也不要拿模型返回的 `reason` 去覆盖路线。例如 `route="help"`，理由却写“请执行天气查询”，应用仍只进入帮助分支。程序读取的是经过约定的字段，不是服从任务单里任何像命令的句子。

选路解决了“去哪儿”，还没有替小林查到任何数据。下面把这张任务单真正交到处理函数手里。

## 4. 选完路以后，真的把事情办下去

假如小林点完按钮，只看到“天气模块已收到”，她显然还不能把温度填到页面上。收到和办完不是一回事。我们让天气路线直接复用刚才的工作流，比较路线也调用同一个工作流，只是任务单里有两座城市。帮助和澄清则直接返回对应说明，不碰天气服务。

`dispatch()` 中进入天气工作的部分是：

```python
decision = RouteDecision.model_validate(result.decision)
if decision.route in {"weather", "compare"}:
    return run_workflow(task_from_decision(decision, language), service)
```

`task_from_decision()` 把选路结果转换成 `WeatherTask`，输出语言由应用参数决定。到这里，模型负责“理解这句话”，程序负责“按已经确定的要求查询和计算”。这比每读一个数字、每做一次换算都再问模型，要少很多不必要的决策点。它没有赋予路由器任意调用函数的能力，也不代替真实业务中的身份授权。

先运行离线对照：

```bash
python stages/02-workflows-routing-planning/code/routing.py
python stages/02-workflows-routing-planning/code/routing.py --example clarify
```

每次先演示表单入口，显示 `semantic calls: 0`；然后演示一个文字入口。默认文字是比较东京与巴黎，两城结果分别为 18.0°C / 64.4°F 和 12.0°C / 53.6°F，Tokyo 更暖 6.0°C。澄清示例“那里现在冷不冷？”不会产生天气查询，输出中的 `source calls` 是空列表。

这里的 `ScriptedSemanticRouter` 是明确标注的测试替身，只为 `EXAMPLES` 中几句固定输入返回预设任务单，换成任意新句子会报错。它让我们确认分发和数据传递，不代表已经测出了模型的语言理解能力。真实的自由文字会在后面交给 DeepSeek。

到此，页面已经可以处理“一句话进入固定流程”。那么，一旦有多个步骤，是不是必须升级成 Planner？还不是。刚才的工作流已经能查询两城、换算和比较，路由器当然也可以把用户交给一个多步骤工作流。规划的价值要从另一个需求说起。

## 5. 小林想先看看这次准备怎么做

小林准备给页面增加一个“先看方案”的演示模式。她希望先看到这一次打算查哪些城市、做哪些换算，再执行。以后步骤变了，也能看见变化发生在哪里，而不是在一长串模型往返里寻找答案。

这时我们把“安排工作”和“实际工作”分开：先得到一张步骤单，检查它能否完成当前任务，再逐项执行。这种提出步骤和依赖的过程，叫作 **Planning（规划）**。提出方案的是 Planner，照着允许的方案办事的是 Executor，也就是执行器。

先用人的语言给两城华氏简报安排一次：读取 Tokyo，读取 Paris，分别换算，最后比较并组织文字。两个读取之间没有数据依赖，谁先查都行；每次换算却必须等对应读取完成。我们不能先把“将来可能查到的温度”放进计算器。

```text
weather_tokyo      读取 Tokyo
weather_paris      读取 Paris
fahrenheit_tokyo   使用 weather_tokyo 的结果换算
fahrenheit_paris   使用 weather_paris 的结果换算
brief              使用两份换算后的记录生成比较简报
```

左侧是步骤编号，不是温度值。右侧说明工作和输入来源。对于这道小题，普通代码也完全能生成这样的清单；`ScriptedPlanner` 就会这样做。我们让真实模型生成清单，是为了学习如何接住一份模型方案，不是在证明这道固定天气题必须花一次模型调用才做得好。

与上一章逐轮决定相比，计划式执行让一段工作在执行前就可检查。代价是计划建立在一些假设上，例如数据源可用。我们稍后会亲手打破这个假设。先把步骤单写成程序能读、也能拒绝的形式。

## 6. 计划里填的是结果引用，不是猜出来的结果

如果计划只写“第一步查天气，第二步算一下”，人能理解，执行器却不知道该把哪份记录交给哪次换算。于是每一步需要名字、允许的操作，以及输入来自哪里。`PlanStep` 的字段是：

```python
class PlanStep(Contract):
    step_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    operation: Literal["read_weather", "convert_temperature", "write_brief"]
    inputs: tuple[str, ...] = Field(default=(), max_length=2)
    city: City | None = None
    source: Source | None = None
```

`step_id` 是本次方案内的编号，限制为简单字符，便于引用。`operation` 只能从三个已实现的操作中选。`inputs` 是前面步骤结果的编号；对于读取，它为空，读取使用 `city` 和 `source`；对于换算，它只有一个元素；对于最后的简报，它包含每座城市要使用的最终记录。

本例有 `primary` 和 `backup` 两个读取入口，都通向同一份 `teaching-v1` 固定资料。先把 `source` 理解成“去哪个柜台取资料”，而不是天气发生的时间。正常方案先用主入口，备用入口的使用条件由应用规定，并非模型随便选。

例如这一步只说“换算刚才查到的 Tokyo”，没有填入一个臆测的 18：

```python
PlanStep(
    step_id="fahrenheit_tokyo",
    operation="convert_temperature",
    inputs=("weather_tokyo",),
)
```

真正的数值要等 `weather_tokyo` 执行完成后再读取。这样，即使教学记录改为 22°C，计划仍然可以不变，换算结果却应该变成 71.6°F。计划描述依赖，数据来自执行，两者不再混在一句“我预计是 18 度”里。

整张 `Plan` 还带一个简短的 `goal` 和最多五个步骤。`goal` 方便人看，但不能改写原始任务。模型把它写成“只查一座城”也不能让两城任务少查一座。真正验收用的是应用已经确认的 `WeatherTask`。下一节就把这些要求变成执行前的检查。

## 7. 执行前先检查整张清单，别干到一半才发现它缺了一页

小林问：“既然有了 Pydantic，不是已经验证过了吗？”它已经帮我们检查字段、类型、有限选项和每种操作的参数形状，但“这一份计划能否完成这一次任务”还需要应用判断。

最简单的坏方案是先换算、后查询。即使两步都写得很像样，换算开始时仍然拿不到输入。我们用一个 `known` 表记住当前已经完成、或在这张清单前面会产生的结果。走到某一步，它的所有引用必须已经在表里：

```python
if step.step_id in known:
    raise PlanRejected("a new step cannot overwrite a completed result")
if not set(step.inputs).issubset(known):
    raise PlanRejected("an input refers to a missing or future result")
```

这里检查的是**整张计划的顺序**，还没有读取天气。检查过程中只推演“哪一步会产生哪类结果”，不制造真实温度。依赖只能向前面找，自己依赖自己、两步互相等待都会被拒绝。这种把生产者放在消费者前面的安排，常叫拓扑顺序；本章不需要图框架，按顺序检查一张短清单就够了。

光有引用还不够。`known` 同时记住结果属于哪个城市、是否已经包含华氏度。于是我们可以拒绝重复换算、把别的城市混进来，以及最后交付错误单位。简报步骤的检查是：

```python
products = [known[key] for key in step.inputs]
expected = {(city, task.fahrenheit) for city in task.cities}
if len(products) != len(expected) or set(products) != expected:
    raise PlanRejected("the brief omits a city or has the wrong units")
```

比如任务要求 Tokyo 与 Paris 都有华氏度，`expected` 就需要两项对应的结果，不能用两个 Tokyo，也不能只交一份 Tokyo，再写一句“Paris 应该也差不多”。`write_brief` 必须在最后；没有最终简报的计划也不完整。

这些关系由 [`validate_plan()`](code/planning.py) 检查，执行器在做任何操作前调用它。因此，哪怕计划前四步看起来都正确，最后一步漏了 Paris，第一条查询也不会先跑。模型可以给独立步骤安排不同顺序，但不能改变必需的输入和交付内容。

当然，一张依赖正确的清单仍可能碰到服务故障。验证保证的是列明的结构与任务约束，不是给外部世界签发“今天绝不出问题”的证明。先按正常顺序执行，我们才有地方记录现实发生了什么。

## 8. 执行器按编号保存结果，再把结果交给下一步

现在轮到执行器干活。它不再向模型询问“第一步是什么意思”，而是根据 `operation` 进入应用写好的分支。每个读取或换算完成后，用 `step_id` 保存结果。模型没有机会通过计划填写这个结果表，更不能把 `temperature_c=99` 夹进换算步骤。

[`PlanExecutor`](code/planning.py) 的两个数据处理分支如下：

```python
if step.operation == "read_weather":
    return self.service.read(step.city, step.source)
if step.operation == "convert_temperature":
    return convert_temperature(results[step.inputs[0]])
```

第一行查记录，第二条分支使用前面保存的 `Reading`。`Reading` 保留城市、摄氏度、天气状况、来源和资料版本；换算函数返回增加了华氏度的新记录。最后的 `write_brief` 取得计划引用的记录，再交给与固定工作流相同的 `render_brief()`，所以两种组织方式的计算口径一致。

本章的简报文字也由固定格式器产生。这样可以直观看见数值有没有沿着依赖传递，不把“规划是否正确”与“模型最后一句是否措辞准确”混成一项检查。格式器还会核对交付城市、单位与资料版本。它能检查这些明确条件，但不会证明真实数据源的内容一定可信。

先运行没有故障的版本：

```bash
python stages/02-workflows-routing-planning/code/planning.py --failure none
```

程序先生成并检查五步方案，再执行五个步骤。终端在运行结束后统一打印保存的方案与执行记录，不提供人工点击确认的界面；程序执行前的计划检查与人工审批不是一回事。最终结果与表单工作流一致：Tokyo 为 18.0°C / 64.4°F，Paris 为 12.0°C / 53.6°F，温差 6.0°C。这里是顺序执行，没有并发；两个读取互不依赖，只表示它们可以交换先后，并不等于 Python 已经同时启动它们。

记住计划清单与执行记录的区别：清单上写了五步，不代表五步全都发生。下面我们故意让第二步拿不到资料，看看程序是否还敢说简报已经完成。

## 9. Tokyo 已经查到，Paris 的柜台却关门了

默认故障演示会让 `primary/Paris` 不可用，Tokyo 仍然可查。这个位置是有意选择的：第一步已经完成，第二步失败，比“什么都没做就失败”更能说明哪些结果该保留。

```bash
python stages/02-workflows-routing-planning/code/planning.py
```

第一份方案执行到 Paris 就停止。此时，结果表里只有 `weather_tokyo`；调用记录中既有一次成功读取，也有一次失败读取。换算和简报虽然列在方案上，却都没有执行。我们不能因为“计划里有 Paris”就假装已经得到 Paris 的温度。

应用把这次可识别的失败记成一个小对象：

```python
@dataclass(frozen=True)
class Failure:
    step_id: str
    city: str
    source: str
    code: str = "source_unavailable"
```

这份对象说明哪个读取失败、哪个城市受影响、哪个入口不可用。它来自执行器捕获的 `SourceUnavailable`，不是模型写一句“主源好像坏了”就能伪造的触发条件。一般的参数错误、代码异常或不合格计划，不会被一概当成换数据源的理由。

在我们的固定资料里，备用入口提供的是**同一份教学快照**，所以两城仍有可比的口径。真实业务更换来源时，还要判断时间、单位、覆盖范围和访问条件；“备用”两个字并不保证数据新鲜或者同样可靠。这里没有联网调用两家气象服务，也不因此声称系统已经具有真实容灾能力。

现在事实变了：Tokyo 已经在手里，Paris 的主入口不可用，仍缺 Paris 和两次换算。把这些事实一起交回去，才有可能得到有意义的新方案。

## 10. 改后半段的方案，不把前半段的工作抹掉

收到失败后重新安排后续工作，叫作 **Replanning（重新规划）**。它不是在失败之后对模型说“再努力一点”，而是提供新的执行事实，并要求新的计划仍然服务于同一个目标。

控制器调用规划器时会携带原任务、已完成结果和失败记录：

```python
plan = planner.make_plan(task, completed=dict(run.completed), failures=tuple(run.failures))
plan = validate_plan(plan, task, run.completed, tuple(run.failures))
run.plans.append(plan)
```

规划器拿到的是结果表的副本，其中 `Reading` 是不可变的数据记录。它能够引用 `weather_tokyo`，但不能把应用保存的 18.0 改成另一个数。这里防止的是正常接口意外改写共享数据，不是把同进程 Python 代码放进了安全沙箱。

新的合法清单可以是：

```text
weather_paris      从 backup 读取 Paris
fahrenheit_tokyo   使用已完成的 weather_tokyo
fahrenheit_paris   使用刚完成的 weather_paris
brief              使用两份换算记录
```

这次 Tokyo 不再查询，已有结果编号不能被覆盖，换一个新编号重复查询同一城市也会被拒绝。失败的 `weather_paris` 没有成功结果，所以可以在新计划中继续使用这个步骤名。它与上一章的调用编号不是同一个概念；执行记录还带有计划轮次，两次尝试不会混成一次成功。

应用也会拒绝再次选择已经观察到不可用的入口；只有对应城市的主入口实际失败后，才允许该城市使用备用入口。模型不能因为偏爱“backup”这个名字，就绕过这条规则。如果它交回的计划不合法，本次运行结束，不会无限请它改格式。

由此也能分清两个容易混淆的动作：重复读取 `primary/Paris` 是 **Retry（重试）**；改成 `backup/Paris` 并继续未完成工作，是本例的重新规划。如果只有这一条固定的备用规则，普通异常处理同样能完成，未必需要模型。这里保留 Planner，是为了观察“方案是数据，执行结果可以改变后续方案”的机制。

本例只保留当前进程中已经完成的只读结果。如果计划中有付款或发送邮件，不能照搬“重新跑一遍”的办法；如果进程退出，内存记录也不会自动恢复。先明确这段代码做到了什么，不要把一次顺利接着查资料解释成所有长任务都已可靠。

方案可以改了，下一件事就必须说清楚：到底允许改几次、总共允许干多少步？

## 11. 重新规划不能顺便领取一份全新的预算

默认第一次执行了两步：Tokyo 成功，Paris 失败。新方案执行四步：备用读取、两次换算、生成简报。合计是 **六次实际操作尝试**，不是“第二张清单只有四步，所以本次只做了四步”。失败尝试也做过工作，不能从计数里消失。

本章用三个不同的限制表达三件事。每份计划最多五步；`max_replans=1` 表示初始计划以外最多再规划一次；`max_execution_steps=8` 限制整次运行的操作尝试，包括失败读取、换算和最终格式化。它们不是同一个计数器，不能都含糊地叫“最多循环八次”。

执行器每动手一次之前检查共享计数：

```python
if run.execution_steps >= max_execution_steps:
    raise ExecutionBudgetExceeded("the whole run's execution budget is exhausted")
run.execution_steps += 1
```

`run` 在整次任务开始时创建，不在每次计划开始时重置。可以把它想成同一张工单的工时表：换了方案，之前花掉的时间不可能自动退回。这里计的是操作次数，不是耗时或金额，名称不同，保证也不同。

把上限设为三试一次：

```bash
python stages/02-workflows-routing-planning/code/planning.py --max-steps 3
```

Tokyo 主源、Paris 主源失败、Paris 备用源，正好三次。两座城市的原始结果都保留了，但尚未换算，不能交付要求包含华氏度的完整简报。程序返回 `failed`，`answer` 仍为空，并以退出码 1 结束。这是限制起作用，不是程序偷偷把不完整结果当成功。

`--max-replans 0` 会在第一份计划遇到故障时结束；`--failure both` 会让 Paris 的备用入口也失败。两者都不会输出比较成功的假象。执行预算已经耗尽时，控制器甚至不会再请求一份注定无法执行的新计划。

次数限制也不会打断一个卡住的 Python 函数。它只在下一次操作开始前检查，不是超时、取消或强制终止机制。眼前这些函数很快，足够观察控制流程；接真实模型时还要单独限制模型请求，并处理响应失败。

## 12. 把理解文字和提出计划交给真实 DeepSeek

到这里，工作流、路由边界和执行器都能独立工作。现在把两个测试替身换掉：一个真实模型负责把自由文字整理成 `RouteDecision`，另一个模型调用负责提出 `Plan`。可以使用同一个 DeepSeek 模型，但这是两种任务，不是让一段大提示词顺便把所有控制工作都接管。

[`deepseek_decisions.py`](code/deepseek_decisions.py) 复用前两章的 Responses 接口。先用结构化输出请求一张任务单：

```python
response = self.client.responses.parse(
    model=self.model, instructions=instructions, input=input_text,
    text_format=schema, max_output_tokens=4096,
)
```

用于选路时，`schema` 是 `RouteDecision`；用于规划时是 `Plan`。应用提供各自的行为规则，不向这个接口注册查询工具。DeepSeek 负责产出候选数据，读取天气仍是后面的执行器在做。[DeepSeek Responses 接口](https://api-docs.deepseek.com/zh-cn/api/create-response/)支持 JSON Schema 格式；SDK 的 `parse()` 还会尝试把响应解析为对应的 Pydantic 对象。

不能只检查“没有网络异常”。适配器要求响应完成、解析类型正确、没有意外工具请求，并重新验证对象；随后控制器再检查当前任务、已完成结果和来源条件。字段关系的 Python 验证函数不会被上传后在模型服务里运行，所以本地检查仍有实际作用。JSON 合法但方案不合格时，本例停止，不把它当成已经发生过的工具故障。

真实规划器拿到的输入也不是一句孤零零的“继续”。它按当前执行事实构造：

```python
context = {
    "task": task.model_dump(mode="json"),
    "completed": {key: asdict(value) for key, value in completed.items()},
    "failures": [asdict(failure) for failure in failures],
}
```

`asdict()` 把数据类转换成普通字典，随后编码为 JSON。这里每次都是完整的新规划请求，所需上下文已经显式包含在输入中，不依赖服务替我们保存旧会话。[DeepSeek 的兼容性说明](https://api-docs.deepseek.com/zh-cn/guides/responses_api/)也明确列出了无状态接口的限制。我们只打印经过验证的决策，不把模型内部推理当执行协议。

两种模型调用共用 `StructuredClient` 的请求计数，默认最多三次：一次选路、一次初始规划，必要时再规划一次。计数在请求发出前增加，失败请求也占次数；SDK 使用 `max_retries=0`，没有隐藏的自动重试。`timeout=30.0` 是客户端一次请求的超时配置，不是整个任务严格三十秒结束的保证。

在当前终端设置密钥和账户可用的模型。下面的模型名是官方示例值，实际可用性以服务和账户为准；不要把密钥写进源文件：

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export DEEPSEEK_MODEL="deepseek-flash"
python stages/02-workflows-routing-planning/code/deepseek_decisions.py --mode route
```

PowerShell 对应为：

```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-api-key"
$env:DEEPSEEK_MODEL="deepseek-flash"
python stages/02-workflows-routing-planning/code/deepseek_decisions.py --mode route
```

`--mode route` 表示只让模型理解请求，随后执行固定工作流。缺少配置或 SDK 会报错，不会悄悄切换为离线答案。还可以用 `--question "读一下巴黎的教学记录，只要摄氏度。"` 替换示例，观察是否真正识别成一城、无需换算。

接着选择“先提出计划”的模式，并制造主源失败：

```bash
python stages/02-workflows-routing-planning/code/deepseek_decisions.py --mode plan --failure primary --show-decisions
```

`--show-decisions` 展示通过结构验证的路由和计划数据；不要因此假定它们全部通过业务验证，最终仍要看运行状态。真实模型可以给独立读取安排不同先后，不一定重现离线示例的编号或轨迹。如果它交回非法方案，程序会报告失败，而不是把预先写好的成功答案替换上去。

规划模式开始时，路由器先确定产品要求，再把它转换成任务：

```python
task = task_from_decision(routing.decision, args.language)
blocked = (("primary", task.cities[-1]),) if args.failure == "primary" else ()
service = WeatherService(unavailable=blocked)
run = run_with_replanning(task, planner=DeepSeekPlanner(model), executor=PlanExecutor(service))
```

第二行只是注入演示故障，不是让模型宣布哪个服务失效。帮助或澄清路线不会进入这段代码，更不会为了展示 Planner 硬凑一张查询方案。这样从文字、路由、计划、执行到简报，才组成了一个完整且各有职责的过程。

## 13. 不只看看它会不会成功，还要看看它为什么成功

小林最关心的是页面有没有把需求办对。我们可以先把 Tokyo 的教学记录改成 22.0°C，再比较固定工作流和计划执行：二者都应该显示 71.6°F，与 Paris 的温差变成 10.0°C。只检查答案里有没有 `64.4`，很容易奖励一个根本没有使用查询结果的程序。

再故意让最后一步引用两份未换算的记录，却仍要求华氏度。整份计划应该在任何查询之前被拒绝。最后把执行上限设为三，观察已完成的读取是否还在，最终答案是否仍然为空。这些反例分别检查数据传递、计划验收和停止语义，不是让代码把错误“优雅地忽略掉”。

运行本章检查：

```bash
python stages/02-workflows-routing-planning/code/checks.py
```

检查还覆盖两种语言的固定路由案例、表单不调用模型、澄清不查询、未来引用、重复编号、错误城市、来源限制、跨计划预算以及两城温度相同的情况。伪客户端会检查真实适配器发送的任务、完成记录和失败记录；可选 SDK 检查使用模拟 HTTP，不请求真实服务。它们验证程序接口与控制行为，不测 DeepSeek 实际的理解正确率。

检查里保留了“城市存在但意图仍可能读错”的反例。知道一个验证器检查不到什么，与知道它能拦住什么同样重要。真实模型还需要用问候、含糊指代、缺少城市、只要摄氏度和两城对照等输入逐项观察；不能拿几个离线替身的通过结果，宣布语义问题已经解决。

回头看，小林的页面并不是一路从“低级流程”升级成“高级 Agent”。同一件工作有不同的分工安排：开关已给答案，就让代码处理；文字含义不明确，就让模型只解释那一小段；需要执行前检查方案，就把方案当数据；每一步都要依据新观察选择时，再使用上一章的循环。它们可以组合，选择依据是问题在哪里，而不是哪个名字更时髦。

现在我们也能看到下一处困难。一次处理同时有路由结果、已经完成的读取、失败入口、当前计划、预算和最终简报。再加入草稿审核与修改时，这些状态会越来越难从局部变量里找齐。小林问“这次到底停在哪里、下一步为什么这么走”，我们需要一份更明确的表示。

[Stage 03：把状态摊在桌面上](../03-stateful-orchestration/README.zh-CN.md)就从这个问题继续。
