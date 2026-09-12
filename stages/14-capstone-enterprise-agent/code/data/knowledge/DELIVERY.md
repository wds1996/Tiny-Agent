<!-- {"id": "DELIVERY", "title": "青禾配送与异常件处理手册 / Delivery operations", "category": "delivery", "tenant": "qinghe", "status": "active", "version": "2026-09", "effective_from": "2026-09-01", "effective_to": null, "fictional": true} -->
# 青禾配送与异常件处理手册 / Delivery operations

虚构教学材料 / FICTIONAL TRAINING DOCUMENT. Not a real merchant policy or legal advice.

## p01 状态解释 / Reading shipment states

### zh

订单状态与物流事件不是同一个字段。processing 表示订单仍在商户处理，shipped 表示已经交给承运流程，delivered 才表示订单服务登记送达。物流事件的日期可以帮助解释经过，但不能为了让退款满足窗口而修改订单的正式送达日期。

客服查询配送时，应先确认订单属于当前客户，再读取承运商、教学运单号与事件列表。运单以 DEMO- 开头，承运商为虚构 Demo Express；不能把这些编号放进真实快递网站要求查询。订单不存在和不属于当前用户应返回相同的不可访问提示。

QH-1005 是尚未送达的收纳包，适合演示物流查询；QH-1006 仍在处理，不能把“正在处理”说成“包裹已经上路”。如果事件为空，助手应报告没有可用事件，而不是填补一个看似合理的运输过程。

### en

Order status and shipment events are separate fields. Processing means merchant preparation; shipped means the carrier workflow has begun; delivered means the order service recorded delivery. Shipment dates help explain the timeline but do not authorize changing the official delivery date to qualify for a return.

First check customer ownership, then read the carrier, demonstration tracking ID and event list. DEMO-prefixed numbers and Demo Express are fictional and must not be presented as trackable real parcels. Unknown and unauthorized orders use the same inaccessible response.

QH-1005 is an undelivered organizer; QH-1006 is still processing. Do not translate processing into dispatched. Empty events mean no available events, not permission to invent a plausible journey.

## p02 承诺与预计时间 / Estimates versus guarantees

### zh

标准配送通常安排在发货后 3 至 5 个工作日完成，但该区间是教学服务目标，不是每笔订单的确定到达时间。偏远地区、地址不完整、节假日或承运异常可能需要更长时间。仅凭规则中的区间不能替某个订单算出精确到小时的承诺。

物流查询返回的是已经发生的事件。如果用户要求“保证明天上午九点送到”，现有工具无法作出这种保证。助手应区分已记录事实、规则中的常见区间和未知信息，必要时建议建立配送查询工单。

询问时间时可以引用本页，解释依据来自哪版手册，同时保留订单事件来源。不得把历史案例的配送速度当成当前订单的预计时间，也不得根据用户急切程度自动升级为付费加急服务。

### en

Standard delivery targets three to five working days after dispatch. This is a fictional service target, not a guaranteed arrival time for every parcel. Remote areas, incomplete addresses, holidays and carrier exceptions can extend the interval. A general range cannot support an exact hourly promise.

Shipment tools return recorded events. They cannot guarantee arrival tomorrow at 9 a.m. Distinguish observed facts, typical policy ranges and unknown information; suggest a delivery inquiry ticket when useful.

Cite this page for the general estimate and the shipment result for order-specific events. Do not treat an old case's speed as a new parcel's ETA or silently upgrade the customer to a paid priority service.

## p03 地址变更与取消 / Changes and cancellation

### zh

正在处理的订单可以提出地址变更或取消请求，但本毕业项目没有直接改地址、取消订单或修改商品数量的工具。客服只能说明当前状态与规则，收集所需信息后由人工处理；不能因为模型能生成一个新地址，就宣称配送系统已更新。

已经发货的订单不能承诺立即截停。建立工单时，摘要应描述请求与订单状态，不包含身份证号、完整支付凭证或不必要的住址。工单创建是一次低风险业务写入，但也必须使用稳定幂等键，避免重复点击创建多份相同请求。

对于已取消的 QH-1011，应首先说明当前记录已经取消，而不是再运行一遍取消流程。用户只是询问政策时不应自动创建工单；需要明确的用户选择或在 CLI 中执行创建工单的动作。

### en

For processing orders a customer may request an address change or cancellation, but this capstone exposes no direct address-edit, cancel-order or quantity-edit tool. Explain the recorded state and leave the change to a human. Generating a new address does not update a delivery system.

Dispatched parcels cannot be promised an immediate interception. A ticket summary should contain the request and relevant status, not identity documents, payment credentials or unnecessary addresses. Ticket creation is a business write and uses a stable idempotency key.

QH-1011 is already cancelled, so explain that fact rather than attempting another cancellation. A policy inquiry alone should not create a ticket: the user must explicitly choose that action through the application.

## p04 丢失或破损 / Missing and damaged parcels

### zh

如果用户报告包裹破损或丢失，当前记录只能证明服务端有哪些物流事件，不能证明用户陈述属实或虚假。助手应以“用户报告”表述未经核验的信息，并建议保留照片、包装、收货记录等材料由人工核实，不能自动判定欺诈。

本项目不接收二进制附件，也没有承运商索赔接口。能够执行的是查询现有物流、解释处理步骤和创建带有订单关联的工单。索赔金额、赔付责任与付款操作不在这些工具权限之内。

工单关闭与款项到账是不同事件。即使工单已经建立，也应说“已创建模拟服务工单”，而不是“问题已经解决”。回答需同时指出已完成的操作和仍需人工处理的事项，让下一位客服能够继续。

### en

A report of loss or damage is a customer statement. Shipment records alone do not prove or disprove it. Attribute unverified statements to the customer and suggest retaining photographs, packaging and delivery records for human review; do not automatically classify fraud.

The project accepts no binary attachments and exposes no carrier-claims API. It can read shipment events, explain the procedure and create an order-linked ticket. Compensation amounts, liability decisions and payments are outside these tool permissions.

Creating or closing a ticket is not equivalent to financial settlement. Say that a simulated service ticket was created and identify what still needs human work, rather than announcing that the entire incident is resolved.
