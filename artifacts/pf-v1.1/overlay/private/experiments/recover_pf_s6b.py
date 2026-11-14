"""Recover study S6b's results from what its runs wrote to disk (deviation D5).

The frozen `compare_pf_tasks_ext.py` ran every task, but read the wrong thing back:

  T8  it kept the last stdout line that parses as JSON, which for `sova rerun --json` (indented
      output) is an inner string such as "gpt-4o-2024-11-20", not the summary. The runs themselves
      completed (exit 0) and wrote their records to s6b/rerun-*/runs.jsonl and a capsule each.
  T10 it passed --max-usd without --price-in/--price-out, which `sova matrix` refuses (exit 2) because
      it cannot enforce the cap. `run_pf_s6b_t10.py` ran the same call with the prices added.

This script reads T8 from each runs.jsonl, checks each re-run capsule with `sova verify`, takes T10
from s6b-t10.json and T9 unchanged from s6b-tasks.json, and writes s6b-tasks-recovered.json.
No model is called.

    python recover_pf_s6b.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE / "results" / "pf-confirmatory-2026-11-14"
SOVA_REPO = HERE.parents[1]


def main() -> int:
    frozen = json.loads((R / "s6b-tasks.json").read_text(encoding="utf-8"))
    t8 = []
    for x in frozen["T8"]:
        stem = x["finding"][: -len(".sova")]
        folder = R / "s6b" / f"rerun-{stem}-{x['model']}"
        runs = [json.loads(line) for line in (folder / "runs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        verdicts = Counter(r["verdict"] for r in runs)
        judged = verdicts["attack"] + verdicts["no-attack"]
        capsules = sorted(folder.glob("*.sova"))
        checks = [subprocess.run(["uv", "run", "--project", str(SOVA_REPO), "sova", "verify", str(c)], cwd=str(SOVA_REPO),
                                 capture_output=True, text=True, encoding="utf-8").returncode for c in capsules]
        t8.append({"finding": x["finding"], "model": x["model"], "exit": x["exit"], "seconds": x["seconds"],
                   "summary": {"attacks": verdicts["attack"], "judged": judged, "runs": len(runs),
                               "cantTell": len(runs) - judged, "errors": sum(1 for r in runs if r.get("error")),
                               "returnedModels": sorted({m for r in runs for m in r.get("returnedModels") or []}),
                               "costUsdEstimate": round(sum(float(r.get("costUsdEstimate") or 0) for r in runs), 6)},
                   "capsules": [c.name for c in capsules], "capsulesVerified": sum(1 for c in checks if c == 0)})
    t10 = json.loads((R / "s6b-t10.json").read_text(encoding="utf-8"))
    doc = dict(frozen, T8=t8, T10={k: t10[k] for k in ("exit", "seconds", "summary", "argsAdded")},
               artifactType="sova.pf-s6b-tasks-recovered",
               recovery={"deviation": "D5", "script": "recover_pf_s6b.py",
                         "T8": "read from s6b/rerun-*/runs.jsonl; the frozen script's summary field held an inner JSON string",
                         "T10": "frozen call refused (exit 2: --max-usd needs --price-in and --price-out); re-run by "
                                "run_pf_s6b_t10.py with --price-in 2.5 --price-out 10 added",
                         "frozenOutput": "s6b-tasks.json (unchanged)"})
    (R / "s6b-tasks-recovered.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for x in t8:
        s = x["summary"]
        print(f"T8 {x['finding']} {x['model']}: {s['attacks']} of {s['judged']} ({s['runs']} runs), capsules verified {x['capsulesVerified']}/{len(x['capsules'])}")
    print("T10", t10["exit"], (t10.get("summary") or {}).get("upgrade", {}).get("counts"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
