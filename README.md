# meridian-openyield

OpenYield's bond data in an [Open Meridian](https://open-meridian.dev)
deployment: an Apache-2.0 data plugin, in Python on the open-meridian SDK
0.36.0 (contract 30), built from OpenYield's public Data Services
documentation.

It records, for the securities a deployment lists and any a reader wants:

- **`marketplace`** -- OpenYield's ATS's firm top of book (quotes, the ATS
  their venue), its mids, and its live US Treasury benchmark curve;
- **`trace_prints`** and **`msrb_prints`** -- the FINRA TRACE and MSRB prints
  OpenYield resells, each naming its underlying source.

Access needs an OpenYield Data Services Agreement and a token OpenYield
issues; the plugin never holds a password ([docs/setup.md](docs/setup.md)).
The terms are yours and OpenYield's to settle ([docs/terms.md](docs/terms.md)).

## Developing it

`AGENTS.md` is the plugin's guide for people and coding agents alike.

    make ci-remote     # lint and tests, in a container
    make check         # meridian plugin check --verified --run-tests
    make e2e           # the plugin on the plugin harness, on sample data
    make preview SHOTS=<dir>   # its pages in a browser, at 375, 582 and 1280 px

Changes land through a pull request; CI (`ci`, `check`, `e2e`) is the gate.
