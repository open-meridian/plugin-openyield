# Changelog

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
