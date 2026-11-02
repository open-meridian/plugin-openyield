"""The pages on sample data, each printed as one HTML file: for looking at
them without a deployment, and for `make preview SHOTS=<dir>`, which checks
each in a browser with the kit at 375, 582 and 1280 pixels.

    python -m openyield.preview connection > preview/connection.html

The plugin's work runs against the suites' recorder in place of a sidecar --
each record resolved, the benchmark curve's record read back as a person
accepted it -- on the sample answers (sample/answers.json), after New
York's close on 30 October 2026: the check run, a want of a mid answered and
one declined. `connection-first` and `datasets-first` are the pages before
the first check.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.suites import Recorder
from meridian.testing import PageClient

from .client import SyntheticOpenYield
from .lake import Lake
from .page import hold, pages

AT = datetime(2026, 10, 30, 22, 0, tzinfo=UTC)
LISTED = ("US037833EW60", "US91282CQB09", "US6500441A14")
NOT_HELD = "not-a-record"
PAGES = {
    "connection": "/",
    "datasets": "/datasets",
    "connection-first": "/",
    "datasets-first": "/datasets",
}


def _want(want_id: str, subject: str) -> Heard[ops.ObservationsWantedEvent]:
    return Heard(
        row="ObservationsWanted",
        message=ops.ObservationsWantedEvent(
            want_id=want_id, dataset="openyield:marketplace", data_type="meridian.v1.Price",
            subjects=[ops.SubjectRef(entity_id=subject)], business_date="2026-10-28",
        ),
    )  # fmt: skip


def _lake(recorder: Recorder) -> Lake:
    own: set[str] = set()
    made: list[str] = []

    def resolve(params: ops.ResolveIdentifierParams) -> ops.ResolveIdentifierResult:
        local = any(i.source == "openyield" for i in params.identifiers)
        made.append(f"{'LCL' if local else 'INS'}-PREVIEW-{len(made) + 1}")
        if local:
            own.add(made[-1])
        return ops.ResolveIdentifierResult(found=True, instrument_id=made[-1])

    def record(params: ops.ResolveInstrumentParams) -> ops.ResolveInstrumentResult:
        if params.instrument_id in own:
            accepted = ops.InstrumentRecord(
                instrument_id=params.instrument_id,
                asset_class=ops.ASSET_CLASS_REFERENTIAL,
                instrument_type=ops.INSTRUMENT_TYPE_RATE_CURVE,
            )
            return ops.ResolveInstrumentResult(found=True, instrument=accepted)
        return ops.ResolveInstrumentResult(found=False)

    recorder.answer("ResolveIdentifier", resolve)
    recorder.answer("ResolveInstrument", record)
    lake = recorder.bind(Lake(SyntheticOpenYield(lambda: AT), now=lambda: AT))
    lake.use(lake.source, LISTED, False)
    return lake


async def _worked(recorder: Recorder) -> Lake:
    lake = _lake(recorder)
    await lake.check()
    await lake.on_observations_wanted(_want("want-1028", lake.records["US037833EW60"]))
    await lake.on_observations_wanted(_want("want-other", NOT_HELD))
    return lake


def render(page: str) -> str:
    recorder = Recorder("openyield")
    lake = _lake(recorder) if page.endswith("-first") else asyncio.run(_worked(recorder))
    hold(lake)
    answer = PageClient(pages, recorder.plugin).get(PAGES[page], "admin")
    if answer.status != 200:
        raise SystemExit(f"{page} answered {answer.status}: {answer.text[:200]}")
    return answer.text


def main() -> None:
    page = sys.argv[1] if len(sys.argv) > 1 else "connection"
    if page not in PAGES:
        raise SystemExit(f"no page {page!r}: {', '.join(PAGES)}")
    sys.stdout.write(render(page))


if __name__ == "__main__":
    main()
