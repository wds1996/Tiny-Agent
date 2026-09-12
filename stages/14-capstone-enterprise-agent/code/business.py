"""A separate, identity-scoped, fictional commerce service behind MCP."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import time

from domain import DATA, BoundaryError, Identity, digest, encode, refund_quote, text
from store import Store


class Commerce:
    def __init__(self, root: Path, identity: Identity):
        self.root, self.identity = Path(root).resolve(), identity
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "commerce.db"
        self.fixture = json.loads((DATA / "business.json").read_text(encoding="utf-8"))
        self.rules = json.loads((DATA / "refund_rules.json").read_text(encoding="utf-8"))
        with self.session() as c:
            c.execute("CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, tenant TEXT, user TEXT, payload TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS effects(key TEXT PRIMARY KEY,payload_hash TEXT,receipt TEXT)")
            c.execute("CREATE TABLE IF NOT EXISTS tickets(id TEXT PRIMARY KEY,tenant TEXT,user TEXT,payload TEXT)")
            for order in self.fixture["orders"]:
                c.execute("INSERT OR IGNORE INTO orders VALUES(?,?,?,?)", (order["order_id"],order["tenant"],order["user"],encode(order)))

    @contextmanager
    def session(self):
        c = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA synchronous=FULL")
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    @property
    def as_of(self):
        return self.fixture["as_of"]

    def _owned(self, c, order_id: str) -> dict:
        row = c.execute("SELECT payload FROM orders WHERE id=? AND tenant=? AND user=?",
                        (order_id,self.identity.tenant,self.identity.user)).fetchone()
        if row is None:
            raise BoundaryError("order_not_accessible")
        return json.loads(row[0])

    def get_order(self, order_id: str) -> dict:
        with self.session() as c:
            order = self._owned(c, order_id)
        return {k:v for k,v in order.items() if k not in {"shipment","invoice","tenant","user"}}

    def list_orders(self) -> dict:
        with self.session() as c:
            rows = c.execute("SELECT payload FROM orders WHERE tenant=? AND user=? ORDER BY id LIMIT 30",
                             (self.identity.tenant,self.identity.user)).fetchall()
        return {"orders":[{k:o[k] for k in ('order_id','sku','status')} for o in map(lambda r:json.loads(r[0]),rows)]}

    def get_shipment(self, order_id: str) -> dict:
        with self.session() as c:
            return {"order_id":order_id,**self._owned(c,order_id)["shipment"]}

    def get_invoice(self, order_id: str) -> dict:
        with self.session() as c:
            return self._owned(c,order_id)["invoice"]

    def get_product(self, sku: str) -> dict:
        for product in self.fixture["products"]:
            if product["sku"] == sku:
                return product
        raise BoundaryError("product_not_found")

    def get_ticket(self, ticket_id: str) -> dict:
        with self.session() as c:
            row=c.execute("SELECT payload FROM tickets WHERE id=? AND tenant=? AND user=?",
                          (ticket_id,self.identity.tenant,self.identity.user)).fetchone()
        if row is None:
            raise BoundaryError("ticket_not_accessible")
        return json.loads(row[0])

    def create_ticket(self, order_id: str, summary: str, idempotency_key: str) -> dict:
        summary=text(summary,maximum=1500)
        key='ticket:'+digest([asdict(self.identity),text(idempotency_key,maximum=100)])
        request=digest([order_id,summary])
        with self.session() as c:
            self._owned(c,order_id)
            old=c.execute("SELECT * FROM effects WHERE key=?",(key,)).fetchone()
            if old:
                if old['payload_hash']!=request: raise BoundaryError('idempotency_conflict')
                return json.loads(old['receipt'])
            receipt={'ticket_id':'T-'+key[-16:],'order_id':order_id,'summary':summary,'status':'open','simulated':True}
            c.execute("INSERT INTO tickets VALUES(?,?,?,?)",(receipt['ticket_id'],self.identity.tenant,self.identity.user,encode(receipt)))
            c.execute("INSERT INTO effects VALUES(?,?,?)",(key,request,encode(receipt)))
            return receipt

    def execute_refund(self, approval_id: str) -> dict:
        approval=Store(self.root).approval(approval_id)
        payload=approval['payload']
        if approval['status']!='approved' or payload['identity']!=asdict(self.identity):
            raise BoundaryError('approved_action_required')
        if digest(payload)!=approval['digest']:
            raise BoundaryError('corrupt_approval')
        reviewer=json.loads(approval['reviewer'])
        if reviewer['role']!='reviewer' or reviewer['tenant']!=self.identity.tenant or reviewer['user']==self.identity.user:
            raise BoundaryError('reviewer_scope_denied')
        # Demo profiles are the local authorization registry. No remote auth is claimed.
        if reviewer not in self.fixture['profiles'].values():
            raise BoundaryError('reviewer_revoked')
        quote=payload['quote']; key='refund:'+approval_id
        with self.session() as c:
            old=c.execute("SELECT * FROM effects WHERE key=?",(key,)).fetchone()
            if old:
                if old['payload_hash']!=approval['digest']: raise BoundaryError('idempotency_conflict')
                return json.loads(old['receipt'])
            if time.time()-approval['created']>900: raise BoundaryError('approval_expired')
            order=self._owned(c,quote['order_id'])
            current=refund_quote(order,self.rules,self.as_of)
            if current!=quote or not current['eligible']:
                raise BoundaryError('quote_stale_or_ineligible')
            order['refunded_cents']+=quote['amount_cents']; order['version']+=1
            receipt={'receipt_id':'SIM-'+approval_id,'order_id':order['order_id'],
                     'amount_cents':quote['amount_cents'],'currency':'CNY','simulated':True}
            c.execute("UPDATE orders SET payload=? WHERE id=?",(encode(order),order['order_id']))
            c.execute("INSERT INTO effects VALUES(?,?,?)",(key,approval['digest'],encode(receipt)))
            return receipt

    def call(self, name: str, arguments: dict) -> dict:
        allowed={'list_orders','get_order','get_shipment','get_invoice','get_product','get_ticket','create_ticket','execute_refund'}
        if name not in allowed: raise BoundaryError('unknown_commerce_tool')
        try:
            return getattr(self,name)(**arguments)
        except TypeError as exc:
            raise BoundaryError('invalid_commerce_arguments') from exc
