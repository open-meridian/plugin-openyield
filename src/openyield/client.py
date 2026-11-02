"""OpenYield's Data Services API, and its stand-in.

OpenYield (openyld.com; its public documentation at docs.openyld.com/dataapi,
OpenAPI 1.3.0) answers `GET` requests at `https://api.openyld.com` with JSON,
every number a string. The plugin asks these paths, and nothing else:

- `/reference/security/{id}` -- a security's identifiers, class and name,
  to resolve it (by ISIN, CUSIP or FIGI);
- `/prices/search?id={id}` -- its top of book on OpenYield's ATS: bid and
  ask prices, yields and size buckets;
- `/prices/intraday/{id}` and `/prices/daily/{id}` -- its mids through
  today and at each day's end (about three months back);
- `/prices/yield_curve` -- the live US Treasury benchmark curve;
- `/reported/security/recent/{id}` and `/reported/security/{date}/{id}` --
  its prints as FINRA's TRACE or MSRB disseminates them, resold.

**The credential.** OpenYield's documented sign-in is a user's email and
password exchanged at `/auth/login` for a bearer token. The plugin never
holds a password: it takes a bearer token the deployment's admin pastes in
its one secret setting, sent as `Authorization: Bearer <token>` and nowhere
else. Whether OpenYield issues a token that does not expire, or a service
credential, is asked of OpenYield (ruling 871); until it does, a token
expires as OpenYield sets it, and the plugin says so when it is refused.

**Pacing is the plugin's** (ruling 1028). OpenYield states one limit, 5,000
calls a day to `/reference/security/{id}`; the plugin asks one request at a
time, at most two a second, reads a security's reference once a day, and
waits out a 429's `retry-after` (a minute where none is said).

`SyntheticOpenYield` answers from the answers committed under sample/, made
in the shape of OpenYield's public documentation's examples, so the plugin's
tests and sample data run offline, the same on any day.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from importlib import resources
from typing import Any, Protocol

BASE = "https://api.openyld.com"
USER_AGENT = "meridian-openyield (+https://github.com/open-meridian/plugin-openyield)"
TIMEOUT = 60.0
MOST_BYTES = 32 * 1024 * 1024
#: The least time between two requests, in seconds.
SPACING = 0.5
#: How long a 429 with no `retry-after` is waited out, in seconds.
RETRY_SECONDS = 60.0


class Unreachable(Exception):  # noqa: N818 - what OpenYield was
    """OpenYield could not be asked: no answer, or not in time."""


class NoToken(Exception):  # noqa: N818 - what the plugin lacks
    """No token is set, so OpenYield is not asked."""


@dataclass(frozen=True)
class Fetched:
    """One answer of OpenYield's, as received: the path asked, the status
    and the answer's text. It never holds the token."""

    path: str
    status: int
    body: str
    fetched_at: datetime

    @property
    def ok(self) -> bool:
        return self.status == 200

    @property
    def error(self) -> str:
        """OpenYield's own words for a refusal, or the status."""
        if self.status == 401:
            return "OpenYield refused the token: it has expired or is not one OpenYield issued"
        try:
            said = json.loads(self.body)
        except ValueError:
            said = None
        if isinstance(said, dict):
            for name in ("detail", "message", "error"):
                if said.get(name):
                    return f"{self.path} answered {self.status}: {str(said[name])[:200]}"
        return f"{self.path} answered {self.status}"


class OpenYield(Protocol):
    mode: str
    calls: int
    rate_limited: int
    failed: str
    last_call_at: str

    def today(self, now: datetime) -> date: ...

    async def get(self, path: str) -> Fetched: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


def redacted(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


def quoted(value: str) -> str:
    return urllib.parse.quote(value, safe="")


@dataclass
class LiveOpenYield:
    """OpenYield itself, asked with `token` (see the module)."""

    token: str = field(repr=False)
    now: Callable[[], datetime] = utc_now
    mode: str = "live"
    calls: int = 0
    rate_limited: int = 0
    failed: str = ""
    last_call_at: str = ""
    _last: float = 0.0
    _not_before: float = 0.0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def today(self, now: datetime) -> date:
        return now.date()

    async def get(self, path: str) -> Fetched:
        if not self.token:
            raise NoToken("no OpenYield token is set")
        async with self._lock:
            wait = max(self._last + SPACING, self._not_before) - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self.calls += 1
            self.last_call_at = self.now().isoformat(timespec="seconds")
            try:
                got, after = await asyncio.to_thread(self._get, path)
            except Unreachable as failed:
                self.failed = str(failed)
                raise
            finally:
                self._last = time.monotonic()
        if got.status == 429:
            self.rate_limited += 1
            self._not_before = time.monotonic() + after
        self.failed = "" if got.ok else got.error
        return got

    def _get(self, path: str) -> tuple[Fetched, float]:
        request = urllib.request.Request(
            BASE + path,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        after = RETRY_SECONDS
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:  # noqa: S310 - OpenYield's https address
                raw = answer.read(MOST_BYTES + 1)
                status = answer.status
        except urllib.error.HTTPError as refused:
            raw = refused.read(MOST_BYTES + 1) if refused.fp else b""
            status = refused.code
            try:
                after = float(refused.headers.get("retry-after", "") or RETRY_SECONDS)
            except ValueError:
                after = RETRY_SECONDS
        except (urllib.error.URLError, TimeoutError, OSError) as failed:
            reason = getattr(failed, "reason", failed)
            raise Unreachable(f"{BASE}{path}: {type(reason).__name__}") from failed
        if len(raw) > MOST_BYTES:
            raise Unreachable(f"{BASE}{path}: answered more than {MOST_BYTES} bytes")
        text = redacted(raw.decode("utf-8", errors="replace"), self.token)
        return Fetched(path, status, text, self.now()), after


class SyntheticOpenYield:
    """The answers committed under sample/ (sample/answers.json): each path
    answered as recorded there, a security's by any of its identifiers, and
    anything else with OpenYield's 404."""

    mode = "synthetic"

    def __init__(self, now: Callable[[], datetime] = utc_now) -> None:
        self._now = now
        held = resources.files(__package__).joinpath("sample")
        recorded = json.loads(held.joinpath("answers.json").read_text(encoding="utf-8"))
        self.today_is = date.fromisoformat(recorded["today"])
        self.securities: dict[str, dict[str, Any]] = recorded["securities"]
        self.curve: dict[str, Any] = recorded["yield_curve"]
        self.aliases: dict[str, str] = {}
        for isin, held_one in self.securities.items():
            reference = held_one["reference"]["security"]
            for name in ("isin", "cusip", "figi"):
                if reference.get(name):
                    self.aliases[str(reference[name]).upper()] = isin
        self.asked: list[str] = []
        self.calls = 0
        self.rate_limited = 0
        self.failed = ""
        self.last_call_at = ""

    def today(self, now: datetime) -> date:
        """The recording's last day, whatever the clock says."""
        return self.today_is

    def _answer(self, path: str) -> tuple[int, Any]:
        route, _, query = path.partition("?")
        parts = [urllib.parse.unquote(p) for p in route.strip("/").split("/")]
        asked = dict(urllib.parse.parse_qsl(query))
        if parts == ["prices", "yield_curve"]:
            return 200, self.curve
        if parts == ["prices", "search"]:
            isin = self.aliases.get(asked.get("id", "").upper())
            book = self.securities[isin]["top_of_book"] if isin else None
            return 200, {"as_of": book["as_of"] if book else None,
                         "results": [book["result"]] if book else []}  # fmt: skip
        isin = self.aliases.get(parts[-1].upper()) if parts else None
        if isin is None:
            return 404, {"detail": "Security not found"}
        held = self.securities[isin]
        if parts[:2] == ["reference", "security"]:
            return 200, held["reference"]
        if parts[:2] == ["prices", "intraday"]:
            return 200, held["intraday"]
        if parts[:2] == ["prices", "daily"]:
            return 200, held["daily"]
        if parts[:3] == ["reported", "security", "recent"]:
            return 200, held["prints"]
        if parts[:2] == ["reported", "security"] and len(parts) == 4:
            on_day = [p for p in held["prints"]["prints"] if p["as_at"].startswith(parts[2])]
            return 200, {**held["prints"], "prints": on_day}
        return 404, {"detail": "Not Found"}

    async def get(self, path: str) -> Fetched:
        self.calls += 1
        self.last_call_at = self._now().isoformat(timespec="seconds")
        self.asked.append(path)
        status, said = self._answer(path)
        return Fetched(path, status, json.dumps(said), self._now())


def openyield(synthetic: bool, token: str, now: Callable[[], datetime] = utc_now) -> OpenYield:
    return SyntheticOpenYield(now) if synthetic else LiveOpenYield(token, now)
