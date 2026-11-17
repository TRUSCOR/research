"""Post hoc analyses for the short version (v1.2) of the PF preprint, raised in review.

None of these was in a frozen protocol; all read released result files and call no model.

1. Goal reweighting of the S2 scoreboard. The scoreboard holds all 20 instances of the hotel
   goal and 4 of each other goal (156 instances). AgentDojo v1.2.2 runs every goal against
   every user task of its suite (949 instances), so the hotel goal is 20 of 949 there. Here each
   goal's rate (benchmark verdict, and audit attack) on trial 1 is weighted by the number of
   instances it has in the full benchmark, counted from the Grok 4.1 Fast pass over all 949.
2. Agreement between the audit and the benchmark on the published runs that did not crash.

    python posthoc_pf_v1_2.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_pf_v2 as an  # noqa: E402

R = HERE / "results" / "pf-confirmatory-2026-11-14"
PUBLISHED = HERE / "results" / "pf-audit-2026-11-14" / "published.json"
OUT = HERE / "results" / "pf-posthoc-v1-2-2026-11-17.json"
AUDIT_ATTACK = {"confirmed", "action-scored-as-no-attack"}


def tau(a: list[float], b: list[float]) -> float:
    """Kendall's tau as analyze_pf_v2.scoreboard computes it (pairs tied on either side dropped)."""
    conc = disc = 0
    for i in range(len(a)):
        for j in range(i + 1, len(a)):
            s = (a[i] - a[j]) * (b[i] - b[j])
            conc += s > 0
            disc += s < 0
    return round((conc - disc) / max(1, conc + disc), 4)


def goal_weights() -> dict[tuple[str, str], int]:
    rows = [r for r in an.load(R / "s2-grok-full") if r["model"] == "grok-4-1-fast-non-reasoning" and r["trial"] == 1]
    users = defaultdict(set)
    goals = defaultdict(set)
    for r in rows:
        users[r["suite"]].add(r["userTask"])
        goals[r["suite"]].add(r["injectionTask"])
    weights = {(s, g): len(users[s]) for s in goals for g in goals[s]}
    assert sum(weights.values()) == 949 and len(weights) == 35, (sum(weights.values()), len(weights))
    return weights


def reweight() -> dict[str, object]:
    weights = goal_weights()
    published = json.loads((R / "scoreboard.json").read_text(encoding="utf-8"))["models"]
    rows = [r for d in (R / "s2", R / "s2-anthropic") for r in an.load(d) if r["condition"] == "baseline" and r["trial"] == 1]
    by = defaultdict(list)
    for r in rows:
        by[r["model"]].append(r)
    models = {}
    for m, rs in sorted(by.items()):
        # Check: the unweighted rates must equal the frozen scoreboard's.
        verdicts = [r for r in rs if r["benchmarkAttack"] is not None]
        judged = [r for r in rs if r["judged"]]
        flat_b = round(sum(r["benchmarkAttack"] for r in verdicts) / max(1, len(verdicts)), 4)
        flat_a = round(sum(r["attack"] for r in judged) / max(1, len(judged)), 4)
        assert (flat_b, flat_a) == (published[m]["benchmarkASR"], published[m]["attackerActionRate"]), m
        per_goal = defaultdict(lambda: {"b": [], "a": []})
        for r in rs:
            g = (r["suite"], r["injectionTask"])
            if r["benchmarkAttack"] is not None:
                per_goal[g]["b"].append(r["benchmarkAttack"])
            if r["judged"]:
                per_goal[g]["a"].append(r["attack"])

        def weighted(field: str) -> float | None:
            num = den = 0.0
            for g, v in per_goal.items():
                if v[field]:
                    num += weights[g] * sum(v[field]) / len(v[field])
                    den += weights[g]
            return round(num / den, 4) if den else None

        hotel = per_goal[an.TEXT_GOAL]
        models[m] = {
            "instances": len(rs),
            "flatBenchmarkASR": flat_b,
            "flatAuditAttackRate": flat_a,
            "weightedBenchmarkASR": weighted("b"),
            "weightedAuditAttackRate": weighted("a"),
            "hotelBenchmarkTrial1": f"{sum(hotel['b'])} of {len(hotel['b'])}",
            "goalsWithoutJudgedRun": sorted(f"{s}/{g}" for (s, g), v in per_goal.items() if not v["a"]),
        }
    names = sorted(models)
    ok = [m for m in names if models[m]["weightedAuditAttackRate"] is not None]
    return {
        "weightsFrom": "instances per goal in AgentDojo v1.2.2 (users per suite), counted from the Grok 4.1 Fast pass over 949 instances",
        "hotelShare": {"scoreboard": "20 of 156", "benchmark": f"{weights[an.TEXT_GOAL]} of 949"},
        "kendallTauFlat": tau([models[m]["flatBenchmarkASR"] for m in names], [models[m]["flatAuditAttackRate"] for m in names]),
        "kendallTauWeighted": tau([models[m]["weightedBenchmarkASR"] for m in ok], [models[m]["weightedAuditAttackRate"] for m in ok]),
        "models": models,
    }


def published_agreement() -> dict[str, object]:
    rows = json.loads(PUBLISHED.read_text(encoding="utf-8"))["rows"]
    not_crashed = [r for r in rows if r["category"] != "crash"]
    agree = sum((r["category"] in AUDIT_ATTACK) == bool(r["verdict"]) for r in not_crashed)
    executed = sum(r["category"] in AUDIT_ATTACK for r in rows)
    missed = sum(r["category"] == "action-scored-as-no-attack" for r in rows)
    either = [r for r in not_crashed if r["category"] in AUDIT_ATTACK or bool(r["verdict"])]
    both = sum(1 for r in either if r["category"] in AUDIT_ATTACK and bool(r["verdict"]))
    landlord = sum(1 for r in rows if r["category"] == "action-scored-as-no-attack"
                   and (r["suite"], r["userTask"]) == ("banking", "user_task_15"))
    return {"eitherCountsAttack": len(either), "bothCountAttack": both, "agreeShareAmongAttacks": round(both / len(either), 4),
            "landlordRunsAmongMissed": landlord,
            "runs": len(rows), "notCrashed": len(not_crashed), "agree": agree,
            "agreeShare": round(agree / len(not_crashed), 4), "executedAttackerActions": executed,
            "executedScoredNoAttack": missed, "missedShare": round(missed / executed, 4)}


def rank_stats(a: list[float], b: list[float]) -> dict[str, float]:
    """Kendall's tau-b, and Goodman and Kruskal's gamma, which the frozen scoreboard reported as tau."""
    from scipy.stats import kendalltau

    return {"tauB": round(float(kendalltau(a, b).statistic), 4), "gamma": tau(a, b)}


def r4(x: float | None) -> float | None:
    return None if x is None else round(float(x), 4)


def comparability() -> dict[str, object]:
    """Intervals the reviews asked for on the S4/E1 test (H1) and the E2 test, from the released runs."""
    import numpy as np
    from scipy.stats import t as student_t

    nm, mat = an.NON_MATERIAL, an.MATERIAL
    plan = json.loads((R / "plan-extended.json").read_text(encoding="utf-8"))
    rates = an.per_finding(an.load(R / "s34"), plan)
    allk = {p["model"]: [tuple(k) for k in p["findings"]] for p in plan["primaries"]}
    added = {p["model"] for p in plan["primaries"] if p.get("addedBy") == "extension E1"}
    frozen_e1 = json.loads((R / "prediction-e1.json").read_text(encoding="utf-8"))["attack"]
    six = an.gap(rates, nm, mat, allk)
    assert abs(six - frozen_e1["H1"]["gap"]) < 1e-9, (six, frozen_e1["H1"]["gap"])

    def worst(s):  # every unjudged run counted against the hypothesis
        x, y = an.pooled(rates, nm, s, 0.0), an.pooled(rates, mat, s, 1.0)
        return None if x is None or y is None else x - y

    sub = {m: ks for m, ks in allk.items() if m in added}
    per = [frozen_e1["perModel"][m]["H1gap"] for m in allk]
    mean, sd = float(np.mean(per)), float(np.std(per, ddof=1))
    half = float(student_t.ppf(0.975, len(per) - 1)) * sd / len(per) ** 0.5
    h1 = {
        "sixModelGap": r4(six),
        "worstCaseSixModels": {"gap": r4(worst(allk)), "ci95": an.boot_ci(worst, allk)},
        "e1AddedModelsOnly": {"models": sorted(added), "gap": r4(an.gap(rates, nm, mat, sub)),
                              "ci95": an.boot_ci(lambda s: an.gap(rates, nm, mat, s), sub)},
        "modelsAsSample": {"meanOfPerModelGaps": r4(mean), "tInterval95": [r4(mean - half), r4(mean + half)],
                           "perModelGaps": {m: r4(frozen_e1["perModel"][m]["H1gap"]) for m in allk}},
    }

    # E2: the declared rules on the same 80 fresh findings that the measured rules were scored on,
    # and whether each change measured non-material stayed below the threshold on fresh findings.
    import extend_pf_e2 as e2

    e2res = json.loads((R / "e2-result.json").read_text(encoding="utf-8"))
    env = e2res["envelopes"]
    e2plan = json.loads((R / "plan-e2.json").read_text(encoding="utf-8"))
    fresh = e2._rates(e2plan, e2.E2, set(e2.TRIALS))
    strata = {p["model"]: [tuple(k) for k in p["findings"]] for p in e2plan["primaries"]}
    measured_sets = {m: (["N1-rerun"] + [c for c in e2.CHANGES if env[m][c]["measured"] == "non-material"],
                         [c for c in e2.CHANGES if env[m][c]["measured"] == "material"]) for m in env}
    four = {m: ks for m, ks in strata.items() if measured_sets[m][1]}

    def gap_for(sets, sample):
        nvals, mvals = [], []
        for m, ks in sample.items():
            n_conds, m_conds = sets[m]
            if not m_conds:
                continue
            for k in ks:
                nvals += [v for c in n_conds if (v := an.mean_rate(fresh[m], [c], [k])) is not None]
                mvals += [v for c in m_conds if (v := an.mean_rate(fresh[m], [c], [k])) is not None]
        return None if not nvals or not mvals else sum(nvals) / len(nvals) - sum(mvals) / len(mvals)

    declared_sets = {m: (e2.CONDS[:3], e2.CONDS[3:]) for m in env}
    measured_gap = gap_for(measured_sets, four)
    assert abs(measured_gap - e2res["measured"]["gap"]) < 5e-5, (measured_gap, e2res["measured"]["gap"])
    held = []
    for m, ks in strata.items():
        for c in e2.CHANGES:
            if env[m][c]["measured"] != "non-material":
                continue
            one = {m: ks}
            drop = an.gap(fresh, ["N1-rerun"], [c], one)
            ci = an.boot_ci(lambda s, c=c: an.gap(fresh, ["N1-rerun"], [c], s), one)
            held.append({"model": m, "change": c, "dropOnFresh": r4(drop), "ci95": ci,
                         "stillBelowThreshold": bool(ci and ci[1] < e2.THRESHOLD)})
    mm = "mistral-medium-3-5"
    saved = an.BOOTS
    an.BOOTS = 20000
    try:
        mm_ci = an.boot_ci(lambda s: gap_for(measured_sets, {mm: s[mm]}), {mm: strata[mm]})
    finally:
        an.BOOTS = saved
    e2out = {
        "measuredGapFourModels": r4(measured_gap),
        "declaredGapSameFourModels": {"gap": r4(gap_for(declared_sets, four)),
                                      "ci95": an.boot_ci(lambda s: gap_for(declared_sets, s), four)},
        "materialChangesPerModel": {m: measured_sets[m][1] for m in four},
        "undeterminedPairs": sum(1 for m in env for c in e2.CHANGES if env[m][c]["measured"] == "undetermined"),
        "pairs": len(env) * len(e2.CHANGES),
        "nonMaterialOnFresh": {"tested": len(held), "stillBelowThreshold": sum(h["stillBelowThreshold"] for h in held),
                               "cells": held},
        "mistralMedium35MeasuredCi95With20000Resamples": mm_ci,
    }
    return {"h1": h1, "e2": e2out}


def upgrades() -> dict[str, object]:
    from scipy.stats import beta

    doc = json.loads((R / "upgrade-e1.json").read_text(encoding="utf-8"))["pairs"]
    out = {}
    for pair, v in doc.items():
        k = sum(f["candidate"][0] for f in v["findings"])
        n = sum(f["candidate"][1] for f in v["findings"])
        out[pair] = {"candidateAttacks": k, "candidateJudgedRuns": n, "wilsonUpper": an.wilson(k, n)[1] if n else None,
                     "classes": v["classes"]}
    return {"pairs": out, "zeroOfThree": {"wilsonUpper": an.wilson(0, 3)[1],
                                          "clopperPearsonUpper": round(float(beta.ppf(0.975, 1, 3)), 4)}}


def main() -> int:
    doc = {"artifactType": "pf-posthoc-v1.2", "note": "post hoc; not in any frozen protocol; no model called",
           "scoreboardReweighting": reweight(), "publishedAgreement": published_agreement(),
           "comparability": comparability(), "upgrades": upgrades(),
           "intervalsQuotedInText": {"wilson8of10": an.wilson(8, 10), "wilson29of30": an.wilson(29, 30)}}
    sb = doc["scoreboardReweighting"]
    names = sorted(sb["models"])
    ok = [m for m in names if sb["models"][m]["weightedAuditAttackRate"] is not None]
    sb["rankFlat"] = rank_stats([sb["models"][m]["flatBenchmarkASR"] for m in names], [sb["models"][m]["flatAuditAttackRate"] for m in names])
    sb["rankWeighted"] = rank_stats([sb["models"][m]["weightedBenchmarkASR"] for m in ok], [sb["models"][m]["weightedAuditAttackRate"] for m in ok])
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sb = doc["scoreboardReweighting"]
    print("tau flat", sb["kendallTauFlat"], "weighted", sb["kendallTauWeighted"])
    for m, v in sorted(sb["models"].items(), key=lambda kv: -(kv[1]["weightedAuditAttackRate"] or 0)):
        print(f"{m:40s} bench {v['flatBenchmarkASR']:.3f} -> {v['weightedBenchmarkASR']:.3f}   audit {v['flatAuditAttackRate']:.3f} -> {v['weightedAuditAttackRate']}  hotel {v['hotelBenchmarkTrial1']}  nogoal {len(v['goalsWithoutJudgedRun'])}")
    print(doc["publishedAgreement"])
    print("rank flat", sb["rankFlat"], "weighted", sb["rankWeighted"])
    print(json.dumps(doc["comparability"]["h1"], indent=1))
    e2o = {k: v for k, v in doc["comparability"]["e2"].items() if k != "nonMaterialOnFresh"}
    print(json.dumps(e2o, indent=1)); nm_ = doc["comparability"]["e2"]["nonMaterialOnFresh"]; print("non-material held", nm_["stillBelowThreshold"], "of", nm_["tested"])
    print(json.dumps(doc["upgrades"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
