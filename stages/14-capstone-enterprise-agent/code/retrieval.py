"""Page-aware bilingual BM25 retrieval. Scores rank passages; they are not probabilities."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import re

from domain import DATA, BoundaryError, text


@dataclass(frozen=True)
class Passage:
    id: str
    document: str
    title: str
    page: str
    language: str
    tenant: str
    status: str
    effective_from: str
    effective_to: str | None
    version: str
    category: str
    body: str


def terms(value: str) -> list[str]:
    english = re.findall(r"[a-z0-9]+", value.lower())
    chinese = re.findall(r"[\u4e00-\u9fff]+", value)
    return english + [s[i:i+2] for s in chinese for i in range(max(1, len(s)-1))]


class KnowledgeBase:
    def __init__(self, directory: Path = DATA / "knowledge"):
        self.passages: list[Passage] = []
        for path in sorted(directory.glob("*.md")):
            content = path.read_text(encoding="utf-8")
            header = content.splitlines()[0]
            meta = json.loads(header.removeprefix('<!-- ').removesuffix(' -->'))
            pages = re.split(r"^## (p\d{2}) (.+)$", content, flags=re.M)
            for i in range(1, len(pages), 3):
                page, heading, body = pages[i:i+3]
                languages = re.split(r"^### (zh|en)\s*$", body, flags=re.M)
                for j in range(1, len(languages), 2):
                    language, prose = languages[j], languages[j+1].strip()
                    # Each authored paragraph is a coherent chunk; no arbitrary word slicing.
                    for number, paragraph in enumerate(prose.split('\n\n')):
                        if len(paragraph) > 2500:
                            raise BoundaryError('paragraph_requires_editorial_split')
                        self.passages.append(Passage(
                            id=f"{meta['id']}:{page}:{language}:{number}", document=meta['id'],
                            title=meta['title']+' / '+heading, page=page, language=language,
                            tenant=meta['tenant'], status=meta['status'],
                            effective_from=meta['effective_from'], effective_to=meta['effective_to'],
                            version=meta['version'], category=meta['category'], body=paragraph))
        if len({p.id for p in self.passages}) != len(self.passages):
            raise BoundaryError('duplicate_passage_id')
        self.by_id = {p.id:p for p in self.passages}

    @staticmethod
    def eligible(p: Passage, tenant: str, language: str, as_of: str) -> bool:
        return (p.tenant == tenant and p.language == language and p.status == 'active'
                and p.effective_from <= as_of and (p.effective_to is None or as_of < p.effective_to))

    def search(self, query: str, *, tenant: str, language: str, as_of: str, k: int = 4) -> list[dict]:
        text(query,maximum=500)
        if type(k) is not int or not 1 <= k <= 6: raise BoundaryError('invalid_top_k')
        # Filter BEFORE scoring: relevance must not become an access-control decision.
        pool = [p for p in self.passages if self.eligible(p,tenant,language,as_of)]
        counts = [Counter(terms(p.title+' '+p.body)) for p in pool]
        lengths = [sum(c.values()) for c in counts]
        average = sum(lengths)/len(lengths) if lengths else 1
        query_terms = set(terms(query))
        ranked = []
        for passage, count, length in zip(pool,counts,lengths):
            score = 0.0
            for term in query_terms:
                frequency = count[term]
                if frequency == 0: continue
                df = sum(term in c for c in counts)
                idf = math.log(1+(len(pool)-df+0.5)/(df+0.5))
                score += idf * frequency*2.5/(frequency+1.5*(0.25+0.75*length/average))
            if score > 0:
                ranked.append({**asdict(passage),'score':round(score,6)})
        return sorted(ranked,key=lambda p:(-p['score'],p['id']))[:k]

    def read(self, passage_id: str, *, tenant: str, language: str, as_of: str) -> dict:
        p=self.by_id.get(passage_id)
        if p is None or not self.eligible(p,tenant,language,as_of):
            raise BoundaryError('passage_not_accessible')
        return asdict(p)

    def page(self, page_id: str, *, tenant: str, language: str, as_of: str) -> list[dict]:
        found=[asdict(p) for p in self.passages if f'{p.document}:{p.page}'==page_id
               and self.eligible(p,tenant,language,as_of)]
        if not found: raise BoundaryError('policy_page_not_accessible')
        return found
