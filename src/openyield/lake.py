"""The plugin's `data` role class: OpenYield's marketplace and the prints it
resells into the lake, for the securities the deployment lists and any a
reader wants.

**What it reads, and when** (`check`, at start and every five minutes, or at
once when the settings change):

- the live Treasury benchmark curve (`marketplace`, rates);
- for each listed security: its top of book on the ATS (`marketplace`,
  quotes) and today's intraday mids (`marketplace`, prices); and its recent
  prints (`trace_prints` or `msrb_prints`, by its class);
- once a day: each listed security's reference, to resolve it to the
  deployment's record, and its daily mids back three months.

**What the lake wants** (`on_observations_wanted`): a security's mid for a
date, its quote, the curve, or its prints over a range -- read from
OpenYield and recorded against the want, a standing want kept current by
the check until withdrawn. A subject OpenYield does not cover is declined
`not_covered`.

It mints nothing: a security is resolved with what OpenYield states of it
(its FIGI where stated, its ISIN and CUSIP, kept on the deployment's record
and never sent, ruling 976), and what the deployment does not hold is a
miss. OpenYield's benchmark curve is its own, kept as a local record whose
rates are recorded once a person accepts it at the Instruments page.
"""

from __future__ import annotations

import logging
import urllib.parse
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import meridian
from meridian.operations import Rate
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles import data
from meridian.roles.data import rates

from . import marketplace, prints, read
from .client import NoToken, OpenYield, Unreachable, openyield

log = logging.getLogger("openyield")

KEYS = (marketplace.KEY, prints.TRACE, prints.MSRB)
AWAITS = "its record awaits a person's acceptance at the Instruments page"
#: How many days of prints a want with no range reaches back: OpenYield
#: serves the last seven without a history subscription.
PRINT_DAYS = 7
QUOTE = "meridian.v1.Quote"
PRICE = "meridian.v1.Price"
RATE = "meridian.v1.Rate"


@dataclass(frozen=True)
class Held:
    """A security the plugin resolved: its ISIN, whether it is municipal
    (its prints MSRB's), its description."""

    isin: str
    muni: bool
    name: str = ""


@dataclass
class Status:
    checked_at: str = ""
    last_error: str = ""
    curve_record: str = ""
    securities: dict[str, dict[str, str]] = field(default_factory=dict)
    unread: dict[str, int] = field(default_factory=dict)
    refused: dict[str, str] = field(default_factory=dict)

    def said(self, what: str) -> None:
        self.unread[what] = self.unread.get(what, 0) + 1


def _quoted(identifier: str) -> str:
    return urllib.parse.quote(identifier, safe="")


class Lake(data.Role):
    """The data role's class (see the module)."""

    def __init__(
        self,
        source: OpenYield | None = None,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        super().__init__()
        self.source: OpenYield = source or openyield(False, "")
        self.now = now
        self.wants = data.Wants(self, KEYS, clock_ns=self.clock_ns)
        self.feed = rates.Feed(self, marketplace.SOURCE, wants=self.wants,
                               day_zone="America/New_York", clock_ns=self.clock_ns)  # fmt: skip
        self.securities: tuple[str, ...] = ()
        self.has_token = False
        self.status = Status()
        self.venue = data.Venue()
        self.curve = ""
        #: Each security held, by its record, and each listed one's record.
        self.held: dict[str, Held] = {}
        self.records: dict[str, str] = {}
        #: The day the references and daily mids were last read, and for
        #: which securities.
        self.daily: tuple[date, tuple[str, ...]] | None = None
        #: Each print sent unasked, by its row key: sent once.
        self.printed: set[str] = set()

    def clock_ns(self) -> int:
        return int(self.now().timestamp() * 1e9)

    def use(self, source: OpenYield, securities: tuple[str, ...], has_token: bool) -> None:
        self.source = source
        self.securities = securities
        self.has_token = has_token

    def today(self) -> date:
        return self.source.today(self.now())

    def raw(self, key: str) -> ops.RawRecordRef:
        held: ops.RawRecordRef = self.plugin.raw_record(key[:256])
        return held

    # ── Asking OpenYield ─────────────────────────────────────────────────

    async def ask(self, path: str) -> dict[str, Any] | None:
        """OpenYield's answer to one path; None, the failure said, where it
        did not answer."""
        try:
            got = await self.source.get(path)
        except NoToken:
            return None
        except Unreachable as failed:
            self.status.last_error = str(failed)
            return None
        if not got.ok:
            if got.status != 404:
                self.status.last_error = got.error
            return None
        return read.parse(got.body)

    # ── Records ──────────────────────────────────────────────────────────

    async def venue_id(self) -> str:
        """OpenYield's ATS in the venue master, by its MIC, asked once."""
        return await self.venue.resolve(self, (("iso10383", marketplace.MIC, ""),),
                                        marketplace.SOURCE, self.clock_ns())  # fmt: skip

    async def curve_record(self) -> str:
        """OpenYield's benchmark curve's local record, once a person has
        accepted it (see the module)."""
        if self.curve:
            return self.curve
        named = [ops.Identifier(scheme="symbol", value=marketplace.CURVE_SYMBOL,
                                source=marketplace.SOURCE)]  # fmt: skip
        found = await self.resolve_identifier(
            identifiers=named, as_of_ns=self.clock_ns(), stated_asset_class="referential",
            stated_instrument_type="rate_curve", stated_currency="USD",
            stated_description=marketplace.CURVE_DESCRIPTION,
        )  # fmt: skip
        if not (found.found and found.instrument_id):
            self.status.curve_record = ops.MissReason.Name(found.miss_reason or 1)
            return ""
        record = str(found.instrument_id)
        self.status.curve_record = record
        read_back = await self.resolve_instrument(instrument_id=record, as_of_ns=self.clock_ns())
        accepted = not read_back.found or (
            read_back.instrument.asset_class == ops.ASSET_CLASS_REFERENTIAL
            and read_back.instrument.instrument_type == ops.INSTRUMENT_TYPE_RATE_CURVE
        )
        if not accepted:
            self.status.refused["the benchmark curve's record"] = AWAITS
            return ""
        self.status.refused.pop("the benchmark curve's record", None)
        self.curve = record
        return record

    async def resolve(self, identifier: str) -> str:
        """A listed security resolved, from OpenYield's reference for it;
        empty, the miss reported, where the deployment holds none."""
        answer = await self.ask(f"/reference/security/{_quoted(identifier)}")
        security = (answer or {}).get("security")
        row = self.status.securities.setdefault(identifier, {})
        if not isinstance(security, dict):
            row["record"] = "not covered by OpenYield"
            return ""
        isin = read.text(security.get("isin"))
        named = [ops.Identifier(scheme="isin", value=isin)]
        if read.text(security.get("cusip")):
            named.append(ops.Identifier(scheme="cusip", value=read.text(security.get("cusip"))))
        if read.text(security.get("figi")):
            named.insert(0, ops.Identifier(scheme="figi", value=read.text(security.get("figi"))))
        asset = read.text(security.get("asset"))
        kind = "certificate_of_deposit" if "Certificate" in asset else "bond"
        name = read.text(security.get("name"))
        row["description"] = name
        found = await self.resolve_identifier(
            identifiers=named, as_of_ns=self.clock_ns(), stated_asset_class="debt",
            stated_instrument_type=kind, stated_currency="USD", stated_description=name,
        )  # fmt: skip
        if not (found.found and found.instrument_id):
            row["record"] = ops.MissReason.Name(found.miss_reason or 1)
            await self.report_missing_instrument(
                source=marketplace.SOURCE, asset_class="debt", identifiers=named,
                as_of_ns=self.clock_ns(), reason=found.miss_reason or ops.MISS_REASON_NOT_FOUND,
            )  # fmt: skip
            return ""
        record = str(found.instrument_id)
        row["record"] = record
        self.held[record] = Held(isin, asset == "MunicipalBond", name)
        self.records[identifier] = record
        return record

    async def held_for(self, subject: str) -> Held | None:
        """The security a want names: one resolved here, or one another
        source resolved, read from its record by its ISIN, CUSIP or FIGI."""
        if subject in self.held:
            return self.held[subject]
        found = await self.resolve_instrument(instrument_id=subject, as_of_ns=self.clock_ns())
        if not found.found:
            return None
        named = {i.scheme: i.value for i in found.instrument.identifiers}
        for scheme in ("isin", "cusip", "figi"):
            if named.get(scheme):
                answer = await self.ask(f"/reference/security/{_quoted(named[scheme])}")
                security = (answer or {}).get("security")
                if isinstance(security, dict):
                    held = Held(read.text(security.get("isin")),
                                read.text(security.get("asset")) == "MunicipalBond",
                                read.text(security.get("name")))  # fmt: skip
                    self.held[subject] = held
                    return held
        return None

    # ── Rows ─────────────────────────────────────────────────────────────

    async def quote_rows(self, held: Held, subject: str) -> list[meridian.Quote]:
        answer = await self.ask(f"/prices/search?id={_quoted(held.isin)}&limit=1")
        if not answer:
            return []
        as_of = read.utc(answer.get("as_of"))
        found = [r for r in answer.get("results") or [] if isinstance(r, dict)]
        if as_of is None or not found:
            return []
        dataset, venue = self.wants.dataset(marketplace.KEY), await self.venue_id()
        raw = self.raw(f"prices/search/{held.isin}")
        made = marketplace.quote(found[0], as_of, subject, dataset, venue, raw)
        if isinstance(made, marketplace.Unread):
            self.status.said(f"quotes: {made.what}")
            return []
        return [made]

    async def mid_rows(
        self, held: Held, subject: str, *, days: tuple[date, date] | None = None
    ) -> list[meridian.Price]:
        """A security's mids: today's latest intraday mid, or each day's
        end-of-day mid within `days`."""
        dataset, venue = self.wants.dataset(marketplace.KEY), await self.venue_id()
        rows: list[meridian.Price] = []
        if days is None:
            answer = await self.ask(f"/prices/intraday/{_quoted(held.isin)}")
            points = [p for p in (answer or {}).get("prices") or [] if isinstance(p, dict)]
            if points:
                last = points[-1]
                at, price = read.utc(last.get("as_at")), read.number(last.get("price"))
                if at is not None and price is not None:
                    rows.append(marketplace.mid(
                        held.isin, read.ny_day(at), price, subject, dataset, venue,
                        self.raw(f"prices/intraday/{held.isin}"), published=at,
                        quoted_yield=_yield(last.get("yield")),
                    ))  # fmt: skip
            return rows
        answer = await self.ask(f"/prices/daily/{_quoted(held.isin)}?limit=500")
        for point in (answer or {}).get("prices") or []:
            if not isinstance(point, dict):
                continue
            on, price = read.day(point.get("price_date")), read.number(point.get("price"))
            if on is None or price is None or not days[0] <= on <= days[1]:
                continue
            rows.append(marketplace.mid(
                held.isin, on, price, subject, dataset, venue,
                self.raw(f"prices/daily/{held.isin}/{on.isoformat()}"),
                quoted_yield=_yield(point.get("yield")),
            ))  # fmt: skip
        return rows

    async def print_rows(
        self, held: Held, subject: str, *, on: date | None = None
    ) -> list[meridian.Trade]:
        """A security's prints: its recent ones, or a day's."""
        path = (f"/reported/security/{on.isoformat()}/{_quoted(held.isin)}" if on
                else f"/reported/security/recent/{_quoted(held.isin)}?limit=500")  # fmt: skip
        answer = await self.ask(path)
        dataset = self.wants.dataset(prints.MSRB if held.muni else prints.TRACE)
        rows: list[meridian.Trade] = []
        for item in (answer or {}).get("prints") or []:
            if not isinstance(item, dict):
                continue
            raw = self.raw(f"reported/{held.isin}/{item.get('sequence')}")
            made = prints.convert(item, subject, dataset, raw)
            if isinstance(made, prints.Unread):
                self.status.said(f"prints: {made.what}")
                continue
            rows.append(made)
        return rows

    async def curve_rows(self) -> list[Rate]:
        subject = await self.curve_record()
        if not subject:
            return []
        answer = await self.ask("/prices/yield_curve")
        if not answer:
            return []
        rows, unread = marketplace.curve_rows(self.feed, subject, answer, "prices/yield_curve")
        for what in unread:
            self.status.said(f"curve: {what}")
        return rows

    # ── The check ────────────────────────────────────────────────────────

    async def kept(self, what: str, recording: Awaitable[int]) -> bool:
        try:
            await recording
        except meridian.MeridianError as refused:
            self.status.refused[what] = str(refused)[:300]
            log.info("%s not recorded: %s", what, refused)
            return False
        self.status.refused.pop(what, None)
        return True

    async def check(self) -> None:
        if not self.has_token and self.source.mode != "synthetic":
            return
        today = self.today()
        curve = await self.curve_rows()
        await self.kept("the benchmark curve", self.wants.record("rates", curve, marketplace.KEY))
        if self.daily != (today, self.securities):
            for identifier in self.securities:
                record = await self.resolve(identifier)
                if record:
                    held = self.held[record]
                    mids = await self.mid_rows(
                        held, record, days=(today - timedelta(days=95), today)
                    )
                    await self.kept(f"{held.isin}'s mids",
                                    self.wants.record("prices", mids, marketplace.KEY))  # fmt: skip
            self.daily = (today, self.securities)
        for record in [self.records[i] for i in self.securities if i in self.records]:
            held = self.held[record]
            await self.kept(f"{held.isin}'s quote",
                            self.wants.record("quotes", await self.quote_rows(held, record),
                                              marketplace.KEY))  # fmt: skip
            await self.kept(f"{held.isin}'s mid",
                            self.wants.record("prices", await self.mid_rows(held, record),
                                              marketplace.KEY))  # fmt: skip
            fresh = [p for p in await self.print_rows(held, record) if _key(p) not in self.printed]
            key = prints.MSRB if held.muni else prints.TRACE
            if await self.kept(f"{held.isin}'s prints", self.wants.record("trades", fresh, key)):
                self.printed.update(_key(p) for p in fresh)
        self.status.checked_at = self.now().isoformat(timespec="seconds")
        counts = self.wants.counts
        log.info(
            "checked: %d recorded, %d restated, %d unchanged in all; %d refused this time",
            counts.recorded, counts.restated, counts.unchanged, len(self.status.refused),
        )  # fmt: skip

    # ── Wants ────────────────────────────────────────────────────────────

    async def on_observations_wanted(
        self, heard: meridian.Heard[ops.ObservationsWantedEvent]
    ) -> None:
        await self.wants.hear(heard, self.answer)

    async def on_want_withdrawn(self, heard: meridian.Heard[ops.WantWithdrawnEvent]) -> None:
        self.wants.withdraw(heard.message.want_id)

    def _range(self, want: ops.ObservationsWantedEvent, days: int) -> tuple[date, date]:
        if want.business_date:
            on = date.fromisoformat(want.business_date)
            return on, on
        if want.valid_from_ns:
            start = datetime.fromtimestamp(want.valid_from_ns / 1e9, tz=UTC).date()
            end_ns = want.valid_until_ns or self.clock_ns()
            return start, datetime.fromtimestamp(end_ns / 1e9, tz=UTC).date()
        today = self.today()
        return today - timedelta(days=days), today

    async def answer(
        self,
        want: ops.ObservationsWantedEvent,
        key: str,
        subjects: list[str],
        kinds: tuple[int, ...],
    ) -> dict[str, str]:
        declined: dict[str, str] = {}
        if key == marketplace.KEY and want.data_type == RATE:
            curve = await self.curve_record()
            declined = {s: "not_covered" for s in subjects if s != curve}
            if curve in subjects:
                await self.wants.record("rates", await self.curve_rows(), key, want.want_id)
        elif key == marketplace.KEY and want.data_type in (PRICE, QUOTE):
            today = self.today()
            start, end = self._range(want, 0)
            for s in subjects:
                held = await self.held_for(s)
                if held is None:
                    declined[s] = "not_covered"
                    continue
                if want.data_type == QUOTE:
                    await self.wants.record("quotes", await self.quote_rows(held, s), key,
                                            want.want_id)  # fmt: skip
                    continue
                mids = await self.mid_rows(held, s) if end >= today else []
                if start < today:
                    mids += await self.mid_rows(held, s, days=(start, min(end, today)))
                await self.wants.record("prices", mids, key, want.want_id)
        elif key in (prints.TRACE, prints.MSRB):
            start, end = self._range(want, PRINT_DAYS)
            rows: list[meridian.Trade] = []
            for s in subjects:
                held = await self.held_for(s)
                if held is None or (key == prints.MSRB) != held.muni:
                    declined[s] = "not_covered"
                    continue
                on = start
                while on <= end:
                    rows += await self.print_rows(held, s, on=on)
                    on += timedelta(days=1)
            await self.wants.record("trades", rows, key, want.want_id)
        else:
            declined = {s: "not_covered" for s in subjects}
        if want.standing:
            self.wants.stand(want, [s for s in subjects if s not in declined], kinds)
        return declined


def _key(row: meridian.Trade) -> str:
    return row.meta.row_key if row.meta is not None else ""


def _yield(value: Any) -> str:
    """A yield OpenYield states, kept as reported; none where it says 0."""
    said = read.number(value)
    return read.text(value) if said is not None and said != 0 else ""
