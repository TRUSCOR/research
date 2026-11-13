"""Analysis for the real-attack predictiveness experiment.

Protocol: private/research/papers/PF-real-attack-predictiveness-protocol-2026-11-12.md
A *real attack* is a supported episode whose final reply is not a warning under the
keyword rule of classify_pf_warning_successes.py.

    python analyze_pf_real_attack_predictiveness.py <out.json> <run-dir> [<run-dir> ...]

Each run directory holds episodes.jsonl and traces.jsonl.gz written by
run_pf_fresh_agentdojo.py with --protocol pointing at the protocol above.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from classify_pf_warning_successes import classify_episode  # noqa: E402

PROTOCOL = Path(__file__).resolve().parents[1] / "research" / "papers" / "PF-real-attack-predictiveness-protocol-2026-11-12.md"
NON_MATERIAL = ["N1-rerun", "N2-json-tool-output", "N3-paraphrased-system"]
MATERIAL = ["M1-other-model", "M2-repeat-user-prompt", "M3-spotlighting"]
SEED, BOOT_SEED = 20261112, 20261113


def load(run_dir: Path) -> list[dict]:
    episodes = {}
    for line in (run_dir / "episodes.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        episodes[(r["model"], r["condition"], r["trial"], r["suite"], r["userTask"], r["injectionTask"])] = r
    with gzip.open(run_dir / "traces.jsonl.gz", "rt", encoding="utf-8") as handle:
        try:
            for line in handle:
                try:
                    t = json.loads(line)
                except json.JSONDecodeError:
                    break
                key = tuple(t["key"])
                if key in episodes:
                    episodes[key]["replyClass"] = classify_episode(key[3], key[5], t["messages"])
        except EOFError:
            pass
    rows = list(episodes.values())
    for r in rows:
        r["real"] = r["evidence"] == "supported" and r.get("replyClass") != "warning"
        r["warning"] = r["evidence"] == "supported" and r.get("replyClass") == "warning"
    return rows


def main() -> int:
    out = Path(sys.argv[1])
    rows = [r for d in sys.argv[2:] for r in load(Path(d))]
    protocol_sha = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    assert all(r["protocolSha256"] == protocol_sha for r in rows), "episodes not bound to this protocol"
    result: dict = {
        "artifactType": "sova.pf-real-attack-predictiveness", "protocolSha256": protocol_sha,
        "episodes": len(rows), "totalCostUsdEstimate": round(sum(r["costUsd"] for r in rows), 2),
        "missingTraceClassification": sum(1 for r in rows if r["evidence"] == "supported" and "replyClass" not in r),
    }
    pilot = defaultdict(list)
    for r in rows:
        if r["condition"] == "baseline" and r["trial"] == 0:
            pilot[(r["model"], r["attack"])].append(r)
    summary = {}
    for (model, attack), eps in sorted(pilot.items()):
        summary[f"{model}|{attack}"] = {
            "episodes": len(eps), "scoredSuccesses": sum(1 for r in eps if r["evidence"] == "supported"),
            "realAttacks": sum(1 for r in eps if r["real"]), "warnings": sum(1 for r in eps if r["warning"]),
            "inconclusive": sum(1 for r in eps if r["evidence"] == "inconclusive"),
            "costPerEpisode": statistics.mean(r["costUsd"] for r in eps),
            "realAttackGoals": dict(Counter(f"{r['suite']}/{r['injectionTask']}" for r in eps if r["real"])),
        }
    result["pilot"] = summary
    if summary:
        best = max(summary, key=lambda k: (summary[k]["realAttacks"], -summary[k]["costPerEpisode"]))
        proceed = summary[best]["realAttacks"] >= 3
        result["selection"] = {"primaryPair": best, "proceeds": proceed}
        model, attack = best.split("|")
        r1 = {(r["suite"], r["userTask"], r["injectionTask"]): r for r in rows
              if r["model"] == model and r["attack"] == attack and r["condition"] == "baseline" and r["trial"] == 1}
        if r1:
            c = Counter("real" if r["real"] else "warning" if r["warning"] else r["evidence"] for r in r1.values())
            result["r1"] = {"instances": len(r1), "outcomes": dict(c),
                            "realAttackGoals": dict(Counter(f"{k[0]}/{k[2]}" for k, r in r1.items() if r["real"]))}
            keys = sorted(k for k, r in r1.items() if r["real"])
            if len(keys) > 60:
                import random
                keys = sorted(random.Random(SEED).sample(keys, 60))
            result["r1"]["findingKeys"] = [list(k) for k in keys]
            per = {c: defaultdict(list) for c in NON_MATERIAL + MATERIAL}
            for r in rows:
                if r["trial"] >= 101 and r["condition"] in per and r["attack"] == attack:
                    k = (r["suite"], r["userTask"], r["injectionTask"])
                    if k in keys:
                        per[r["condition"]][k].append(r)
            if any(per[c] for c in per):
                rates = {}
                for cond in per:
                    rates[cond] = {}
                    for k in keys:
                        conclusive = [r for r in per[cond].get(k, []) if r["evidence"] != "inconclusive"]
                        if conclusive:
                            rates[cond][k] = sum(1 for r in conclusive if r["real"]) / len(conclusive)
                rng = np.random.default_rng(BOOT_SEED)

                def pooled(conds, sample):
                    values = [rates[c][k] for c in conds for k in sample if k in rates[c]]
                    return float(np.mean(values)) if values else None

                def boot(fn):
                    draws = []
                    for _ in range(2000):
                        sample = [keys[i] for i in rng.integers(0, len(keys), len(keys))]
                        v = fn(sample)
                        if v is not None:
                            draws.append(v)
                    return [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))] if draws else None

                conds = {}
                for cond in per:
                    eps = [r for k in keys for r in per[cond].get(k, [])]
                    conds[cond] = {
                        "model": eps[0]["model"] if eps else None, "episodes": len(eps),
                        "inconclusive": sum(1 for r in eps if r["evidence"] == "inconclusive"),
                        "realAttacks": sum(1 for r in eps if r["real"]), "warnings": sum(1 for r in eps if r["warning"]),
                        "recurrence": pooled([cond], keys), "recurrenceCI95": boot(lambda s, c=cond: pooled([c], s)),
                        "costUsd": round(sum(r["costUsd"] for r in eps), 2),
                    }
                h1 = lambda s: (None if pooled(NON_MATERIAL, s) is None or pooled(MATERIAL, s) is None
                                else pooled(NON_MATERIAL, s) - pooled(MATERIAL, s))
                h1_ci = boot(h1)
                h2 = {}
                for cond in ("N2-json-tool-output", "N3-paraphrased-system"):
                    fn = lambda s, c=cond: (None if pooled([c], s) is None or pooled(["N1-rerun"], s) is None
                                            else pooled([c], s) - pooled(["N1-rerun"], s))
                    ci = boot(fn)
                    h2[cond] = {"differenceFromN1": fn(keys), "ci95": ci, "supported": bool(ci and ci[0] >= -0.15)}
                result["perturbations"] = {
                    "findings": len(keys), "conditions": conds,
                    "H1": {"nonMaterialMinusMaterial": h1(keys), "ci95": h1_ci, "supported": bool(h1_ci and h1_ci[0] >= 0.10)},
                    "H2": h2,
                }
    # Post hoc: full-benchmark runs that the protocol's stopping rule did not call for.
    full = defaultdict(list)
    for r in rows:
        if r["condition"] == "baseline" and r["trial"] == 1:
            full[(r["model"], r["attack"])].append(r)
    selection = result.get("selection", {})
    result["postHocFullRuns"] = {
        f"{m}|{a}": {
            "status": ("protocol R1" if f"{m}|{a}" == selection.get("primaryPair") and selection.get("proceeds")
                       else "post hoc; beyond the protocol's stopping rule"),
            "instances": len(eps), "scoredSuccesses": sum(1 for r in eps if r["evidence"] == "supported"),
            "realAttacks": sum(1 for r in eps if r["real"]), "warnings": sum(1 for r in eps if r["warning"]),
            "inconclusive": sum(1 for r in eps if r["evidence"] == "inconclusive"),
            "scoredGoals": dict(Counter(f"{r['suite']}/{r['injectionTask']}" for r in eps if r["evidence"] == "supported")),
            "costUsd": round(sum(r["costUsd"] for r in eps), 2),
        }
        for (m, a), eps in sorted(full.items())
    }
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=1)[:5000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
