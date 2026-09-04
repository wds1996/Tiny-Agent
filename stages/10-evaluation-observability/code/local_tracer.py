"""Stage 10 example 2: nested local spans before introducing any platform."""

from tiny_agent import InMemorySpanSink, LocalTracer, trace_tree_lines


sink = InMemorySpanSink()
tracer = LocalTracer(sink)

with tracer.span("research_agent", kind="agent") as root:
    root.set_attribute("task.type", "research")
    with tracer.span("retrieve", kind="retrieval") as retrieval:
        retrieval.set_attribute("retrieval.top_k", 3)
    with tracer.span("execute_tool summarize", kind="tool") as tool:
        tool.set_attribute("tool.name", "summarize")

print("Trace tree:")
for line in trace_tree_lines(sink.spans):
    print(line)

print("\nRaw inputs/outputs are absent by default:")
for span in sink.spans:
    print(span.name, "input=", span.input_data, "output=", span.output_data)
