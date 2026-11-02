"""The plugin's pages, as an admin of the plugin sees them through the
deployment's dashboard: the data role's common pages
(spec/plugin-pages-follow-their-role), built on `meridian.roles.data`.

A data plugin shows its connection and its datasets, never a value: quotes,
prices, rates and prints are the reading roles' to show. Both pages are at
`admin`, under the dashboard's Manage, in the role's order:

- Connection (/): "Key", "Limits and use" and "Stream", from
  `ConnectionRead`; OpenYield's own rows in "Key": "Access" -- a token,
  never a password -- and "Securities", each listed security's record;
- Datasets (/datasets): "Served", "Wants" and "Subjects", from
  `DatasetsRead`, with a notice of what OpenYield stated that was not
  recorded or what the lake refused, and the benchmark curve's record.

Each page declares the record it renders (`answers=`), so it is also a read
tool on the deployment's MCP surface: `read_connection` and
`read_datasets`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import meridian
from meridian.roles import data

if TYPE_CHECKING:
    from .lake import Lake

TITLE = "OpenYield"
KEY_LABEL = "OpenYield token"
#: How the plugin reaches OpenYield (ruling 871's access question).
ACCESS = (
    "A bearer token OpenYield issued; the plugin never holds a password. A token that "
    "does not expire, or a service credential, is asked of OpenYield."
)

pages = meridian.Pages(TITLE, templates=Path(__file__).parent / "templates")

running: list[Lake] = []


def hold(lake: Lake) -> None:
    running[:] = [lake]


@dataclass(frozen=True)
class SecurityRead:
    security: str
    description: str = ""
    record: str = ""
    miss: str = ""


@dataclass(frozen=True)
class ConnectionRead(data.ConnectionRead):
    """Connection's common fields, then OpenYield's: how it is reached, and
    each listed security."""

    access: str = ""
    securities: list[SecurityRead] = field(default_factory=list)
    checked_at: str = ""


@dataclass(frozen=True)
class DatasetsRead(data.DatasetsRead):
    """Datasets' common fields, then OpenYield's: the benchmark curve's
    record, and what was stated but not recorded or refused."""

    served: list[data.Served] = field(default_factory=list)
    wants: list[data.WantHeard] = field(default_factory=list)  # type: ignore[assignment]
    curve_record: str = ""
    not_recorded: list[str] = field(default_factory=list)


def mode(lake: Lake) -> str:
    if lake.source.mode == "synthetic":
        return "Sample data"
    return "Live" if lake.has_token else "No key"


def _held(record: str) -> str:
    return record if record.startswith(("INS-", "LCL-")) else ""


def connection_read(lake: Lake) -> ConnectionRead:
    source = lake.source
    return ConnectionRead(
        mode=mode(lake),
        credentials=[data.Credential(KEY_LABEL, lake.has_token)],
        entitled_at_vendor=f"{len(lake.securities)} securities listed",
        limit="One request at a time, two a second; 5,000 references a day",
        calls=source.calls,
        rate_limited=source.rate_limited,
        last_call_at=source.last_call_at,
        last_error=source.failed or lake.status.last_error,
        sessions=None,
        access=ACCESS,
        securities=[
            SecurityRead(
                security=named,
                description=row.get("description", ""),
                record=_held(row.get("record", "")),
                miss="" if _held(row.get("record", "")) else row.get("record", ""),
            )
            for named, row in sorted(lake.status.securities.items())
        ],
        checked_at=lake.status.checked_at,
    )


def datasets_read(lake: Lake) -> DatasetsRead:
    from .declaration import DECLARATION

    instance = lake.plugin.identity.instance_id if lake._role_plugin is not None else ""
    said = [f"{what} ({n})" for what, n in sorted(lake.status.unread.items())]
    said += [f"{what}: {why}" for what, why in sorted(lake.status.refused.items())]
    return DatasetsRead(
        served=data.served(DECLARATION.catalogue, instance, lake.wants,
                           f"{len(lake.securities)} securities listed"),
        wants=list(data.want_rows(lake.wants)),
        curve_record=lake.status.curve_record,
        not_recorded=said,
    )  # fmt: skip


def _lake() -> Lake:
    if running:
        return running[0]
    from .lake import Lake

    return Lake()


@pages.page("/", "Connection", levels="admin", answers=ConnectionRead, name="read_connection")
async def connection(request: meridian.Request) -> meridian.Response:
    """Whether OpenYield answers, how it is reached, and each listed
    security's record."""
    return pages.answer("connection.html", connection_read(_lake()))


@pages.page("/datasets", "Datasets", levels="admin", answers=DatasetsRead, name="read_datasets")
async def datasets(request: meridian.Request) -> meridian.Response:
    """Each dataset this plugin serves the lake, whether it is licensed, the
    wants it answered, and the benchmark curve's record."""
    return pages.answer("datasets.html", datasets_read(_lake()))


def figures(lake: Lake) -> list[meridian.Figure]:
    source = lake.source
    return data.figures(
        connection=mode(lake) if mode(lake) != "Live" else (
            "Not answering" if source.failed else "Answering"),
        entitled_at_vendor=f"{len(lake.securities)} securities listed",
        stream="Does not stream",
        last_recorded=lake.status.checked_at or "None yet",
        rate_use=f"{source.calls} calls",
    )  # fmt: skip
