import pytest

from tiny_agent.observability import (
    InMemorySpanSink,
    LocalTracer,
    TraceCapturePolicy,
    trace_tree_lines,
)


def test_local_tracer_builds_parent_child_trace_tree():
    sink = InMemorySpanSink()
    tracer = LocalTracer(sink)

    with tracer.span("agent", kind="agent") as root:
        with tracer.span("execute_tool search", kind="tool") as child:
            child.set_attribute("tool.name", "search")

    spans = sink.spans
    assert len(spans) == 2
    root_record = next(span for span in spans if span.span_id == root.span_id)
    child_record = next(span for span in spans if span.span_id == child.span_id)
    assert child_record.trace_id == root_record.trace_id
    assert child_record.parent_span_id == root_record.span_id
    assert child_record.attributes["tool.name"] == "search"
    assert trace_tree_lines(spans)[0].startswith("- agent [agent] ok")


def test_default_capture_policy_does_not_store_raw_inputs_or_outputs():
    sink = InMemorySpanSink()
    tracer = LocalTracer(sink)

    with tracer.span("tool", kind="tool") as span:
        span.record_input({"password": "do-not-store", "query": "hello"})
        span.record_output({"token": "secret", "answer": "world"})

    record = sink.spans[0]
    assert record.input_data is None
    assert record.output_data is None


def test_opt_in_capture_redacts_sensitive_keys_and_truncates_text():
    sink = InMemorySpanSink()
    tracer = LocalTracer(
        sink,
        capture_policy=TraceCapturePolicy(
            capture_inputs=True,
            capture_outputs=True,
            max_text_chars=5,
        ),
    )

    with tracer.span("model", kind="model") as span:
        span.record_input({"api_key": "sk-secret", "prompt": "abcdefghij"})
        span.record_output({"answer": "uvwxyz"})

    record = sink.spans[0]
    assert record.input_data["api_key"] == "<redacted>"
    assert "sk-secret" not in str(record.input_data)
    assert record.input_data["prompt"].startswith("abcde")
    assert "<truncated>" in record.input_data["prompt"]
    assert "<truncated>" in record.output_data["answer"]


def test_direct_sensitive_attribute_key_is_redacted_but_token_count_is_not():
    sink = InMemorySpanSink()
    tracer = LocalTracer(sink)

    with tracer.span("request") as span:
        span.set_attribute("authorization", "Bearer hidden")
        span.set_attribute("gen_ai.usage.input_tokens", 123)

    record = sink.spans[0]
    assert record.attributes["authorization"] == "<redacted>"
    assert record.attributes["gen_ai.usage.input_tokens"] == 123


def test_nested_attribute_values_are_sanitized():
    sink = InMemorySpanSink()
    tracer = LocalTracer(sink)

    with tracer.span(
        "request",
        attributes={"auth": {"authorization": "Bearer hidden", "tenant": "demo"}},
    ):
        pass

    assert sink.spans[0].attributes["auth"]["authorization"] == "<redacted>"


def test_exception_marks_span_error_and_is_reraised_without_storing_message():
    sink = InMemorySpanSink()
    tracer = LocalTracer(sink)

    with pytest.raises(RuntimeError, match="secret-db-password"):
        with tracer.span("explode", kind="tool"):
            raise RuntimeError("secret-db-password")

    record = sink.spans[0]
    assert record.status == "error"
    assert record.error_type == "RuntimeError"
    assert "secret-db-password" not in str(record.attributes)
    assert record.input_data is None
    assert record.output_data is None
