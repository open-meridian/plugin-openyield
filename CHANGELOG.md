# Changelog

## 0.2.0

On open-meridian 0.36.0, contract 30, on core aae501d's harness (chart
0.1.538); `meridian` 0.1.60 in the check. What the plugin records is
unchanged.

- **OpenYield's terms in words** (ruling 1032): each dataset's
  `terms_and_pricing` names its underlying source (OpenYield's ATS, FINRA
  TRACE as resold, MSRB as resold, with their terms alongside) and what
  OpenYield publishes (a Data Services Agreement, institutional use,
  pricing by agreement), shown on Data sources and in the Datasets page's
  row details. The plugin still declares no licence.
- **A gap recovered by backfill** (`gap_recovery`): OpenYield serves its
  mids about three months back and its prints a week, read again on a want.
- **TRACE's prints follow TRACE's hours** (`sessions_calendar_id`, ruling
  455): `trace_prints` names the platform's US bond market sessions
  (`CAL-01M6CDQRFE48WF62BG9KFJEEEB`: FINRA's TRACE system hours with SIFMA's
  recommended early closes). The ATS's own hours and MSRB's are no calendar
  the platform curates yet.
- **Row keys checked against the lake's rule 5** (ruled 2026-11-12): a
  quote is keyed by its ISIN and its time, never restated; a day's mid by
  its ISIN and New York day, restated as it moves over the same day and
  security; the benchmark curve through the SDK's `rates.Feed`, keyed by
  its day and record. A print is keyed by its source, New York day and
  OpenYield's sequence (`trace:<day>:<sequence>`), naming no security: were
  a sequence not unique within a day, two prints would collide as a
  restatement changing the first subject and valid time; and TRACE's and
  MSRB's corrections are not carried (asked of OpenYield). Listed for step
  3d, unchanged.
- `meridian plugin migrate --to 0.36.0` moved the pins (the base by
  digest, `meridian` 0.1.60); the test of the absent licence reads the
  words instead.
- Core's runtime and harness images at `aae501d`, by digest.

## 0.1.0

The first version, on open-meridian 0.35.3 (contract v29), built from
OpenYield's public Data Services documentation (rulings 868, 869, 1059).

- `marketplace`: the ATS's firm top of book as quotes, the ATS (`OYLD`) its
  venue, size buckets as their floors "at least" (900's R2, R6); its mids as
  prices of class `firm_quote` (906); its live Treasury benchmark curve as
  rates on OpenYield's own local curve record.
- `trace_prints` and `msrb_prints`: the TRACE and MSRB prints OpenYield
  resells, each dataset naming its underlying source, with the fixed-income
  characteristics and TRACE's capped sizes as `quantity_capped`; no cancel or
  correction (900's R3) and no capacity or other flag (R4) presented.
- A bearer token, never a password: the access question (ruling 871) in
  docs/setup.md and docs/terms.md.
- No default licence declared (rulings 1030 to 1032).
