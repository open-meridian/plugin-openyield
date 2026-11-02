"""OpenYield's API as the plugin asks it: the token, a 401, a 429, and the
stand-in's answers."""

from __future__ import annotations

import asyncio

import pytest

from openyield import client
from openyield.client import LiveOpenYield, NoToken

from conftest import APPLE, AT, source


def test_no_token_asks_nothing() -> None:
    with pytest.raises(NoToken):
        asyncio.run(LiveOpenYield("").get("/prices/yield_curve"))


def test_a_refused_token_is_said_and_never_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    live = LiveOpenYield("secret-token", lambda: AT)

    def get(path: str) -> tuple[client.Fetched, float]:
        body = client.redacted('{"detail": "bad token secret-token"}', "secret-token")
        return client.Fetched(path, 401, body, AT), 60.0

    monkeypatch.setattr(live, "_get", get)
    got = asyncio.run(live.get("/prices/yield_curve"))
    assert "secret-token" not in got.body and "expired" in live.failed


def test_a_429_is_waited_out(monkeypatch: pytest.MonkeyPatch) -> None:
    live = LiveOpenYield("t", lambda: AT)
    monkeypatch.setattr(live, "_get", lambda path: (client.Fetched(path, 429, "{}", AT), 30.0))
    asyncio.run(live.get("/reference/security/x"))
    assert live.rate_limited == 1 and live._not_before > 0


def test_the_stand_in_answers_by_any_identifier() -> None:
    sample = source()
    for named in (APPLE, "037833EW6", "BBG01G3PQ9C7"):
        got = asyncio.run(sample.get(f"/reference/security/{named}"))
        assert got.ok and APPLE in got.body
    assert asyncio.run(sample.get("/reference/security/NOPE")).status == 404
    day = asyncio.run(sample.get(f"/reported/security/2026-10-30/{APPLE}"))
    assert day.body.count('"sequence"') == 3
