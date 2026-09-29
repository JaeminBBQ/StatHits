"""The swappable sign-up boundary: invite code + typed Riot ID today, RSO later.

The web layer only ever sees `SignupError` subclasses, so replacing this with
Riot Sign On won't touch routes, ingestion or boards.
"""

from __future__ import annotations

import hmac

from sqlalchemy.orm import Session

from didyouhit.ingest import add_member
from didyouhit.models import Member
from didyouhit.riot.client import RiotClient
from didyouhit.riot.errors import RiotAuthError, RiotError, RiotNotFoundError


class SignupError(Exception):
    """Base class for sign-up failures the web layer can map to messages."""


class InvalidRiotId(SignupError):
    """The Riot ID doesn't look like `Name#TAG`."""


class RiotIdNotFound(SignupError):
    """The Riot ID doesn't exist in that region (HTTP 404)."""


class SignupUnavailable(SignupError):
    """The key is rejected or the API is down; try again later."""


def register_member(
    session: Session,
    client: RiotClient,
    riot_id: str,
    platform: str,
    *,
    now_ms: int,
    backfill_days: int,
) -> Member:
    """Register (or re-activate) a member, translating failures to `SignupError`s."""
    try:
        return add_member(
            session,
            client,
            riot_id,
            platform,
            now_ms=now_ms,
            backfill_days=backfill_days,
        )
    except ValueError as error:
        raise InvalidRiotId(str(error)) from error
    except RiotNotFoundError as error:
        raise RiotIdNotFound from error
    except RiotAuthError as error:
        raise SignupUnavailable from error
    except RiotError as error:
        raise SignupUnavailable from error


def check_invite_code(given: str | None, expected: str | None) -> bool:
    """Constant-time invite code check; no configured code means closed."""
    if not expected or not given:
        return False
    return hmac.compare_digest(given, expected)
