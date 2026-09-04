from __future__ import annotations

from pathlib import Path

from tiny_agent.capstone import (
    BaseOpenScholarAgent,
    HeuristicResearchModel,
    InMemoryResearchMemory,
    LocalResearchCorpus,
    MarkdownReportExporter,
    ResearchAgentConfig,
    load_corpus_jsonl,
)

HERE = Path(__file__).resolve().parent
STAGE_ROOT = HERE.parent
DATA_DIR = STAGE_ROOT / "data"
GENERATED_DIR = STAGE_ROOT / "generated"
EXPORT_DIR = GENERATED_DIR / "exports"


def synthetic_corpus() -> LocalResearchCorpus:
    return LocalResearchCorpus(
        load_corpus_jsonl(DATA_DIR / "synthetic_corpus.jsonl"),
        chunk_size=80,
        overlap=12,
    )


def generated_corpus() -> LocalResearchCorpus:
    path = GENERATED_DIR / "corpus.jsonl"
    if not path.exists():
        raise SystemExit(
            "Generated corpus not found. First run:\n"
            "python stages/15-capstone-enterprise-agent/code/bootstrap_open_corpus.py"
        )
    return LocalResearchCorpus(load_corpus_jsonl(path))


def offline_base_agent(
    *,
    corpus: LocalResearchCorpus | None = None,
    memory: InMemoryResearchMemory | None = None,
    exporter: MarkdownReportExporter | None = None,
) -> BaseOpenScholarAgent:
    return BaseOpenScholarAgent(
        model=HeuristicResearchModel(),
        corpus=corpus or synthetic_corpus(),
        memory=memory or InMemoryResearchMemory(),
        exporter=exporter,
        config=ResearchAgentConfig(
            max_subquestions=3,
            local_top_k=3,
            max_evidence=8,
            max_revisions=1,
            min_local_evidence=1,
            min_local_score=0.01,
        ),
    )
