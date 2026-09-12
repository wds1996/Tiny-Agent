---
name: invoice
description: Explain a simulated invoice and distinguish invoice total from refundable value.
---

# invoice

## zh

先查询订单所有权，再读取 get_invoice；必要时 get_product 补充商品型号。引用 INVOICES 解释总额、状态和模拟标识。不能把票面总额当成本次退款金额；涉及可退余额时必须查询 calculate_refund。

用户只问发票流程时不需要遍历所有订单。发票工具只读，不能更改抬头、重开发票或发送邮件。遇到争议可建议人工工单，但不能宣称真实税务系统已更新。

答案分清原商品净支付、运费和既往退款，并引用实际取得的来源。不对真实税务效力或抵扣资格下结论，明确这是一份教学模拟发票。

## en

Verify order access and read get_invoice; use get_product only if the SKU matters. Cite INVOICES for totals, states and simulation labeling. Invoice total is not refundable balance; use calculate_refund when the latter is requested.

A general invoice question need not enumerate all orders. Tools are read-only: no title edits, reissuance or email. Suggest human follow-up for disputes without claiming a tax system changed.

Separate net items, shipping and prior refunds. Cite obtained sources and explain that the invoice is fictional; make no real tax-validity or deductibility determination.
