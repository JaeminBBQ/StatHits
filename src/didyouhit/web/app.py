"""FastAPI app: this week's boards, past weeks, member pages, join, and the
background ingest loop.

Templates live in `web/templates/`, static CSS in `web/static/`. The app owns
one engine + session factory and, per process, one `RiotClient` (created only
when a Riot API key is configured).
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event, Thread

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from didyouhit.boards import BOARDS, BoardDef, BoardEntry, past_weeks, weekly_boards
from didyouhit.config import Settings, get_settings
from didyouhit.db import make_engine, make_session_factory
from didyouhit.riot.client import RiotClient
from didyouhit.riot.routing import PLATFORMS
from didyouhit.signup import (
    InvalidRiotId,
    RiotIdNotFound,
    SignupUnavailable,
    check_invite_code,
    register_member,
)
from didyouhit.web.formatting import (
    board_value,
    format_date,
    format_dt,
    intcomma,
    ordinal,
    reset_countdown,
)
from didyouhit.web.ingest_loop import ingest_loop
from didyouhit.web.queries import get_active_member, member_games
from didyouhit.weeks import week_bounds, week_from_label, week_label, week_start_ms

WEB_DIR = Path(__file__).parent
INGEST_THREAD_NAME = "didyouhit-ingest"

# (section title, board keys in order). From docs/PRODUCT.md -> "Pages".
BOARD_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Big numbers", ("peak_ap", "peak_ad", "peak_health", "largest_crit")),
    (
        "Damage & utility",
        ("damage_to_champions", "damage_mitigated", "ally_heal_shield", "cc_time"),
    ),
    (
        "Per minute",
        (
            "damage_to_champions_per_min",
            "damage_mitigated_per_min",
            "ally_heal_shield_per_min",
            "cc_time_per_min",
        ),
    ),
    ("This week's totals", ("first_places", "games_played")),
)

PLATFORM_LABELS = {
    "na1": "North America",
    "br1": "Brazil",
    "la1": "Latin America North",
    "la2": "Latin America South",
    "euw1": "Europe West",
    "eun1": "Europe Nordic & East",
    "tr1": "Türkiye",
    "ru": "Russia",
    "me1": "Middle East",
    "kr": "Korea",
    "jp1": "Japan",
    "oc1": "Oceania",
    "sg2": "Singapore",
    "tw2": "Taiwan",
    "vn2": "Vietnam",
}

WEEK_LABEL_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _riot_client(settings: Settings) -> RiotClient | None:
    if settings.riot_api_key is None or not settings.riot_api_key.get_secret_value():
        return None
    return RiotClient(settings.riot_api_key.get_secret_value(), rate_limits=settings.rate_limits)


def _board_defs() -> dict[str, BoardDef]:
    return {board.key: board for board in BOARDS}


def _section_views(boards: dict[str, list[BoardEntry]], defs: dict[str, BoardDef]) -> list[dict]:
    return [
        {
            "title": title,
            "boards": [
                {"label": defs[key].label, "unit": defs[key].unit, "entries": boards[key]}
                for key in keys
            ],
        }
        for title, keys in BOARD_SECTIONS
    ]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else get_settings()
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
    templates.env.globals["app_name"] = settings.app_name
    templates.env.globals["week_tz"] = settings.week_tz
    for name, function in (
        ("intcomma", intcomma),
        ("board_value", board_value),
        ("ordinal", ordinal),
        ("format_dt", format_dt),
        ("format_date", format_date),
        ("reset_countdown", reset_countdown),
    ):
        templates.env.filters[name] = function

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.riot_client = _riot_client(settings)
        thread: Thread | None = None
        if settings.ingest_enabled:
            stop_event = Event()
            thread = Thread(
                target=ingest_loop,
                args=(stop_event, settings),
                kwargs={"session_factory": session_factory, "client": app.state.riot_client},
                name=INGEST_THREAD_NAME,
                daemon=True,
            )
            thread.start()
        yield
        if thread is not None:
            stop_event.set()
            thread.join(timeout=10)

    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.engine = engine
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")

    def db_session(request: Request) -> Iterator[Session]:
        with request.app.state.session_factory() as session:
            yield session

    @app.get("/")
    def home(request: Request, session: Session = Depends(db_session)):
        now = _now_ms()
        boards = weekly_boards(session, now, settings.week_tz, limit=settings.display_limit)
        start_ms, end_ms = week_bounds(now, settings.week_tz)
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "week_label": week_label(start_ms, settings.week_tz),
                "reset": reset_countdown(end_ms - now),
                "sections": _section_views(boards, _board_defs()),
            },
        )

    @app.get("/weeks")
    def weeks(request: Request, session: Session = Depends(db_session)):
        defs = _board_defs()
        view = [
            {
                "label": week.label,
                "url": f"/weeks/{week.label}",
                "boards": [
                    {
                        "label": defs[key].label,
                        "unit": defs[key].unit,
                        "winner": week.winners[key],
                    }
                    for key in defs
                ],
            }
            for week in past_weeks(session, _now_ms(), settings.week_tz)
        ]
        return templates.TemplateResponse(
            request=request, name="weeks.html", context={"weeks": view}
        )

    @app.get("/weeks/{label}")
    def week_detail(request: Request, label: str, session: Session = Depends(db_session)):
        if not WEEK_LABEL_RE.fullmatch(label):
            raise HTTPException(status_code=404)
        try:
            start_ms = week_from_label(label, settings.week_tz)
        except ValueError:
            raise HTTPException(status_code=404) from None
        if start_ms > week_start_ms(_now_ms(), settings.week_tz):
            raise HTTPException(status_code=404)
        boards = weekly_boards(session, start_ms, settings.week_tz, limit=10)
        return templates.TemplateResponse(
            request=request,
            name="week.html",
            context={"week_label": label, "sections": _section_views(boards, _board_defs())},
        )

    @app.get("/members/{member_id}")
    def member_page(
        request: Request,
        member_id: int,
        session: Session = Depends(db_session),
        joined: int = 0,
    ):
        member = get_active_member(session, member_id)
        if member is None:
            raise HTTPException(status_code=404)
        return templates.TemplateResponse(
            request=request,
            name="member.html",
            context={
                "member": member,
                "since": format_date(member.created_at_ms, settings.week_tz),
                "joined": bool(joined),
                "games": member_games(session, member_id),
            },
        )

    def join_form(
        request: Request,
        *,
        status_code: int = 200,
        error: str | None = None,
        riot_id: str = "",
        platform: str = "na1",
        closed: bool = False,
    ):
        return templates.TemplateResponse(
            request=request,
            name="join.html",
            context={
                "closed": closed,
                "error": error,
                "riot_id": riot_id,
                "platform": platform,
                "platforms": PLATFORM_LABELS,
            },
            status_code=status_code,
        )

    @app.get("/join")
    def join_page(request: Request):
        if not settings.invite_code:
            return join_form(request, closed=True)
        return join_form(request)

    @app.post("/join")
    def join_submit(
        request: Request,
        session: Session = Depends(db_session),
        riot_id: str = Form(""),
        platform: str = Form("na1"),
        invite_code: str = Form(""),
    ):
        if not settings.invite_code:
            return join_form(request, status_code=403, closed=True)
        if not check_invite_code(invite_code, settings.invite_code):
            return join_form(
                request,
                status_code=403,
                error="That invite code isn't right.",
                riot_id=riot_id,
                platform=platform,
            )
        if platform not in PLATFORMS:
            return join_form(
                request,
                status_code=400,
                error="That region isn't supported.",
                riot_id=riot_id,
            )
        client = request.app.state.riot_client
        if client is None:
            return join_form(
                request,
                status_code=503,
                error="Sign-ups are temporarily unavailable. Try again later.",
                riot_id=riot_id,
                platform=platform,
            )
        try:
            member = register_member(
                session,
                client,
                riot_id.strip(),
                platform,
                now_ms=_now_ms(),
                backfill_days=settings.backfill_days,
            )
        except InvalidRiotId:
            return join_form(
                request,
                status_code=400,
                error="Enter your Riot ID like Name#TAG.",
                riot_id=riot_id,
                platform=platform,
            )
        except RiotIdNotFound:
            return join_form(
                request,
                status_code=404,
                error="We couldn't find that Riot ID in that region.",
                riot_id=riot_id,
                platform=platform,
            )
        except SignupUnavailable:
            return join_form(
                request,
                status_code=503,
                error="Sign-ups are temporarily unavailable. Try again later.",
                riot_id=riot_id,
                platform=platform,
            )
        session.commit()
        return RedirectResponse(url=f"/members/{member.id}?joined=1", status_code=303)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            detail = "That page doesn't exist."
        else:
            detail = str(exc.detail) if exc.detail else "Something went wrong."
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"status": exc.status_code, "detail": detail},
            status_code=exc.status_code,
        )

    return app
