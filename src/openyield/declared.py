"""What this version declares beside its role: its catalogue (W10.1,
contract v18), built from code and used twice -- `__main__` registers with
it, and `meridian plugin upload` reads it from the built image.

**Three datasets** (names proposed in the pull request), one per
underlying source (ruling 387), each naming it as its vendor -- who
originated the data -- and OpenYield as its aggregator where OpenYield
carries another's:

- `marketplace` -- OpenYield's ATS's own: its firm top of book (`Quote`,
  the ATS its venue, 900's R6), its mids (`Price` of kind `mid`, class
  `firm_quote`, 906) and its live Treasury benchmark curve (`Rate`);
  pushed by the five-minute check and pulled on a want; New York's day;
- `trace_prints` -- FINRA TRACE's prints of corporates, agencies,
  Treasuries and CDs, as OpenYield resells them (`Trade`): delayed four
  hours by TRACE's dissemination terms unless the OpenYield account holds a
  real-time TRACE entitlement, the delay declared;
- `msrb_prints` -- MSRB's prints of municipal bonds, as OpenYield resells
  them (`Trade`).

**No calendar.** No settlement calendar is declared. **Trading sessions**
(contract 30, `sessions_calendar_id`, ruling 455): `trace_prints` names the
platform's US bond market sessions, FINRA's TRACE system hours with
SIFMA's recommended early closes, the hours TRACE's prints are reported
in; the ATS's own hours and MSRB's are no calendar the platform curates
yet. **Terms** are the deployment's to settle with OpenYield, under its
Data Services Agreement (rulings 1030 to 1032): each dataset describes them
in words (`terms_and_pricing`, contract 30), as docs/terms.md does, never a
licence. **A gap** is recovered by `backfill` (`gap_recovery`): OpenYield
serves its mids about three months back and its prints a week, read again
on a want.
"""

from __future__ import annotations

from meridian import DatasetDeclaration

from .marketplace import KEY
from .prints import MSRB, TRACE

VENDOR = "OpenYield"
NEW_YORK = "America/New_York"
#: TRACE's dissemination delay without a real-time entitlement: four hours.
TRACE_DELAY_NS = 4 * 3600 * 1_000_000_000
#: How far back OpenYield serves: its daily mids about three months, its
#: prints seven days without a history subscription.
MIDS_HISTORY = 95
PRINTS_HISTORY = 7
#: The platform's "US bond market sessions (SIFMA recommended early closes)"
#: trading-sessions calendar, read from the platform on 2026-11-12: FINRA's
#: TRACE system hours, 08:00 to 18:29:59 New York, each business day.
US_BOND_SESSIONS = "CAL-01M6CDQRFE48WF62BG9KFJEEEB"
#: What OpenYield publishes of its terms, in plain words (contract 30, ruling
#: 1032), as read on 30 October 2026: docs/terms.md, shortened.
OPENYIELD_TERMS = (
    "Access requires a signed Data Services Agreement with OpenYield Trading LLC, which is "
    "not public; its data services are for institutional use. Pricing is not published: "
    "data services are priced by agreement, with add-ons for the trade tape, reference, the "
    "calculator and prints. Its website's terms of use cover the website, not the API."
)
MARKETPLACE_TERMS = (
    "OpenYield's own ATS, its firm all-to-all order book: its top of book, mids and live "
    "Treasury benchmark curve. " + OPENYIELD_TERMS
)
TRACE_TERMS = (
    "FINRA TRACE's prints of corporates, agencies, Treasuries and CDs, resold by OpenYield "
    "under a separate licence: real-time TRACE is a per-account entitlement, otherwise four "
    "hours delayed. FINRA's terms for its data may apply alongside OpenYield's. " + OPENYIELD_TERMS
)
MSRB_TERMS = (
    "MSRB's dissemination of municipal trades, resold by OpenYield. MSRB's terms for its "
    "data may apply alongside OpenYield's. " + OPENYIELD_TERMS
)

MARKETPLACE = DatasetDeclaration(
    key=KEY,
    vendor=VENDOR,
    data_types=["meridian.v1.Quote", "meridian.v1.Price", "meridian.v1.Rate"],
    modes=["push", "pull"],
    cadence=300,
    history=MIDS_HISTORY,
    day_time_zone=NEW_YORK,
    price_source_class="firm_quote",
    terms_and_pricing=MARKETPLACE_TERMS,
    gap_recovery="backfill",
)

TRACE_PRINTS = DatasetDeclaration(
    key=TRACE,
    vendor="FINRA TRACE",
    aggregator=VENDOR,
    data_types=["meridian.v1.Trade"],
    modes=["push", "pull"],
    cadence=300,
    history=PRINTS_HISTORY,
    day_time_zone=NEW_YORK,
    declared_delay_ns=TRACE_DELAY_NS,
    sessions_calendar_id=US_BOND_SESSIONS,
    terms_and_pricing=TRACE_TERMS,
    gap_recovery="backfill",
)

MSRB_PRINTS = DatasetDeclaration(
    key=MSRB,
    vendor="MSRB",
    aggregator=VENDOR,
    data_types=["meridian.v1.Trade"],
    modes=["push", "pull"],
    cadence=300,
    history=PRINTS_HISTORY,
    day_time_zone=NEW_YORK,
    terms_and_pricing=MSRB_TERMS,
    gap_recovery="backfill",
)

CATALOGUE = [MARKETPLACE, TRACE_PRINTS, MSRB_PRINTS]
