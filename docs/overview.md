# Overview

## What it is

OpenYield (openyld.com) runs an all-to-all bond ATS and sells data from it
through its Data Services API: its firm top of book, mids derived from its
firm orders, a live US Treasury benchmark curve, and FINRA TRACE and MSRB
prints it resells. Its coverage: Treasuries, municipal bonds, corporates,
agencies and certificates of deposit. This plugin reads that API with a
token the deployment holds, and holds one role, `data`.

## What it records

- **`marketplace`** -- the ATS's own: each listed security's best bid and
  offer, a quote with the ATS (MIC `OYLD`) as its venue, prices per 100 of
  face; each side's size as the floor of OpenYield's size bucket, marked
  "at least"; each security's mid through the day and at each day's end;
  and the benchmark curve, the on-the-run Treasuries' yields by tenor.
- **`trace_prints`** -- FINRA TRACE's prints of corporates, agencies,
  Treasuries and CDs, as OpenYield resells them, four hours delayed unless
  the account holds a real-time TRACE entitlement.
- **`msrb_prints`** -- MSRB's prints of municipal bonds, as OpenYield
  resells them.

Each print carries its price, its face (TRACE's capped sizes as "at least"),
its TRACE or MSRB sequence number, its contra party and whether it was on an
ATS. The reporting dealer's side and the print's yield are kept as
reported.

## What it does not record

- **A print's cancel or correction**: OpenYield's prints carry neither, so a
  print TRACE corrects stays as first stated here.
- **A print's capacity, when-issued, special-price and primary-market
  flags**: not stated; no flag listed means none stated.
- **Yields as yields**: OpenYield does not state a yield's day count, which
  the lake records with every yield, so each is kept as reported.
- **Reference terms**: OpenYield states next call, put and sink dates, not
  schedules or day counts; the terms come from a reference source.

## Records

It never mints a record. Each security is resolved by its FIGI where
OpenYield states one, else its ISIN and CUSIP (kept on your deployment's
record, never sent). The benchmark curve is OpenYield's own: a local record,
its rates recorded once a person accepts it at the Instruments page.
