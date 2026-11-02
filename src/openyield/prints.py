"""The prints OpenYield resells -- FINRA's TRACE for corporates, agencies,
Treasuries and CDs, MSRB's for municipal bonds -- as the lake's trades, each
under the dataset of its underlying source: `trace_prints` or `msrb_prints`
(rulings 387, 900).

Each print (`/reported/security/...`) becomes one `Trade` (W10.4):

- **its key** the print's day and its TRACE or MSRB sequence number
  (`source_sequence`), so a print read again is the same row;
- **its time** OpenYield's `as_at`, New York local time, the trade's
  execution;
- **its price** per 100 of face (`percent_of_par`), in US dollars; a print
  MSRB reported with no price is not recorded, and said;
- **its quantity** in face: OpenYield states bonds of $1,000 face, so 10 is
  10,000; TRACE's capped sizes (`1000.001`, `5000.001`) are 1,000,000 and
  5,000,000 at least (`quantity_capped`; 685);
- **its characteristics** by meaning (`meridian.helpers.debt`): its contra
  party (TRACE's `D-C` reporting-contra parties, MSRB's `Dealer` or
  `Customer`), and executed on an ATS;
- **kept as reported** (`ObservationMeta.unconverted`): the reporting
  dealer's side (`Buy` or `Sell`), which no characteristic carries, and the
  trade's yield, whose day count OpenYield does not state.

**Not stated, so not presented** (900's R3 and R4): a cancel or a
correction -- OpenYield's prints carry neither, so a print TRACE later
corrects is never withdrawn here -- and a print's capacity, when-issued,
special-price and primary-market flags: none listed means none the source
states. A regular print -- its size exact -- is eligible for each statistic
of a bar; a capped one's eligibility is left unstated.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import meridian
from meridian.helpers import debt
from meridian.plugin.v1 import operations_pb2 as ops

from . import read

TRACE = "trace_prints"
MSRB = "msrb_prints"
SOURCE = "openyield"
#: OpenYield's quantity unit, a bond, in face.
BOND = Decimal(1000)
#: TRACE's capped sizes as OpenYield writes them, in bonds, and their floors.
CAPPED = {Decimal("1000.001"): Decimal(1000), Decimal("5000.001"): Decimal(5000)}
_TRACE_PARTY = {"D": "dealer", "C": "customer", "A": "affiliate"}
_MSRB_PARTY = {"Dealer": "dealer", "Customer": "customer"}
_ELIGIBLE = meridian.Eligibility(
    high_low="ELIGIBLE_ELIGIBLE", open="ELIGIBLE_ELIGIBLE", close="ELIGIBLE_ELIGIBLE",
    volume="ELIGIBLE_ELIGIBLE",
)  # fmt: skip


@dataclass(frozen=True)
class Unread:
    what: str


def _as_reported(name: str, value: str) -> ops.AsReported:
    return ops.AsReported(scheme=f"{SOURCE}:{name}"[:64], code=value[:128], text=value[:256])


def contra(parties: str, is_ats: bool, msrb: bool) -> tuple[str, bool] | None:
    """The contra party's kind and whether the trade was on an ATS, from
    OpenYield's `parties`; None for a code not known. TRACE's `A` is an
    affiliate, or the ATS where `is_ats` says so."""
    if msrb:
        found = _MSRB_PARTY.get(parties)
        return None if found is None else (found, is_ats)
    reporting, _, other = parties.partition("-")
    if not reporting or other not in _TRACE_PARTY:
        return None
    if other == "A" and is_ats:
        return "", True
    return _TRACE_PARTY[other], is_ats


def convert(
    item: dict[str, Any], subject: str, dataset: str, raw: ops.RawRecordRef
) -> meridian.Trade | Unread:
    """One print as the lake's trade, or why it is none."""
    msrb = dataset.endswith(MSRB)
    sequence = item.get("sequence")
    moment = read.new_york(item.get("as_at"))
    price = read.number(item.get("price"))
    bonds = read.number(item.get("quantity"))
    if not isinstance(sequence, Decimal | int) or moment is None or bonds is None:
        return Unread("a print with no sequence, time or quantity")
    if price is None:
        return Unread("a print reported with no price")
    capped = bonds in CAPPED
    face = (CAPPED[bonds] if capped else bonds) * BOND
    parties = read.text(item.get("parties"))
    is_ats = item.get("is_ats") is True
    found = contra(parties, is_ats, msrb)
    reported = []
    if found is None:
        reported.append(_as_reported("parties", parties or "?"))
        found = ("", is_ats)
    side = read.text(item.get("side"))
    if side:
        reported.append(_as_reported("side", side))
    said_yield = read.number(item.get("yield"))
    if said_yield is not None and said_yield != 0:
        reported.append(_as_reported("yield", read.text(item.get("yield"))))
    at = read.ns(moment)
    day = read.ny_day(moment)
    meta = meridian.ObservationMeta(
        row_key=f"{'msrb' if msrb else 'trace'}:{day.isoformat()}:{int(sequence)}",
        subjects=[meridian.SubjectRef(entity_id=subject)],
        source=ops.Source(dataset=dataset),
        valid_from_ns=at,
        source_times=[meridian.SourceTime(kind="event", at_ns=at)],
        raw=raw,
        unconverted=reported,
    )
    return meridian.Trade(
        meta=meta,
        price=meridian.Money(price, currency_code="USD"),
        quantity=face,
        quantity_capped=capped,
        source_sequence=int(sequence),
        basis="percent_of_par",
        attributes=meridian.TradeAttributes(
            consolidated=None if capped else _ELIGIBLE,
            market_centre=None if capped else _ELIGIBLE,
            characteristics=debt.characteristics(contra_party=found[0], ats=found[1]),
        ),
    )
