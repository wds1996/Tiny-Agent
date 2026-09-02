"""OpenScholar capstone: an integrated academic research Agent."""

from .base_agent import BaseOpenScholarAgent, ResearchAgentConfig
from .corpus import CorpusDocument, LocalResearchCorpus, extract_pdf_text, load_corpus_jsonl, write_corpus_jsonl
from .evaluation import ResearchEvaluation, evaluate_research_report
from .export import MarkdownReportExporter, render_report_markdown
from .heuristic import HeuristicResearchModel
from .langgraph_agent import LangGraphOpenScholarAgent
from .memory import InMemoryResearchMemory, ResearchMemoryStore
from .models import Critique, Evidence, ResearchMetrics, ResearchModel, ResearchPlan, ResearchReport, ResearchRequest
from .openai_adapter import OpenAIResearchModel
from .scholarly import CrossrefScholarlySearch, CrossrefSearchConfig, ScholarlySearchClient, StaticScholarlySearch

__all__ = [
    "BaseOpenScholarAgent",
    "CorpusDocument",
    "Critique",
    "CrossrefScholarlySearch",
    "CrossrefSearchConfig",
    "Evidence",
    "HeuristicResearchModel",
    "InMemoryResearchMemory",
    "LangGraphOpenScholarAgent",
    "LocalResearchCorpus",
    "MarkdownReportExporter",
    "OpenAIResearchModel",
    "ResearchAgentConfig",
    "ResearchEvaluation",
    "ResearchMemoryStore",
    "ResearchMetrics",
    "ResearchModel",
    "ResearchPlan",
    "ResearchReport",
    "ResearchRequest",
    "ScholarlySearchClient",
    "StaticScholarlySearch",
    "evaluate_research_report",
    "extract_pdf_text",
    "load_corpus_jsonl",
    "render_report_markdown",
    "write_corpus_jsonl",
]
