<!-- {"id": "WARRANTY", "title": "商品保修与故障排查 / Warranty and product support", "category": "warranty", "tenant": "qinghe", "status": "active", "version": "2026-09", "effective_from": "2026-09-01", "effective_to": null, "fictional": true} -->
# 商品保修与故障排查 / Warranty and product support

虚构教学材料 / FICTIONAL TRAINING DOCUMENT. Not a real merchant policy or legal advice.

## p01 商品与期间 / Product terms

### zh

桌面支架 DESK-01 与阅读灯 LAMP-02 的教学保修期为 12 个月，连接线 CABLE-03、刻字杯 MUG-04、收纳包 CASE-06 为 6 个月。数字练习册 EBOOK-05 的 warranty_months 为零，表示不采用本实物保修流程，不表示客户没有任何支持渠道。

具体商品型号来自订单或商品目录，不能仅根据用户说“我买的是最贵那款”去选择更长保修期。订单查询与商品目录查询是两项不同能力：前者涉及用户所有权，后者是本商城公开的产品说明。

保修期和普通退货的 30 天窗口是两套规则。送达 90 天的阅读灯 QH-1012 不符合自动原路退款，但仍可咨询故障维修。助手不能把“退款不符合”简化为“售后完全不能处理”。

### en

The teaching warranty is 12 months for DESK-01 stands and LAMP-02 lamps, and six months for CABLE-03 cables, MUG-04 engraved mugs and CASE-06 organizers. EBOOK-05 has warranty_months=0 because it does not use this physical repair workflow, not because no support exists.

Identify the SKU from authorized order facts or the product catalog. A customer's claim to own the premium model does not establish a longer warranty. Order access is private; catalog information is public within the fictional store.

Warranty and the 30-day ordinary return window are separate rules. A 90-day-old lamp such as QH-1012 can be outside automatic refunds while still needing repair support. Do not turn refund ineligibility into a blanket denial of all support.

## p02 排查步骤 / Troubleshooting

### zh

阅读灯不亮时，先询问是否使用匹配电源、接口是否松动、是否已经尝试正常开关。不要要求用户拆解电源、电池或接触带电部件；本知识库不提供电气维修指导。对于发热、异味或外壳破损，建议停止使用并联系人工支持。

排查结果应记录为用户提供的现象，而不是实验室检测结论。没有视频、测量或实物检测时，不应给出确定的故障部件名称。本工具集也无法远程控制设备，不能声称已经重置或修复产品。

一份有用的工单包含订单、型号、出现问题的时间及已经尝试的安全步骤。避免收集与维修无关的个人信息。引用本页只能支持排查流程，不能作为检测成功或保修批准的凭证。

### en

For a lamp that does not turn on, ask about a compatible power supply, a loose connector and ordinary switch operation. Do not ask customers to open power supplies or touch energized components. This corpus is not an electrical repair guide. Heat, unusual smells or enclosure damage should lead to stopping use and contacting human support.

Record observations as customer-reported symptoms rather than laboratory findings. Without inspection or measurements, do not identify a failed component with certainty. The tools cannot remotely control or reset a device.

A useful ticket contains the order, SKU, onset and safe steps already tried, without unrelated personal information. Citing this page supports a procedure, not a successful diagnosis or warranty approval.

## p03 维修与更换 / Repair and replacement

### zh

维修申请需要核对订单、产品类型与症状，必要时由人工判断维修、换货或其他方案。系统不把商品目录中的保修月数直接转成“免费更换已批准”，因为使用情况、损坏原因和具体服务条件尚未核实。

本项目的 create_ticket 可以建立待人工处理的申请，但没有仓库换货、预约上门或支付赔偿的能力。创建成功后应保留工单编号，供 get_ticket 查询当前模拟状态。相同工单请求重放应返回同一编号。

如果现有资料不足，助手应列出缺少的事项，不要通过重复检索同一段话制造证据充足的错觉。一段材料重复出现五次，仍然只是同一个来源。

### en

A repair request needs order facts, product type and symptoms; a human may then choose repair, replacement or another remedy. A catalog warranty duration alone cannot establish that free replacement was approved, since conditions and causes are not verified.

create_ticket opens a request for human handling. The project cannot dispatch a replacement, book an on-site visit or pay compensation. Preserve the ticket ID for get_ticket and replay identical creation requests under the same idempotency key.

When information is incomplete, name the missing facts. Repeatedly retrieving the same paragraph does not create independent supporting evidence. Five copies of one source are still one source.

## p04 无匹配条款 / Unsupported products

### zh

本商城的演示目录没有月球瞬移设备、医疗器械或车辆。遇到这类产品时，不能从阅读灯的保修规则外推，也不能编造一种“行业通常做法”。应明确表示现有材料不覆盖，并请求实际商品编号或交由人工确认。

对于型号拼写不明的情况，可以先查询用户自己的订单列表，让用户选择明确的订单；不要猜一个恰好存在但属于别人的订单号。工具返回不可访问时，不向用户暴露该订单是否真实存在或属于谁。

客户可以补充信息后重新发起请求。上一轮证据不足不是长期黑名单，也不能自动成为用户记忆中的事实。保留的只应是经过同意的有限偏好以及有权限访问的业务记录。

### en

The demonstration catalog contains no lunar teleporters, medical devices or vehicles. Do not extrapolate their support terms from lamp warranties or invent an industry convention. State that the available material does not cover the request and ask for an actual product identifier or human assistance.

If the SKU is unclear, list only the current customer's orders and ask them to choose. Do not guess an existing order belonging to somebody else. An inaccessible result does not authorize revealing whether that order exists or who owns it.

Customers may provide more information and start another request. An insufficient-evidence result is not a permanent blacklist or a durable fact about the person. Retain only consented preferences and properly scoped business records.
