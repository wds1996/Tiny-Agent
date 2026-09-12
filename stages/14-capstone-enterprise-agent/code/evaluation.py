"""Retrieval component evaluation; fixed labels stay out of model inputs."""
from __future__ import annotations
import argparse
import json
from retrieval import KnowledgeBase
from domain import DATA

CASES=(
 ('refund-date','送达后30天包含第30天仓库签收','RETURNS:p02'),
 ('refund-amount','净支付 商品金额 运费 既往退款','RETURNS:p03'),
 ('approval','审批 15分钟 摘要 幂等回执','RETURNS:p04'),
 ('shipping','发货 配送 3至5个工作日 预计','DELIVERY:p02'),
 ('invoice','发票 票面总额 商品净支付 运费','INVOICES:p01'),
 ('warranty','阅读灯 保修 12个月 30天退货','WARRANTY:p01'),
 ('privacy','私人订单 向量索引 身份 数据最小化','AGREEMENT:p02'),
 ('unknown','lunar teleportation quantum service',None),
)


def evaluate():
    kb=KnowledgeBase(); rows=[]
    for case_id,query,expected in CASES:
        found=kb.search(query,tenant='qinghe',language='zh',as_of='2026-09-12',k=4)
        ids=[p['document']+':'+p['page'] for p in found]
        rr=next((1/(i+1) for i,v in enumerate(ids) if v==expected),0) if expected else None
        rows.append({'case':case_id,'ranked_pages':ids,'recall_at_4':int(expected in ids) if expected else None,'reciprocal_rank':rr})
    applicable=[r for r in rows if r['recall_at_4'] is not None]
    return {'kind':'offline retrieval, NOT LLM answer quality','cases':rows,
            'mean_recall_at_4':sum(r['recall_at_4'] for r in applicable)/len(applicable),
            'mrr_at_4':sum(r['reciprocal_rank'] for r in applicable)/len(applicable),
            'unanswerable_note':'Non-empty retrieval may still be irrelevant. An unanswerable case needs end-to-end abstention evaluation, not a perfect recall score.'}


if __name__=='__main__': print(json.dumps(evaluate(),ensure_ascii=False,indent=2))
