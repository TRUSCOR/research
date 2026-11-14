"""Cross-check: does the released `sova calibrate` rule give extension E2's measured envelopes?

E2's envelopes come from the frozen research code (`extend_pf_e2.measured_envelopes`, numpy
bootstrap). This script feeds the same per-finding recurrence rates (the 40 S3/S4 findings of each
E1 primary and all their runs) to the product's `measure_drop` and `classify`, with the same
threshold, resamples and seed, and compares the class of every model and change. The two use
different random generators, so intervals differ slightly; the classes are what E2 tests.

    uv run --project SOVA-OSS --with numpy python check_pf_calibrate.py   # -> calibrate-crosscheck.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_pf_v2 as an  # noqa: E402
import extend_pf_e2 as e2  # noqa: E402

from sova.rerun.calibrate import classify, measure_drop  # noqa: E402

PRODUCT_LABEL = {
    "N2-json-tool-output": "json",
    "N3-paraphrased-system": "paraphrase",
    "M1-other-model": "model",
    "M2-repeat-user-prompt": "repeat-user-prompt",
    "M3-spotlighting": "spotlighting",
}


def main() -> None:
    plan = json.loads((e2.R / "plan-extended.json").read_text(encoding="utf-8"))
    rates = an.per_finding(an.load(e2.R / "s34"), plan)
    research = e2.measured_envelopes()
    rows, agree, widest = [], 0, 0.0
    for p in plan["primaries"]:
        m = p["model"]
        keys = [tuple(k) for k in p["findings"]]
        base = [an.mean_rate(rates[m], ["N1-rerun"], [k]) for k in keys]
        for c in e2.CHANGES:
            changed = [an.mean_rate(rates[m], [c], [k]) for k in keys]
            _, _, drop, interval, used = measure_drop(base, changed, resamples=an.BOOTS, seed=an.BOOT_SEED)
            product = classify(interval, e2.THRESHOLD)
            r = research[m][c]
            diff = None
            if interval and r["ci95"]:
                diff = max(abs(interval[0] - r["ci95"][0]), abs(interval[1] - r["ci95"][1]))
                widest = max(widest, diff)
            same = product == r["measured"]
            agree += same
            rows.append({"model": m, "change": PRODUCT_LABEL[c], "findingsUsed": used,
                         "research": {"drop": r["drop"], "ci95": r["ci95"], "class": r["measured"]},
                         "product": {"drop": None if drop is None else round(drop, 4),
                                     "ci95": None if interval is None else [round(x, 4) for x in interval],
                                     "class": product},
                         "sameClass": same, "intervalDifference": None if diff is None else round(diff, 4)})
    out = {"pairs": len(rows), "sameClass": agree, "largestIntervalDifference": round(widest, 4),
           "rows": rows}
    (e2.R / "calibrate-crosscheck.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"classes agree on {agree} of {len(rows)}; largest interval endpoint difference {widest:.4f}")


if __name__ == "__main__":
    main()
