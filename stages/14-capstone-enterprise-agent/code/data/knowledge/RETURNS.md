<!-- {"id": "RETURNS", "title": "青禾商城退货退款规则 / Qinghe returns and refunds", "category": "refund", "tenant": "qinghe", "status": "active", "version": "2026-09", "effective_from": "2026-09-01", "effective_to": null, "fictional": true} -->
# 青禾商城退货退款规则 / Qinghe returns and refunds

虚构教学材料 / FICTIONAL TRAINING DOCUMENT. Not a real merchant policy or legal advice.

## p01 适用范围 / Scope

### zh

青禾商城在本教学环境中销售桌面支架、阅读灯、连接线、收纳包、刻字杯与数字练习册。本规则只适用于商户标识为 qinghe 的普通实物订单；数字内容与定制商品需要依照第三页的例外处理。另一家商户的服务承诺、已归档版本或客服聊天中的猜测，都不能替代当前有效条款。

本规则区分“询问是否能退”“提交退货申请”和“执行退款”。用户询问资格时，客服可以解释规则并计算参考金额，但不能据此创建支付成功回执。用户申请退款后，也必须确认仓库签收与人工审批条件，才能进入模拟退款执行。

订单详情由订单服务提供，金额使用人民币分记录。知识库不是订单余额的来源；一份政策可以解释如何算钱，却不能告诉客服某笔订单已经退过多少钱。查询个人订单时，必须同时使用已确认的商户和用户身份。

### en

This fictional policy covers Qinghe orders for ordinary physical products: desk stands, lamps, cables and organizers. Digital workbooks and engraved goods have separate exceptions on page 3. Policies belonging to another merchant, archived versions and unsupported statements in chat are not substitutes for the effective rule.

An eligibility question, a return request and an executed refund are different events. Answering a question must not produce a payment receipt. Even an explicit refund request still requires a warehouse receipt and human approval before the simulated financial action.

Order facts come from the order service. Amounts are integer CNY cents. A policy explains the calculation but cannot establish an order's current paid or previously refunded balance. Personal order access must use both the trusted merchant and customer identity.

## p02 时间窗口与收货条件 / Window and warehouse receipt

### zh

普通实物订单的退货窗口为送达后 30 个自然日，包含第 30 天。起算依据是订单服务的 delivered_on，而不是下单日、付款日或用户自述日期。送达后第 31 天的普通原路退款不在本自动流程内，应说明原因并由人工处理其他可能方案，不能把不符合条件的订单交给审批按钮“变合格”。

可自动计算的订单必须为 delivered 状态，并且 return_received 为真，表示退回商品已由仓库登记签收。正在运输、尚未送达、已取消，以及仓库尚未收到退件的订单，都不能直接执行这条退款流程。仓库签收为假的订单可以继续查询物流或建立服务工单，不应声称“退款已发出”。

教学快照的业务日期为 2026-09-12。QH-1001 于 2026-09-05 送达，已退回仓库，处于窗口内；QH-1002 恰好为第 30 天，仍在窗口；QH-1003 为第 31 天，不符合自动退款条件。业务日期必须作为计算依据保留，不能由模型随口指定。

### en

The ordinary return window is 30 calendar days after delivery, including day 30. Use the order service's delivered_on date, not placement, payment or a date claimed in chat. On day 31 this automatic original-payment flow is unavailable. Explain the limit and refer other options to a human; approval does not turn an ineligible order into an eligible one.

The order must have status delivered and return_received=true, meaning the warehouse has recorded the returned goods. In-transit, undelivered, cancelled or not-yet-received returns cannot execute this refund. Shipment lookup and a service ticket remain possible alternatives.

The teaching business snapshot is 2026-09-12. QH-1001 was delivered on September 5 and received back at the warehouse. QH-1002 is exactly at day 30; QH-1003 is at day 31. Preserve the business date used in a quote rather than accepting a model-selected clock.

## p03 金额与例外 / Amount and exclusions

### zh

本自动流程处理整件商品的可退余额，不处理多件商品中的部分数量。参考金额为 paid_items_cents 减去 refunded_cents，且不得小于零；只能使用实际净支付的商品金额，不能用划线原价，也不能把优惠券恢复为现金。本教学规则不退运费，所以 shipping_refund_cents 固定为零。币种固定为 CNY，不进行汇率换算。

QH-1001 的商品净支付为 12900 分，运费为 1200 分，既往退款为零，因此本次可退商品金额为 12900 分，而不是 14100 分。QH-1009 的商品净支付同为 12900 分，但已有 4900 分退款，只剩 8000 分；QH-1010 已退完商品金额，不能再申请一次全额退款。

category 为 custom 的刻字杯和 digital 的数字练习册不适用上述自动原路退款，应进入人工政策解释与服务工单。本例不推导任何现实消费者权益。审批金额必须和报价一致；如果人工希望改变金额，应重新生成有明确依据的新提案，而不是编辑已批准的动作。

### en

This automatic flow returns the remaining value of whole items, not a selected quantity from a multi-item order. The quote is paid_items_cents minus refunded_cents, floored at zero. Use the net amount actually paid, not list price or a coupon's face value. Shipping is not refunded here, so shipping_refund_cents is zero. Currency is CNY; no currency conversion occurs.

QH-1001 has 12,900 cents in paid items and 1,200 cents shipping, with no previous refund: the quote is 12,900, not 14,100. QH-1009 has the same item payment and a previous 4,900-cent refund, leaving 8,000. QH-1010 has no remaining refundable item balance.

Custom engraved mugs and digital workbooks require human handling rather than this automatic original-payment path. These are fictional business rules, not consumer-law advice. Approved parameters must match the quote; changing an amount requires a new proposal, not mutation of an approved action.

## p04 审批与回执 / Approval and receipts

### zh

一份退款提案应列出订单编号、净金额、币种、订单版本、规则版本、业务日期和引用条款。系统将这些字段绑定到一个摘要，审批人确认的是这一份精确动作，不是“以后让助手随便处理退款”。审批人必须具有同一商户的 reviewer 角色，且不能由发起该订单请求的客户冒充。

提案在本演示中只保留 15 分钟的执行有效期。审批后真正执行前，订单服务会重新核对当前版本、可退余额、仓库签收与适用规则。期间订单发生变化时，旧提案应失效并重新评估；审批记录不是绕过业务检查的通行证。

执行服务以审批编号建立幂等记录。重复送达相同审批及参数时，返回原有模拟回执，不重复增加退款金额；相同键却携带不同内容必须拒绝。界面必须明确显示 SIMULATED，该回执只是本地教学账本记录，不是银行或第三方支付的到账凭证。

### en

A refund proposal names the order, amount, currency, order version, rule version, business date and policy references. A digest binds these exact fields. A reviewer approves that action, not unlimited future refunds. The reviewer must belong to the same merchant and hold the reviewer role; the requesting customer cannot become that reviewer through a prompt.

In this demonstration a proposal is executable for 15 minutes. Before execution, the order service checks the current order version, remaining balance, warehouse receipt and rule version again. A changed order invalidates the old quote. Approval is not permission to skip business validation.

The execution service stores an idempotency record keyed by approval ID. A repeated identical request returns the existing simulated receipt; different content under the same key is rejected. Receipts must display SIMULATED. They record a local teaching effect and are not proof of settlement by a bank or payment provider.
