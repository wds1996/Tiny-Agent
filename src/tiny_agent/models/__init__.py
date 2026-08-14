"""Model-provider adapters for Tiny-Agent."""

from .openai import OpenAIResponsesModel
from .openai_structured import OpenAIStructuredDecisionModel

__all__ = [
    "OpenAIResponsesModel",
    "OpenAIStructuredDecisionModel",
]
