"""Exceptions raised by the Riot API client.

No message here ever contains the API key or request headers; callers build
messages from the method, path and status only.
"""

from __future__ import annotations


class RiotError(Exception):
    """Base class for all Riot API errors."""


class RiotNotFoundError(RiotError):
    """Raised on HTTP 404 (e.g. a match with no data yet)."""


class RiotAuthError(RiotError):
    """Raised on HTTP 401/403: the key is rejected or expired."""

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__("Riot API key rejected or expired (HTTP 4xx)")


class RiotUnavailableError(RiotError):
    """Raised when a request still fails after all retries are exhausted."""
