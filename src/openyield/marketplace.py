"""OpenYield's marketplace -- its ATS's firm top of book, its mids and its
Treasury benchmark curve -- as the lake's quotes, prices and rates, under
the dataset `marketplace` (the ATS's own; ruling 900's R6, 906).

**A quote** (`/prices/search`) is the ATS's best bid and offer for a
security, a `Quote` with OpenYield's ATS as its venue (ISO 10383 MIC
`OYLD`): its prices per 100 of face (`percent_of_par`, clean, as OpenYield's
own price calculator takes and gives a price), in force from the snapshot's
time. OpenYield states each side's size as a bucket of bonds ($1,000 face
each), never a size: the bucket's floor is recorded, in face, marked "at
least" (`bid_size_capped`, `ask_size_capped`; 900's R2) -- `[1000+]` at
least 1,000,000, `[100-1000)` at least 100,000, and `[0-100)` at least
1,000, a side quoted being at least one bond. A side not quoted is no price.

**A mid** (`/prices/intraday`, `/prices/daily`) is a `Price` of kind `mid`,
per 100 of face, the dataset's class `firm_quote` (906: OpenYield derives it
from its firm order book), one row a security a New York day: today's
restated as each intraday mid is read, the published time each one's, and
each past day's its end-of-day mid.

**The benchmark curve** (`/prices/yield_curve`) is the live yield of each
on-the-run Treasury benchmark (CT02 to CT30), by its tenor. Each point is a
`Rate` under OpenYield's own curve record (`OPENYIELD_UST_BENCHMARK`, kept
local), today's `current` restated through the day, the previous business
day's close from `previous`. The contract's kinds name no benchmark yield,
so a point is recorded as `par_yield`, an on-the-run note or bond being
auctioned at a coupon set to its yield; bond-equivalent (semi-annual,
actual/actual), as Treasury yields are stated.

**Yields beside a quote or a mid are kept as reported**
(`ObservationMeta.unconverted`): the lake records a quoted yield with its
day count, which OpenYield does not state for a security's yield (asked,
ruling 871).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

import meridian
from meridian.operations import Rate, Tenor, UnitValue
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles.data import rates

from . import read

KEY = "marketplace"
#: OpenYield's ATS, by its ISO 10383 MIC.
MIC = "OYLD"
SOURCE = "openyield"
CURVE_SYMBOL = "OPENYIELD_UST_BENCHMARK"
CURVE_DESCRIPTION = "OpenYield US Treasury benchmark curve (on-the-run yields)"
#: A bucket of bonds ($1,000 face each), as OpenYield names it, and its
#: floor in face.
BOND = Decimal(1000)
BUCKETS = {
    "[0-100)": Decimal(1) * BOND,
    "[100-1000)": Decimal(100) * BOND,
    "[1000+]": Decimal(1000) * BOND,
}


@dataclass(frozen=True)
class Unread:
    what: str


def _as_reported(name: str, value: str) -> ops.AsReported:
    return ops.AsReported(scheme=f"{SOURCE}:{name}"[:64], code=value[:128], text=value[:256])


def size(bucket: str) -> tuple[Decimal, bool] | None:
    """A size bucket's floor in face, at least; None for one not known."""
    floor = BUCKETS.get(bucket.strip())
    return None if floor is None else (floor, True)


def quote(
    result: dict[str, Any], as_of: datetime, subject: str, dataset: str, venue: str,
    raw: ops.RawRecordRef,
) -> meridian.Quote | Unread:  # fmt: skip
    """One top of book as the ATS's quote, or why it is none."""
    isin = read.text(result.get("isin"))
    bid, ask = read.number(result.get("bid_price")), read.number(result.get("ask_price"))
    if bid is None and ask is None:
        return Unread("a top of book quoting neither side")
    sides: dict[str, Any] = {}
    reported: list[ops.AsReported] = []
    for side, price in (("bid", bid), ("ask", ask)):
        if price is None:
            continue
        sized = size(read.text(result.get(f"{side}_quantity")))
        if sized is None:
            return Unread(f"a {side} size bucket not known: {result.get(f'{side}_quantity')}")
        sides[side] = meridian.Money(price, currency_code="USD")
        sides[f"{side}_quantity"], sides[f"{side}_size_capped"] = sized
        quoted_yield = read.text(result.get(f"{side}_yield"))
        if quoted_yield:
            reported.append(_as_reported(f"{side}_yield", quoted_yield))
    at = read.ns(as_of)
    meta = meridian.ObservationMeta(
        row_key=f"oyld:{isin}:{at}"[:128],
        subjects=[meridian.SubjectRef(entity_id=subject)],
        source=ops.Source(dataset=dataset, venue_id=venue),
        valid_from_ns=at,
        source_times=[meridian.SourceTime(kind="published", at_ns=at)],
        raw=raw,
        unconverted=reported,
    )
    return meridian.Quote(meta=meta, basis="percent_of_par", **sides)


def _day_window(day: date) -> tuple[int, int]:
    start = datetime.combine(day, time(), read.NEW_YORK)
    return read.ns(start), read.ns(start + timedelta(days=1))


def mid(
    isin: str, day: date, price: Decimal, subject: str, dataset: str, venue: str,
    raw: ops.RawRecordRef, *, published: datetime | None = None, quoted_yield: str = "",
) -> meridian.Price:  # fmt: skip
    """A security's mid for a New York day: today's restated as it moves,
    a past day's its end-of-day mid."""
    start, end = _day_window(day)
    meta = meridian.ObservationMeta(
        row_key=f"oyld:mid:{isin}:{day.isoformat()}"[:128],
        subjects=[meridian.SubjectRef(entity_id=subject)],
        source=ops.Source(dataset=dataset, venue_id=venue),
        valid_from_ns=start,
        valid_until_ns=end,
        business_date=day,
        source_times=(
            [meridian.SourceTime(kind="published", at_ns=read.ns(published))] if published else []
        ),
        raw=raw,
        unconverted=[_as_reported("yield", quoted_yield)] if quoted_yield else [],
    )
    return meridian.Price(
        meta=meta, kind="mid", price=meridian.Money(price, currency_code="USD"),
        basis="percent_of_par",
    )  # fmt: skip


def previous_business_day(day: date) -> date:
    at = day - timedelta(days=1)
    while at.weekday() >= 5:
        at -= timedelta(days=1)
    return at


def tenor_of(years: Decimal) -> str | None:
    if years > 0 and years == years.to_integral_value():
        return f"{int(years)}Y"
    return None


def curve_rows(
    feed: rates.Feed, subject: str, answer: dict[str, Any], raw_key: str
) -> tuple[list[Rate], list[str]]:
    """The benchmark curve's points, today's and the previous business
    day's, and what could not be read."""
    as_of = read.utc(answer.get("as_of"))
    unread: list[str] = []
    if as_of is None:
        return [], ["a benchmark curve with no time"]
    today = read.ny_day(as_of)
    current: dict[str | Tenor, UnitValue | Decimal | str | None] = {}
    previous: dict[str | Tenor, UnitValue | Decimal | str | None] = {}
    for point in answer.get("benchmarks") or []:
        if not isinstance(point, dict):
            continue
        years = read.number(point.get("tenor"))
        label = tenor_of(years) if years is not None else None
        if label is None:
            unread.append(f"a benchmark at {point.get('tenor')} years")
            continue
        current[label] = read.number(point.get("current"))
        previous[label] = read.number(point.get("previous"))
    rows = feed.curve(
        subject, KEY, "par_yield", current, business_date=today,
        published_ns=read.ns(as_of), convention=rates.BOND_EQUIVALENT, raw_key=raw_key,
    )  # fmt: skip
    rows += feed.curve(
        subject, KEY, "par_yield", previous, business_date=previous_business_day(today),
        convention=rates.BOND_EQUIVALENT, raw_key=raw_key,
    )  # fmt: skip
    return rows, unread
