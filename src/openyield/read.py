"""Reading OpenYield's answers, once, at the edge.

OpenYield writes every number as a string ("94.53", "5.230"), so each is
read as a `Decimal` from OpenYield's own text, exactly, never through a
binary float. A print's time is New York local time without an offset, as
OpenYield states it; a snapshot's (`as_of`) is UTC.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")


def parse(text: str) -> dict[str, Any]:
    """OpenYield's JSON; any number it wrote as a JSON number a Decimal."""
    try:
        read = json.loads(text, parse_float=Decimal, parse_int=Decimal)
    except ValueError:
        return {}
    return read if isinstance(read, dict) else {}


def number(value: Any) -> Decimal | None:
    """A number as OpenYield wrote it, or None where it states none."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return Decimal(value.strip())
        except InvalidOperation:
            return None
    return None


def text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if isinstance(value, str) and value else None
    except ValueError:
        return None


def new_york(value: Any) -> datetime | None:
    """A print's `as_at`, New York local time without an offset."""
    if not isinstance(value, str) or not value:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=NEW_YORK)


def utc(value: Any) -> datetime | None:
    """A snapshot's `as_of`, in UTC (`2026-05-07T18:30:00Z`)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def ns(moment: datetime) -> int:
    return int(moment.timestamp()) * 1_000_000_000 + moment.microsecond * 1_000


def ny_day(moment: datetime) -> date:
    return moment.astimezone(NEW_YORK).date()
