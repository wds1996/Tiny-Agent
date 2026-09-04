"""Stage 09 example 3: bounded retry from scratch, then the Tenacity equivalent."""

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from tiny_agent import RetryPolicy, TransientToolError


policy = RetryPolicy(
    max_attempts=4,
    base_delay_seconds=0.5,
    max_delay_seconds=2.0,
    jitter_ratio=0.0,
)

print("Tiny-Agent backoff schedule:")
for retry_number in range(1, policy.max_attempts):
    print(f"retry {retry_number}: {policy.delay_for_retry(retry_number):.1f}s")

calls = 0


def flaky_read():
    global calls
    calls += 1
    if calls < 3:
        raise TransientToolError("Temporary read failure.")
    return "document loaded"


retryer = Retrying(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0, min=0, max=0),
    retry=retry_if_exception_type(TransientToolError),
    reraise=True,
)

print("\nTenacity result:", retryer(flaky_read))
print("Attempts:", calls)

# Important: the retry *library* does not decide whether repeating a side
# effect is safe. Tiny-Agent keeps retry_safe as an application-owned policy.
