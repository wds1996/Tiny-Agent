"""Explicit offline rehearsal: fake model + direct service double, real Host/storage/RAG."""
import asyncio
from pathlib import Path
import tempfile
from agent import SupportAgent
from domain import profile
from replay import ReplayModel, direct_connection
from store import Store


async def main():
    with tempfile.TemporaryDirectory() as tmp:
        store=Store(Path(tmp)); model=ReplayModel()
        agent=SupportAgent(store,model,connection=direct_connection)
        run_id=store.create(profile('alice'),'请退款 QH-1001','zh')
        pending=await agent.drain(run_id,'alice')
        print('OFFLINE REHEARSAL; not a real model or MCP test')
        print('before human decision:',pending['status'])
        # The human step is deliberately NOT performed by the offline demo.
        print('quote:',pending.get('proposal'))
        print('budget:',store.counts(run_id))
        print('events:',store.events(run_id,profile('alice')))


if __name__=='__main__':asyncio.run(main())
