"""The two pages under Manage, and their read tools."""

from __future__ import annotations

import asyncio

import pytest
from meridian.suites import Recorder
from meridian.testing import PageClient

from openyield.page import figures, hold, pages

from conftest import APPLE, holding, lake, want


@pytest.fixture
def client() -> PageClient:
    recorder = Recorder("openyield")
    holding(recorder)
    work = lake(recorder)

    async def run() -> None:
        await work.check()
        await work.on_observations_wanted(want("w-1", "marketplace", [work.records[APPLE]],
                                               day="2026-10-28"))  # fmt: skip

    asyncio.run(run())
    hold(work)
    return PageClient(pages, recorder.plugin)


def test_each_page_is_managed_alone(client: PageClient) -> None:
    served = {(r.page.path, r.level): r.response.status for r in client.every_page()}
    assert {level: status for (_, level), status in served.items()} == {
        "admin": 200, "write": 403, "read": 403,
    }  # fmt: skip
    client.assert_no_account_data("94.53", "94.745", "4.262", "94.512")


def test_connection_says_a_token_never_a_password(client: PageClient) -> None:
    text = client.get("/", "admin").text
    assert '<th scope="row">Access</th>' in text and "never holds a password" in text
    assert "3 of 3 resolved" in text and "Sample data" in text and "Does not stream" in text


def test_datasets_lists_each_dataset_and_the_curve_s_record(client: PageClient) -> None:
    text = client.get("/datasets", "admin").text
    for key in ("marketplace", "trace_prints", "msrb_prints"):
        assert f"<code>openyield:{key}</code>" in text
    assert "INS-ref-" in text


def test_the_tools_answer_what_the_pages_show(client: PageClient) -> None:
    connection = client.call_tool("read_connection").data
    assert connection["credentials"] == [{"label": "OpenYield token", "set": True}]
    assert len(connection["securities"]) == 3
    datasets = client.call_tool("read_datasets").data
    assert datasets["curve_record"].startswith("INS-ref-")


def test_the_figures_are_the_role_s() -> None:
    labels = [f.label for f in figures(lake(Recorder("openyield")))]
    assert labels[:5] == [
        "Connection", "Entitled at the vendor", "Stream", "Last recorded", "Rate use",
    ]  # fmt: skip
