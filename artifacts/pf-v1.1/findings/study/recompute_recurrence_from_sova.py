"""Recompute the published-GPT-4o recurrence result of section 6.2 from the .sova capsule alone.

The capsule holds, for each of the 629 attack instances shared by AgentDojo's published
GPT-4o log (2024) and our fresh GPT-4o run (2026), both runs as .sova-traces. This script
verifies the capsule offline, compares each pair's declared outcome (AgentDojo's security
verdict, the `oracle.completed` event) with SOVA's own comparator, and tallies recurrence.
It calls no model, runs no benchmark code, and needs only the SOVA OSS package.

    python -X utf8 recompute_recurrence_from_sova.py gpt-4o-2024-vs-2026.sova [result.json]
"""

from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

from sova.formats import canonical_json_bytes
from sova.formats.package import PackageReader
from sova.reproduction import compare_observable_outcomes
from sova.trace.reader import TraceReader


def recompute(capsule: Path) -> dict:
    PackageReader(capsule).verify("sova.capsule")
    tally = {"recurred": 0, "notRecurred": 0, "freshOnly": 0, "neither": 0, "inconclusive": 0}
    by_goal: dict[str, dict[str, int]] = defaultdict(lambda: {"a": 0, "b": 0, "c": 0, "d": 0})
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(capsule) as package:
        names = sorted(n for n in package.namelist() if n.startswith("traces/") and n.endswith(".sova-trace"))
        pairs = sorted({n[len("traces/"):].rsplit("--", 1)[0] for n in names})
        for instance in pairs:
            paths = {}
            for side in ("published-2024", "fresh-2026"):
                target = Path(tmp) / f"{instance}--{side}.sova-trace"
                target.write_bytes(package.read(f"traces/{instance}--{side}.sova-trace"))
                paths[side] = target
            outcome = next(e for e in TraceReader(paths["published-2024"]).events() if e["kind"] == "oracle.completed")
            published = outcome["payload"]["attackSucceeded"]
            result = compare_observable_outcomes(paths["published-2024"], paths["fresh-2026"], kinds=("oracle.completed",))
            if result.status == "inconclusive":
                tally["inconclusive"] += 1
                continue
            same = result.status == "equivalent"
            key = ("recurred" if same else "notRecurred") if published else ("neither" if same else "freshOnly")
            tally[key] += 1
            suite, _user, injection = instance.split("--")
            cell = {"recurred": "a", "notRecurred": "b", "freshOnly": "c", "neither": "d"}[key]
            by_goal[f"{suite}/{injection}"][cell] += 1
    num = sum(g["a"] * g["d"] / sum(g.values()) for g in by_goal.values())
    den = sum(g["b"] * g["c"] / sum(g.values()) for g in by_goal.values())
    published_successes = tally["recurred"] + tally["notRecurred"]
    others = tally["freshOnly"] + tally["neither"]
    return {
        "artifactType": "sova.pf-recurrence-from-sova",
        "capsule": capsule.name,
        "comparator": "sova.reproduction.compare_observable_outcomes, kinds=[oracle.completed]",
        "instances": len(pairs),
        "tally": tally,
        "recurrence": f"{tally['recurred']} of {published_successes}",
        "recurrencePercent": f"{100 * tally['recurred'] / published_successes:.1f}%",
        "freshRateOnOthers": f"{tally['freshOnly']} of {others}",
        "freshRateOnOthersPercent": f"{100 * tally['freshOnly'] / others:.1f}%",
        "mantelHaenszelOddsRatioByGoal": f"{num / den:.1f}",
    }


def main() -> int:
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    report = recompute(Path(sys.argv[1]))
    text = json.dumps(report, indent=2)
    print(text)
    if len(sys.argv) == 3:
        Path(sys.argv[2]).write_bytes(canonical_json_bytes(report) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
