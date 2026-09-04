"""Stage 09 example 1: typed failures and model-safe redaction."""

from tiny_agent import TransientToolError, failure_from_exception


unexpected = RuntimeError("database password=super-secret-value")
redacted = failure_from_exception(unexpected)

print("Unexpected exception -> model observation")
print(redacted.observation())
print("Internal type retained for later audit:", redacted.internal_exception_type)

safe_transient = TransientToolError("Upstream service is temporarily unavailable.")
classified = failure_from_exception(safe_transient)

print("\nExplicit safe operational failure -> model observation")
print(classified.observation())
print("Retryable:", classified.retryable)

# The important rule is not "never show errors". It is:
#
# known + deliberately sanitized error -> may cross the model boundary
# arbitrary exception text            -> stays internal
