# Troubleshooting

## Connection

| What you see | What it means | What to do |
|---|---|---|
| **No key** | No OpenYield token is set | Paste a token OpenYield issued in Settings |
| **OpenYield refused the token** | It has expired, or is not one OpenYield issued | Ask OpenYield for a new token and paste it |
| Calls **rate-limited** | OpenYield answered 429; the plugin waited | Nothing; past 5,000 references a day, ask OpenYield for more |

## Records and prints

| What you see | What it means | What to do |
|---|---|---|
| A security **not covered by OpenYield** | OpenYield holds no reference for it | Check the identifier; read it from another source |
| A security's record **ambiguous** | Its identifiers meet two of your records | Merge them at the Instruments page |
| The benchmark curve **awaits a person's acceptance** | Its record is local, its class and type only offered | Accept them at the Instruments page |
| A print **reported with no price** | MSRB disseminated it without one | Nothing: it is not recorded |

## Wants

| What you see | What it means | What to do |
|---|---|---|
| A subject declined, *not covered* | Not a security OpenYield covers, or a municipal bond asked of TRACE's prints | Read it from the right dataset |
| Datasets: **Not licensed yet** | No deployment admin has licensed the dataset | Ask a deployment admin to license it on Data sources |
