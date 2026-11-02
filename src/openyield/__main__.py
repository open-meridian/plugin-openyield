"""OpenYield as an Open Meridian data plugin (rulings 869, 900, 906, 1059):
its ATS's firm top of book, its mids and its live Treasury benchmark curve,
and the TRACE and MSRB prints it resells, into the deployment's lake.

It runs its data role class, `Running` (lake.py, with its lifecycle here),
with `meridian.run` on the sidecar it is launched beside; `meridian.run`
delivers the settings, serves the two pages (page.py), hands it what the
lake wants, and sets the data role's figures on each heartbeat. It reads
OpenYield at start and every five minutes, and its datasets' licences every
minute. It holds nothing else: a restart reads OpenYield again, and the
lake answers what it recorded before unchanged.

Everything it says to the deployment goes through the sidecar; everything
it reads comes from OpenYield's Data Services, with the token the
deployment's Settings hold, or with sample data from the answers committed
with it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import meridian

from .client import openyield
from .declaration import DECLARATION, PORT
from .lake import Lake
from .page import figures, hold, pages
from .settings import config_from

log = logging.getLogger("openyield")

#: How often OpenYield is read, in seconds: every five minutes.
CHECK_SECONDS = 300
LICENCES_SECONDS = 60


class Running(Lake):
    """The data role's class with its lifecycle."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.wake = asyncio.Event()

    async def on_settings(self, delivered: Any) -> None:
        config = config_from(delivered.values)
        self.use(openyield(config.sample_data, config.token, self.now), config.securities,
                 bool(config.token))  # fmt: skip
        self.wake.set()

    async def run(self) -> None:
        await asyncio.gather(self._check(), self._licences())

    async def _check(self) -> None:
        while True:
            self.wake.clear()
            try:
                await self.check()
            except meridian.MeridianError as failed:
                self.status.last_error = f"the deployment refused a recording: {failed}"
                log.warning("this check stopped: %s", failed)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self.wake.wait(), timeout=CHECK_SECONDS)

    async def _licences(self) -> None:
        while True:
            try:
                await self.wants.read_licences()
            except meridian.MeridianError as failed:
                log.warning("the datasets' licences were not read this time: %s", failed)
            await asyncio.sleep(LICENCES_SECONDS)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    lake = Running()
    hold(lake)
    meridian.run(
        declaration=DECLARATION,
        roles=[lake],
        pages=pages,
        port=PORT,
        on_settings=lake.on_settings,
        figures=lambda: figures(lake),
    )


if __name__ == "__main__":
    main()
