"""Complete the locked xAI design that deviation D2 had cut (S3, S4, S5), then re-run the frozen analyses.

Run on the author's instruction of 2026-11-14, after the first analysis of the reduced design:
the xAI primary (grok-4-20-non-reasoning) gets the locked 40 findings and halves, reconstructed from
the frozen selection rule (`plan-locked.json`; the first 10 of each half equal the D2 plan exactly),
N1 trials 101-110 and N2, N3, M1, M2, M3 trials 101-103, as the protocol fixed them. S5 runs the
40 findings on grok-4.7, trials 101-103. Runs already made are skipped. Azure spend is capped so
that all fresh runs of the PF studies stay within the author's USD 500 Azure budget.

    PF_AZURE_NOTES=<notes file> python drive_pf_complete_locked.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import drive_pf_remaining as dr  # noqa: E402  (sets rc.PACE = 0.92, as under D2)
import run_pf_confirmatory as rc  # noqa: E402

R = rc.RESULTS
# All Azure agent runs before this stage cost USD 423.39 (12 to 14 November, all PF result folders),
# and the blind readers at most USD 25 more. This folder's own Azure spend was USD 260.98, so a cap
# of USD 305 for this folder keeps the total below USD 500 in the worst case.
rc.BUDGET["azure"] = 305.0


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} COMPLETE {msg}", flush=True)


def main() -> int:
    plan = json.loads((R / "plan-locked.json").read_text(encoding="utf-8"))
    x = [e for e in plan["primaries"] if e["model"] == "grok-4-20-non-reasoning"][0]
    d2 = json.loads((R / "plan.json").read_text(encoding="utf-8"))
    old = {tuple(k) for e in d2["primaries"] if e["model"] == x["model"] for k in e["findings"]}
    new = {"primaries": [{**x, "findings": [k for k in x["findings"] if tuple(k) not in old]}]}
    allx = {"primaries": [x]}
    assert len(x["findings"]) == 40 and len(new["primaries"][0]["findings"]) == 20
    five = ["N2-json-tool-output", "N3-paraphrased-system", "M1-other-model", "M2-repeat-user-prompt", "M3-spotlighting"]
    # Most valuable first: the 20 new findings' design, then the top-ups of the first 20.
    s34 = (dr.perturb_jobs(new, ["N1-rerun"], range(101, 111)) + dr.perturb_jobs(new, five, range(101, 104))
           + dr.perturb_jobs(allx, ["N1-rerun"], range(101, 111)) + dr.perturb_jobs(allx, five, range(101, 104)))
    s5 = [("grok-4.7", "N1-rerun", t, tuple(k)) for t in range(101, 104) for k in x["findings"]]
    seen: set = set()
    s34 = [j for j in s34 if not (j in seen or seen.add(j))]
    log(f"jobs: s34 {len(s34)} (before skipping done), s5 {len(s5)}; azure cap {rc.BUDGET['azure']}")
    dr.run_parallel([("s34-locked", s34, R / "s34"), ("s5-locked", s5, R / "s5")])
    log("ALL LOCKED RUNS DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
