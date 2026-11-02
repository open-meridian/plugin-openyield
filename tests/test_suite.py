"""The data suite (meridian.suites, contract v29), each case OpenYield
presents mapped to the plugin's own conversion of the sample answers, each
it never presents named with why.

**Presented:** a quote two-sided and one-sided, and a crossed one recorded
invalid at the edge; a trade recorded (a regular TRACE print) and a
condition not converted (the reporting dealer's side, kept as reported);
an exact price, a want recorded against, a subject another source resolved,
a venue resolved and one not held (the ATS's mids, venue OYLD); a curve for
a date, a tenor not published and a same-day revision (the benchmark
curve); its feed delay (each quote's and mid's published time); an asset
that does not resolve; a subject declined; a standing want withdrawn; its
datasets' licences; and the cases the SDK answers.

**Not presented, with why:** a close and a forming day (OpenYield states
mids, never a close), bars, a currency's rate, a crypto asset; an odd-lot
condition and the aggressor, which a bond print never states; a withdrawal
(OpenYield's prints carry no cancel or correction, 900's R3); streaming,
its liveness and a restart's gap (it polls); a quote's duplicate and a
sequence gap (OpenYield's top of book carries no sequence number); a fixing,
an index level, two conventions, another source's point; the lake query,
calendars and settlement dates; and the kinds it never publishes.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles.data.testing import feed_delay
from meridian.suites import ANSWERED_BY_SDK, Recorder, run, suite

from openyield import marketplace, prints
from openyield.lake import Held

from conftest import APPLE, TREASURY, Varied, holding, lake, want

Producer = Callable[[Recorder], Awaitable[None]]

NEVER_KINDS = {
    "closes": "OpenYield states mids, never a close",
    "bars": "OpenYield states no bars",
    "a currency's rate against another currency": "OpenYield states no currency's rate",
    "a crypto asset's price": "OpenYield states no crypto asset",
    "outcomes": "OpenYield states no event contract",
    "disputed outcomes": "OpenYield states no event contract",
    "option chains": "OpenYield states no option",
    "filings": "OpenYield states no filing",
    "holdings": "OpenYield states no holdings",
    "corporate actions": "OpenYield states no corporate action",
    "ratings": "an S&P rating on OpenYield's reference is no rating agency's action; not recorded",
    "derived series": "it publishes no figure of its own",
    "factors": "OpenYield states no pool's or class's factor",
    "streams": "OpenYield is polled every five minutes; it records no stream's liveness",
    "calendars": "it records what OpenYield states; it reads no calendar",
    "settlement dates": "it records what OpenYield states; it asks no settlement date",
}
PRESENTED_ABOUT_CLOSES = {"an-exact-price", "a-want-recorded-against"}
NEVER = {
    "a-condition-converted": "a bond print states no odd-lot condition",
    "the-takers-side-stated": "a print's side is the reporting dealer's, not who took liquidity",
    "the-makers-side-inverted": "a print's side is the reporting dealer's, not who took liquidity",
    "a-trade-withdrawn": (
        "OpenYield's resold prints carry no cancel or correction, so none is withdrawn "
        "(ruling 900's R3)"
    ),
    "a-standing-want-streamed": "OpenYield's prints are polled, never streamed here",
    "a-restarts-gap-backfilled": "polled over the last seven days, so a restart leaves no gap",
    "queries-the-lake-within-bounds": "it records what OpenYield states and reads nothing back",
    "a-duplicate-is-recorded-suspicious": "OpenYield's top of book carries no sequence number",
    "rows-after-a-gap-are-suspicious": "OpenYield's top of book carries no sequence number",
    "a-rate-fixing": "OpenYield states a benchmark curve, no fixing",
    "an-index-level": "OpenYield states no index",
    "two-conventions-one-tenor": "OpenYield states one yield a benchmark",
    "a-curve-point-from-another-source": "OpenYield states its whole benchmark curve",
}
NOT_PRESENTED = {
    **{
        case.name: NEVER_KINDS[case.about]
        for case in suite("data").cases
        if case.about in NEVER_KINDS
        and case.name not in ANSWERED_BY_SDK
        and case.name not in PRESENTED_ABOUT_CLOSES
    },
    **NEVER,
}


def quoted(isin: str, how: str = "") -> Producer:
    async def produce(recorder: Recorder) -> None:
        work = lake(recorder, openyield=Varied(how) if how else None)
        rows = await work.quote_rows(Held(isin, False), "INS-SECURITY")
        assert rows
        await work.wants.record("quotes", rows, marketplace.KEY)

    return produce


async def a_print(recorder: Recorder) -> None:
    work = lake(recorder)
    rows = await work.print_rows(Held(APPLE, False), "INS-SECURITY")
    await work.wants.record("trades", rows[:1], prints.TRACE)


async def exact(recorder: Recorder) -> None:
    work = lake(recorder)
    rows = await work.mid_rows(Held(APPLE, False), "INS-SECURITY")
    assert str(rows[0].price.amount) == "94.745000000000000001"
    await work.wants.record("prices", rows, marketplace.KEY)


async def wanted(recorder: Recorder) -> None:
    holding(recorder)
    work = lake(recorder)
    await work.resolve(APPLE)
    record = work.records[APPLE]
    recorder.answer("ObservationsWanted", lambda _: want("w-1", marketplace.KEY, [record],
                                                         day="2026-10-28").message)  # fmt: skip
    await recorder.hear(work, "ObservationsWanted")


async def elsewhere(recorder: Recorder) -> None:
    recorder.answer("ResolveInstrument", lambda p: ops.ResolveInstrumentResult(
        found=True, instrument=ops.InstrumentRecord(instrument_id=p.instrument_id, identifiers=[
            ops.Identifier(scheme="cusip", value="037833EW6"),
            ops.Identifier(scheme="symbol", value="AAPL53", source="custodian")])))  # fmt: skip
    work = lake(recorder, securities=())
    recorder.answer("ObservationsWanted", lambda _: want("w-1", marketplace.KEY, ["LCL-CUSTODIAN"],
                                                         day="2026-10-29").message)  # fmt: skip
    await recorder.hear(work, "ObservationsWanted")


async def venue_not_held(recorder: Recorder) -> None:
    recorder.answer("ResolveVenue", lambda _: ops.ResolveVenueResult(
        found=False, miss_reason=ops.MISS_REASON_NOT_FOUND))  # fmt: skip
    await exact(recorder)


def curve(how: str = "", twice: bool = False) -> Producer:
    async def produce(recorder: Recorder) -> None:
        holding(recorder)
        work = lake(recorder, securities=(), openyield=Varied(how) if how else None)
        for _ in range(2 if twice else 1):
            await work.wants.record("rates", await work.curve_rows(), marketplace.KEY)
        if twice:
            first, second = recorder.on("RecordRates")
            ten = [r for r in second.rates if ":10Y:" in r.meta.row_key]
            before = [r for r in first.rates if r.meta.row_key == ten[0].meta.row_key]
            assert before[0].value != ten[0].value

    return produce


async def ambiguous(recorder: Recorder) -> None:
    recorder.answer("ResolveIdentifier", lambda _: ops.ResolveIdentifierResult(
        found=False, miss_reason=ops.MISS_REASON_AMBIGUOUS))  # fmt: skip
    await lake(recorder).resolve(APPLE)


async def declined(recorder: Recorder) -> None:
    recorder.answer("ResolveInstrument", lambda _: ops.ResolveInstrumentResult(found=False))
    work = lake(recorder, securities=())
    recorder.answer("ObservationsWanted",
                    lambda _: want("w-1", prints.TRACE, ["not-a-bond"],
                                   data_type="meridian.v1.Trade").message)  # fmt: skip
    await recorder.hear(work, "ObservationsWanted")


async def withdrawn(recorder: Recorder) -> None:
    work = lake(recorder, securities=())
    recorder.answer("WantWithdrawn", lambda _: ops.WantWithdrawnEvent(
        want_id="w-1", dataset="openyield:marketplace"))  # fmt: skip
    await recorder.hear(work, "WantWithdrawn")


async def licences(recorder: Recorder) -> None:
    await lake(recorder, securities=()).wants.read_licences()


async def delayed(recorder: Recorder, latency: Any) -> None:
    work = lake(recorder)
    work.wants.latency = latency
    await work.wants.record("quotes", await work.quote_rows(Held(APPLE, False), "INS-S"),
                            marketplace.KEY)  # fmt: skip


PRODUCERS: dict[str, Producer] = {
    "a-quote-recorded": quoted(APPLE),
    "a-one-sided-quote": quoted(TREASURY),
    "a-crossed-quote-is-recorded-invalid": quoted(APPLE, "crossed"),
    "a-trade-recorded": a_print,
    "a-condition-not-converted": a_print,
    "an-exact-price": exact,
    "a-want-recorded-against": wanted,
    "a-subject-another-source-resolved": elsewhere,
    "a-venue-resolved": exact,
    "a-venue-not-held": venue_not_held,
    "a-curve-for-a-date": curve(),
    "a-tenor-not-published": curve("gap"),
    "a-same-day-revision": curve("revised", twice=True),
    "reports-its-feed-delay": feed_delay(delayed),
    "an-asset-that-does-not-resolve": ambiguous,
    "a-subject-declined": declined,
    "a-standing-want-withdrawn": withdrawn,
    "reads-its-datasets-licences": licences,
}


def test_the_data_suite_passes() -> None:
    report = run("data", PRODUCERS, not_presented=NOT_PRESENTED, instance_id="openyield")
    assert report.passed, report.failures
    assert set(report.passed_cases) == set(PRODUCERS) | set(ANSWERED_BY_SDK)


def test_a_withdrawal_is_not_presented_ruling_900_r3() -> None:
    assert "R3" in NOT_PRESENTED["a-trade-withdrawn"]
