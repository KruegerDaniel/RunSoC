from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock

from flask import Request


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int
    retry_after: int


class InMemoryIpRateLimiter:
    def __init__(self, *, requests: int, window_seconds: int):
        if requests <= 0:
            raise ValueError("Rate limit requests must be greater than zero.")
        if window_seconds <= 0:
            raise ValueError("Rate limit window must be greater than zero seconds.")

        self.requests = requests
        self.window_seconds = window_seconds
        self._hits = defaultdict(deque)
        self._lock = Lock()

    def check(self, ip_address: str) -> RateLimitDecision:
        now = time.monotonic()
        window_started_at = now - self.window_seconds

        with self._lock:
            hits = self._hits[ip_address]

            while hits and hits[0] <= window_started_at:
                hits.popleft()

            if len(hits) >= self.requests:
                retry_after = max(1, int(hits[0] + self.window_seconds - now))
                return RateLimitDecision(
                    allowed=False,
                    limit=self.requests,
                    remaining=0,
                    reset_seconds=retry_after,
                    retry_after=retry_after,
                )

            hits.append(now)
            remaining = max(0, self.requests - len(hits))
            reset_seconds = max(1, int(hits[0] + self.window_seconds - now))

            return RateLimitDecision(
                allowed=True,
                limit=self.requests,
                remaining=remaining,
                reset_seconds=reset_seconds,
                retry_after=0,
            )


class ConcurrentIpRequestLimiter:
    def __init__(self, *, max_running_requests: int):
        if max_running_requests <= 0:
            raise ValueError("Max running requests must be greater than zero.")

        self.max_running_requests = max_running_requests
        self._running_requests = defaultdict(int)
        self._lock = Lock()

    def acquire(self, ip_address: str) -> bool:
        with self._lock:
            running_requests = self._running_requests[ip_address]

            if running_requests >= self.max_running_requests:
                return False

            self._running_requests[ip_address] += 1
            return True

    def release(self, ip_address: str) -> None:
        with self._lock:
            running_requests = self._running_requests.get(ip_address, 0)

            if running_requests <= 1:
                self._running_requests.pop(ip_address, None)
                return

            self._running_requests[ip_address] = running_requests - 1


def get_client_ip(request: Request, *, trust_proxy_headers: bool) -> str:
    if trust_proxy_headers:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

    return request.remote_addr or "unknown"


def count_request_tasks(data: dict) -> int | None:
    tasks = data.get("tasks")
    if isinstance(tasks, list):
        return len(tasks)

    runnables = data.get("runnables")
    if isinstance(runnables, dict):
        return len(runnables)
    if isinstance(runnables, list):
        return len(runnables)

    return None
