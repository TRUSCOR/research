"""Post-hoc sensitivity checks added after review (not part of the frozen protocol).

    python posthoc_sensitivity_pf.py <out.json>

1. H1 with the three primary models weighted equally. The locked 40/40/40 design implied equal
   weight; deviation D2 cut the xAI model to 20 findings. Bootstrap within each primary, as frozen.
2. The findings whose Wilson lower bound stays below 0.5, with their k of n.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

import analyze_pf_v2 as an  # noqa: E402

R = Path(__file__).resolve().parent / "results" / "pf-confirmatory-2026-11-14"
N = ["N1-rerun", "N2-json-tool-output", "N3-paraphrased-system"]
M = ["M1-other-model", "M2-repeat-user-prompt", "M3-spotlighting"]


def main() -> int:
    plan = json.loads((R / "plan.json").read_text(encoding="utf-8"))
    rates = an.per_finding(an.load(R / "s34"), plan)
    strata = {p["model"]: [tuple(k) for k in p["findings"]] for p in plan["primaries"]}

    def eq_gap(sample):
        gaps = []
        for m, ks in sample.items():
            g = an.gap(rates, N, M, {m: ks})
            if g is not None:
                gaps.append(g)
        return float(np.mean(gaps)) if len(gaps) == len(sample) else None

    out = {"equalWeightH1": {"gap": round(eq_gap(strata), 4), "ci95": an.boot_ci(eq_gap, strata)}}
    rel = json.loads((R / "reliability.json").read_text(encoding="utf-8"))["byPrimary"]
    below = []
    for m, r in rel.items():
        for f in r["perFinding"]:
            if f["judged"] and not (f["wilson"] and f["wilson"][0] >= 0.5):
                below.append({"model": m, "finding": f["finding"], "k": f["attacks"], "n": f["judged"], "rate": f["rate"]})
    out["belowHalfBound"] = below
    out["belowHalfBoundAtLeast80"] = sum(1 for b in below if b["rate"] >= 0.8)
    Path(sys.argv[1]).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out["equalWeightH1"]), out["belowHalfBoundAtLeast80"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
