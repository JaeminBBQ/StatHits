"""Rate-limited, retrying client for the official Riot API.

`clock` and `sleep` are injectable so tests can run without real waiting.
Error messages are always built from method, path and status; the API key
and request headers never appear in an exception, `repr` or log line.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Callable, Iterator
from urllib.parse import quote

import httpx

from didyouhit.riot.errors import RiotAuthError, RiotError, RiotNotFoundError, RiotUnavailableError
from didyouhit.riot.routing import account_route, match_route

MAX_ATTEMPTS = 5
BACKOFF_SECONDS = (1.0, 2.0, 4.0, 8.0)
RETRYABLE_STATUSES = (500, 502, 503, 504)
DEFAULT_RETRY_AFTER = 10.0
RATE_LIMIT_SLACK = 0.05  # small buffer beyond the window edge, as in the Phase 1 probe


def _parse_rate_limits(spec: str) -> list[tuple[int, float]]:
    limits: list[tuple[int, float]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        count, _, seconds = part.partition(":")
        limits.append((int(count), float(seconds)))
    return limits


def _retry_after_seconds(response: httpx.Response) -> float:
    raw = response.headers.get("Retry-After")
    try:
        return float(raw) if raw is not None else DEFAULT_RETRY_AFTER
    except ValueError:
        return DEFAULT_RETRY_AFTER


class RiotClient:
    """Sync httpx client with sliding-window rate limits and retries."""

    def __init__(
        self,
        api_key: str,
        rate_limits: str = "20:1,100:120",
        *,
        http: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self._http = http if http is not None else httpx.Client()
        self._clock = clock
        self._sleep = sleep
        self._limits = _parse_rate_limits(rate_limits)
        self._sent: deque[float] = deque()
        self.calls = 0

    def _wait_for_rate_limit(self) -> None:
        """Sleep until every `count:seconds` window has room for one request."""
        max_window = max(seconds for _, seconds in self._limits)
        while True:
            now = self._clock()
            while self._sent and now - self._sent[0] > max_window:
                self._sent.popleft()
            wait = 0.0
            for count, window in self._limits:
                cutoff = now - window
                recent = [sent for sent in self._sent if sent > cutoff]
                if len(recent) >= count:
                    wait = max(wait, window - (now - recent[0]) + RATE_LIMIT_SLACK)
            if wait <= 0:
                return
            self._sleep(wait)

    def _request(
        self, method: str, url: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        path = httpx.URL(url).path
        headers = {"X-Riot-Token": self._api_key, "User-Agent": "didyouhit/0.1"}
        last_status: int | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._wait_for_rate_limit()
            self._sent.append(self._clock())
            self.calls += 1
            try:
                response = self._http.request(method, url, params=params, headers=headers)
            except httpx.TransportError:
                if attempt == MAX_ATTEMPTS:
                    break
                self._sleep(BACKOFF_SECONDS[attempt - 1])
                continue
            last_status = response.status_code
            if response.status_code == 200:
                return response.json()
            if response.status_code == 429:
                if attempt == MAX_ATTEMPTS:
                    break
                self._sleep(_retry_after_seconds(response))
                continue
            if response.status_code in RETRYABLE_STATUSES:
                if attempt == MAX_ATTEMPTS:
                    break
                self._sleep(BACKOFF_SECONDS[attempt - 1])
                continue
            if response.status_code == 404:
                raise RiotNotFoundError(f"Riot API returned 404 for {method} {path}")
            if response.status_code in (401, 403):
                raise RiotAuthError(response.status_code)
            raise RiotError(
                f"Riot API returned unexpected status for {method} {path} (HTTP {response.status_code})"
            )
        raise RiotUnavailableError(
            f"Riot API unavailable after {MAX_ATTEMPTS} attempts: {method} {path} "
            f"(last status {last_status})"
        )

    def get_account(self, game_name: str, tag_line: str, platform: str) -> dict[str, Any]:
        path = (
            f"/riot/account/v1/accounts/by-riot-id/"
            f"{quote(game_name, safe='')}/{quote(tag_line, safe='')}"
        )
        return self._request("GET", f"https://{account_route(platform)}.api.riotgames.com{path}")

    def get_match_ids(
        self,
        puuid: str,
        platform: str,
        *,
        start_time_s: int | None,
        start: int = 0,
        count: int = 100,
    ) -> list[str]:
        params: dict[str, Any] = {"start": start, "count": count}
        if start_time_s is not None:
            params["startTime"] = start_time_s
        url = f"https://{match_route(platform)}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        return list(self._request("GET", url, params))

    def iter_match_ids(self, puuid: str, platform: str, *, start_time_s: int) -> Iterator[str]:
        """Yield all match IDs for a member, paginating 100 at a time."""
        start = 0
        while True:
            page = self.get_match_ids(
                puuid, platform, start_time_s=start_time_s, start=start, count=100
            )
            yield from page
            if len(page) < 100:
                return
            start += len(page)

    def get_match(self, match_id: str, platform: str) -> dict[str, Any]:
        url = f"https://{match_route(platform)}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        return self._request("GET", url)

    def get_timeline(self, match_id: str, platform: str) -> dict[str, Any]:
        url = (
            f"https://{match_route(platform)}.api.riotgames.com"
            f"/lol/match/v5/matches/{match_id}/timeline"
        )
        return self._request("GET", url)
