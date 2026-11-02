"""Shared stand-ins: the sample answers (src/openyield/sample/), a fixed
clock, the deployment's records as a recorder answers them, and the lake's
wants as the sidecar delivers them."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.suites import Recorder

from openyield.client import Fetched, SyntheticOpenYield
from openyield.lake import Lake

#: After New York's close on Friday 30 October 2026.
AT = datetime(2026, 10, 30, 22, 0, tzinfo=UTC)
INSTANCE = "openyield"
APPLE = "US037833EW60"
TREASURY = "US91282CQB09"
MUNI = "US6500441A14"
LISTED = (APPLE, TREASURY, MUNI)


def source() -> SyntheticOpenYield:
    return SyntheticOpenYield(lambda: AT)


class Varied(SyntheticOpenYield):
    """The sample, varied for a case: `crossed`, Apple's bid above its ask;
    `revised`, the curve's 10-year a basis point higher on the second read;
    `gap`, the curve stating no 7-year today."""

    def __init__(self, how: str) -> None:
        super().__init__(lambda: AT)
        self.how = how
        self.reads = 0

    async def get(self, path: str) -> Fetched:
        if self.how == "crossed" and path.startswith("/prices/search"):
            held = deepcopy(self.securities[APPLE]["top_of_book"])
            held["result"]["bid_price"] = "95.50"
            return Fetched(path, 200, json.dumps({"as_of": held["as_of"],
                                                  "results": [held["result"]]}), AT)  # fmt: skip
        if path == "/prices/yield_curve" and self.how in ("revised", "gap"):
            self.reads += 1
            curve = deepcopy(self.curve)
            for point in curve["benchmarks"]:
                if self.how == "revised" and self.reads > 1 and point["shortcut"] == "CT10":
                    point["current"] = "4.272"
                if self.how == "gap" and point["shortcut"] == "CT07":
                    point["current"] = None
            return Fetched(path, 200, json.dumps(curve), AT)
        return await super().get(path)


def lake(
    recorder: Recorder, *, securities: tuple[str, ...] = LISTED, openyield: Any = None
) -> Lake:
    made = recorder.bind(Lake(openyield or source(), now=lambda: AT))
    made.use(made.source, securities, True)
    return made


def holding(recorder: Recorder) -> None:
    """The deployment's records as the store answers them: the benchmark
    curve's local record as a person accepted it (`INS-ref-n`); a security's
    `INS-debt-n`."""
    made: list[str] = []

    def resolve(params: Any) -> ops.ResolveIdentifierResult:
        own = any(i.source == "openyield" for i in params.identifiers)
        made.append("ref" if own else "debt")
        return ops.ResolveIdentifierResult(found=True, instrument_id=f"INS-{made[-1]}-{len(made)}")

    def record(params: Any) -> ops.ResolveInstrumentResult:
        if params.instrument_id.startswith("INS-ref-"):
            return ops.ResolveInstrumentResult(found=True, instrument=ops.InstrumentRecord(
                instrument_id=params.instrument_id, asset_class=ops.ASSET_CLASS_REFERENTIAL,
                instrument_type=ops.INSTRUMENT_TYPE_RATE_CURVE))  # fmt: skip
        return ops.ResolveInstrumentResult(found=False)

    recorder.answer("ResolveIdentifier", resolve)
    recorder.answer("ResolveInstrument", record)


def want(
    want_id: str,
    dataset: str,
    subjects: list[str],
    *,
    data_type: str = "meridian.v1.Price",
    day: str = "",
    standing: bool = False,
) -> Heard[ops.ObservationsWantedEvent]:
    return Heard(
        row="ObservationsWanted",
        message=ops.ObservationsWantedEvent(
            want_id=want_id,
            dataset=f"{INSTANCE}:{dataset}",
            data_type=data_type,
            subjects=[ops.SubjectRef(entity_id=s) for s in subjects],
            business_date=day,
            standing=standing,
        ),
    )
