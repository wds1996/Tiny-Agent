"""Stage 08 example 10: current LangSmith @traceable API without network in CI.

To actually upload traces outside CI:

    export LANGSMITH_TRACING=true
    export LANGSMITH_API_KEY=...
    export LANGSMITH_PROJECT=tiny-agent-stage08

This demo explicitly disables submission so it is safe to run offline.
"""

from langsmith import traceable, tracing_context


@traceable(name="tiny-agent-pipeline")
def pipeline(question: str) -> str:
    return question.upper()


with tracing_context(enabled=False):
    print(pipeline("trace me without uploading me"))

print("LangSmith tracing integration loaded; network submission stayed disabled.")
