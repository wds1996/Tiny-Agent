# 04 — Offline / Online Evaluation 与 Dataset Design

> Language: [English](04-offline-online-and-datasets.md) | 简体中文

Evaluation 的质量高度依赖你选择了什么 examples。一个很复杂的 evaluator 放在错误 dataset 上，只会让你对错误的事情产生更高级的自信。

---

## 1. Offline Evaluation

Offline evaluation 在 deployment 前，对受控 dataset 运行。

典型用途：

- prompt regression；
- model comparison；
- Tool schema change；
- RAG change；
- planning change；
- safety-policy change；
- backtest known incident。

环境应尽量 reproducible。

Offline example 可以安全携带比 production trace 更丰富的 reference：

```text
reference output
expected Tool
reference Tool arguments
required sequence
forbidden Tool
```

---

## 2. Online Evaluation

Online evaluation 对选中的 production behavior 打分。

用于：

- detect drift；
- monitor real user distribution；
- catch rare failure；
- collect human feedback；
- sample LLM judges；
- 找出应该晋升为 regression case 的 trace。

Online 往往没有 trusted gold answer，所以更多依赖：policy check、reference-free grader、human feedback、anomaly detection、sampled LLM judge、operational metric。

---

## 3. Feedback Loop

成熟工作流：

```text
Offline dataset
    -> candidate experiment
    -> release
    -> production traces
    -> online signals / human feedback
    -> interesting failures
    -> curated new offline cases
    -> next regression run
```

这会积累真实系统 failure 的工程知识，但注意：

```text
Evaluation dataset
!=
Agent memory
```

前者用于训练/测试工程系统；后者会影响 runtime context/behavior。

---

## 4. 先从 Curated Critical Examples 开始

第一版 dataset 至少覆盖：

```text
happy path
boundary values
known previous bugs
ambiguous requests
no-tool requests
tool-required requests
unsafe requests
retrieval miss
transient failure
permission denial
multi-step task
```

20 个认真 review 的 case，可能比 5000 个没人看过的 auto-generated case 更有价值。

Synthetic generation 是扩展手段，不是“免思考按钮”。

---

## 5. Dataset Split

可使用 metadata：

```text
smoke
regression
adversarial
long_tail
safety
retrieval
planning
```

再配置：

```text
PR CI        -> smoke + critical regression
nightly      -> full regression
pre-release  -> regression + adversarial
production   -> online sampled evaluation
```

不是每个 evaluator 都必须每次 commit 全跑一遍。

---

## 6. Dataset 必须 Versioned

如果 dataset 变了，score 不能脱离版本直接比较。

至少记录：

```text
dataset version
code commit
model/provider version
prompt/config version
Tool schema version
retrieval index/version when relevant
```

否则：

```text
quality 0.82 -> 0.91
```

可能只是有人把最难的 case 删除了。

---

## 7. Reference Output 也不是神谕

Reference 可能：stale、不完整、只是多个合法答案之一、来自非专家、与当前 policy 冲突。

所以 reference 应被当成 reviewed artifact，而不是 divine truth。

开放任务经常更适合 rubric，而不是 exact text。

---

## 8. Dataset Leakage 与 Overfitting

如果一直对同一小型 regression set 优化 prompt，就可能 overfit。

这相当于：

> “我把答案册背下来了，所以我已经理解微积分。”

可使用 held-out set、fresh production case、periodic refresh、category analysis、必要时 blind human review。

---

## 9. Offline Reproducibility

能冻结的尽量冻结：

```text
model version
prompt
Tool definitions
retrieval corpus
seed/temperature if supported
external fixtures
clock
```

如果仍调用 live external service，就不要假装完全 deterministic；记录足够 metadata 解释 variability。

---

## 10. Stochastic Target 需要 Repetition

```text
example A
  run 1 -> pass
  run 2 -> pass
  run 3 -> fail
```

一次 run 会隐藏 instability。

Tiny-Agent：

```python
suite.run(dataset, target, repetitions=3)
```

应看 mean、execution-success rate、variance/distribution、worst-case failure。

偶发 catastrophic unsafe behavior 的“平均 0.95”，与稳定 0.95 完全不是一回事。

---

## 11. Metric Coverage

100 个 example，50 个在 correctness evaluator 前 crash，剩余 50 个全部 1.0。

Naive report：

```text
correctness = 1.0
```

危险地误导。

应该同时报告：

```text
correctness = 1.0
coverage    = 0.5
execution_success = 0.5
```

Tiny-Agent 的 gated metric 默认要求 full coverage。**Missing score 本身也是数据。**

---

## 12. Production Sampling

Online LLM judge 很贵，可以例如：

```text
100% errors
100% policy violations
100% high-cost outliers
10% normal success
1% low-risk high-volume traffic
```

具体比例产品自定，但 sampling rule 必须记录，否则 sampled statistic 会有 bias。

---

## 13. 从 Trace 变成 Regression Case

Production failure 有价值时：

1. redact sensitive data；
2. minimize case；
3. 定义 expected behavior；
4. 加 reference/policy constraint；
5. 标记 provenance；
6. 放入 regression split；
7. 验证 old version fails / fixed version passes。

这就是把一次线上疼痛转成永久工程知识。

---

## 14. Eval Dataset 也需要 Governance

Dataset 可能包含真实 user input/output，因此同样需要：

- access control；
- retention；
- anonymization；
- licensing/data-use rules；
- deletion workflow；
- provenance；
- review ownership。

文件放在 `tests/` 目录里，并不会自动让其中的数据变得无害。
