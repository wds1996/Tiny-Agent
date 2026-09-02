"""Stage 08 example 7: LLM-as-judge is an evaluator, not an oracle."""

from tiny_agent import EvalExample, LLMJudgeEvaluator, RunArtifact


class DeterministicDemoJudge:
    """Fake judge for an offline runnable example; no provider/API required."""

    def judge(self, *, rubric, inputs, output, reference_output):
        del rubric, inputs
        if output == reference_output:
            return {"score": 1.0, "comment": "Matches the reference."}
        return {"score": 0.5, "comment": "Partially useful but differs from reference."}


evaluator = LLMJudgeEvaluator(
    key="helpfulness",
    rubric="Score helpfulness from 0 to 1.",
    judge_model=DeterministicDemoJudge(),
)
score = evaluator.evaluate(
    EvalExample("judge-001", {"question": "2+2?"}, reference_output="4"),
    RunArtifact(output="Four."),
)[0]

print(score)
print("\nIn production, calibrate real judges against human labels and track variance.")
