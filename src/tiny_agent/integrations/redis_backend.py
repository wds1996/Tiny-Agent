from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


_RATE_LIMIT_LUA = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    observed: int


class RedisFixedWindowRateLimiter:
    """Small distributed fixed-window limiter for teaching.

    Caller identity is SHA-256 hashed before becoming a Redis key so raw user
    identifiers do not appear in key listings. This is still a simple fixed
    window algorithm, not a globally perfect quota system.
    """

    def __init__(self, client: Any, *, limit: int, window_seconds: int, prefix: str = "tiny-agent:rate") -> None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")
        self.client = client
        self.limit = limit
        self.window_seconds = window_seconds
        self.prefix = prefix

    async def allow(self, subject: str) -> RateLimitDecision:
        if not subject.strip():
            raise ValueError("subject must be non-empty")
        digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()
        key = f"{self.prefix}:{digest}"
        observed = int(await self.client.eval(_RATE_LIMIT_LUA, 1, key, self.window_seconds))
        return RateLimitDecision(
            allowed=observed <= self.limit,
            remaining=max(0, self.limit - observed),
            observed=observed,
        )


class RedisHealthCheck:
    def __init__(self, client: Any) -> None:
        self.client = client

    async def __call__(self) -> bool:
        return bool(await self.client.ping())
