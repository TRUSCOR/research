"""PF study: cross-model semantic reproduction of published AgentDojo prompt-injection outcomes.

Implements protocol `PF-agentdojo-reproduction-protocol-2026-11-12.md` (frozen
before any run log was read; SHA-256 recorded below). Reads AgentDojo's
published `runs/` logs as untrusted JSON, one file at a time. Executes no
AgentDojo or model code and makes no network call.

Usage (from any directory):
    python run_pf_agentdojo_reproduction.py <agentdojo-repo-dir> <out.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

PROTOCOL_SHA256 = "672e4d7deb1a7b78d740683a3edbc27e689e41e108eca34c8285250211710f88"
PROTOCOL_FROZEN_AT = "2026-11-12T09:05:20Z"
ATTACK = "important_instructions"
DEFENSE_SUFFIXES = (
    "-tool_filter",
    "-spotlighting_with_delimiting",
    "-transformers_pi_detector",
    "-repeat_user_prompt",
)
REQUIRED = ("suite_name", "user_task_id", "injection_task_id", "attack_type", "security", "utility", "messages")
MIN_CONCLUSIVE = 20
BOOTSTRAP = 2000
SEED = 20261112
STATES = ("evidence-invalid", "unsafe", "incompatible", "inconclusive", "divergent", "equivalent")


def wilson(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    if trials == 0:
        return None
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    radius = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return (max(0.0, centre - radius), min(1.0, centre + radius))


def read_log(path: Path) -> dict[str, Any]:
    """Classify one log as evidence for the claim 'the injection goal was executed'."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"malformed": True}
    if not isinstance(data, dict) or any(key not in data for key in REQUIRED):
        return {"malformed": True}
    messages = data.get("messages") or []
    assistant = any(isinstance(m, dict) and m.get("role") == "assistant" for m in messages)
    error = data.get("error")
    security = data.get("security")
    deviation = False
    if security is True:
        evidence = "supported" if (error is None and assistant) else "inconclusive"
    elif security is False:
        if error is not None:
            evidence = "inconclusive"
        elif assistant:
            evidence = "not-observed"
        else:
            # Not specified by the frozen protocol; resolved conservatively and disclosed.
            evidence = "inconclusive"
            deviation = True
    else:
        return {"malformed": True}
    return {
        "malformed": False,
        "key": (data["suite_name"], data["user_task_id"], data["injection_task_id"], data["attack_type"]),
        "evidence": evidence,
        "security": bool(security),
        "utility": data.get("utility"),
        "errorPresent": error is not None,
        "assistantPresent": assistant,
        "benchmarkVersion": data.get("benchmark_version"),
        "protocolGap": deviation,
    }


def decide(a: dict[str, Any], b: dict[str, Any] | None, envelope: str) -> str:
    """Ordered gates of the frozen protocol, for an instance where A is supported."""
    if b is None:
        return "inconclusive"
    if b["malformed"]:
        return "evidence-invalid"
    va, vb = a["benchmarkVersion"], b["benchmarkVersion"]
    if va is not None and vb is not None and va != vb:
        return "incompatible"
    if b["evidence"] == "inconclusive":
        return "inconclusive"
    if envelope == "E1" and (va is None or vb is None):
        return "inconclusive"
    if b["evidence"] == "not-observed":
        return "divergent"
    return "equivalent"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    started = time.perf_counter()
    runs = args.repo / "runs"
    commit = subprocess.run(
        ["git", "-C", str(args.repo), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()

    logs: dict[str, dict[tuple[str, ...], dict[str, Any]]] = defaultdict(dict)
    malformed_paths: list[str] = []
    files = 0
    total_bytes = 0
    path_mismatch = 0
    for path in sorted(runs.glob(f"*/*/*/{ATTACK}/*.json")):
        pipeline, suite, task = path.parts[-5], path.parts[-4], path.parts[-3]
        if not task.startswith("user_task_"):
            continue
        files += 1
        total_bytes += path.stat().st_size
        record = read_log(path)
        if record["malformed"]:
            malformed_paths.append(path.relative_to(args.repo).as_posix())
            key = (suite, task, path.stem, ATTACK)
        else:
            key = record["key"]
            if key[0] != suite or key[1] != task or key[3] != ATTACK:
                path_mismatch += 1
        logs[pipeline][key] = record

    all_pipelines = sorted(logs)
    defended = [p for p in all_pipelines if p.endswith(DEFENSE_SUFFIXES)]
    candidates = [p for p in all_pipelines if p not in defended]
    counts = {p: len(logs[p]) for p in all_pipelines}
    modal = Counter(counts[p] for p in candidates).most_common(1)[0][0] if candidates else 0
    excluded = [p for p in candidates if counts[p] < 0.5 * modal]
    included = [p for p in candidates if p not in excluded]

    # M1 and M5 per pipeline (all pipelines, including defended and excluded).
    per_pipeline = {}
    for p in all_pipelines:
        records = [r for r in logs[p].values() if not r["malformed"]]
        security_true = [r for r in records if r["security"]]
        laundered = [r for r in security_true if r["evidence"] == "inconclusive"]
        per_pipeline[p] = {
            "logs": counts[p],
            "malformed": sum(1 for r in logs[p].values() if r["malformed"]),
            "securityTrue": len(security_true),
            "securityTrueWithError": sum(1 for r in security_true if r["errorPresent"]),
            "securityTrueWithoutAssistant": sum(1 for r in security_true if not r["assistantPresent"]),
            "launderedSuccesses": len(laundered),
            "launderedShareOfSecurityTrue": (len(laundered) / len(security_true)) if security_true else None,
            "supported": sum(1 for r in records if r["evidence"] == "supported"),
            "notObserved": sum(1 for r in records if r["evidence"] == "not-observed"),
            "inconclusive": sum(1 for r in records if r["evidence"] == "inconclusive"),
            "errorPresent": sum(1 for r in records if r["errorPresent"]),
            "benchmarkVersionPresent": sum(1 for r in records if r["benchmarkVersion"] is not None),
            "benchmarkVersions": dict(Counter(str(r["benchmarkVersion"]) for r in records)),
            "protocolGapCases": sum(1 for r in records if r["protocolGap"]),
            "role": "defended-excluded" if p in defended else ("excluded-incomplete" if p in excluded else "included"),
            "asrSupported": (
                sum(1 for r in records if r["evidence"] == "supported") / len(logs[p]) if logs[p] else None
            ),
            "asrNaiveSecurityFlag": (len(security_true) / len(records)) if records else None,
        }

    # M2: pairwise decisions for E1 and E2, plus baseline B1.
    pairs: dict[str, dict[str, Any]] = {}
    for envelope in ("E1", "E2"):
        for a in included:
            for b in included:
                if a == b:
                    continue
                tally = Counter()
                for key, ra in logs[a].items():
                    if ra["malformed"] or ra["evidence"] != "supported":
                        continue
                    tally[decide(ra, logs[b].get(key), envelope)] += 1
                eq, div, inc = tally["equivalent"], tally["divergent"], tally["inconclusive"]
                invalid = tally["evidence-invalid"]
                conclusive = eq + div
                unresolved_total = eq + div + inc + invalid
                pairs.setdefault(f"{a} -> {b}", {})[envelope] = {
                    "states": {state: tally[state] for state in STATES},
                    "conclusive": conclusive,
                    "reproductionRate": (eq / conclusive) if conclusive else None,
                    "wilson95": wilson(eq, conclusive),
                    "partialIdentification": (
                        (eq / unresolved_total, (eq + inc + invalid) / unresolved_total)
                        if unresolved_total
                        else None
                    ),
                }
    b1_mismatch = Counter()
    b1_equivalent = 0
    for a in included:
        for b in included:
            if a == b:
                continue
            for key, ra in logs[a].items():
                rb = logs[b].get(key)
                if ra["malformed"] or rb is None or rb["malformed"]:
                    continue
                if ra["security"] and rb["security"]:
                    b1_equivalent += 1
                    procedure = decide(ra, rb, "E2") if ra["evidence"] == "supported" else "no-supported-finding-on-A"
                    if procedure != "equivalent":
                        b1_mismatch[procedure] += 1

    # M3 summary and asymmetry.
    summary: dict[str, Any] = {}
    for envelope in ("E1", "E2"):
        rates = {
            name: v[envelope]["reproductionRate"]
            for name, v in pairs.items()
            if v[envelope]["conclusive"] >= MIN_CONCLUSIVE
        }
        values = sorted(rates.values())
        asymmetry = []
        for a in included:
            for b in included:
                if a < b and f"{a} -> {b}" in rates and f"{b} -> {a}" in rates:
                    asymmetry.append(abs(rates[f"{a} -> {b}"] - rates[f"{b} -> {a}"]))
        totals = Counter()
        for v in pairs.values():
            totals.update(v[envelope]["states"])
        summary[envelope] = {
            "qualifyingOrderedPairs": len(values),
            "medianReproductionRate": statistics.median(values) if values else None,
            "q1": float(np.percentile(values, 25)) if values else None,
            "q3": float(np.percentile(values, 75)) if values else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "medianAsymmetry": statistics.median(asymmetry) if asymmetry else None,
            "maxAsymmetry": max(asymmetry) if asymmetry else None,
            "allPairStateTotals": {state: totals[state] for state in STATES},
        }

    # M4: lift and bootstrap over attack instances (E1 and E2).
    instances = sorted({key for p in included for key in logs[p]})
    index = {key: i for i, key in enumerate(instances)}
    P, I = len(included), len(instances)
    supported = np.zeros((P, I))
    not_observed = np.zeros((P, I))
    present = np.zeros((P, I))
    version_known = np.zeros((P, I))
    for pi, p in enumerate(included):
        for key, r in logs[p].items():
            i = index[key]
            present[pi, i] = 1
            if r["malformed"]:
                continue
            supported[pi, i] = r["evidence"] == "supported"
            not_observed[pi, i] = r["evidence"] == "not-observed"
            version_known[pi, i] = r["benchmarkVersion"] is not None
    rng = np.random.default_rng(SEED)

    def median_lift(weights: np.ndarray, envelope: str) -> tuple[float | None, int]:
        if envelope == "E1":
            vk = version_known * weights
            eq = (supported * vk) @ (supported * version_known).T
            dv = (supported * vk) @ (not_observed * version_known).T
        else:
            eq = (supported * weights) @ supported.T
            dv = (supported * weights) @ not_observed.T
        asr = (supported * weights).sum(axis=1) / np.maximum((present * weights).sum(axis=1), 1e-12)
        lifts = []
        for x in range(P):
            for y in range(P):
                if x == y:
                    continue
                conclusive = eq[x, y] + dv[x, y]
                if conclusive >= MIN_CONCLUSIVE and asr[y] > 0:
                    lifts.append((eq[x, y] / conclusive) / asr[y])
        return (float(np.median(lifts)) if lifts else None, len(lifts))

    lift_report = {}
    for envelope in ("E1", "E2"):
        point, n_pairs = median_lift(np.ones(I), envelope)
        draws = []
        if point is not None:
            for _ in range(BOOTSTRAP):
                weights = rng.multinomial(I, np.full(I, 1.0 / I)).astype(float)
                value, _ = median_lift(weights, envelope)
                if value is not None:
                    draws.append(value)
        low = float(np.percentile(draws, 2.5)) if draws else None
        high = float(np.percentile(draws, 97.5)) if draws else None
        lift_report[envelope] = {
            "medianLift": point,
            "pairs": n_pairs,
            "bootstrap95": (low, high),
            "bootstrapDraws": len(draws),
            "H1Supported": (low is not None and low > 1.0),
        }

    totals_logs = sum(per_pipeline[p]["logs"] for p in all_pipelines)
    security_true_all = sum(per_pipeline[p]["securityTrue"] for p in all_pipelines)
    laundered_all = sum(per_pipeline[p]["launderedSuccesses"] for p in all_pipelines)
    security_true_inc = sum(per_pipeline[p]["securityTrue"] for p in included)
    laundered_inc = sum(per_pipeline[p]["launderedSuccesses"] for p in included)
    result = {
        "artifactType": "sova.pf-agentdojo-reproduction-study",
        "schemaVersion": "1.0.0",
        "protocol": {
            "path": "private/research/papers/PF-agentdojo-reproduction-protocol-2026-11-12.md",
            "sha256": PROTOCOL_SHA256,
            "frozenAt": PROTOCOL_FROZEN_AT,
        },
        "source": {
            "repository": "https://github.com/ethz-spylab/agentdojo",
            "commit": commit,
            "attack": ATTACK,
            "logFiles": files,
            "logBytes": total_bytes,
            "codeLicence": "MIT",
            "runLogLicence": "not separately stated",
            "redistributed": False,
        },
        "pipelines": {
            "all": all_pipelines,
            "included": included,
            "defendedExcluded": defended,
            "incompleteExcluded": excluded,
            "modalLogCount": modal,
        },
        "attackInstances": I,
        "malformedLogs": len(malformed_paths),
        "malformedPaths": malformed_paths[:50],
        "pathFieldMismatches": path_mismatch,
        "M1": {
            "allPipelines": {
                "securityTrue": security_true_all,
                "launderedSuccesses": laundered_all,
                "share": (laundered_all / security_true_all) if security_true_all else None,
            },
            "includedPipelines": {
                "securityTrue": security_true_inc,
                "launderedSuccesses": laundered_inc,
                "share": (laundered_inc / security_true_inc) if security_true_inc else None,
            },
        },
        "M5": {
            "logs": totals_logs,
            "benchmarkVersionPresent": sum(per_pipeline[p]["benchmarkVersionPresent"] for p in all_pipelines),
            "errorPresent": sum(per_pipeline[p]["errorPresent"] for p in all_pipelines),
            "missingRelativeToModalSet": {p: max(0, modal - counts[p]) for p in candidates},
        },
        "perPipeline": per_pipeline,
        "M2pairs": pairs,
        "M3summary": summary,
        "M4lift": lift_report,
        "B1": {
            "flagOnlyEquivalentDecisions": b1_equivalent,
            "classifiedOtherwiseByProcedureE2": dict(b1_mismatch),
        },
        "deviations": [
            "Protocol did not specify security=false with null error and no assistant message; "
            "classified inconclusive (count in perPipeline.protocolGapCases)."
        ],
        "limitations": [
            "Retrospective analysis of third-party logs produced at different times by the benchmark authors.",
            "Outcomes are AgentDojo's own deterministic checker verdicts, not independent labels.",
            "Provider-side model drift and benchmark revisions cannot be excluded where benchmark_version is absent.",
            "One attack (important_instructions); same-team analysis; protocol custody is same-team.",
        ],
        "environment": {"python": sys.version.split()[0], "numpy": np.__version__},
        "runtimeSeconds": round(time.perf_counter() - started, 1),
        "scriptSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("attackInstances", "malformedLogs", "M1", "M3summary", "M4lift", "B1")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
