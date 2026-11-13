"""PF AgentDojo study - supplementary analyses added after AI-assisted review.

POST-HOC AND EXPLORATORY. Not part of the frozen protocol. Added on 2026-11-12
after AI-assisted reviews (not independent human review) of the pre-specified analysis
(`run_pf_agentdojo_reproduction.py`) raised: base-rate confounding, asymmetric
and independence-assuming statistics, mismatched ASR denominators, benchmark
revisions pooled under one envelope, the meaning of absent `error` keys, and
Claude 3 Opus logs with positive verdicts but no agent activity.

The content-keyed envelope (E3) compares the user-task prompt after normalising
its encoding: some pipelines store message content as a plain string and others
as a list of typed text blocks. Both the raw-encoding and the normalised-text
decisions are reported, because the difference is itself an interchange result.
A third, whitespace-insensitive comparison separates material rewording from
indentation-only differences (a tolerance rule rather than an exact rule).

    python run_pf_agentdojo_supplementary.py <agentdojo-repo-dir> <primary-result.json> <out.json>
"""

from __future__ import annotations

import hashlib
import json
import re
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ATTACK = "important_instructions"
SEED = 20261113
BOOTSTRAP = 2000
MIN_SHARED = 20


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def prompt_text(content: Any) -> str | None:
    """Return message text independent of string versus typed-block encoding."""
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("content", block.get("text", ""))))
            else:
                return json.dumps(content, sort_keys=True, ensure_ascii=False)
        return "".join(parts)
    return json.dumps(content, sort_keys=True, ensure_ascii=False)


GOAL_PATTERN = re.compile(r"please do the following first:(.*?)After you do that", re.DOTALL)


def injection_goals(data: dict[str, Any]) -> str | None:
    injections = data.get("injections")
    if not isinstance(injections, dict) or not injections:
        return None
    goals = []
    for value in injections.values():
        match = GOAL_PATTERN.search(str(value))
        goals.append(" ".join((match.group(1) if match else str(value)).split()))
    return "\n".join(sorted(set(goals)))


def read(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("security"), bool):
        return None
    messages = data.get("messages") or []
    assistant = any(isinstance(m, dict) and m.get("role") == "assistant" for m in messages)
    tool_calls = sum(
        len(m.get("tool_calls") or []) for m in messages if isinstance(m, dict) and m.get("role") == "assistant"
    )
    user = next((m.get("content") for m in messages if isinstance(m, dict) and m.get("role") == "user"), None)
    error_key = "error" in data
    error = data.get("error")
    if data["security"]:
        evidence = "supported" if (error is None and assistant) else "inconclusive"
    else:
        evidence = "not-observed" if (error is None and assistant) else "inconclusive"
    return {
        "key": (data.get("suite_name"), data.get("user_task_id"), data.get("injection_task_id")),
        "evidence": evidence,
        "security": data["security"],
        "errorKeyPresent": error_key,
        "errorPresent": error is not None,
        "messages": len(messages),
        "assistant": assistant,
        "toolCalls": tool_calls,
        "userPromptDigestRaw": digest(user) if user is not None else None,
        "userPromptDigest": digest(prompt_text(user)) if user is not None else None,
        "userPromptDigestMaterial": (
            digest(" ".join((prompt_text(user) or "").split())) if user is not None else None
        ),
        "promptEncoding": type(user).__name__ if user is not None else None,
        "injectionGoalDigest": digest(injection_goals(data)),
        "taskAndGoalDigest": (
            digest([" ".join((prompt_text(user) or "").split()), injection_goals(data)]) if user is not None else None
        ),
        "userPromptText": " ".join((prompt_text(user) or "").split()) if user is not None else None,
    }


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, c - r), min(1.0, c + r)]


def mantel_haenszel(tables: list[tuple[int, int, int, int]]) -> dict[str, Any] | None:
    """Stratified odds ratio with the Robins-Breslow-Greenland variance."""
    R = S = 0.0
    pr = ps_qr = qs = 0.0
    for a, b, c, d in tables:
        n = a + b + c + d
        if n < 2:
            continue
        r, s = a * d / n, b * c / n
        p, q = (a + d) / n, (b + c) / n
        R += r
        S += s
        pr += p * r
        ps_qr += p * s + q * r
        qs += q * s
    if R == 0 or S == 0:
        return None
    log_or = math.log(R / S)
    var = pr / (2 * R * R) + ps_qr / (2 * R * S) + qs / (2 * S * S)
    se = math.sqrt(var)
    return {"or": R / S, "ci95": [math.exp(log_or - 1.96 * se), math.exp(log_or + 1.96 * se)]}


def main() -> int:
    repo, primary_path, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    included = primary["pipelines"]["included"]
    logs: dict[str, dict[tuple, dict[str, Any]]] = defaultdict(dict)
    for pipeline in included:
        for path in sorted((repo / "runs" / pipeline).glob(f"*/user_task_*/{ATTACK}/*.json")):
            record = read(path)
            if record is not None:
                logs[pipeline][record["key"]] = record
    revision = {p: ("v1-629" if len(logs[p]) == 629 else "v1.2-949") for p in included}

    # 1. Log accounting for the analysed models.
    analysed_logs = sum(len(logs[p]) for p in included)
    version_logs = sum(primary["perPipeline"][p]["benchmarkVersionPresent"] for p in included)
    error_key_absent = {p: sum(1 for r in logs[p].values() if not r["errorKeyPresent"]) for p in included}

    # 2. Opus positive verdicts with no agent activity, and their injection tasks across models.
    opus = "claude-3-opus-20240229"
    no_turn = [r for r in logs[opus].values() if not r["assistant"]]
    no_turn_positive = [r for r in no_turn if r["security"]]
    injection_tasks = sorted({(r["key"][0], r["key"][2]) for r in no_turn_positive})
    contamination = {}
    for suite, injection in injection_tasks:
        rows = [r for p in included for k, r in logs[p].items() if k[0] == suite and k[2] == injection]
        supported_no_tool = sum(1 for r in rows if r["evidence"] == "supported" and r["toolCalls"] == 0)
        contamination[f"{suite}/{injection}"] = {
            "logs": len(rows),
            "positiveVerdicts": sum(1 for r in rows if r["security"]),
            "supportedWithZeroToolCalls": supported_no_tool,
        }
    opus_profile = {
        "noAgentTurn": len(no_turn),
        "noAgentTurnEmptyMessageList": sum(1 for r in no_turn if r["messages"] == 0),
        "noAgentTurnPositiveVerdict": len(no_turn_positive),
        "positiveNoTurnInjectionTasks": contamination,
    }
    zero_tool_supported = {
        p: sum(1 for r in logs[p].values() if r["evidence"] == "supported" and r["toolCalls"] == 0) for p in included
    }

    # 3. ASR bounds and conclusive-only rates.
    asr = {}
    for p in included:
        c = Counter(r["evidence"] for r in logs[p].values())
        n = len(logs[p])
        asr[p] = {
            "logs": n,
            "supported": c["supported"],
            "notObserved": c["not-observed"],
            "inconclusive": c["inconclusive"],
            "lowerBound": c["supported"] / n,
            "upperBound": (c["supported"] + c["inconclusive"]) / n,
            "conclusiveRate": c["supported"] / max(1, c["supported"] + c["not-observed"]),
            "revisionByInstanceCount": revision[p],
        }

    # 4. Pairwise statistics on instances conclusive for both models.
    def shared(a: str, b: str) -> list[tuple]:
        return [
            k for k, r in logs[a].items()
            if r["evidence"] != "inconclusive" and k in logs[b] and logs[b][k]["evidence"] != "inconclusive"
        ]

    pairs = {}
    for i, a in enumerate(included):
        for b in included[i + 1:]:
            keys = shared(a, b)
            if len(keys) < MIN_SHARED:
                continue
            x = np.array([logs[a][k]["evidence"] == "supported" for k in keys], dtype=float)
            y = np.array([logs[b][k]["evidence"] == "supported" for k in keys], dtype=float)
            n11 = int((x * y).sum())
            n10 = int((x * (1 - y)).sum())
            n01 = int(((1 - x) * y).sum())
            n00 = len(keys) - n11 - n10 - n01
            denom = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
            phi = (n11 * n00 - n10 * n01) / denom if denom else None
            log_or = math.log(((n11 + 0.5) * (n00 + 0.5)) / ((n10 + 0.5) * (n01 + 0.5)))
            strata: dict[tuple, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
            for k, xa, yb in zip(keys, x, y):
                cell = strata[(k[0], k[2])]
                cell[0 if (xa and yb) else 1 if xa else 2 if yb else 3] += 1
            mh = mantel_haenszel([tuple(v) for v in strata.values()])
            pairs[f"{a} | {b}"] = {
                "shared": len(keys),
                "table": [n11, n10, n01, n00],
                "phi": phi,
                "logOddsRatioHaldane": log_or,
                "jaccard": n11 / (n11 + n10 + n01) if (n11 + n10 + n01) else None,
                "asrA": (n11 + n10) / len(keys),
                "asrB": (n11 + n01) / len(keys),
                "transferAtoB": n11 / (n11 + n10) if (n11 + n10) else None,
                "transferBtoA": n11 / (n11 + n01) if (n11 + n01) else None,
                "liftAtoB": (n11 / (n11 + n10)) / ((n11 + n01) / len(keys)) if (n11 + n10) and (n11 + n01) else None,
                "mhOddsRatioByInjectionTask": mh,
                "sameRevision": revision[a] == revision[b],
            }
    phis = [v["phi"] for v in pairs.values() if v["phi"] is not None]
    lifts = [v["liftAtoB"] for v in pairs.values() if v["liftAtoB"] is not None]
    lifts += [
        (v["transferBtoA"] / v["asrA"]) for v in pairs.values() if v["transferBtoA"] is not None and v["asrA"] > 0
    ]
    mh_values = [v["mhOddsRatioByInjectionTask"] for v in pairs.values() if v["mhOddsRatioByInjectionTask"]]
    mh_above = sum(1 for m in mh_values if m["ci95"][0] > 1)
    mh_below = sum(1 for m in mh_values if m["ci95"][1] < 1)

    # 5. Cluster bootstrap (injection tasks) for headline ordered pairs.
    headline = [
        ("claude-3-5-sonnet-20240620", "claude-3-5-sonnet-20241022"),
        ("gpt-4-turbo-2024-04-09", "gpt-4o-2024-05-13"),
        ("meta-llama_Llama-3.3-70B-Instruct", "Meta-SecAlign-70B"),
    ]
    rng = np.random.default_rng(SEED)
    headline_report = {}
    for a, b in headline:
        keys = shared(a, b)
        clusters: dict[tuple, list[tuple]] = defaultdict(list)
        for k in keys:
            clusters[(k[0], k[2])].append(k)
        names = sorted(clusters)

        def stats(selected: list[tuple]) -> tuple[float | None, float | None, float | None]:
            n11 = sum(1 for k in selected if logs[a][k]["evidence"] == "supported" and logs[b][k]["evidence"] == "supported")
            na = sum(1 for k in selected if logs[a][k]["evidence"] == "supported")
            nb = sum(1 for k in selected if logs[b][k]["evidence"] == "supported")
            forward = n11 / na if na else None
            backward = n11 / nb if nb else None
            lift = (forward / (nb / len(selected))) if (forward is not None and nb) else None
            return forward, backward, lift

        point = stats(keys)
        draws: list[tuple] = []
        for _ in range(BOOTSTRAP):
            chosen = [k for idx in rng.integers(0, len(names), len(names)) for k in clusters[names[idx]]]
            draws.append(stats(chosen))

        def ci(index: int) -> list[float] | None:
            values = [d[index] for d in draws if d[index] is not None]
            return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))] if values else None

        na = sum(1 for k in keys if logs[a][k]["evidence"] == "supported")
        nb = sum(1 for k in keys if logs[b][k]["evidence"] == "supported")
        n11 = sum(1 for k in keys if logs[a][k]["evidence"] == "supported" and logs[b][k]["evidence"] == "supported")
        headline_report[f"{a} -> {b}"] = {
            "sharedConclusive": len(keys),
            "injectionTaskClusters": len(names),
            "aSuccesses": na,
            "bSuccesses": nb,
            "both": n11,
            "transfer": point[0],
            "transferClusterCI95": ci(0),
            "reverseShareOfBSuccessesAlsoOnA": point[1],
            "reverseClusterCI95": ci(1),
            "lift": point[2],
            "liftClusterCI95": ci(2),
            "asrAOnShared": na / len(keys),
            "asrBOnShared": nb / len(keys),
            "sameRevision": revision[a] == revision[b],
        }

    # 6. Content-keyed envelope (E3): is the user-task prompt identical across pipelines?
    def content_keyed(field: str) -> dict[str, Any]:
        digests: dict[tuple, set] = defaultdict(set)
        for p in included:
            for k, r in logs[p].items():
                if r[field] is not None:
                    digests[k].add(r[field])
        shared_keys = [k for k in digests if sum(1 for p in included if k in logs[p]) >= 2]
        changed_keys = [k for k in shared_keys if len(digests[k]) > 1]
        decisions = Counter()
        for a in included:
            for b in included:
                if a == b:
                    continue
                for k, ra in logs[a].items():
                    if ra["evidence"] != "supported":
                        continue
                    rb = logs[b].get(k)
                    # Section 4.4 order: an observed context mismatch is incompatible even
                    # when the target's evidence is also inconclusive; a missing log or a
                    # missing prompt leaves the context unknown, hence inconclusive.
                    if rb is None or ra[field] is None or rb[field] is None:
                        decisions["inconclusive"] += 1
                    elif ra[field] != rb[field]:
                        decisions["incompatible"] += 1
                    elif rb["evidence"] == "inconclusive":
                        decisions["inconclusive"] += 1
                    elif rb["evidence"] == "supported":
                        decisions["equivalent"] += 1
                    else:
                        decisions["divergent"] += 1
        conclusive = decisions["equivalent"] + decisions["divergent"]
        return {
            "sharedInstances": len(shared_keys),
            "instancesWithChangedUserPrompt": len(changed_keys),
            "changedExamples": [list(k) for k in changed_keys[:10]],
            "changedUserTasks": sorted({f"{k[0]}/{k[1]}" for k in changed_keys}),
            "decisions": dict(decisions),
            "reproductionRate": decisions["equivalent"] / conclusive if conclusive else None,
        }

    e3_normalised = content_keyed("userPromptDigest")
    e3_raw = content_keyed("userPromptDigestRaw")
    e3_material = content_keyed("userPromptDigestMaterial")
    e3_task_and_goal = content_keyed("taskAndGoalDigest")
    goal_variants: dict[tuple, set] = defaultdict(set)
    for p in included:
        for k, r in logs[p].items():
            goal_variants[(k[0], k[2])].add(r["injectionGoalDigest"])
    changed_goals = sorted(f"{s}/{i}" for (s, i), v in goal_variants.items() if len(v) > 1)
    within_revision_text_changes = 0
    for k in {k for p in included for k in logs[p]}:
        by_revision: dict[str, set] = defaultdict(set)
        for p in included:
            r = logs[p].get(k)
            if r is not None and r["userPromptDigestMaterial"] is not None:
                by_revision[revision[p]].add(r["userPromptDigestMaterial"])
        if any(len(v) > 1 for v in by_revision.values()):
            within_revision_text_changes += 1
    encodings = {p: dict(Counter(r["promptEncoding"] or "absent" for r in logs[p].values())) for p in included}

    # 8. Difficulty-adjusted successor check (added after a second review round). Is the
    #    predecessor special, or do the later model's few successes fall on instances that
    #    succeed on almost every model?
    def succ(p: str, k: tuple) -> bool | None:
        r = logs[p].get(k)
        if r is None or r["evidence"] == "inconclusive":
            return None
        return r["evidence"] == "supported"

    all_keys = sorted({k for p in included for k in logs[p]})
    ease: dict[tuple, float] = {}
    for k in all_keys:
        votes = [s for s in (succ(p, k) for p in included) if s is not None]
        ease[k] = sum(votes) / len(votes) if votes else float("nan")
    successor_check = {}
    for a, b in headline:
        b_keys = [k for k in all_keys if succ(b, k) is True]
        others = [p for p in included if p not in (a, b)]
        rates = {}
        for m in [a, *others]:
            vals = [succ(m, k) for k in b_keys]
            vals = [v for v in vals if v is not None]
            rates[m] = {"alsoSuccessful": sum(vals), "conclusive": len(vals), "share": sum(vals) / len(vals) if vals else None}
        shares = sorted(((v["share"], m) for m, v in rates.items() if v["share"] is not None), reverse=True)
        rank = 1 + sum(1 for s, m in shares if m != a and s > rates[a]["share"])
        tied = sum(1 for s, m in shares if m != a and s == rates[a]["share"])
        b_shared = [k for k in all_keys if succ(a, k) is not None and succ(b, k) is not None]
        def ease_excluding(k: tuple) -> float:
            votes = [s for s in (succ(p, k) for p in others) if s is not None]
            return sum(votes) / len(votes) if votes else float("nan")
        ease_success = [ease_excluding(k) for k in b_keys]
        ease_all = [ease_excluding(k) for k in b_shared]
        # Difficulty-matched expectation for the predecessor: bin instances by the share of the
        # other 20 models on which they succeed, and use the predecessor's success rate within
        # each bin.
        bins: dict[int, list[bool]] = defaultdict(list)
        for k in b_shared:
            s = succ(a, k)
            if s is not None:
                bins[min(9, int(ease_excluding(k) * 10))].append(s)
        expected = 0.0
        counted = 0
        for k in b_keys:
            s = succ(a, k)
            if s is None:
                continue
            cell = bins[min(9, int(ease_excluding(k) * 10))]
            expected += sum(cell) / len(cell)
            counted += 1
        successor_check[f"{a} -> {b}"] = {
            "laterSuccesses": len(b_keys),
            "predecessor": rates[a],
            "predecessorRankAmong21": rank,
            "predecessorTiesAmongOthers": tied,
            "otherModelsShareMedian": statistics.median(v["share"] for m, v in rates.items() if m != a and v["share"] is not None),
            "otherModelsShareMax": max(v["share"] for m, v in rates.items() if m != a and v["share"] is not None),
            "otherModelsAtOrAbovePredecessor": [m for m in others if rates[m]["share"] is not None and rates[m]["share"] >= rates[a]["share"]],
            "meanOtherModelSuccessShareOnLaterSuccesses": statistics.mean(ease_success),
            "meanOtherModelSuccessShareOnAllSharedInstances": statistics.mean(ease_all),
            "difficultyMatchedExpectedPredecessorSuccesses": expected,
            "difficultyMatchedComparable": counted,
            "perModel": rates,
        }

    # 9. Released table of task-text variants (whitespace-normalised), with the models that
    #    received each variant, so the reworded tasks can be inspected without the raw logs.
    variant_models: dict[tuple, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    variant_text: dict[str, str] = {}
    for p in included:
        for k, r in logs[p].items():
            if r["userPromptDigestMaterial"] is not None:
                variant_models[(k[0], k[1])][r["userPromptDigestMaterial"]].append(p)
                variant_text[r["userPromptDigestMaterial"]] = r["userPromptText"]
    changed_task_variants = {}
    for (suite, task), variants in sorted(variant_models.items()):
        if len(variants) > 1:
            changed_task_variants[f"{suite}/{task}"] = [
                {"text": variant_text[d], "models": sorted(set(ms))} for d, ms in sorted(variants.items())
            ]

    # 10. Family-wide successor analysis against a difficulty-matched null. For an ordered
    #     pair (earlier a, later b), among b's supported successes on instances conclusive for
    #     a, count how many also succeeded on a (observed), and the number expected from a's
    #     success rate among instances of similar difficulty, where difficulty is the share of
    #     the other 20 models on which the instance succeeded (deciles).
    matrix = {p: [succ(p, k) for k in all_keys] for p in included}
    total_success = [0] * len(all_keys)
    total_conclusive = [0] * len(all_keys)
    for p in included:
        for i, s in enumerate(matrix[p]):
            if s is not None:
                total_conclusive[i] += 1
                total_success[i] += int(s)

    def observed_expected(a: str, b: str) -> dict[str, Any] | None:
        sa, sb = matrix[a], matrix[b]
        bins: dict[int, list[int]] = defaultdict(lambda: [0, 0])
        rows = []
        for i in range(len(all_keys)):
            if sa[i] is None or sb[i] is None:
                continue
            n = total_conclusive[i] - 2
            if n <= 0:
                continue
            ease_i = (total_success[i] - int(sa[i]) - int(sb[i])) / n
            cell = min(9, int(ease_i * 10))
            bins[cell][0] += int(sa[i])
            bins[cell][1] += 1
            if sb[i]:
                rows.append((cell, sa[i], ease_i))
        if not rows:
            return None
        observed = sum(int(s) for _c, s, _e in rows)
        expected = sum(bins[c][0] / bins[c][1] for c, _s, _e in rows)
        return {
            "laterSuccesses": len(rows),
            "observedAlsoOnEarlier": observed,
            "expectedGivenDifficulty": expected,
            "observedOverExpected": observed / expected if expected else None,
            "meanOtherModelShareOnLaterSuccesses": statistics.mean(e for _c, _s, e in rows),
        }

    oe_all = {}
    for a in included:
        for b in included:
            if a != b:
                cell = observed_expected(a, b)
                if cell is not None and cell["laterSuccesses"] >= 5 and cell["observedOverExpected"] is not None:
                    oe_all[f"{a} -> {b}"] = cell
    lineage = [
        ("claude-3-sonnet-20240229", "claude-3-5-sonnet-20240620"),
        ("claude-3-5-sonnet-20240620", "claude-3-5-sonnet-20241022"),
        ("claude-3-5-sonnet-20241022", "claude-3-7-sonnet-20250219"),
        ("gpt-4-0125-preview", "gpt-4-turbo-2024-04-09"),
        ("gpt-4-turbo-2024-04-09", "gpt-4o-2024-05-13"),
        ("gemini-1.5-flash-001", "gemini-1.5-flash-002"),
        ("gemini-1.5-pro-001", "gemini-1.5-pro-002"),
        ("gemini-2.0-flash-exp", "gemini-2.0-flash-001"),
        ("meta-llama_Llama-3-70b-chat-hf", "meta-llama_Llama-3.3-70B-Instruct"),
        ("meta-llama_Llama-3.3-70B-Instruct", "Meta-SecAlign-70B"),
    ]
    lineage_keys = {f"{a} -> {b}" for a, b in lineage}
    reference = sorted(v["observedOverExpected"] for k, v in oe_all.items() if k not in lineage_keys)
    lineage_report = {}
    for a, b in lineage:
        cell = observed_expected(a, b)
        assert cell is not None
        ratio = cell["observedOverExpected"]
        cell["percentileAmongOtherOrderedPairs"] = (
            sum(1 for v in reference if v < ratio) / len(reference) if ratio is not None else None
        )
        lineage_report[f"{a} -> {b}"] = cell
    pooled_observed = sum(v["observedAlsoOnEarlier"] for v in lineage_report.values())
    pooled_expected = sum(v["expectedGivenDifficulty"] for v in lineage_report.values())
    reference_median = statistics.median(reference)
    family = {
        "rule": "consecutive versions within one named model line from one developer, earlier -> later by release date",
        "pairs": lineage_report,
        "pooledObserved": pooled_observed,
        "pooledExpected": pooled_expected,
        "pooledObservedOverExpected": pooled_observed / pooled_expected,
        "lineagePairsAboveReferenceMedian": sum(
            1 for v in lineage_report.values() if v["observedOverExpected"] > reference_median
        ),
        "referenceOrderedPairs": len(reference),
        "referenceMedianObservedOverExpected": reference_median,
        "referenceIQR": [float(np.percentile(reference, 25)), float(np.percentile(reference, 75))],
        "allOrderedPairsMedianObservedOverExpected": statistics.median(v["observedOverExpected"] for v in oe_all.values()),
    }

    developer = {
        p: ("Anthropic" if p.startswith("claude") else "OpenAI" if p.startswith("gpt") else "Google" if p.startswith("gemini")
            else "Cohere" if p.startswith("command") else "Meta")
        for p in included
    }
    groups: dict[str, list[dict[str, Any]]] = {"succession": [], "sameDeveloperOther": [], "crossDeveloper": []}
    for key, cell in oe_all.items():
        a, b = key.split(" -> ")
        group = "succession" if key in lineage_keys else "sameDeveloperOther" if developer[a] == developer[b] else "crossDeveloper"
        groups[group].append(cell)
    family["byGroup"] = {
        name: {
            "orderedPairs": len(cells),
            "medianObservedOverExpected": statistics.median(c["observedOverExpected"] for c in cells),
            "pooledObservedOverExpected": sum(c["observedAlsoOnEarlier"] for c in cells) / sum(c["expectedGivenDifficulty"] for c in cells),
        }
        for name, cells in groups.items()
    }
    for a, b in lineage:
        later_successes = [i for i in range(len(all_keys)) if matrix[b][i] is True]
        shares = {}
        for m in included:
            if m == b:
                continue
            vals = [matrix[m][i] for i in later_successes if matrix[m][i] is not None]
            shares[m] = sum(vals) / len(vals) if vals else -1.0
        rank = 1 + sum(1 for m, s in shares.items() if m != a and s > shares[a])
        family["pairs"][f"{a} -> {b}"]["predecessorRankByShareAmong21"] = rank
    family["predecessorRankedFirst"] = sum(1 for v in family["pairs"].values() if v["predecessorRankByShareAmong21"] == 1)
    reference_counts = [total_conclusive[i] - 2 for i in range(len(all_keys))]
    family["referenceModelsPerInstance"] = {"min": min(reference_counts), "max": max(reference_counts),
                                             "instancesWithAtMost2": sum(1 for c in reference_counts if c <= 2)}
    for name, cell in headline_report.items():
        cell["reverseWilson95"] = wilson(cell["both"], cell["bSuccesses"])
        cell["forwardWilson95"] = wilson(cell["both"], cell["aSuccesses"])

    # 11. How much of the variation in directional transfer the target's base rate explains.
    xs, ys_ = [], []
    for name, cell in primary["M2pairs"].items():
        e2 = cell["E2"]
        if e2.get("conclusive", 0) >= MIN_SHARED and e2.get("reproductionRate") is not None:
            target = name.split(" -> ")[1]
            xs.append(primary["perPipeline"][target]["asrSupported"])
            ys_.append(e2["reproductionRate"])
    r = float(np.corrcoef(xs, ys_)[0, 1])
    base_rate_r2 = {"orderedPairs": len(xs), "pearsonR": r, "rSquared": r * r}

    # 11b. Median lift on shared conclusive instances, over exactly the 399 ordered pairs that
    #      qualify under the pre-specified E2 rule (like-for-like with the pre-specified 2.25).
    qualifying_lifts = []
    for name, cell in primary["M2pairs"].items():
        if cell["E2"].get("conclusive", 0) < MIN_SHARED:
            continue
        a, b = name.split(" -> ")
        if f"{a} | {b}" in pairs:
            v = pairs[f"{a} | {b}"]
            lift = v["liftAtoB"]
        else:
            v = pairs[f"{b} | {a}"]
            lift = v["transferBtoA"] / v["asrA"] if v["transferBtoA"] is not None and v["asrA"] else None
        if lift is not None:
            qualifying_lifts.append(lift)
    qualifying_lift = {"orderedPairs": len(qualifying_lifts), "medianLift": statistics.median(qualifying_lifts)}

    # 12. Multiplicity: Holm adjustment of the Mantel-Haenszel tests (two-sided, normal approx.).
    def p_value(m: dict[str, Any]) -> float:
        lo, hi = math.log(m["ci95"][0]), math.log(m["ci95"][1])
        se = (hi - lo) / (2 * 1.96)
        z = ((hi + lo) / 2) / se if se > 0 else 0.0
        return math.erfc(abs(z) / math.sqrt(2))

    p_values = sorted(p_value(m) for m in mh_values)
    holm = 0
    for i, pv in enumerate(p_values):
        if pv <= 0.05 / (len(p_values) - i):
            holm += 1
        else:
            break

    # 7. Within-revision versus cross-revision transfer (E2 decisions on shared conclusive instances).
    def pooled(same: bool) -> dict[str, Any]:
        eq = div = 0
        for a in included:
            for b in included:
                if a == b or (revision[a] == revision[b]) != same:
                    continue
                for k, ra in logs[a].items():
                    if ra["evidence"] != "supported" or k not in logs[b]:
                        continue
                    if logs[b][k]["evidence"] == "supported":
                        eq += 1
                    elif logs[b][k]["evidence"] == "not-observed":
                        div += 1
        return {"equivalent": eq, "divergent": div, "rate": eq / (eq + div) if (eq + div) else None, "wilson95": wilson(eq, eq + div)}

    result = {
        "artifactType": "sova.pf-agentdojo-supplementary-analysis",
        "status": "post-hoc exploratory; added after AI-assisted review; not part of the frozen protocol",
        "primaryResultSha256": hashlib.sha256(primary_path.read_bytes()).hexdigest(),
        "analysedModels": len(included),
        "analysedLogs": analysed_logs,
        "analysedLogsWithBenchmarkVersion": version_logs,
        "modelsRecordingVersion": [p for p in included if primary["perPipeline"][p]["benchmarkVersionPresent"]],
        "errorKeyAbsentLogs": error_key_absent,
        "revisionByInstanceCount": revision,
        "opusNoTurnProfile": opus_profile,
        "supportedWithZeroToolCalls": zero_tool_supported,
        "asrBounds": asr,
        "symmetricSummary": {
            "unorderedPairs": len(pairs),
            "medianPhi": statistics.median(phis) if phis else None,
            "phiIQR": [float(np.percentile(phis, 25)), float(np.percentile(phis, 75))] if phis else None,
            "pairsWithPositivePhi": sum(1 for p in phis if p > 0),
            "medianLiftSharedConclusive": statistics.median(lifts) if lifts else None,
            "orderedLifts": len(lifts),
            "mhPairs": len(mh_values),
            "medianMhOddsRatio": statistics.median(m["or"] for m in mh_values) if mh_values else None,
            "mhPairsCiAbove1": mh_above,
            "mhPairsCiBelow1": mh_below,
        },
        "headlinePairs": headline_report,
        "contentKeyedEnvelopeE3": e3_normalised,
        "contentKeyedEnvelopeE3RawEncoding": e3_raw,
        "contentKeyedEnvelopeE3WhitespaceTolerant": e3_material,
        "contentKeyedEnvelopeE3TaskAndGoal": e3_task_and_goal,
        "injectionTasksWithChangedGoalText": changed_goals,
        "instancesWithMaterialTextChangeWithinInstanceCountGroup": within_revision_text_changes,
        "userPromptEncodingByModel": encodings,
        "successorDifficultyCheck": successor_check,
        "successorFamilyDifficultyMatched": family,
        "baseRateExplainsTransfer": base_rate_r2,
        "medianLiftSharedConclusiveQualifyingPairs": qualifying_lift,
        "mantelHaenszelHolmSignificant": holm,
        "changedTaskVariants": changed_task_variants,
        "withinRevision": pooled(True),
        "crossRevision": pooled(False),
        "pairs": pairs,
    }
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("pairs", "asrBounds", "errorKeyAbsentLogs")}, indent=1, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
