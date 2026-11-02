"""The plugin's settings, declared to the SDK, and what it makes of them.

In the data role's order (spec/plugin-pages-follow-their-role): no
`environment` (OpenYield's Data Services has one host); the credential; the
plugin's own; then the role's sample data.

- `openyield_token` -- a bearer token OpenYield issued for the deployment's
  account, a secret. The plugin never holds a password: OpenYield's
  documented sign-in exchanges a user's email and password for a token,
  which a person does, never the plugin; a token that does not expire, or a
  service credential, is asked of OpenYield (ruling 871). Without it nothing
  is asked of OpenYield.
- `securities` -- the bonds and CDs whose quotes, mids and prints are kept
  current: a typed table, one column, each an ISIN, a CUSIP or a FIGI. A
  security not listed is read when the lake wants it.
- `sample_data` -- a developer's setting: the answers committed under
  sample/ in place of OpenYield, for the e2e and for trying the plugin
  without a token.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import meridian

TOKEN = "openyield_token"
SECURITIES = "securities"
SECURITY_COLUMN = "security"
SAMPLE_DATA = "sample_data"
MOST_SECURITIES = 500


@meridian.settings
class Declared:
    """The settings as declared, in the data role's order."""

    openyield_token: str = meridian.setting(
        "OpenYield token",
        secret=True,
        description=(
            "A bearer token OpenYield issued for the deployment's account. Never a "
            "password: the plugin does not sign in. Without it the plugin asks OpenYield "
            "nothing."
        ),
    )
    securities: list = meridian.setting(  # type: ignore[type-arg]
        "Securities",
        description=(
            "The bonds and CDs whose quotes, mids and prints are kept current. Any other "
            "is read when a reader wants it."
        ),
        columns=[
            meridian.Column(
                SECURITY_COLUMN,
                kind="text",
                label="ISIN, CUSIP or FIGI",
                required=True,
                description="The security's ISIN, CUSIP or FIGI",
            )
        ],
        most_rows=MOST_SECURITIES,
    )
    sample_data: bool = meridian.sample_data(
        description=(
            "Serve the answers committed with the plugin, made in the shape of OpenYield's "
            "public documentation, instead of asking OpenYield: quotes, mids, the benchmark "
            "curve and prints to 30 October 2026. No token needed. Development deployments "
            "only."
        )
    )


DECLARED = Declared


@dataclass(frozen=True)
class Config:
    token: str = field(default="", repr=False)
    securities: tuple[str, ...] = ()
    sample_data: bool = False


def _securities(rows: object) -> tuple[str, ...]:
    held: list[str] = []
    if not isinstance(rows, Sequence) or isinstance(rows, str):
        return ()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        said = str(row.get(SECURITY_COLUMN, "")).strip().upper()
        if said.isalnum() and len(said) in (9, 12) and said not in held:
            held.append(said)
    return tuple(held)


def config_from(values: Mapping[str, object]) -> Config:
    token = values.get(TOKEN)
    return Config(
        token=token.strip() if isinstance(token, str) else "",
        securities=_securities(values.get(SECURITIES)),
        sample_data=values.get(SAMPLE_DATA) is True,
    )
