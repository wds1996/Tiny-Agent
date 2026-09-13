# Stage 03：简报写好了，为什么还不能交？——把状态和流程一起讲清楚

> Language: [English](README.md) | **简体中文**

[上一章](../02-workflows-routing-planning/README.zh-CN.md)，小林的出行练习页面已经能处理两座城市：先拿到 Tokyo 与 Paris 的记录，需要时换算温度，再生成简报；一个来源失败时，还能保留已完成的结果，调整剩余计划。现在她增加了一条交付要求：“显示之前再检查一下。两座城市不能漏，温度单位要对，还得写清楚这不是实时天气。检查不通过就修改，但不要一直改到明天。”

于是问题不再只是“会不会调用工具”。草稿写到哪一版了？刚才检查的是不是这一版？查过的天气要不要重新查？如果修改次数用完了，能不能还把草稿当成正式结果？这些问题需要程序记清当前进度，而不能依赖模型说一句“我记得”。

我们继续使用前面的固定天气记录，把一份简报从取数、起草、检查、修改走到交付。先用普通 Python 把发生的事情讲清楚，再把同一流程交给 LangGraph。最后，回到 Stage 01 的模型—工具循环，看看它怎样放进相同的状态与转移框架。整章的重点是让人看懂程序正在做什么，不是给原来的函数换一批听起来更专业的名字。

## 1. 先看稿子哪里不合格，不急着背图的名词

小林选中了 Tokyo、Paris，并勾选“同时显示华氏度”。第一版简报是：

```text
Tokyo: 18.0°C / 64.4°F, cloudy.
Paris: 12.0°C / 53.6°F, light rain.
```

数值都对，但它没有说明数据来源。放到出行页面上，读者可能以为这是刚查询的天气。对于这份练习稿，我们要求末尾还要有一句“固定教学数据，不是实时天气。”所以它需要修改；已经查到的两条记录则没有失效，不必重新读取。

先在纸上把这件事办一遍：取数后写稿，写完检查；通过就交付，不通过且还允许修改就修改，然后检查新稿；次数用完仍不合格，就保留草稿并说明没有通过。这里有两个不同的“结束”：交付成功和停止尝试。程序停下来了，不代表任务已经做好。

**有状态编排**可以先这样理解：程序带着一份清楚的工作单，安排不同步骤接着处理。工作单回答“现在有什么”，流程回答“接下来做什么”。我们已经会写字典、函数和条件语句，这一章只是把它们之间的关系摆得更清楚。

不使用框架也能完成这个流程。[`workflow.py`](code/workflow.py) 中的 `run_plain()` 就用普通循环执行相同的检查规则。用 Python 3.10 或更新版本，在仓库根目录运行：

```bash
python stages/03-stateful-orchestration/code/workflow.py
```

输出会先记录缺少来源说明，再记录修改与复查，最后显示带说明的两城简报。这个入口没有模型调用。先把“改的是哪份稿，为什么需要再检查”理解清楚，后面的状态和节点才有具体含义。

## 2. 工作单上应该放什么？

设想检查函数刚发现问题，我们暂时把程序停在这里。下一步要修改，至少需要知道用户选了哪些城市、是否需要华氏度、已经查到的记录、当前草稿、检查意见，以及已经改过几次。这些就是本次执行的 **State（状态）**：继续工作所需的数据，不是整个应用的全部资料。

[`workflow.py`](code/workflow.py) 的 `initial_state()` 会检查城市与单位开关，再创建这份工作单。它返回的字典是：

```python
return {
    "cities": list(cities), "include_fahrenheit": include_fahrenheit, "language": language,
    "readings": [], "draft": None, "review": None, "revisions": 0,
    "events": [], "answer": None, "status": "working",
}
```

`readings` 从空列表开始，取数后才有内容；`draft` 和 `review` 的 `None` 表示尚未产生草稿与检查结果。`revisions=0` 表示还没有修改过，不表示草稿一定不合格。`answer` 只有通过交付检查以后才填写。`events` 是我们另外保留的经过记录，便于观察它走过哪些步骤。

注意状态与历史的区别。`draft` 保存当前稿，`review` 保存当前检查结果；它们不是每一版文档的档案库。`events` 才有意累积简单记录。需要新值还是需要历史，要由字段的用途决定，不能因为都是列表或字典就采取同一种处理。

也不要把这张工作单直接等同于模型上下文。检查器需要修改次数，模型未必需要；应用的状态里可以有内部进度，但只有显式放进模型请求的内容才会被模型看到。后面的真实模型入口会只发送消息记录，不把整张状态表倾倒过去。

还有一个小区别：业务状态没有偷偷藏着 Python 的执行位置。正在运行哪个步骤，由调度程序掌握；只打印这一份字典，不等于保存了进程或恢复了运行。眼前先把数据组织清楚，随后再把步骤之间的去向组织清楚。

## 3. 每个步骤交回一张改动单，不搬走整张工作单

取数完成时，最自然的报告是“记录已经拿到了”，而不是把城市、修改次数、草稿和所有历史重新交一遍。代码也可以这样表达：函数读取当前状态，只返回这次新增或改变的字段。这样一个有明确工作的函数，就可以作为 **Node（节点）**。

在 `ReportNodes.collect()` 中，程序逐个读取所选城市，检查返回的城市、有限数值与来源说明，最后只返回：

```python
return {"readings": readings, "events": ["collected requested records"]}
```

这就是 **局部更新（partial update）**。它的意思是更新 `readings`，并产生一条新事件；它没有要求删除原来的 `cities`，也没有改变 `revisions`。省略字段通常意味着保持原值，不是把该字段清空。局部更新让责任更容易看清，但它本身不是字段权限系统；框架不会仅凭这份写法，自动阻止节点返回其他字段。

起草节点接着使用已保存的记录，按照单位开关生成行数据。我们给第一稿设置了一个能观察到的缺陷：默认漏掉来源说明，而不是造一个只有作者知道含义的 `draft-v0` 标记。实际方法是：

```python
def write_draft(self, state: State) -> State:
    notice = NOTICES[state["language"]] if self.draft_style == "complete" else ""
    return {
        "draft": {"rows": expected_rows(state), "notice": notice},
        "review": None, "events": ["wrote draft"],
    }
```

`expected_rows()` 用实际读取的温度计算华氏度，不会把 64.4 写死。`draft` 由 `rows` 和 `notice` 组成：前者是页面将显示的天气行，后者是来源说明。`review=None` 则有明确含义：新稿出来，原来的检查结论不再适用。这里要清空，所以必须显式返回 `None`，不能仅仅省略 `review`。

节点不一定要小到一行，也不应该大到包办全部工作。取齐这份小简报的记录是一个步骤，检查一份稿是一个步骤；把 `strip()` 也拆成节点，并不会增加多少可理解性。一个实用判断是：当它失败时，我们能否说清楚失败的是哪件事？

## 4. 草稿应该换新，经过记录却应该接着写

现在有了改动单，还差一个约定：怎样把它并进工作单？假设原来是 `draft=旧稿`、`events=[取数完成]`，起草节点返回 `draft=新稿`、`events=[起草完成]`。草稿当然要替换，但事件如果也替换，前面的取数记录就消失了。

所以字段需要各自的更新规则。默认规则是用新值覆盖旧值；只有需要累积的字段，才额外指定合并函数。这个合并函数叫 **Reducer**。名字不必吓人，在这里它就是“旧值和本次新值怎样组成下一份值”。事件列表使用：

```python
def append_events(left: list, right: list) -> list:
    return [*left, *right]
```

方括号里的 `*` 把两个列表的元素依次放进新列表，不修改原列表。已有 `['collected']`，本次返回 `['drafted']`，合并后就是 `['collected', 'drafted']`。节点只负责本次的一条记录，不负责把全部历史再抄一遍。

[`state_graph.py`](code/state_graph.py) 中真正做合并的部分如下。`candidate` 是原状态的独立副本：

```python
candidate = deepcopy(dict(state))
for key, value in update.items():
    right = deepcopy(value)
    reducer = reducers.get(key)
    candidate[key] = reducer(candidate[key], right) if reducer and key in candidate else right
return deepcopy(candidate)
```

没有 Reducer 的 `draft` 会整体替换，不是自动深度合并里面的 `rows` 与 `notice`。如果只返回 `draft={'notice': '...'}`，旧行数据不会被这个规则自动补回来。相反，`events` 配置追加后，如果节点返回“旧历史加新历史”，旧记录会再追加一次。字段语义、返回值和合并规则必须对应。

这里先在副本上完成整次合并，全部成功后才采用新状态。即使某个 Reducer 抛错，也不会让前面几个字段已经更新、后面几个停在旧值。这个保证只针对这次内存状态合并：节点此前查过接口、写过文件的话，复制字典不会撤销那些外部行为。

手写引擎还会把深拷贝交给节点与选路函数，减少嵌套列表被意外原地修改的影响。不过这是本章小引擎的实现选择，不是 LangGraph 对所有对象的隔离承诺，更不是安全沙箱。业务函数本身仍按“读取输入、返回新值”的方式编写。

## 5. 检查的是当前草稿，不是“已经改过一次”

工作单合并好了，检查器终于可以读稿。我们的验收标准很窄：行数据必须与已查询的城市、数值和单位相符，来源说明必须是页面要求的那一句。没有让模型给自己打分，也没有规定“第一遍否决，第二遍自动通过”。

`review_issues()` 检查 `rows` 和 `notice`，返回具体问题。随后检查节点把问题与所检查的稿子一起记下来：

```python
def check_draft(self, state: State) -> State:
    issues = review_issues(state)
    return {
        "review": {"passed": not issues, "issues": issues, "checked_draft": deepcopy(state["draft"])},
        "events": ["checked draft: " + (", ".join(issues) if issues else "accepted")],
    }
```

`passed` 表示这些明确规则是否通过，`issues` 说明没有通过的原因，`checked_draft` 留下此次检查的内容副本。它像在稿子上签收，而不是签一张“以后的稿子都可以”的空白通行证。

第一稿缺少说明时，问题是 `missing_fixed_data_notice`。修改节点补上说明、增加修改次数，并把 `review` 清空，然后重新检查。它使用已有的 `readings`，不会重新查 Tokyo 和 Paris。数据准备与内容修改分开以后，这种“不该重做的工作”就容易说清楚了。

这也说明为什么要提供三种可观察的情形：`missing-notice` 是默认缺陷；`complete` 表示第一稿已经合格；`stubborn` 则故意让修改器仍漏掉说明。第三种情况下，改过多少遍都不能把不合格变合格。它用来检验停止规则，不是假装模型一定会如此。

这种检查没有解决开放式文章的全部质量问题。这里的稿子是结构明确的页面数据，比较的是指定字段和固定说明；把它搬去判断新闻真假或一段复杂分析是否有依据，就超出了这套规则。以后换成自由文本，必须重新定义适合那类输出的验收方法。

## 6. 检查完去哪里？先把允许的路线写出来

检查函数只负责写下结果。接下来是另一个问题：通过了去交付，不通过还能改就修改，没有次数就保留草稿并停止。负责连接这些步骤的关系叫 **Edge（边）**。固定边只有一个下一站；条件边先读取更新后的状态，再从已声明的去向中选择。

`ReportNodes.route_after_check()` 做的就是选路，不会顺手修改稿子：

```python
def route_after_check(self, state: State) -> str:
    review = state["review"]
    if review is None or review["checked_draft"] != state["draft"]:
        raise ValueError("The current draft has not been checked")
    if review["passed"]:
        return "accept"
    return "revise" if state["revisions"] < self.max_revisions else "hold"
```

`max_revisions` 是应用配置，不由草稿或模型填写。设成 1，表示最多执行一次修改；第一次检查和修改后的复查是两次不同的检查，不会都扣成“修改一次”。零次修改也仍然允许检查和交付本来就正确的初稿。

现在把路线放在一起看，每个名字都已经有具体工作：

```text
START → collect → write_draft → check_draft
                                  ├─ accept → publish → END
                                  ├─ revise → revise_draft → check_draft
                                  └─ hold   → hold → END
```

上面回环的准确连接可以直接读成 `check_draft → revise_draft → check_draft`。`START` 和 `END` 是入口、结束的特殊标记，不是查数据或生成文字的业务函数。`hold` 也会走到 `END`，但它留下 `status='needs_attention'` 和 `answer=None`，不会冒充已交付。

对应的条件边只需一张映射表：

```python
builder.add_conditional_edges("check_draft", nodes.route_after_check,
                              {"accept": "publish", "revise": "revise_draft", "hold": "hold"})
```

返回 `accept` 只能去 `publish`，返回 `revise` 只能去 `revise_draft`；不能通过返回一个陌生字符串凭空创造新节点。这延续了上一章的有限路由，只是现在目的地是步骤而不是整个处理模块。

到达交付节点时，程序还会确认检查所对应的稿件没有改变，并重新核对这套小规则。`publish` 只是把合格数据转为返回文本，不会上传网页或发邮件。当前节点、业务结果、外部动作是不同东西，名字叫“发布”不等于网络上真的出现了新内容。

## 7. 这张路线图怎样真正执行？

到这里我们才需要一个 **Graph（图）**：把刚才的节点和边组合起来，形成调度程序能执行的路线。它不是另一种模型。手写的 `MiniStateGraph` 只保存函数表、固定去向、条件去向和 Reducer，然后生成一个可以运行的对象。

调用 `compile()` 时，小引擎会检查入口、节点名称、目的地、没有出边的节点，以及从入口无法到达的节点。还会检查每个节点在结构上至少存在一条去往 `END` 的可能路径。这能发现拼错名称或完全封死的环，但不能证明选路函数真的会选择出口。

例如，条件表允许 `again` 和 `done`，选路函数却永远返回 `again`，图在结构上有出口，运行时仍会无限兜圈。因此执行时还有 `max_steps`。它数的是手写引擎实际完成的节点次数，不是修改次数，也不是模型调用次数。达到上限以后，不再启动下一个节点。

每次启动节点后的核心工作仍然很普通：

```python
update = self.nodes[current](deepcopy(state))
candidate = merge_update(state, update, self.reducers)
```

随后采用合并后的状态，记录完成的节点，再根据新状态选择下一站。所谓“图执行”，没有消灭循环，只是把“做什么”和“做完去哪里”从越来越长的条件语句中分离了出来。小引擎一次只运行一个节点，不实现并行分支。

运行这条路线：

```bash
python stages/03-stateful-orchestration/code/state_graph.py --show-updates
```

默认经过 `collect → write_draft → check_draft → revise_draft → check_draft → publish`，共六次节点执行，最终是一份带来源说明的简报。每个 `StepSnapshot` 同时保留节点名、本次局部更新和合并后的状态副本，便于回看“哪一步使检查结果改变了”。

如果节点或合并出错，`GraphExecutionError` 会携带失败位置、此前已完成的节点和最后成功合并的状态。未返回的局部变量不会被编造成已完成结果；外部操作也不会自动回滚。比如取数节点读了第一座城市后，在第二座城市抛错，本次节点还没提交 `readings`，不能把整个取数节点标成成功。需要逐次保留时，就应把读取分成更小的提交单元。

这也解释了节点大小为什么有实际含义：节点边界同时决定我们在哪些位置观察和接受一次状态变化。

## 8. 换成 LangGraph，先保持同一份工作不变

现在换负责调度的实现，而不换问题、验收规则或修改方式。**LangGraph** 提供了现成的状态图执行能力；我们要交给它的，仍是这份工作单和前面那组普通函数。先认识它最关键的两个约定就够了：状态有哪些字段，以及某个字段收到新值时怎样合并。

[`langgraph_workflow.py`](code/langgraph_workflow.py) 用 `TypedDict` 描述状态。它与普通字典具有相同的运行时形态，类型提示主要帮助编辑器和检查工具理解字段，不会自动为所有输入做验证或生成默认值。[Python 的 TypedDict 说明](https://docs.python.org/3/library/typing.html#typing.TypedDict)对这个限制有明确解释。这里仍通过前面的 `initial_state()` 检查选项并创建初值。

```python
class ReportState(TypedDict):
    cities: list[str]
    include_fahrenheit: bool
    language: str
    readings: list[dict[str, Any]]
    draft: dict[str, Any] | None
    review: dict[str, Any] | None
    revisions: int
    events: Annotated[list[str], add]
    answer: str | None
    status: str
```

普通字段沿用替换语义。`Annotated[list[str], add]` 则在列表类型后附上一个约定：由 `operator.add` 合并两份列表。这不是让 Python 的所有列表都改变行为，而是 LangGraph 读取这个标注，为 `events` 配置 Reducer。相关接口见 [LangGraph 状态与 Reducer](https://docs.langchain.com/oss/python/langgraph/graph-api#reducers)。

构建函数没有复制一套业务实现：

```python
def build_graph(**options: Any):
    builder = state_graph_type()(ReportState)
    connect_report(builder, ReportNodes(**options))
    return builder.compile()
```

`connect_report()` 注册同样的节点和边，`ReportNodes` 提供同样的检查与修改函数。这样比较两种执行器时，变的是调度实现，而不是悄悄换了验收标准。`state_graph_type()` 只是导入真实 `StateGraph` 并在缺少依赖时给出提示，不会拿手写引擎冒充 LangGraph。

安装并运行：

```bash
python -m pip install -r stages/03-stateful-orchestration/code/requirements.txt
python stages/03-stateful-orchestration/code/langgraph_workflow.py --show-updates
```

LangGraph 的 `compile()` 负责构建可执行图和框架支持的结构检查，并不是把业务函数编译成另一种语言，也不会证明稿件正确。不要假定它和我们的小引擎具有完全相同的静态检查集合；本章用行为对照检查自己依赖的更新与选路语义。

这时可以回答一个经常混淆的问题了：没有一次模型调用的流程，也能使用 LangGraph。图是一种组织状态变化的方式；是否让模型动态选择行动，是另一件事。我们先把确定的工作流表示清楚，再考虑模型参与的情况。

## 9. 既要看过程，也要拿结果，不必再执行第二遍

小林想看“为什么先改后交”，只拿最后的 `answer` 不够。`graph.invoke()` 适合直接获取本次运行结束后的状态；`graph.stream()` 则在执行中逐步交出记录。它们都在运行图，`stream()` 后再调用 `invoke()` 不是查同一份结果，而是又开始了一次执行。

流式观察有两个容易混淆的视角。`updates` 是某个节点刚提交的改动单，比如只有一条新事件；`values` 是合并后的整份工作单，其中已经包含前面的事件。[LangGraph 流式接口](https://docs.langchain.com/oss/python/langgraph/streaming)区分了这两种模式。本例一次订阅两种模式，在同一次执行中打印更新、取得最后状态：

```python
final = None
for mode, payload in graph.stream(state, stream_mode=["updates", "values"],
                                   config={"recursion_limit": recursion_limit}):
    if mode == "updates" and show_updates:
        for node, update in payload.items():
            print(node, "updated:", sorted(update) if isinstance(update, dict) else [])
    elif mode == "values":
        final = payload
```

`payload` 在更新模式下按节点名组织，在状态模式下是当前值。循环结束后，`final` 才用于显示结果；程序不会为了拿 `answer` 再跑一遍取数和修改。打印时只显示变更字段名，不把每份内部消息都默认展开。

这里传给配置的 `recursion_limit` 是 LangGraph 的图执行轮次限制。框架把一轮调度称作 **super-step**：顺序相连的节点分属不同轮，能够同时调度的多个节点则可能在同一轮。当前图没有并发分支，但仍不能把这个限制直接说成“最多调用几次模型”。它也不是 Python 函数递归深度，或多少秒以后强制终止。

业务上的 `max_revisions` 负责说“最多改几稿”；图的执行上限负责防止错误接线一直运行。前者到达上限可以走 `hold`，后者耗尽通常是调度异常。把正常的未通过和程序控制失常分开，比一律打印“结束了”更有用。

## 10. 自由输入框里的助手，也能带着工作单循环

小林的表单路线现在已经稳定。输入框却仍可能收到不同请求：只问候、只查 Tokyo，或者查询以后再换算。这正是 Stage 01 的模型—工具循环。我们不把确定的草稿审核重新交给模型，只观察这段已经学过的动态处理，怎样用图表达。

仍然使用同样的天气来源，不突然换成一道乘法题。这个对照入口返回模型回复，**不等于上面经过结构化检查的已交付简报**。一个系统可以把模型回复当候选材料再检查；仅仅把循环画成图，并不会附送这种验收能力。

两类节点就足够表达循环：`model` 看消息，交回答案或申请；`tools` 执行通过检查的申请，交回观察。模型还有新申请就去工具节点，工具成功后再问模型；拿到答案或者出现不能继续的错误，就结束。

```text
START → model ── 工具申请 ─→ tools
          │                   │
          │              成功后回到 model
          │
          └─ 最终答案或错误 ─→ END
                    tools 执行失败也进入 END
```

[`agent_graph.py`](code/agent_graph.py) 的状态因此换成了这段工作真正需要的字段：

```python
class AgentState(TypedDict):
    messages: Annotated[list[dict[str, Any]], add]
    pending_tool_calls: list[ToolCall]
    final_answer: str | None
    error: str | None
    model_steps: int
    tool_calls: int
    events: Annotated[list[str], add]
    diagnostic_tag: str
```

`messages` 累积用户请求、模型申请和工具结果。`pending_tool_calls` 却只代表眼前尚未处理的申请，所以不配置追加规则：执行后写入空列表，就能清掉它。若给它也加 `add`，空列表与旧申请相加仍然是旧申请，下一轮可能又执行一遍。这不是列表类型的问题，而是“历史”和“待办”两个含义不同。

`model_steps` 与 `tool_calls` 是程序的次数记录；`diagnostic_tag` 是本地诊断标签。这些都留在应用侧。模型节点只取 `messages` 构造调用，类型提示或字段名字不会自动完成这项选择。

## 11. 节点换了位置，模型与执行的分工不能变

先用 `ScriptedModel` 观察相同线路。它是按演示选项配置的测试替身，不理解任意用户语言；收到已有天气观察后，才用其中的摄氏温度构造换算请求。真实模型稍后使用同样的节点，而不是复制另一套图。

模型节点返回新消息和当前申请，旧历史由 Reducer 合并。工具节点先检查整批申请的名字与参数，再开始执行，避免同一批第二个明显非法请求出现之前，第一个工具就已经运行。天气工具只接受已提供的城市，换算工具拒绝字符串、布尔值与非有限数字；不会把模型写的名字交给 `eval()`。

执行后的状态更新如下：

```python
return {"messages": observations, "pending_tool_calls": [], "tool_calls": used,
        "error": error, "events": ["tools failed" if error else "tools completed"]}
```

`observations` 只包含本次结果，`pending_tool_calls=[]` 表示这批申请不再待执行。失败时也会记录已完成结果与安全错误，并停止后面的模型调用；没有把失败翻译成成功，更不会自动重试。这些行为来自节点代码，不是图框架替我们猜出来的。

次数控制也仍然存在。`max_model_steps` 在请求前检查，失败的请求也占一次；`max_tool_calls` 在整批执行前检查，实际尝试执行的工具才进入计数。相同 `call_id` 不得在同次运行中重复，但这只是调用关联检查，不等于验证两次不同编号的业务动作是否重复。

运行真实 LangGraph 上的离线替身：

```bash
python stages/03-stateful-orchestration/code/langgraph_scripted_agent.py --show-updates
```

默认是 `model → tools → model → tools → model`：五次节点工作、三次模型替身调用、两次工具执行。结果是 Tokyo 的 18.0°C 与 64.4°F，待办列表清空。`--task weather` 只查不换算，`--task greet` 则不执行工具。还可以显式加 `--engine mini`，让同一组节点由手写引擎运行；它是一个明确选择的对照，不是缺少 LangGraph 时的静默替代。

把 `--max-model-steps` 设成 1 时，天气查询可以已经完成，但第二次模型请求不会发生。状态保留查询结果，`final_answer` 为空，命令以非零退出码结束。已经做过的事情与整个任务是否成功，是两份不同事实。

## 12. 换成真实 DeepSeek，下一轮仍从这次运行拿材料

现在只替换负责提出下一步的对象。模型节点仍调用 `generate(messages)`；[`langgraph_deepseek_agent.py`](code/langgraph_deepseek_agent.py) 中的 `DeepSeekModel` 把消息变成服务接受的输入，再把响应转成 `ModelTurn`。实际请求是：

```python
response = self.client.responses.create(
    model=self.model, instructions=INSTRUCTIONS, input=to_input(messages),
    tools=tool_definitions(), max_output_tokens=4096,
)
```

`tool_definitions()` 描述天气与换算两项能力；真正的函数仍在应用中执行。服务响应必须完成，工具参数必须能解析为对象，没有工具请求时还要有非空最终文字。响应中同时出现申请和说明文字时，适配器按申请继续，不把“我来查一下”当最终答案。

[DeepSeek Responses 接口](https://api-docs.deepseek.com/api/create-response/)是无状态的多轮接口，后续请求需要客户端携带历史。适配器保留每轮服务输出的完整项目，包含续接可能需要的协议数据：

```python
provider_items = tuple(item.model_dump(mode="json", exclude_none=True) for item in output)
```

这些项目跟着当前运行的消息走，不放进一个跨用户共享的“上次响应”变量。下一轮转换时把原输出项与匹配 `call_id` 的 `function_call_output` 一起发送；状态中的计数和诊断标签不会因此被发送。程序不根据推理文字选路，也不在默认输出中打印推理内容。

这与前两章是一条相同的数据流：不是远端模型神奇地记住了 Python 变量，而是应用把已发生的事情明确交回去。更换调用对象，不改变消息归属、参数检查和执行预算。

安装本章依赖后，在同一个终端设置密钥与账户实际可用的模型 ID。Bash 示例：

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export DEEPSEEK_MODEL="your-available-model-id"
python stages/03-stateful-orchestration/code/langgraph_deepseek_agent.py --show-updates
```

PowerShell 中前两行对应为：

```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-api-key"
$env:DEEPSEEK_MODEL="your-available-model-id"
```

入口会明确显示正在使用真实 DeepSeek，需要网络并产生服务用量。客户端使用 `max_retries=0`，不自动增加请求尝试；`timeout=30.0` 是一次客户端请求的配置，不是整个图必须三十秒结束的保证。缺少 SDK、配置或服务调用失败时，不会偷偷返回测试替身的答案。

真实模型的措辞、申请数量与调用顺序可能不同。运行时能够限制过程，却不会自动确认每一句最终文字正确。如果它不查工具就说“99 度”，这是一份不满足任务的回复，但仍可能符合“非空最终文字”的协议。不要把成功到达 `END`、数据契约通过和答案正确混成同一个结论。

## 13. 让同一份简报走过每一条出口

现在可以有目的地做几次对照，而不是只看默认成功。先让第一稿就带来源说明，预测不会出现修改节点；再让修改器一直漏掉说明，预测最后走 `hold` 而不是 `publish`：

```bash
python stages/03-stateful-orchestration/code/state_graph.py --draft-style complete
python stages/03-stateful-orchestration/code/state_graph.py --draft-style stubborn --max-revisions 2
```

第二条命令应以退出码 1 结束，保留最后草稿，但没有正式答案。这里的失败是实验要观察的结果，不是让读者通过删除检查把它改成成功。

再把 Tokyo 的记录临时改成 22.0°C，观察草稿、检查与最终输出是否一起变成 71.6°F。修改完成后不应该再查两遍天气。最后，在一份已通过检查的草稿里改动温度，尝试交付；旧检查不能给新稿放行。这几次实验分别对应实际数据传递、节点职责和检查结果的适用范围。

本章的自动检查可以直接运行：

```bash
python stages/03-stateful-orchestration/code/checks.py
```

它分别检查普通函数、手写引擎和模型适配器；安装了 LangGraph 后，还会实际比较两种引擎的分支与合并结果，并检查单次流式运行。可选 SDK 检查使用模拟 HTTP，不请求付费服务。缺少可选依赖时会明确显示跳过，这不能算作真实框架已经验证通过。

回到小林的需求，我们已经能分清：状态里有什么、这次改了什么、检查为什么不通过、下一步由哪条边决定，以及什么情况下只是停止而非成功。状态仍只保存在本次进程内，重新启动不会自动继续；经过记录也不是持久化系统或完整监控平台。把当前保证说准确，才知道下一处问题究竟需要增加什么。

现在再换一个问题：如果用户不问两条字典里已有的天气，而是问一份刚更新的商店政策，状态图本身会把资料送给模型吗？不会。它能组织处理过程，却不能凭空提供事实。[Stage 04：从检索到 Agentic RAG](../04-agentic-rag/README.zh-CN.md)继续解决资料从哪里来的问题。
