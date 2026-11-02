"""`make e2e`: the plugin on the plugin harness of the runtime it pins
(contract v29), beside `reader`, a reporting plugin (e2e/reader.py) entitled
to its datasets, and the harness's admin. Run from the repository's root by
the Makefile, which builds the image and writes the harness's plugins first;
standard library only.

No OpenYield token is used: OpenYield's API answers nowhere (the e2e's hosts
file), and sample data answers from the answers committed with the plugin,
made in the shape of OpenYield's public documentation.

1. No token: Connection says "No key", and nothing is recorded.
2. Sample data on, three securities listed -- a corporate, a Treasury and a
   municipal bond -- each resolved.
3. Parity: through the deployment's MCP, `read_connection` answers what the
   page shows -- the token not set, three securities each a record -- and
   `read_datasets` the three datasets; core's `dashboard__list_datasets`
   lists the prints' datasets naming their underlying source, OpenYield
   their aggregator.
4. The benchmark curve's record, kept local since it is OpenYield's own,
   completed by the deployment admin through core's
   `dashboard__complete_instruments` as the plugin stated it.
5. The lake holds the three quotes, the mids (the corporate's five days,
   the Treasury's and the municipal's one each), the curve's fourteen points
   (today's and the previous close), the corporate's three TRACE prints and
   the municipal's two MSRB prints, one TRACE print capped.
6. Licensed and entitled, the reader reads the benchmark curve of 30
   October: seven points in tenor order, the 10-year 4.262 per cent.
"""

import json
import os
import subprocess
import sys
import time

PROJECT = "openyield-e2e"
LOG = ".e2e/runner.log"
COMPONENTS = ".e2e/components.log"
COMPOSE = ["docker", "compose", "-p", PROJECT, "-f", ".e2e/harness/compose.yaml",
           "-f", ".e2e/harness/plugins.yaml", "-f", "e2e/plugin.yaml"]
INSTANCE = "openyield"
KEYS = ["marketplace", "trace_prints", "msrb_prints"]
DATASETS = [f"{INSTANCE}:{key}" for key in KEYS]
MARKETPLACE, TRACE, MSRB = DATASETS
SECURITIES = ["US037833EW60", "US91282CQB09", "US6500441A14"]
CURVE = "OPENYIELD_UST_BENCHMARK"
DAY = "2026-10-30"


class Failed(Exception):
    pass


def log(text):
    with open(LOG, "a", encoding="utf-8") as kept:
        kept.write(text + "\n")


def compose(*args, check=True, timeout=600):
    done = subprocess.run(COMPOSE + list(args), capture_output=True, text=True,
                          timeout=timeout)
    log(f"$ compose {' '.join(args)[:300]}\n{done.stdout[-4000:]}{done.stderr[-2000:]}")
    if check and done.returncode != 0:
        raise Failed(f"compose {' '.join(args)[:200]}: {(done.stdout + done.stderr).strip()[-600:]}")
    return done


def runner(*args, check=True):
    done = compose("run", "--rm", "-T", "runner", *args, check=check)
    return done.stdout if check else done


def must(condition, why):
    if not condition:
        raise Failed(why)


def until(seconds, attempt, what):
    deadline = time.monotonic() + seconds
    last = None
    while True:
        try:
            answer = attempt()
        except Failed as failed:
            answer, last = None, failed
        if answer:
            return answer
        if time.monotonic() > deadline:
            raise Failed(f"{what}, in {seconds} seconds" + (f": {last}" if last else ""))
        time.sleep(2)


def page(instance, level, path):
    said = runner("page", "--instance", instance, "--level", level, path)
    status, _, body = said.partition("\n")
    must(status.strip() == "200", f"{instance} {path} answered {said[-600:]}")
    return body


def call(tool, arguments=None):
    done = runner("mcp", "call", tool, json.dumps(arguments or {}), check=False)
    try:
        answer = json.loads(done.stdout)
    except ValueError:
        raise Failed(f"{tool}: no answer: {(done.stdout + done.stderr)[-400:]}")
    must(answer.get("outcome") in ("read", "unchanged"), f"{tool} answered {done.stdout[-700:]}")
    return answer["data"]


def store_lake():
    return compose("run", "--rm", "-T", "store", "lake").stdout


def reader(path):
    return json.loads(page("reader", "read", path))


def run():
    started = time.time()
    compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
    compose("up", "-d")
    runner("ready")
    runner("ready", "--instance", "reader")

    # 1. No token.
    runner("page", "--level", "admin", "/", "--until", "No key", "--seconds", "90")
    must("row|" not in store_lake(), "step 1, nothing recorded without a token")

    # 2. Sample data, three securities listed.
    listed = [f"securities[{n}].security={s}" for n, s in enumerate(SECURITIES)]
    runner("settings", "sample_data=true", *listed)
    runner("page", "--level", "admin", "/", "--until", "3 of 3 resolved", "--seconds", "180")

    # 3. Parity through the deployment's MCP, and core's view of the catalogue.
    runner("grant", "--level", "admin")
    runner("mcp", "connect", "--covers", "deployment_admin", "--covers", f"{INSTANCE}:admin")
    tools = runner("mcp", "list").split()
    read_connection = next((t for t in tools if t.endswith("read_connection")), "")
    read_datasets = next((t for t in tools if t.endswith("read_datasets")), "")
    must(read_connection and read_datasets, f"step 3, the plugin's two tools are listed: {tools}")
    connection = call(read_connection)
    must(connection["mode"] == "Sample data"
         and connection["credentials"] == [{"label": "OpenYield token", "set": False}]
         and sorted(s["security"] for s in connection["securities"]) == sorted(SECURITIES)
         and all(s["record"].startswith(("INS-", "LCL-")) for s in connection["securities"]),
         f"step 3, read_connection: {connection}")
    datasets = call(read_datasets)
    must([s["dataset"] for s in datasets["served"]] == DATASETS, f"step 3, read_datasets: {datasets}")
    listed = {d["dataset"]: d for d in call("dashboard__list_datasets")["datasets"]}
    must(all(d in listed for d in DATASETS), f"step 3, core lists the three datasets: {list(listed)}")
    trace = listed[TRACE].get("catalogue_entry", {})
    must(trace.get("vendor") == "FINRA TRACE" and trace.get("aggregator") == "OpenYield",
         f"step 3, core lists {TRACE} naming its underlying source: {listed[TRACE]}")

    # 4. The benchmark curve's record, completed as the plugin stated it.
    records = call("dashboard__list_instruments_to_complete")["records"]
    own = [r for r in records for i in r["identifiers"]
           if i["source"] == "openyield" and i["value"] == CURVE]
    must(len(own) == 1, f"step 4, the curve's record listed to complete: {records}")
    done = runner("mcp", "call", "dashboard__complete_instruments", json.dumps({"completions": [
        {"instrument_id": own[0]["instrument_id"], "against_version": own[0]["version"],
         "values": [{"asset_class": "ASSET_CLASS_REFERENTIAL"}, {"currency": "USD"},
                    {"instrument_type": "INSTRUMENT_TYPE_RATE_CURVE"}],
         "source": "OpenYield's plugin, as it stated the record",
         "note": "OpenYield's own benchmark curve, accepted as its plugin states it."}]}),
        check=False)
    must('"outcome": "made"' in done.stdout, f"step 4, the record completed: {done.stdout[-600:]}")
    curve_record = own[0]["instrument_id"]
    flipped = [f"securities[{n}].security={s}" for n, s in enumerate(reversed(SECURITIES))]
    runner("settings", "sample_data=true", *flipped)

    # 5. The lake.
    def keys(dataset, kind):
        return {line.split("|")[4] for line in store_lake().splitlines()
                if line.startswith(f"row|{dataset}|{kind}|")}

    until(120, lambda: len(keys(MARKETPLACE, "rate")) == 14,
          "step 5, the benchmark curve's fourteen points were not recorded")
    quotes, mids = keys(MARKETPLACE, "quote"), keys(MARKETPLACE, "price")
    traced, munis = keys(TRACE, "trade"), keys(MSRB, "trade")
    must(len(quotes) == 3, f"step 5, three quotes: {quotes}")
    must(len(mids) == 7, f"step 5, seven mids, each a security's day: {sorted(mids)}")
    must(len(traced) == 3 and len(munis) == 2, f"step 5, the prints: {traced} {munis}")

    # 6. Licensed and entitled: the benchmark curve of 30 October.
    runner("licence", MARKETPLACE, "kept=true", "retention_days=0", "derived_use=false",
           "display=true", "personal_use=false", "note=OpenYield's agreement, as the deployment's.")
    runner("entitle", "--instance", "reader", MARKETPLACE, "note=The e2e's reader reads them.")
    runner("grant", "--instance", "reader", "--level", "read")
    curve = until(90, lambda: (lambda r: r if len(r["rates"]) == 7 else None)(
        reader(f"/curve?subject={curve_record}&date={DAY}&dataset={MARKETPLACE}")),
        "step 6, the benchmark curve of 30 October was not read")
    points = curve["rates"]
    ten = [r for r in points if r["tenor"] == "10Y"]
    must([r["tenor"] for r in points] == ["2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"]
         and ten and ten[0]["value"] == "4.262" and ten[0]["kind"] == "RATE_KIND_PAR_YIELD"
         and ten[0]["convention"] == ["DAY_COUNT_ACT_ACT", "COMPOUNDING_COMPOUNDED", 2],
         f"step 6, the curve in tenor order: {curve}")

    print(f"e2e OK in {int(time.time() - started)}s on the plugin harness: no token said and nothing "
          f"recorded; three securities resolved; read_connection and read_datasets answering what "
          f"the pages show, core listing the prints' datasets under their underlying sources; the "
          f"benchmark curve's local record completed; three quotes, seven mids, fourteen curve "
          f"points and five prints in the lake; and the curve of 30 October read in tenor order "
          f"(10-year 4.262)")


def main():
    os.makedirs(".e2e", exist_ok=True)
    open(LOG, "w").close()
    try:
        run()
    except (Failed, subprocess.TimeoutExpired, KeyError, ValueError, IndexError, TypeError) as failed:
        with open(COMPONENTS, "a", encoding="utf-8") as kept:
            kept.write(compose("logs", "--no-color", check=False).stdout)
        compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
        print(f"e2e FAILED: {failed}; the runner's log is in {LOG}, the components' in {COMPONENTS}",
              file=sys.stderr)
        return 1
    compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
