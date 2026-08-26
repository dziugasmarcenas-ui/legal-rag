"""Spend protection for a public demo endpoint.

Two layers, because they stop different things:

  per-IP window   stops one bored visitor hammering the endpoint
  daily budget    stops many visitors, or one visitor with many addresses,
                  from running up a bill -- this is the one that protects money

Deliberately in-process and dependency-free. That means the counters reset on
redeploy and are per-instance, which is honest for a single-instance demo and
would be wrong for a real multi-instance service. Redis would be the answer
there; this is not that.
"""

import os
import time

from collections import defaultdict, deque

PER_IP_MAX = int(os.environ.get("RATE_PER_IP_MAX", "5"))
PER_IP_WINDOW = int(os.environ.get("RATE_PER_IP_WINDOW", "60"))
DAILY_BUDGET = int(os.environ.get("DAILY_BUDGET", "300"))


class RateLimiter:
    def __init__(self, per_ip_max=PER_IP_MAX, per_ip_window=PER_IP_WINDOW,
                 daily_budget=DAILY_BUDGET, clock=time.time):
        self.per_ip_max = per_ip_max
        self.per_ip_window = per_ip_window
        self.daily_budget = daily_budget
        self.clock = clock
        self._hits = defaultdict(deque)
        self._day = None
        self._spent_today = 0

    def _roll_day(self, now):
        day = int(now // 86400)
        if day != self._day:
            self._day = day
            self._spent_today = 0

    def check(self, ip):
        """Return None if allowed, or (status_code, message, retry_after)."""
        now = self.clock()
        self._roll_day(now)

        if self._spent_today >= self.daily_budget:
            return (503, "daily_budget_exhausted",
                    int(86400 - (now % 86400)))

        window = self._hits[ip]
        cutoff = now - self.per_ip_window
        while window and window[0] < cutoff:
            window.popleft()

        if len(window) >= self.per_ip_max:
            return (429, "rate_limited", int(window[0] + self.per_ip_window - now) + 1)

        window.append(now)
        self._spent_today += 1
        return None

    def stats(self):
        self._roll_day(self.clock())
        return {"spent_today": self._spent_today,
                "daily_budget": self.daily_budget,
                "per_ip": f"{self.per_ip_max}/{self.per_ip_window}s"}


def client_ip(request):
    """Real client address behind Railway's proxy.

    request.client.host is the proxy, so the first entry of X-Forwarded-For is
    the caller. That header is spoofable, which matters for abuse but not for
    the budget layer -- the daily cap does not depend on it.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
