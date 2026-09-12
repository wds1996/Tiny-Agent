"""Only application-chosen artifact paths. No shell or model-written executable code."""
from __future__ import annotations
import hashlib
import html
from pathlib import Path
import os
import tempfile
from domain import BoundaryError


def export_case(root: Path, state: dict) -> str:
    run_id=state['id']
    if len(run_id)!=32 or any(c not in '0123456789abcdef' for c in run_id):
        raise BoundaryError('invalid_artifact_id')
    body='# SIMULATED SUPPORT CASE / 虚构售后案件\n\n'
    body+=f"Case: {run_id}\n\nStatus: {state['status']}\n\n"
    body+=html.escape(state.get('answer',{}).get('answer','No accepted answer.'))+'\n\n'
    if state.get('proposal'):
        q=state['proposal'];body+=f"Pending proposal: {q['order_id']}, CNY {q['amount_cents']/100:.2f}. Not a payment.\n\n"
    if state.get('receipt'):
        body+='SIMULATED receipt: '+html.escape(str(state['receipt']))+'\n\n'
    body+='## Evidence\n\n'
    for item in state.get('answer',{}).get('citations',[]):
        body+='- '+html.escape(item)+'\n'
    encoded=body.encode('utf-8'); name=run_id+'-'+hashlib.sha256(encoded).hexdigest()[:16]+'.md'
    directory=root.resolve()/'artifacts';directory.mkdir(exist_ok=True)
    if directory.is_symlink(): raise BoundaryError('artifact_directory_symlink')
    destination=directory/name
    if destination.exists():
        if destination.is_symlink() or destination.read_bytes()!=encoded: raise BoundaryError('artifact_conflict')
        return str(destination)
    fd,temporary=tempfile.mkstemp(dir=directory,prefix='.pending-')
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(encoded);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return str(destination)
