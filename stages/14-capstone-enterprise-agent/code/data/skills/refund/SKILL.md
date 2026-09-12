---
name: refund
description: Explain return eligibility and prepare an exact proposal; never execute a refund.
---

# refund

## zh

你正在处理退货资格或退款请求。先确认订单号来自本次用户问题；没有订单号时，只解释政策或请用户选择订单。读取当前身份可访问的订单，再检索 RETURNS 的时间、仓库签收与金额例外条款。用户指定的金额不能作为支付事实。

使用 calculate_refund 得到净商品余额和可退条件。它会排除运费、扣除既往退款，并核对仓库签收、日期与商品类别。缺少条件时说明原因，不请求别人点击批准来绕过规则。询问能否退款与要求执行退款不同：只有明确退款意图才建议形成提案。

回答说明订单事实、引用条款、报价结果与未完成事项。使用原文提供的证据编号，不创造来源。不能声称已经到账，不能调用 execute_refund，也不能改变用户或审核员身份。等待人工审批时，告诉用户案件编号与待审批金额。对未知商品或冲突条款提出人工处理，不要反复查询相同文本。

自检：第30天仍在窗口；第31天不自动退款；custom/digital 不走本自动流程；仓库未签收不付款；已有退款必须扣减。

## en

Handle return eligibility or a refund request. An order ID must come from this request; without one, explain general policy or ask the customer to select an order. Read the accessible order and retrieve RETURNS pages covering the window, warehouse receipt, amount and exclusions. A user-supplied amount is not a payment fact.

Use calculate_refund for net item balance and eligibility. It excludes freight, subtracts prior refunds and checks receipt, date and category. Explain missing conditions instead of using approval to bypass them. Distinguish an eligibility question from an explicit action request.

Explain facts, references, quote and remaining work. Copy actual evidence IDs; invent none. Never claim settlement, call execute_refund or change customer/reviewer identity. When proposing, identify the pending amount and case. Escalate unsupported products or conflicting clauses rather than repeatedly retrieving the same text.

Check day 30 versus day 31, custom/digital exclusions, absent warehouse receipt and existing refunds.
