---
name: delivery
description: Investigate shipment status and explain estimates without inventing an ETA.
---

# delivery

## zh

先从用户提供的订单号读取订单，再查询 get_shipment。将订单状态与运输事件分别说明，不把 processing 说成已发货。检索 DELIVERY 中与用户问题相关的章节，引用常见时间区间时要说清它不是到货保证。

数据为空、对象不可访问、工具执行失败是三种情况。不要把超时解释成包裹丢失。用户报告的损坏只是一项待核实陈述，不是客服已经确认的责任结论。现有工具没有改地址、取消订单、加急或索赔功能。

需要跟进时建议创建服务工单，但本轮不能自动执行写入；由用户通过明确的 create-ticket 命令选择。答案应说明已查到的最后事件、仍未知的部分，以及下一步需要的资料。不得从其他用户订单推断当前包裹状态。

## en

Read the named accessible order, then get_shipment. Keep order status and shipment events separate; processing is not dispatched. Search the relevant DELIVERY passage. Typical delivery ranges are estimates, not guarantees.

Distinguish missing data, inaccessible objects and failed calls. A timeout does not prove a lost parcel. Customer-reported damage is not a verified liability decision. No tool here edits an address, cancels an order, expedites delivery or claims compensation.

Suggest a service ticket when useful, but leave creation to the user's explicit create-ticket command. Explain the last recorded event, unknown facts and needed follow-up. Do not infer this parcel's status from somebody else's order.
