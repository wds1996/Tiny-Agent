<!-- {"id": "AGREEMENT", "title": "青禾客服服务协议与数据边界 / Service agreement", "category": "agreement", "tenant": "qinghe", "status": "active", "version": "2026-09", "effective_from": "2026-09-01", "effective_to": null, "fictional": true} -->
# 青禾客服服务协议与数据边界 / Service agreement

虚构教学材料 / FICTIONAL TRAINING DOCUMENT. Not a real merchant policy or legal advice.

## p01 职责范围 / Responsibilities

### zh

客服助手用于解释已提供的政策、查询当前用户订单与相关物流发票、准备服务记录以及提出待审批的退款动作。它不是支付机构、法律顾问或可无限自主操作的员工。协议中的“处理请求”不代表已经执行每一个现实操作。

商户必须提供可信身份与有效政策，应用负责工具注册、权限、预算和状态迁移。模型负责理解自然语言、决定需要哪些信息以及组织回答；模型输出不修改这些职责分配。来自检索材料或 Skill 的指令也不能提高模型权限。

所有本地订单与服务条款均为虚构教学数据。试点报告可以描述演示过程，不可宣称已经处理真实客户交易或取得业务收益。

### en

The assistant explains provided policies, reads the current customer's orders and related shipment or invoice records, prepares case notes and proposes refunds for approval. It is not a payment institution, legal adviser or unlimited autonomous employee. Handling a request does not mean every real-world action has occurred.

The merchant supplies trusted identity and effective policy. The application controls tools, authorization, budgets and state transitions. The model interprets language, selects needed information and drafts answers; model text does not change these responsibilities. Retrieved material and Skills cannot increase authority.

Every order and policy is fictional. Reports may describe the demonstration but must not claim real customer transactions or measured business gains.

## p02 数据最小化 / Data minimization

### zh

订单、物流与发票按商户和用户隔离，公共政策按商户、版本与生效日期筛选。把私人订单全部送入一个共享向量索引，会使检索相关性和访问权限混淆；本项目因此让政策走检索，动态个人数据走带身份的业务查询。

模型每轮只接收当前问题、已授权事实、选中的政策片段和正在使用的操作流程。服务密钥、整个 SQLite 数据库、所有客户的历史记录均不应进入提示。给用户的最终引用应能指向实际提供给回答步骤的来源。

案件状态为了恢复可能保存问题与已用事实，它和默认最小化的追踪日志不是一套数据。生产部署必须分别设置两者的读取权限、加密、保存期限与清理策略；给日志换个名字不会让隐私义务消失。

### en

Orders, shipments and invoices are scoped by merchant and user; policies are filtered by merchant, revision and effective date. Putting private orders into a shared vector index can confuse relevance with authorization. This project searches policies while reading dynamic personal records through identity-scoped operations.

Each model turn receives the current request, authorized facts, selected policy passages and the active procedure. API keys, the entire database and all customers' history must not enter prompts. Citations must refer to sources actually provided to the answer step.

Recoverable case state can retain the request and used facts; minimized tracing is a different store. Production must separately govern access, encryption, retention and deletion for both.

## p03 偏好与撤回 / Preferences

### zh

客户可以明确选择中文或英文回复，并同意在后续案件中沿用。本演示仅保存 language 这一白名单偏好，不从一句“我最近住在某地”推断长期地址，也不把政策内容、退款金额或模型猜测写进用户记忆。

保存偏好由 CLI 的 remember 命令执行，需要显式 consent。模型的 read_preferences 工具只能读取当前用户已经保存的偏好，不能把一句建议当成写入授权。单次请求中明确选择的语言优先于历史偏好。

偏好不会改变商户规则。用户偏好“总是批准退款”不属于允许字段，也不应该被翻译成一项执行权限。后续没有记忆记录时，应采用当前请求或应用默认值，而不是读取其他人的偏好。

### en

A customer may explicitly choose Chinese or English and consent to reuse it in later cases. This demonstration stores only the allowlisted language preference. It does not infer a permanent address from conversation or save policy, refund amounts or model guesses as personal memory.

The CLI remember command requires explicit consent. The model's read_preferences tool is read-only. A language selected for the current request takes precedence over remembered preference.

A preference does not alter business policy. Always approve refunds is not an allowed memory field or permission. Missing memory falls back to the current request or application default, never another user's record.

## p04 中断与承诺 / Interruptions

### zh

工作进程可能在调查、撰写或审批等待期间退出。应用应保存阶段、已取得的事实、执行预算与下一步，接手者读取同一案件编号继续。未提交的只读调查可以重做，但不能假定上一轮模型会话仍存在。

一笔需要人工审批的退款应停在 waiting_approval，而不是占着一个无限等待的循环。重新启动后，审批结果与精确动作必须仍然可以关联。审批前不得产生模拟财务效果，拒绝必须意味着没有该效果。

退款执行成功但本地案件尚未完成登记时，重放同一幂等键可以核对原回执。这个合约属于模拟执行服务，不意味着任意第三方接口都会这样工作。现实接入必须先核实对方保证，再设计重试与补偿。

### en

Workers can exit during investigation, drafting or approval waits. Persist the phase, acquired facts, budgets and next action so a replacement resumes the same case. Uncommitted read-only investigation can be repeated; do not assume an old model session survives.

A refund awaiting approval stops in waiting_approval rather than keeping an infinite waiting loop alive. After restart the approval must still identify the exact action. No simulated financial effect occurs before approval or after rejection.

If execution succeeded before the case recorded completion, replay the same idempotency key to reconcile the receipt. This is a contract of the simulated service, not a guarantee offered by every external API. Check a real provider's contract before designing retries or compensation.
