<!-- {"id": "INVOICES", "title": "发票与金额说明 / Invoices and payment explanations", "category": "invoice", "tenant": "qinghe", "status": "active", "version": "2026-09", "effective_from": "2026-09-01", "effective_to": null, "fictional": true} -->
# 发票与金额说明 / Invoices and payment explanations

虚构教学材料 / FICTIONAL TRAINING DOCUMENT. Not a real merchant policy or legal advice.

## p01 字段含义 / Invoice fields

### zh

模拟发票包含 invoice_id、currency、total_cents、state 和 customer_label。total_cents 是原始商品净支付与运费之和，不是当前可退余额。客服解释退款金额时，应同时区分原票面总额、运费和已退款项，不能见到发票总额就直接拿去退款。

QH-1001 的票面总额为 14100 分，其中商品 12900 分、运费 1200 分；退款报价排除运费，因此可能低于票面总额。已发生部分退款的订单还要继续扣减既往退款金额。发票查询不修改任何金额或发票状态。

customer_label 是虚构展示标签，不是纳税人身份信息。该演示不会生成真实税务票据，也不能用来报销。客服返回时应保留模拟说明，避免把教学编号误当成正式发票代码。

### en

A simulated invoice contains invoice_id, currency, total_cents, state and customer_label. total_cents is the original net item payment plus shipping, not the current refundable balance. Explain invoice total, shipping and prior refunds separately rather than refunding the invoice total by default.

QH-1001 shows 14,100 cents: 12,900 in items and 1,200 in shipping. A refund excludes shipping and can therefore be lower than the invoice. Previously refunded amounts further reduce remaining item value. Reading an invoice changes no balances or status.

customer_label is a fictional display label, not taxpayer identity. These records are not tax invoices or reimbursement documents. Keep the simulated designation visible.

## p02 访问与交付 / Access and delivery

### zh

查询发票必须先通过订单所有权检查。知道 INV 编号不构成读取权限；本工具使用订单号作为入口，在服务端由订单定位发票，而不是接受任意数据库主键。不可访问订单与不存在订单使用相同错误形式。

助手可以解释已有发票字段或把允许的信息写进案件摘要，但不能把所有客户发票打包给当前用户。工作区导出的文件只包含本次请求实际使用的证据与结果，不应附上整份业务数据库。

若用户只想了解如何获取发票，先解释流程即可，不需要查询每一笔历史订单。工具是否调用由任务需要决定；能调用十个工具，不意味着每次都要把十个都点一遍。

### en

Invoice access first checks order ownership. Knowing an INV identifier is not authorization. The tool accepts an order ID and resolves its invoice on the server rather than exposing arbitrary database keys. Inaccessible and nonexistent orders use the same error form.

The assistant can explain authorized fields or include them in a case report, but cannot export every customer's invoices. An artifact should contain only the evidence and results used in that request, not the entire business database.

A general question about obtaining invoices does not require inspecting every historical order. Tool availability is not a requirement to invoke all tools.

## p03 更正与状态 / Corrections and state

### zh

issued 表示演示系统已有一份模拟发票记录，void 表示对应记录作废。已取消订单可能返回 void，客服应如实说明，不能把它改写为“正在开票”。工具没有更改抬头、重开发票或发送邮件的功能。

涉及抬头错误或金额争议时，助手可以提出需要人工协助，并在用户明确选择后建立工单。工单摘要应包含订单号和问题类型，避免直接复制完整银行账户或身份证照片。

本教程没有对现实税务规则进行建模。因此即使检索到了本页，也只足以说明演示接口能做什么，不足以判断真实发票的法律效力、抵扣资格或税率。

### en

Issued means a simulated invoice record exists; void marks a cancelled record. A cancelled order may return void. Report that state rather than calling it pending issuance. The tools cannot change invoice titles, reissue tax documents or send email.

For a title error or disputed amount, explain the need for human assistance and open a ticket only after explicit user choice. Include the order and issue category, not full bank account details or identity photographs.

No real tax rules are modeled. This page describes demonstration behavior and cannot support conclusions about legal validity, deductibility or tax rates.

## p04 对账例子 / Reconciliation examples

### zh

对 QH-1009，首先查询商品支付和既往退款，再读取原始模拟发票。发票仍记录原付款，不应因为这次查询就减少；可退余额由订单服务记录与退款规则计算。两个接口回答不同问题，数字不相等不一定是错误。

如果模型提出“按发票退全部 141 元”，Host 应忽略这个金额提议并采用 calculate_refund 的可信结果。该工具的输入只有订单号，不接受模型提供的原价、折扣或退款金额，减少低信任数据进入计算的机会。

最终案件记录应注明报价来源、引用条款与模拟回执编号。记录可以帮助核查过程，但它不是不可篡改审计系统，也不替代现实支付机构的账单。

### en

For QH-1009, read net item payment and previous refunds, then the original simulated invoice. The invoice continues to describe the original purchase; reading it does not reduce its value. Remaining refundable balance comes from order facts and the return rule. Different interfaces can correctly answer different monetary questions.

If a model proposes refunding the entire invoice, the Host must use calculate_refund instead. That tool accepts only an order ID, not model-supplied list price, discount or amount, reducing untrusted inputs to arithmetic.

A case report records the quote source, policy references and simulated receipt ID. This helps inspect the workflow but is not a tamper-proof audit system or a replacement for a payment provider's statement.
