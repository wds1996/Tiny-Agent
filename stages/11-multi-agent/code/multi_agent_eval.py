from tiny_agent import RunArtifact


single = RunArtifact(
    output="single-agent answer",
    metrics={
        "quality": 0.84,
        "latency_ms": 650.0,
        "cost_usd": 0.012,
        "agent_call_attempts": 1.0,
    },
)

multi = RunArtifact(
    output="multi-agent answer",
    metrics={
        "quality": 0.90,
        "latency_ms": 1180.0,
        "cost_usd": 0.026,
        "agent_call_attempts": 3.0,
    },
)

quality_gain = multi.metrics["quality"] - single.metrics["quality"]
latency_ratio = multi.metrics["latency_ms"] / single.metrics["latency_ms"]
cost_ratio = multi.metrics["cost_usd"] / single.metrics["cost_usd"]

print(f"Quality gain: {quality_gain:+.2f}")
print(f"Latency ratio: {latency_ratio:.2f}x")
print(f"Cost ratio: {cost_ratio:.2f}x")
print("Agent calls:", int(multi.metrics["agent_call_attempts"]))

if quality_gain >= 0.05 and cost_ratio <= 2.5:
    print("Decision: multi-Agent is worth further evaluation for this slice.")
else:
    print("Decision: prefer the simpler baseline until evidence improves.")

print("A team is an architecture choice, not a participation trophy.")
