# Setup

## Access

Access to OpenYield's Data Services needs a signed OpenYield Data Services
Agreement. OpenYield's documented sign-in exchanges a user's email and
password for a bearer token; **this plugin never holds a password**. Ask
OpenYield for a token issued to your account, and paste it in the
plugin's settings. A token expires when OpenYield says; the Connection page
says when OpenYield refuses it.

## Launching it

Launch the plugin and approve its role, `data`. In the Settings form:

- **OpenYield token** -- the bearer token, a secret: never shown again,
  logged or put on a page.
- **Securities** -- the bonds and CDs whose quotes, mids and prints are kept
  current, one ISIN, CUSIP or FIGI a row, up to 500. Any other is read when
  a reader wants it.
- **Sample data**, on a deployment installed for development only: answers
  committed with the plugin, in the shape of OpenYield's public
  documentation, in place of OpenYield.

It reads OpenYield at once and every five minutes: the benchmark curve and
each listed security's top of book, mid and recent prints; once a day each
listed security's reference and its daily mids, three months back.

## Its datasets

On the deployment's **Data sources** page (deployment admins): license
`<instance>:marketplace`, `trace_prints` and `msrb_prints` on the terms of
your agreement with OpenYield (and FINRA's and MSRB's for the prints);
entitle the plugins that read them; and set their priority among your other
sources of the same securities.

## The benchmark curve's record

OpenYield's benchmark curve is no record the platform curates, so your
deployment keeps it local (`OPENYIELD_UST_BENCHMARK`). Accept its class
(referential), type (a rate curve) and currency at the **Instruments** page;
its points are recorded from the next read.
