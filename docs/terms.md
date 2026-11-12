# Terms

## Whose terms

The terms under which you use OpenYield's data are in your OpenYield Data
Services Agreement, which is not public, and are between you and OpenYield
Trading LLC. Each dataset describes them in words on the Data sources page;
the plugin declares no licence: the deployment admin sets each dataset's
licence there. What follows describes
what OpenYield publishes, as read on 30 October 2026, to help you and your
agent decide; it is not legal advice.

## What OpenYield publishes

- **Access** requires a signed Data Services Agreement; data services are
  for institutional use.
- **Its website's terms of use** (openyld.com/terms-of-use) cover the
  website, not the API: a limited licence for your own use, no resale and
  no compiling its content into a database.
- **Pricing** is not published; data services are priced by agreement, with
  add-ons for the trade tape, reference, the calculator and prints.

## Underlying sources

- `marketplace`: OpenYield's own ATS, its firm all-to-all order book.
- `trace_prints`: FINRA's TRACE, resold under a separate licence; real-time
  TRACE is a per-account entitlement, otherwise four hours delayed.
- `msrb_prints`: MSRB's dissemination of municipal trades.

FINRA's and MSRB's terms for their data may apply alongside OpenYield's.

## Open questions

Put to OpenYield (the plugin waits on its answers): a token that does not
expire, or a service credential, rather than a user's login; what a
deployment may keep and display; whether its prints can carry TRACE's and
MSRB's cancels, corrections and capacity; the day count of the yields it
states; and confirmation that its mids and top of book are clean prices.
