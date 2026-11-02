"""The data role's work on the sample: the ATS's quotes and mids, the
benchmark curve, the resold prints, wants, and what is kept as reported."""

from __future__ import annotations

import asyncio
from decimal import Decimal

from meridian.operations import as_decimal
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import Recorder

from openyield import marketplace, prints
from openyield.lake import Lake

from conftest import APPLE, LISTED, MUNI, TREASURY, holding, lake, want


def checked() -> tuple[Recorder, Lake]:
    recorder = Recorder("openyield")
    holding(recorder)
    work = lake(recorder)
    asyncio.run(work.check())
    return recorder, work


def test_the_check_records_quotes_mids_curve_and_prints() -> None:
    recorder, work = checked()
    quotes = [q for s in recorder.on("RecordQuotes") for q in s.quotes]
    mids = [p for s in recorder.on("RecordPrices") for p in s.prices]
    curve = [r for s in recorder.on("RecordRates") for r in s.rates]
    trades = [t for s in recorder.on("RecordTrades") for t in s.trades]
    assert len(quotes) == 3 and len(curve) == 14
    assert {t.meta.source.dataset for t in trades} == {"openyield:trace_prints",
                                                       "openyield:msrb_prints"}  # fmt: skip
    assert len(trades) == 5
    assert all(p.kind == ops.PRICE_KIND_MID for p in mids)
    assert sorted(work.records) == sorted(LISTED)


def test_a_quote_s_size_buckets_are_their_floors_at_least() -> None:
    recorder, _ = checked()
    quotes = {q.meta.row_key.split(":")[1]: q for s in recorder.on("RecordQuotes")
              for q in s.quotes}  # fmt: skip
    apple = quotes[APPLE]
    assert as_decimal(apple.bid_quantity) == Decimal(100_000) and apple.bid_size_capped
    assert as_decimal(apple.ask_quantity) == Decimal(1_000) and apple.ask_size_capped
    assert apple.basis == ops.PRICE_BASIS_PERCENT_OF_PAR and apple.meta.source.venue_id
    assert [u.scheme for u in apple.meta.unconverted] == ["openyield:bid_yield",
                                                          "openyield:ask_yield"]  # fmt: skip
    one_sided = quotes[TREASURY]
    assert not one_sided.HasField("ask") and as_decimal(one_sided.bid_quantity) == 1_000_000


def test_a_capped_print_and_the_ats() -> None:
    recorder, _ = checked()
    trades = {t.meta.row_key: t for s in recorder.on("RecordTrades") for t in s.trades}
    capped = trades["trace:2026-10-30:3110958"]
    assert as_decimal(capped.quantity) == Decimal(5_000_000) and capped.quantity_capped
    assert not capped.attributes.HasField("consolidated")
    ats = trades["trace:2026-10-30:3121006"]
    names = [ops.TradeCharacteristic.Name(c) for c in ats.attributes.characteristics]
    assert names == ["TRADE_CHARACTERISTIC_ATS_EXECUTED"]
    customer = trades["trace:2026-10-30:3104472"]
    assert [ops.TradeCharacteristic.Name(c) for c in customer.attributes.characteristics] == [
        "TRADE_CHARACTERISTIC_CONTRA_CUSTOMER"
    ]
    assert as_decimal(customer.quantity) == Decimal(25_000) and customer.source_sequence == 3104472
    muni = trades["msrb:2026-10-30:1511840"]
    assert muni.meta.source.dataset == f"openyield:{prints.MSRB}"
    assert not any(t.cancelled for t in trades.values())


def test_the_benchmark_curve_today_and_its_previous_close() -> None:
    recorder, work = checked()
    curve = [r for s in recorder.on("RecordRates") for r in s.rates]
    days = {r.meta.business_date for r in curve}
    assert days == {"2026-10-30", "2026-10-29"}
    ten = [r for r in curve if r.tenor.count == 10 and r.meta.business_date == "2026-10-30"]
    assert as_decimal(ten[0].value.value) == Decimal("4.262")
    assert ten[0].kind == ops.RATE_KIND_PAR_YIELD and ten[0].convention.periods_per_year == 2
    assert work.status.curve_record


def test_an_unaccepted_curve_records_nothing() -> None:
    recorder = Recorder("openyield")
    recorder.answer("ResolveInstrument", lambda p: ops.ResolveInstrumentResult(
        found=True, instrument=ops.InstrumentRecord(instrument_id=p.instrument_id)))  # fmt: skip
    work = lake(recorder, securities=())
    asyncio.run(work.check())
    assert not recorder.on("RecordRates")
    assert work.status.refused["the benchmark curve's record"].startswith("its record awaits")


def test_prints_are_sent_once_unasked() -> None:
    recorder, work = checked()
    asyncio.run(work.check())
    assert len([t for s in recorder.on("RecordTrades") for t in s.trades]) == 5


def test_a_want_of_a_muni_s_prints_over_a_day() -> None:
    recorder = Recorder("openyield")
    holding(recorder)
    work = lake(recorder)
    asyncio.run(work.resolve(MUNI))
    record = work.records[MUNI]
    heard = want("w-1", prints.MSRB, [record], data_type="meridian.v1.Trade", day="2026-10-29")
    asyncio.run(work.on_observations_wanted(heard))
    [sent] = recorder.on("RecordTrades")
    assert sent.want_id == "w-1" and len(sent.trades) == 1
    traced = want("w-2", prints.TRACE, [record], data_type="meridian.v1.Trade")
    asyncio.run(work.on_observations_wanted(traced))
    [declined] = recorder.on("DeclineWant")
    assert [s.entity_id for s in declined.subjects] == [record]


def test_a_security_resolves_with_what_openyield_states() -> None:
    recorder = Recorder("openyield")
    work = lake(recorder)
    asyncio.run(work.resolve(APPLE))
    [asked] = recorder.on("ResolveIdentifier")
    assert [(i.scheme, i.value) for i in asked.identifiers] == [
        ("figi", "BBG01G3PQ9C7"), ("isin", APPLE), ("cusip", "037833EW6"),
    ]  # fmt: skip
    assert (
        asked.stated_currency == "USD" and asked.stated_instrument_type == ops.INSTRUMENT_TYPE_BOND
    )


def test_size_buckets() -> None:
    assert marketplace.size("[1000+]") == (Decimal(1_000_000), True)
    assert marketplace.size("[0-100)") == (Decimal(1_000), True)
    assert marketplace.size("lots") is None
    assert prints.contra("D-C", False, False) == ("customer", False)
    assert prints.contra("D-A", True, False) == ("", True)
    assert prints.contra("Dealer", False, True) == ("dealer", False)
    assert prints.contra("X", False, False) is None
