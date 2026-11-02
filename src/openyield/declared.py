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

**No calendar.** No calendar the platform curates holds the US bond
market's closes yet. **Terms** are the deployment's to settle with
OpenYield, under its Data Services Agreement (rulings 1030 to 1032): no
default licence is declared; docs/terms.md describes them in plain words.
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

MARKETPLACE = DatasetDeclaration(
    key=KEY,
    vendor=VENDOR,
    data_types=["meridian.v1.Quote", "meridian.v1.Price", "meridian.v1.Rate"],
    modes=["push", "pull"],
    cadence=300,
    history=MIDS_HISTORY,
    day_time_zone=NEW_YORK,
    price_source_class="firm_quote",
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
)

CATALOGUE = [MARKETPLACE, TRACE_PRINTS, MSRB_PRINTS]
