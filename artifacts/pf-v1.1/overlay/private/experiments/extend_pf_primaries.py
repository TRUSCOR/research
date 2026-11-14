"""PF extension E1: more primary models for S3, S4 and S5, and a third blind reader for S7.

Frozen by `PF-extension-addendum-2026-11-14.md` before any of its runs. Steps:

    python extend_pf_primaries.py select   # writes plan-extended.json (no model call)
    python extend_pf_primaries.py run      # S3/S4/S5 runs for the added primaries (calls models)
    python extend_pf_primaries.py read     # third blind reader over the frozen S7 items (calls a model)
    python extend_pf_primaries.py analyze  # frozen analyses over all primaries (no model call)

Selection rule for added primaries: every model with at least 40 confirmed action-goal attacks
(the text goal excluded) in its trial-1 baseline runs of S2 or of a full pass, that is not already a
primary. Findings and halves are drawn exactly as analyze_pf_v2.select draws them
(random.Random(f"{SEED}:{model}"), 40 findings, seeded shuffle, two halves).
"""

from __future__ import annotations

import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_pf_v2 as an  # noqa: E402

R = HERE / "results" / "pf-confirmatory-2026-11-14"
MIN_ELIGIBLE = 40
ALTERNATIVE = "gpt-4o"  # M1 model for every added primary: the fastest attack-prone deployment of another developer
UPGRADES = {"grok-4-1-fast-non-reasoning": "grok-4.7"}  # S5 pairs for added primaries (same developer, newer model)
THIRD_READER = "cohere-command-a"  # a fourth developer; not a primary model
AZURE_CAP_FOR_THIS_FOLDER = None  # set in run(): keeps all PF Azure spend within USD 700


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} EXTEND {msg}", flush=True)


def select() -> None:
    base = json.loads((R / "plan-locked.json").read_text(encoding="utf-8"))
    current = {e["model"] for e in base["primaries"]}
    rows = [r for d in (R / "s2", R / "s2-grok-full") for r in an.load(d) if r["condition"] == "baseline" and r["trial"] == 1]
    conf: dict[str, set] = defaultdict(set)
    for r in rows:
        if r["category"] == "confirmed" and (r["suite"], r["injectionTask"]) != an.TEXT_GOAL:
            conf[r["model"]].add(an.key(r))
    added = sorted(m for m, ks in conf.items() if len(ks) >= MIN_ELIGIBLE and m not in current)
    plan = dict(base)
    plan["extension"] = {"rule": f">= {MIN_ELIGIBLE} confirmed action-goal attacks in trial-1 baseline runs; not already a primary",
                         "eligibleCounts": {m: len(ks) for m, ks in sorted(conf.items())}, "added": added}
    for m in added:
        pool = sorted(conf[m])
        rng = random.Random(f"{an.SEED}:{m}")
        chosen = sorted(rng.sample(pool, min(an.FINDINGS_PER_PRIMARY, len(pool))))
        order = chosen[:]
        rng.shuffle(order)
        half = len(order) // 2
        plan["primaries"].append({"model": m, "alternative": ALTERNATIVE, "eligible": len(pool), "addedBy": "extension E1",
                                  "findings": [list(k) for k in chosen],
                                  "calibration": [list(k) for k in sorted(order[:half])],
                                  "test": [list(k) for k in sorted(order[half:])]})
    (R / "plan-extended.json").write_text(json.dumps(plan, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    log(f"added primaries {added}; eligible {plan['extension']['eligibleCounts']}")


def run() -> None:
    import drive_pf_remaining as dr  # sets rc.PACE = 0.92
    import run_pf_confirmatory as rc

    # All Azure agent runs of 12 to 14 November before E1, plus the S7 readers at most, stay below
    # USD 700: cap this folder's Azure spend at its value when E1 starts plus USD 170.
    rc.BUDGET["azure"] = rc.spent("azure") + 170.0
    plan = json.loads((R / "plan-extended.json").read_text(encoding="utf-8"))
    added = {"primaries": [e for e in plan["primaries"] if e.get("addedBy") == "extension E1"]}
    five = ["N2-json-tool-output", "N3-paraphrased-system", "M1-other-model", "M2-repeat-user-prompt", "M3-spotlighting"]
    s34 = dr.perturb_jobs(added, ["N1-rerun"], range(101, 111)) + dr.perturb_jobs(added, five, range(101, 104))
    s5 = [(UPGRADES[e["model"]], "N1-rerun", t, tuple(k)) for e in added["primaries"] if e["model"] in UPGRADES
          for t in range(101, 104) for k in e["findings"]]
    log(f"jobs s34 {len(s34)}, s5 {len(s5)}; azure cap for this folder {rc.BUDGET['azure']:.2f}")
    dr.run_parallel([("s34-e1", s34, R / "s34"), ("s5-e1", s5, R / "s5")])
    log("E1 RUNS DONE")


def read() -> None:
    import read_pf_blind as rb

    rb.read(R / "readers-items.json", R / f"readers-{THIRD_READER}.jsonl", THIRD_READER)
    rb.agree(R / "readers-items.json", [R / f"readers-{r}.jsonl" for r in ("gpt-5.5", "grok-4.7", THIRD_READER)],
             R / "readers-agreement-e1.json")
    log("E1 READER DONE")


def analyze() -> None:
    plan = R / "plan-extended.json"
    an.reliability(plan, R / "s34", R / "reliability-e1.json")
    an.prediction(plan, R / "s34", R / "prediction-e1.json")
    p = json.loads(plan.read_text(encoding="utf-8"))
    pairs = json.loads((R / "upgrade-pairs.json").read_text(encoding="utf-8"))
    pairs += [{"baseline": e["model"], "candidate": UPGRADES[e["model"]], "findings": e["findings"]}
              for e in p["primaries"] if e.get("addedBy") == "extension E1" and e["model"] in UPGRADES]
    (R / "upgrade-pairs-e1.json").write_text(json.dumps(pairs, indent=1) + "\n", encoding="utf-8")
    an.upgrade(R / "upgrade-pairs-e1.json", R / "upgrade-e1.json", [R / "s34", R / "s5", R / "s5-anthropic"])
    log("E1 ANALYSES DONE")


if __name__ == "__main__":
    {"select": select, "run": run, "read": read, "analyze": analyze}[sys.argv[1]]()
