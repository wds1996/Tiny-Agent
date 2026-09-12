"""Explicit test doubles. These are NOT the application's live entry point."""
from __future__ import annotations
from contextlib import asynccontextmanager
import re
from business import Commerce
from domain import encode, profile


@asynccontextmanager
async def direct_connection(root,profile_name):
    """In-process business double for offline tests, not an MCP transport."""
    class Direct:
        async def call(self,name,arguments): return Commerce(root,profile(profile_name)).call(name,arguments)
    yield Direct()


class ReplayModel:
    """Scripted decisions test the same Host path without measuring LLM quality."""
    def __init__(self): self.requests=[]

    async def call(self,*,purpose,instructions,payload,budget,tools=None,history=None):
        budget('model');self.requests.append((purpose,payload))
        result={'calls':[],'usage':None}
        if purpose=='plan':
            question=payload['question'];lower=question.lower()
            intent=('refund' if any(w in lower for w in ('refund','退款','退货')) else
                    'invoice' if any(w in lower for w in ('invoice','发票')) else
                    'delivery' if any(w in lower for w in ('delivery','shipment','物流','配送')) else
                    'warranty' if any(w in lower for w in ('warranty','保修')) else 'policy')
            match=re.search(r'QH-\d{4}',question)
            result['text']=encode({'intent':intent,'order_id':match.group() if match else None,
                 'action_requested':any(w in lower for w in ('please refund','请退款')),
                 'queries':[intent], 'steps':['read records','read effective policy','answer with references']})
        elif purpose=='investigate':
            if not history:
                plan=payload['plan'];oid=plan['order_id'];intent=plan['intent']
                args=[('search_knowledge',{'query':{'refund':'退货退款 30 天 运费 净支付' if payload['language']=='zh' else 'refund return thirty days shipping amount',
                        'delivery':'配送 物流 事件' if payload['language']=='zh' else 'delivery shipment events',
                        'invoice':'发票 总额 原始支付' if payload['language']=='zh' else 'invoice total original payment',
                        'warranty':'保修 维修 商品' if payload['language']=='zh' else 'warranty product repair'}.get(intent,payload['question'])})]
                if oid:
                    args.append(('get_order',{'order_id':oid}))
                    if intent=='refund':args.append(('calculate_refund',{'order_id':oid}))
                    if intent=='invoice':args.append(('get_invoice',{'order_id':oid}))
                    if intent=='delivery':args.append(('get_shipment',{'order_id':oid}))
                calls=[{'id':f'call-{i}','name':n,'arguments':a} for i,(n,a) in enumerate(args)]
                result.update(text='',calls=calls,assistant={'role':'assistant','content':None,
                     'tool_calls':[{'id':c['id'],'type':'function','function':{'name':c['name'],'arguments':encode(c['arguments'])}} for c in calls]})
            else:result['text']='Research complete (scripted test).'
        elif purpose=='answer':
            citations=[e['id'] for e in payload['evidence']]+list(payload['facts'])
            if payload['plan']['order_id'] and not payload['facts']:
                action='needs_input';answer='订单不可访问，需要确认订单。 / The order is not accessible.'
            elif not citations:
                action='needs_input';answer='资料不足 / Insufficient evidence.'
            elif payload.get('quote',{} ) and payload['quote']['eligible'] and payload['plan']['action_requested']:
                action='request_refund';answer='可准备待审批的模拟退款提案，尚未付款。 / Eligible for a pending simulated refund proposal, not paid.'
            else:
                action='answer';answer='请参考所列的虚构政策和已查询事实。 / See the cited fictional policy and observed facts.'
            result['text']=encode({'answer':answer,'citations':citations[:16],'next_action':action})
        elif purpose=='review':result['text']=encode({'verdict':'pass','feedback':'scripted contract test only'})
        else:raise ValueError(purpose)
        return result

    async def close(self):pass
