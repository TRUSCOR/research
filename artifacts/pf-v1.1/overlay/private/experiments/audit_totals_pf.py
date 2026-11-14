"""Totals of the frozen audit categories over every run of the 2026-11-14 studies (paper sections 4.3, 5.1).

    python audit_totals_pf.py <out.json>

Uses analyze_pf_v2.load (the frozen audit) and nothing else. Also counts, per model, the trial-1
hotel-goal replies that the frozen warning rule reads as endorsements, so that the audit rate can
be split into tool actions and hotel endorsements.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_pf_v2 as an  # noqa: E402

R = Path(__file__).resolve().parent / "results" / "pf-confirmatory-2026-11-14"
GROUPS = {"S2": ["s2", "s2-anthropic"], "S3S4": ["s34"], "S5": ["s5", "s5-anthropic"], "S2grokfull": ["s2-grok-full"]}


def main() -> int:
    out = {}
    for group, dirs in GROUPS.items():
        rows = [r for d in dirs for r in an.load(R / d)]
        if group == "S2":
            rows = [r for r in rows if r["condition"] == "baseline"]
        cats = Counter(r["category"] for r in rows)
        by_model: dict = defaultdict(Counter)
        for r in rows:
            by_model[r["model"]][r["category"]] += 1
        hotel_t1 = Counter(r["model"] for r in rows if r["trial"] == 1 and r["condition"] == "baseline"
                           and (r["suite"], r["injectionTask"]) == ("travel", "injection_task_6") and r["category"] == "confirmed")
        out[group] = {
            "runs": len(rows),
            "categories": dict(cats),
            "crashSecurityField": dict(Counter(str(r.get("security")) for r in rows if r["category"] == "crash")),
            "executedActions": cats["confirmed"] + cats["action-scored-as-no-attack"],
            "executedByModel": {m: c["confirmed"] + c["action-scored-as-no-attack"] for m, c in by_model.items()},
            "actionScoredNoAttackByModel": {m: c["action-scored-as-no-attack"] for m, c in by_model.items() if c["action-scored-as-no-attack"]},
            "warningsByModel": {m: c["warning-scored-as-attack"] for m, c in by_model.items() if c["warning-scored-as-attack"]},
            "unsupportedByModel": {m: c["unsupported"] for m, c in by_model.items() if c["unsupported"]},
            "attemptScoredByModel": {m: c["attempt-scored-as-attack"] for m, c in by_model.items() if c["attempt-scored-as-attack"]},
            "trial1HotelEndorsementsByModel": dict(hotel_t1),
        }
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({g: {k: v for k, v in d.items() if k in ("runs", "categories", "executedActions")} for g, d in out.items()}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
