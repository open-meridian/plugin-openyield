"""The catalogue and settings, from code, as the deployment approves them."""

from __future__ import annotations

from openyield.declaration import DECLARATION
from openyield.settings import config_from


def test_three_datasets_each_naming_its_underlying_source() -> None:
    marketplace, trace, msrb = DECLARATION.catalogue
    assert (marketplace.key, trace.key, msrb.key) == ("marketplace", "trace_prints", "msrb_prints")
    assert marketplace.vendor == "OpenYield" and not marketplace.aggregator
    assert marketplace.price_source_class == "firm_quote"
    assert list(marketplace.data_types) == [
        "meridian.v1.Quote", "meridian.v1.Price", "meridian.v1.Rate",
    ]  # fmt: skip
    assert (trace.vendor, trace.aggregator) == ("FINRA TRACE", "OpenYield")
    assert (msrb.vendor, msrb.aggregator) == ("MSRB", "OpenYield")
    assert trace.declared_delay_ns == 4 * 3600 * 10**9
    for dataset in DECLARATION.catalogue:
        assert dataset.licence_default is None  # terms are the deployment's (1030 to 1032)


def test_the_token_is_a_token_and_the_securities_are_identifiers() -> None:
    config = config_from({
        "openyield_token": " t ",
        "securities": [{"security": "us037833ew60"}, {"security": "037833EW6"},
                       {"security": "BBG01G3PQ9C7"}, {"security": "not one"}],
    })  # fmt: skip
    assert config.token == "t"
    assert config.securities == ("US037833EW60", "037833EW6", "BBG01G3PQ9C7")
