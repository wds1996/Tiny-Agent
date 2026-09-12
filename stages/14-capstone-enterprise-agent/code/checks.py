"""Run: python checks.py. No LLM bill. The real MCP test skips if SDK 2 is absent."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from agent import SupportAgent
from business import Commerce
from decision import parse_plan, parse_answer, parse_review
from domain import DATA, BoundaryError, digest, encode, object_from_json, profile, refund_quote
from evaluation import evaluate
from mcp_bridge import connect, MCPBridge, HOST_TOOLS
from model import DeepSeekModel
from replay import ReplayModel, direct_connection
from retrieval import KnowledgeBase
from skills import SkillLibrary
from store import Store
from tools import ToolRouter, SPECS, definitions
from workspace import export_case


class FixtureChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.store=Store(self.root)
        self.commerce=Commerce(self.root,profile('alice'));self.kb=KnowledgeBase()

    def quote(self,oid):
        o=self.commerce.get_order(oid)
        return refund_quote({**o,'tenant':'qinghe','user':'alice'},self.commerce.rules,self.commerce.as_of)

    def test_corpus_size_and_unique_passages(self):
        self.assertEqual(len({p.document for p in self.kb.passages}),8)
        self.assertEqual(len({(p.document,p.page) for p in self.kb.passages}),28)
        self.assertEqual({p.language for p in self.kb.passages},{'zh','en'})
        self.assertGreater(len(self.kb.passages),140)

    def test_business_records_are_substantial(self):
        self.assertEqual(len(self.commerce.fixture['orders']),24)
        self.assertEqual(len(self.commerce.fixture['products']),6)
        self.assertTrue(self.commerce.fixture['fictional'])

    def test_rag_filters_archive_and_tenant_before_ranking(self):
        results=self.kb.search('退款 14 天 45 天',tenant='qinghe',language='zh',as_of='2026-09-12',k=6)
        self.assertTrue(results)
        self.assertTrue(all(r['tenant']=='qinghe' and r['status']=='active' for r in results))
        self.assertFalse(any(r['document'] in {'RETURNS_OLD','SOUTH_TERMS'} for r in results))

    def test_future_policy_is_unavailable(self):
        self.assertEqual(self.kb.search('退款',tenant='qinghe',language='zh',as_of='2026-08-01'),[])

    def test_direct_read_cannot_bypass_policy_filter(self):
        with self.assertRaises(BoundaryError):
            self.kb.read('SOUTH_TERMS:p01:zh:0',tenant='qinghe',language='zh',as_of='2026-09-12')
        with self.assertRaises(BoundaryError):
            self.kb.read('RETURNS_OLD:p01:zh:0',tenant='qinghe',language='zh',as_of='2026-09-12')

    def test_bilingual_retrieval(self):
        for lang,query in [('zh','商品净支付 运费 既往退款'),('en','paid item amount prior refund shipping')]:
            found=self.kb.search(query,tenant='qinghe',language=lang,as_of='2026-09-12',k=6)
            self.assertIn('RETURNS:p03',[r['document']+':'+r['page'] for r in found])
            self.assertTrue(all(r['language']==lang for r in found))

    def test_retrieval_eval_reports_unanswerable_as_not_applicable(self):
        report=evaluate();self.assertEqual(len(report['cases']),8)
        self.assertIsNone(report['cases'][-1]['recall_at_4'])

    def test_known_foreign_order_and_unknown_order_have_same_error(self):
        errors=[]
        for oid in ['QH-2001','QH-3001','QH-9999']:
            with self.assertRaises(BoundaryError) as c:self.commerce.get_order(oid)
            errors.append(str(c.exception))
        self.assertEqual(len(set(errors)),1)

    def test_order_list_is_scoped(self):
        self.assertEqual(len(self.commerce.list_orders()['orders']),12)
        self.assertTrue(all(r['order_id'].startswith('QH-10') for r in self.commerce.list_orders()['orders']))

    def test_invoice_is_not_quote(self):
        self.assertEqual(self.commerce.get_invoice('QH-1001')['total_cents'],14100)
        self.assertEqual(self.quote('QH-1001')['amount_cents'],12900)

    def test_partial_refund_balance(self):self.assertEqual(self.quote('QH-1009')['amount_cents'],8000)
    def test_day_30_included(self):self.assertTrue(self.quote('QH-1002')['eligible'])
    def test_day_31_rejected(self):self.assertEqual(self.quote('QH-1003')['reason'],'outside_window')
    def test_warehouse_required(self):self.assertEqual(self.quote('QH-1004')['reason'],'return_not_received')
    def test_shipment_not_delivery(self):self.assertEqual(self.quote('QH-1005')['reason'],'not_delivered')
    def test_custom_excluded(self):self.assertEqual(self.quote('QH-1007')['reason'],'excluded_category')
    def test_fully_refunded(self):self.assertEqual(self.quote('QH-1010')['reason'],'already_refunded')

    def test_south_merchant_is_not_given_qinghe_automatic_policy(self):
        com=Commerce(self.root,profile('lin'));order=com.get_order('QH-3001')
        quote=refund_quote({**order,'tenant':'south','user':'lin'},com.rules,com.as_of)
        self.assertEqual(quote['reason'],'merchant_requires_manual_review')

    def test_ticket_replay_and_scope(self):
        a=self.commerce.create_ticket('QH-1005','Please inspect shipment.','request-one')
        b=self.commerce.create_ticket('QH-1005','Please inspect shipment.','request-one')
        self.assertEqual(a,b)
        with self.assertRaises(BoundaryError):self.commerce.create_ticket('QH-1005','Different request','request-one')
        with self.assertRaises(BoundaryError):Commerce(self.root,profile('bob')).get_ticket(a['ticket_id'])

    def test_skills_are_progressively_loaded(self):
        library=SkillLibrary();self.assertEqual(len(library.discover()),5)
        self.assertNotIn('procedure',library.discover()[0])
        self.assertIn('calculate_refund',library.load('refund','zh'))
        self.assertIn('calculate_refund',library.load('refund','en'))
        with self.assertRaises(BoundaryError):library.load('../RETURNS','zh')

    def test_no_financial_write_in_model_registry(self):
        self.assertEqual(len(SPECS),12)
        self.assertNotIn('execute_refund',SPECS);self.assertNotIn('create_ticket',SPECS)
        self.assertTrue({'execute_refund','create_ticket'}<=HOST_TOOLS)
        self.assertTrue(all(not d['function']['parameters']['additionalProperties'] for d in definitions()))

    def test_preference_requires_consent_and_is_scoped(self):
        with self.assertRaises(BoundaryError):self.store.remember(profile('alice'),'en',consent=False)
        self.store.remember(profile('alice'),'en',consent=True)
        self.assertEqual(Store(self.root).preference(profile('alice')),{'language':'en'})
        self.assertEqual(self.store.preference(profile('bob')), {})

    def test_json_duplicate_and_nonfinite_rejected(self):
        for value in ['{"x":1,"x":2}','{"x":NaN}','[]']:
            with self.assertRaises(BoundaryError):object_from_json(value)

    def test_plan_cannot_invent_order(self):
        p={'intent':'refund','order_id':'QH-1002','action_requested':True,'queries':['退款'],'steps':['read']}
        with self.assertRaises(BoundaryError):parse_plan(encode(p),'请退款 QH-1001')

    def test_answer_cannot_invent_citation(self):
        with self.assertRaises(BoundaryError):parse_answer(encode({'answer':'x','citations':['fake'],'next_action':'answer'}),{'real'})

    def test_reviewer_contract(self):
        with self.assertRaises(BoundaryError):parse_review('{"verdict":"approve_payment","feedback":"x"}')

    def test_run_access_is_scoped(self):
        rid=self.store.create(profile('alice'),'hello','zh')
        with self.assertRaises(BoundaryError):self.store.get(rid,profile('bob'))

    def test_two_workers_and_expired_token(self):
        rid=self.store.create(profile('alice'),'hello','zh');state,token=self.store.claim(rid,profile('alice'))
        with self.assertRaises(BoundaryError):self.store.claim(rid,profile('alice'))
        with self.store.session() as c:c.execute('UPDATE runs SET lease_until=0 WHERE id=?',(rid,))
        new,new_token=self.store.claim(rid,profile('alice'))
        with self.assertRaises(BoundaryError):self.store.save(state,token)
        with self.assertRaises(BoundaryError):self.store.heartbeat(rid,token)
        new.update(status='queued',phase='plan');self.store.save(new,new_token)

    def test_budget_survives_failed_work_and_retry(self):
        rid=self.store.create(profile('alice'),'hello','zh');state,token=self.store.claim(rid,profile('alice'))
        for _ in range(20):self.store.consume(rid,token,'model')
        with self.assertRaises(BoundaryError):self.store.consume(rid,token,'model')
        self.store.fail(state,token,'test');self.store.retry(rid,profile('alice'))
        _,token2=self.store.claim(rid,profile('alice'))
        with self.assertRaises(BoundaryError):self.store.consume(rid,token2,'model')

    def test_artifact_id_cannot_escape(self):
        with self.assertRaises(BoundaryError):export_case(self.root,{'id':'../elsewhere','status':'completed'})

    def test_artifact_replay_matches_bytes(self):
        state={'id':'a'*32,'status':'completed','answer':{'answer':'<script>not executable</script>','citations':[]}}
        first=export_case(self.root,state);self.assertEqual(first,export_case(self.root,state))
        self.assertIn('&lt;script&gt;',Path(first).read_text())

    def test_trace_drops_raw_prompt_fields(self):
        rid=self.store.create(profile('alice'),'private test text','zh')
        self.store.event(rid,'test',question='secret',response='secret',count=1)
        self.assertNotIn('secret',encode(self.store.events(rid,profile('alice'))))

    def test_real_subprocess_can_read_checkpoint(self):
        rid=self.store.create(profile('alice'),'a case retained across processes','zh')
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('demo.py')),'--state-dir',str(self.root),
                               'inspect',rid],text=True,capture_output=True,check=True,timeout=10)
        self.assertIn(rid,result.stdout)


class WorkflowChecks(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.store=Store(self.root)
        self.model=ReplayModel();self.agent=SupportAgent(self.store,self.model,connection=direct_connection)

    async def pending(self,question='请退款 QH-1001'):
        rid=self.store.create(profile('alice'),question,'zh')
        state=await self.agent.drain(rid,'alice')
        return rid,state

    async def approve(self,rid,state):
        self.store.review(rid,profile('chen'),state['approval_digest'],approve=True)

    async def test_full_case_waits_without_effect(self):
        rid,state=await self.pending()
        self.assertEqual(state['status'],'waiting_approval')
        self.assertEqual(state['proposal']['amount_cents'],12900)
        self.assertEqual(Commerce(self.root,profile('alice')).get_order('QH-1001')['refunded_cents'],0)
        self.assertEqual(self.store.counts(rid)['model'],5)

    async def test_question_does_not_auto_propose(self):
        _,state=await self.pending('QH-1001 能退款吗？')
        self.assertEqual(state['status'],'completed');self.assertNotIn('proposal',state)

    async def test_late_order_does_not_wait_for_approval(self):
        _,state=await self.pending('请退款 QH-1003')
        self.assertEqual(state['status'],'completed');self.assertNotIn('approval_digest',state)

    async def test_customer_cannot_review(self):
        rid,state=await self.pending()
        with self.assertRaises(BoundaryError):self.store.review(rid,profile('alice'),state['approval_digest'],approve=True)

    async def test_other_merchant_cannot_review(self):
        rid,state=await self.pending()
        with self.assertRaises(BoundaryError):self.store.review(rid,profile('mei'),state['approval_digest'],approve=True)

    async def test_wrong_digest_and_repeated_review(self):
        rid,state=await self.pending()
        with self.assertRaises(BoundaryError):self.store.review(rid,profile('chen'),'0'*64,approve=True)
        await self.approve(rid,state)
        with self.assertRaises(BoundaryError):self.store.review(rid,profile('chen'),state['approval_digest'],approve=True)

    async def test_reject_has_no_effect(self):
        rid,state=await self.pending();self.store.review(rid,profile('chen'),state['approval_digest'],approve=False)
        self.assertEqual((await self.agent.drain(rid,'alice'))['status'],'rejected')
        self.assertEqual(Commerce(self.root,profile('alice')).get_order('QH-1001')['refunded_cents'],0)

    async def test_unapproved_effect_rejected_at_service(self):
        rid,_=await self.pending()
        with self.assertRaises(BoundaryError):Commerce(self.root,profile('alice')).execute_refund(rid)

    async def test_approved_receipt_survives_replay(self):
        rid,state=await self.pending();await self.approve(rid,state)
        result=await self.agent.drain(rid,'alice')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['receipt'],Commerce(self.root,profile('alice')).execute_refund(rid))
        self.assertEqual(Commerce(self.root,profile('alice')).get_order('QH-1001')['refunded_cents'],12900)
        self.assertTrue(Path(result['artifact']).is_file())

    async def test_concurrent_same_approval_does_not_duplicate_effect(self):
        rid,state=await self.pending();await self.approve(rid,state)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(lambda _:Commerce(self.root,profile('alice')).execute_refund(rid),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(Commerce(self.root,profile('alice')).get_order('QH-1001')['refunded_cents'],12900)

    async def test_two_old_quotes_cannot_refund_twice(self):
        one,a=await self.pending();two,b=await self.pending()
        await self.approve(one,a);await self.approve(two,b)
        self.assertEqual((await self.agent.drain(one,'alice'))['status'],'completed')
        second=await self.agent.drain(two,'alice')
        self.assertEqual(second['status'],'failed')
        self.assertEqual(second['error'],'quote_stale_or_ineligible')

    async def test_expired_approval_rejected(self):
        rid,state=await self.pending()
        with self.store.session() as c:c.execute('UPDATE approvals SET created=0 WHERE id=?',(rid,))
        with self.assertRaises(BoundaryError):await self.approve(rid,state)

    async def test_order_version_change_invalidates_quote(self):
        rid,state=await self.pending();await self.approve(rid,state)
        commerce=Commerce(self.root,profile('alice'))
        with commerce.session() as c:
            o=commerce._owned(c,'QH-1001');o['version']+=1
            c.execute('UPDATE orders SET payload=? WHERE id=?',(encode(o),'QH-1001'))
        self.assertEqual((await self.agent.drain(rid,'alice'))['status'],'failed')

    async def test_lost_receipt_then_resume_reconciles_existing_effect(self):
        rid,state=await self.pending();await self.approve(rid,state)
        @asynccontextmanager
        async def lost(root,name):
            class B:
                async def call(self,tool,args):
                    Commerce(root,profile(name)).call(tool,args)
                    raise BoundaryError('simulated_response_lost')
            yield B()
        broken=SupportAgent(self.store,self.model,connection=lost)
        failed=await broken.drain(rid,'alice');self.assertEqual(failed['status'],'failed')
        self.store.retry(rid,profile('alice'))
        result=await self.agent.drain(rid,'alice')
        self.assertEqual(result['status'],'completed')
        self.assertEqual(Commerce(self.root,profile('alice')).get_order('QH-1001')['refunded_cents'],12900)

    async def test_step_can_resume_with_new_agent_and_store(self):
        rid=self.store.create(profile('alice'),'请退款 QH-1001','zh')
        first=await self.agent.work_once(rid,'alice');self.assertEqual(first['phase'],'investigate')
        other=SupportAgent(Store(self.root),ReplayModel(),connection=direct_connection)
        self.assertEqual((await other.drain(rid,'alice'))['status'],'waiting_approval')

    async def test_missing_evidence_cannot_be_hidden_by_fabricated_citation(self):
        class Bad(ReplayModel):
            async def call(self,**kw):
                result=await super().call(**kw)
                if kw['purpose']=='answer':result['text']=encode({'answer':'unsupported','citations':['invented'],'next_action':'answer'})
                return result
        rid=self.store.create(profile('alice'),'请退款 QH-1001','zh')
        result=await SupportAgent(self.store,Bad(),connection=direct_connection).drain(rid,'alice')
        self.assertEqual(result['status'],'needs_input')

    async def test_reviewer_cannot_approve_payment(self):
        class Bad(ReplayModel):
            async def call(self,**kw):
                result=await super().call(**kw)
                if kw['purpose']=='review':result['text']=encode({'verdict':'approve_payment','feedback':'x'})
                return result
        rid=self.store.create(profile('alice'),'请退款 QH-1001','zh')
        result=await SupportAgent(self.store,Bad(),connection=direct_connection).drain(rid,'alice')
        self.assertEqual(result['status'],'failed')
        self.assertEqual(Commerce(self.root,profile('alice')).get_order('QH-1001')['refunded_cents'],0)

    async def test_false_refund_intent_cannot_skip_approval(self):
        # Even a mistaken plan never gets a model-owned financial execution tool.
        rid,state=await self.pending('请退款 QH-1001 for 99999')
        self.assertEqual(state['proposal']['amount_cents'],12900)
        self.assertEqual(state['status'],'waiting_approval')

    async def test_shipping_and_invoice_paths(self):
        for q,name in [('QH-1005 物流状态','get_shipment:QH-1005'),('QH-1001 发票总额','get_invoice:QH-1001')]:
            _,state=await self.pending(q);self.assertEqual(state['status'],'completed');self.assertIn(name,state['facts'])

    async def test_model_cannot_switch_orders_or_add_identity_arguments(self):
        rid=self.store.create(profile('alice'),'请退款 QH-1001','zh');await self.agent.work_once(rid,'alice')
        state,token=self.store.claim(rid,profile('alice'))
        async with direct_connection(self.root,'alice') as b:
            router=ToolRouter(state,b,KnowledgeBase(),SkillLibrary(),lambda k:self.store.consume(rid,token,k))
            with self.assertRaises(BoundaryError):await router.execute('get_order',{'order_id':'QH-1002'})
            with self.assertRaises(BoundaryError):await router.execute('get_order',{'order_id':'QH-1001','user':'bob'})
            with self.assertRaises(BoundaryError):await router.execute('execute_refund',{'approval_id':'x'})


class AdditionalBoundaryChecks(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name))

    async def test_create_rejects_empty_question_and_unknown_language(self):
        for question, language in [("", "zh"), ("x", "unknown"), ("x" * 1801, "en")]:
            with self.assertRaises(BoundaryError):
                self.store.create(profile("alice"), question, language)

    async def test_order_id_can_touch_chinese_text(self):
        plan = {"intent": "refund", "order_id": "qh-1001", "action_requested": True,
                "queries": ["退款"], "steps": ["查订单"]}
        result = parse_plan(encode(plan), "请退款QH-1001并给出依据")
        self.assertEqual(result["order_id"], "QH-1001")
        for question in ["QH-10011", "ABCQH-1001", "QH-1001-EXTRA"]:
            with self.assertRaises(BoundaryError):
                parse_plan(encode(plan), question)

    async def test_invalid_lease_durations(self):
        rid = self.store.create(profile("alice"), "Hello", "en")
        for seconds in [0, -1, True, float("nan"), float("inf")]:
            with self.assertRaises(BoundaryError):
                self.store.claim(rid, profile("alice"), seconds=seconds)

    async def test_reviewer_reads_exact_proposal_but_other_tenant_cannot(self):
        rid = self.store.create(profile("alice"), "请退款 QH-1001", "zh")
        agent = SupportAgent(self.store, ReplayModel(), connection=direct_connection)
        await agent.drain(rid, "alice")
        record = self.store.approval_for(rid, profile("chen"))
        self.assertEqual(record["payload"]["quote"]["amount_cents"], 12900)
        for identity in [profile("alice"), profile("mei")]:
            with self.assertRaises(BoundaryError):
                self.store.approval_for(rid, identity)

    async def test_model_request_budget_survives_failed_phase_retry(self):
        class Failed(ReplayModel):
            async def call(self, **kwargs):
                kwargs["budget"]("model")
                raise ConnectionError("synthetic provider error")
        rid = self.store.create(profile("alice"), "Hello", "en")
        agent = SupportAgent(self.store, Failed(), connection=direct_connection)
        state = await agent.work_once(rid, "alice")
        self.assertEqual(state["status"], "failed")
        self.assertEqual(self.store.counts(rid)["model"], 1)
        self.store.retry(rid, profile("alice"))
        await agent.work_once(rid, "alice")
        self.assertEqual(self.store.counts(rid)["model"], 2)

    async def test_successful_retry_does_not_keep_old_error(self):
        rid = self.store.create(profile("alice"), "Hello", "en")
        state, token = self.store.claim(rid, profile("alice"))
        self.store.fail(state, token, "old_failure")
        self.store.retry(rid, profile("alice"))
        result = await SupportAgent(self.store, ReplayModel(), connection=direct_connection).work_once(rid, "alice")
        self.assertNotIn("error", result)

    async def test_case_note_is_selected_but_not_a_long_term_preference(self):
        rid = self.store.create(profile("alice"), "QH-1001能退款吗", "zh")
        agent = SupportAgent(self.store, ReplayModel(), connection=direct_connection)
        await agent.work_once(rid, "alice")
        state, token = self.store.claim(rid, profile("alice"))
        router = ToolRouter(state, None, KnowledgeBase(), SkillLibrary(), lambda k: None)
        await router.execute("save_case_note", {"note": "Need to distinguish freight from item balance."})
        self.assertEqual(len(router.context()["case_notes"]), 1)
        self.assertEqual(self.store.preference(profile("alice")), {})

    async def test_reviewer_rejection_allows_one_rewrite_not_two(self):
        class Rejecting(ReplayModel):
            async def call(self, **kwargs):
                result = await super().call(**kwargs)
                if kwargs["purpose"] == "review":
                    result["text"] = encode({"verdict": "revise", "feedback": "Still missing a condition."})
                return result
        rid = self.store.create(profile("alice"), "QH-1001能退款吗", "zh")
        state = await SupportAgent(self.store, Rejecting(), connection=direct_connection).drain(rid, "alice")
        self.assertEqual(state["repairs"], 1)
        self.assertEqual(state["status"], "needs_input")

    async def test_live_eval_preview_does_not_require_credentials(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("live_eval.py"))],
                                capture_output=True, text=True, encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn("No requests sent", result.stdout)

    async def test_top_k_requires_a_positive_integer(self):
        for k in [True, 0, -1, 7, 1.5]:
            with self.assertRaises(BoundaryError):
                KnowledgeBase().search("refund", tenant="qinghe", language="en", as_of="2026-09-12", k=k)


class AdapterChecks(unittest.IsolatedAsyncioTestCase):
    def fake(self, response):
        class API:
            def __init__(self): self.requests=[]
            async def create(self,**kw):self.requests.append(kw);return response
        api=API();return NS(chat=NS(completions=api)),api

    async def test_live_adapter_uses_json_and_reports_unknown_usage(self):
        response=NS(choices=[NS(finish_reason='stop',message=NS(content='{}',tool_calls=None))],usage=None)
        client,api=self.fake(response);charged=[]
        result=await DeepSeekModel(client=client,model='test').call(purpose='plan',instructions='Return JSON',payload={'question':'x'},budget=charged.append)
        self.assertEqual(charged,['model']);self.assertIsNone(result['usage'])
        self.assertEqual(api.requests[0]['response_format'],{'type':'json_object'})
        self.assertEqual(api.requests[0]['extra_body']['thinking']['type'],'disabled')

    async def test_tool_history_returns_matching_call_id(self):
        response=NS(choices=[NS(finish_reason='tool_calls',message=NS(content=None,tool_calls=[NS(id='call-one',type='function',function=NS(name='get_order',arguments='{"order_id":"QH-1001"}'))]))],usage=None)
        client,api=self.fake(response);model=DeepSeekModel(client=client,model='test')
        result=await model.call(purpose='investigate',instructions='Tools',payload={},budget=lambda k:None,tools=definitions())
        history=[result['assistant'],{'role':'tool','tool_call_id':'call-one','content':'{"ok":true}'}]
        await model.call(purpose='investigate',instructions='Tools',payload={},budget=lambda k:None,tools=definitions(),history=history)
        self.assertEqual(api.requests[-1]['messages'][-1]['tool_call_id'],'call-one')

    async def test_incomplete_provider_response_rejected(self):
        client,_=self.fake(NS(choices=[NS(finish_reason='length',message=NS())],usage=None))
        with self.assertRaises(BoundaryError):await DeepSeekModel(client=client,model='test').call(purpose='plan',instructions='JSON',payload={},budget=lambda k:None)

    async def test_context_budget_checked_before_network(self):
        client,api=self.fake(None)
        with self.assertRaises(BoundaryError):await DeepSeekModel(client=client,model='test').call(purpose='plan',instructions='JSON',payload={'x':'a'*40000},budget=lambda k:None)
        self.assertEqual(api.requests,[])

    async def test_mcp_errors_are_not_successful_facts(self):
        class C:
            async def call_tool(self,*args):return NS(is_error=True,structured_content={'secret':'no'})
        with self.assertRaises(BoundaryError):await MCPBridge(C()).call('get_order',{'order_id':'x'})

    @unittest.skipUnless(importlib.util.find_spec('mcp') is not None,'MCP SDK 2 is not installed; real stdio integration NOT tested')
    async def test_real_mcp_stdio_discovery_and_customer_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            async with connect(Path(tmp),'alice') as bridge:
                self.assertEqual(set(await bridge.discover()),HOST_TOOLS)
                data=await bridge.call('get_order',{'order_id':'QH-1001'})
                self.assertEqual(data['paid_items_cents'],12900)
                with self.assertRaises(BoundaryError):await bridge.call('get_order',{'order_id':'QH-2001'})


if __name__=='__main__': unittest.main(verbosity=2)
