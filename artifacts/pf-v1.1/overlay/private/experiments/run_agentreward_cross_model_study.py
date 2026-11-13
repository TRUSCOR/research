"""External recorded cross-model WebArena trajectory comparison.

The source trajectories and expert annotations are public external records.
The SOVA mapping and comparison rule are same-team research work. Raw source
content is never copied into the retained result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tempfile
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from private.experiments.prototypes.semantic import (
    ContextMode,
    ContextRule,
    OutcomePredicate,
    PredicateOperator,
    SemanticOutcome,
    TrialRecord,
    decide_reproduction,
    estimate_reproduction,
)
from sova.capsule import build_capsule, capsule_manifest_template
from sova.formats import PackageReader, sha256_digest
from sova.trace import TraceReader, TraceWriter

ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "private"
    / "experiments"
    / "results"
    / "agentreward-cross-model-study-2026-07-31.json"
)
SPACE_COMMIT = "271f96552e2e6dd13fe8e3572f0e5264039f6fd0"
SOURCE_MODEL = "GenericAgent-Qwen_Qwen2.5-VL-72B-Instruct"
CANDIDATE_MODEL = "GenericAgent-gpt-4o-2024-11-20"
ACTION_VERB = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.-]*)")


def _source_path(filename: str) -> str:
    return filename.replace("__", "/")


def _digest_bytes(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _action_verb(action: Any) -> str:
    match = ACTION_VERB.match(action if isinstance(action, str) else "")
    return match.group(1).lower() if match else "unknown"


def _forbidden_probes(document: dict[str, Any]) -> list[bytes]:
    values: list[str] = []
    goal = document.get("goal")
    if isinstance(goal, str):
        values.append(goal)
    steps = document.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            for key in (
                "reasoning",
                "axtree",
                "axtree_pruned",
                "screenshot_path",
                "url",
                "focused_element",
            ):
                value = step.get(key)
                if isinstance(value, str):
                    values.append(value)
            messages = step.get("chat_messages")
            if isinstance(messages, list):
                for message in messages:
                    if not isinstance(message, dict):
                        continue
                    for value in message.values():
                        if isinstance(value, str):
                            values.append(value)
    probes: list[bytes] = []
    for value in values:
        normalized = value.strip()
        if len(normalized) < 12:
            continue
        probe = normalized[:96].encode("utf-8", errors="ignore")
        if probe and probe not in probes:
            probes.append(probe)
        if len(probes) >= 64:
            break
    return probes


def _trajectory_record(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    document = json.loads(raw)
    if not isinstance(document, dict):
        raise RuntimeError(f"trajectory is not an object: {path.name}")
    steps = document.get("steps")
    if not isinstance(steps, list):
        raise RuntimeError(f"trajectory steps are not a list: {path.name}")
    actions: list[dict[str, Any]] = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise RuntimeError(f"trajectory step is not an object: {path.name}:{index}")
        action = step.get("action")
        action_text = action if isinstance(action, str) else ""
        actions.append(
            {
                "step": index,
                "verb": _action_verb(action_text),
                "digest": sha256_digest(action_text.encode("utf-8")),
            }
        )
    source_path = _source_path(path.name)
    segments = source_path.split("/")
    if len(segments) < 6:
        raise RuntimeError(f"unexpected trajectory path: {source_path}")
    task_id = Path(source_path).stem
    model_name = segments[3]
    experiment = segments[4]
    forbidden = _forbidden_probes(document)
    return {
        "sourcePath": source_path,
        "sourceBytes": len(raw),
        "sourceDigest": _digest_bytes(raw),
        "benchmark": str(document.get("benchmark", "webarena")),
        "taskId": task_id,
        "model": model_name,
        "experiment": experiment,
        "packageVersion": str(document.get("package_version", "not-recorded")),
        "valid": bool(document.get("valid", False)),
        "actions": actions,
        "forbiddenProbes": forbidden,
    }


def _annotations(path: Path) -> tuple[dict[tuple[str, str, str], list[dict[str, str]]], str]:
    raw = path.read_bytes()
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    reader = csv.DictReader(raw.decode("utf-8-sig").splitlines())
    for row in reader:
        key = (row["benchmark"], row["task_id"], row["model_name"])
        grouped[key].append(
            {
                "success": row["trajectory_success"],
                "sideEffect": row["trajectory_side_effect"],
                "optimality": row["trajectory_optimality"],
                "looping": row["trajectory_looping"],
            }
        )
    return grouped, _digest_bytes(raw)


def _consensus(rows: list[dict[str, str]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "records": len(rows),
        "agreement": {},
        "labels": {},
        "counts": {},
    }
    for field in ("success", "sideEffect", "optimality", "looping"):
        counts = Counter(row[field] for row in rows)
        result["counts"][field] = dict(sorted(counts.items()))
        if len(counts) == 1:
            result["labels"][field] = next(iter(counts))
            result["agreement"][field] = "unanimous"
        else:
            highest = max(counts.values())
            leaders = sorted(label for label, count in counts.items() if count == highest)
            result["labels"][field] = leaders[0] if len(leaders) == 1 else None
            result["agreement"][field] = "plurality" if len(leaders) == 1 else "tie"
    return result


def _write_trace(
    directory: Path,
    trajectory: dict[str, Any],
    consensus: dict[str, Any],
) -> tuple[Path, int]:
    trace = directory / f"{trajectory['model']}--{trajectory['taskId']}.sova-trace"
    writer = TraceWriter(
        trace,
        capture_profile="standard",
        authorization={
            "decision": "not-required",
            "scopeDigest": None,
            "decidedBy": "offline-external-import",
        },
        environment={
            "platform": "external-recorded-webarena",
            "python": "not-recorded",
            "codeDigest": f"sha256:{SPACE_COMMIT}{'0' * 24}",
            "model": {
                "id": trajectory["model"],
                "source": "AgentRewardBench-recorded-trajectory",
            },
            "dependencies": [
                {
                    "name": "AgentRewardBench-demo-Space",
                    "version": "commit",
                    "digest": f"git:{SPACE_COMMIT}",
                }
            ],
        },
        executor={
            "id": "external:webarena",
            "name": "Recorded WebArena environment",
            "version": "not-recorded",
            "capabilityDigest": None,
        },
    )
    writer.append(
        "run.started",
        {
            "source": "AgentRewardBench recorded trajectory",
            "sourceCommit": SPACE_COMMIT,
            "sourceDigest": trajectory["sourceDigest"],
            "benchmark": trajectory["benchmark"],
            "taskId": trajectory["taskId"],
            "model": trajectory["model"],
            "experiment": trajectory["experiment"],
            "packageVersion": trajectory["packageVersion"],
            "valid": trajectory["valid"],
            "contentPolicy": "action-verb-and-digest-only",
        },
        producer={
            "id": "external:agentrewardbench",
            "kind": "imported",
            "name": "AgentRewardBench",
        },
    )
    for action in trajectory["actions"]:
        writer.append(
            "browser.action.observed",
            action,
            producer={
                "id": "external:agentrewardbench",
                "kind": "imported",
                "name": "AgentRewardBench",
            },
            actor={
                "id": f"external:model:{sha256_digest(trajectory['model'].encode())[7:23]}",
                "kind": "model",
                "name": trajectory["model"],
            },
            target={
                "id": "external:environment:webarena",
                "kind": "environment",
                "name": "WebArena",
            },
        )
    writer.append(
        "judge.completed",
        {
            "source": "AgentRewardBench expert annotations",
            "records": consensus["records"],
            "agreement": consensus["agreement"],
            "labels": consensus["labels"],
            "counts": consensus["counts"],
            "annotatorIdentityIncluded": False,
        },
        producer={
            "id": "external:agentrewardbench:expert-labels",
            "kind": "imported",
            "name": "AgentRewardBench expert annotations",
        },
    )
    writer.append(
        "run.completed",
        {
            "status": "imported",
            "stepCount": len(trajectory["actions"]),
            "rawContentIncluded": False,
        },
    )
    writer.finalize()
    verification = TraceReader(trace).verify()
    return trace, verification.event_count


def _write_capsule(
    directory: Path,
    trajectory: dict[str, Any],
    trace: Path,
    consensus: dict[str, Any],
) -> Path:
    manifest = capsule_manifest_template(
        title=f"Imported WebArena behavior — {trajectory['taskId']}",
        summary="Privacy-minimized external recorded trajectory for behavioral comparison.",
        author="Gautam R. Patil",
    )
    manifest["license"] = "NOASSERTION"
    manifest["safety"]["impact"] = "unknown"
    manifest["limitations"].extend(
        [
            "External recorded trajectory; SOVA did not observe the original run.",
            "Environment snapshot and tool/runtime versions are unavailable.",
            "Only action verbs, action digests, and aggregated expert labels are retained.",
            "No controlled re-execution or environment equivalence is claimed.",
        ]
    )
    manifest["extensions"]["x-agentrewardbench-import"] = {
        "sourceCommit": SPACE_COMMIT,
        "sourceDigest": trajectory["sourceDigest"],
        "benchmark": trajectory["benchmark"],
        "taskId": trajectory["taskId"],
        "model": trajectory["model"],
        "stepCount": len(trajectory["actions"]),
        "expertLabels": consensus["labels"],
        "expertAgreement": consensus["agreement"],
        "rawSourceIncluded": False,
    }
    capsule = directory / f"{trajectory['model']}--{trajectory['taskId']}.sova"
    build_capsule(capsule, manifest, traces=[trace])
    PackageReader(capsule).verify("sova.capsule")
    return capsule


def _privacy_violations(
    trajectory: dict[str, Any],
    trace: Path,
    capsule: Path,
) -> int:
    events = TraceReader(trace).events()
    manifest = PackageReader(capsule).manifest("sova.capsule")
    retained = json.dumps(
        {"events": events, "manifest": manifest},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    forbidden_keys = {
        "goal",
        "reasoning",
        "axtree",
        "axtree_obj",
        "axtree_pruned",
        "screenshot_path",
        "url",
        "open_pages_urls",
        "chat_messages",
        "annotator_name",
    }

    def count_keys(value: Any) -> int:
        if isinstance(value, dict):
            return sum(key in forbidden_keys for key in value) + sum(
                count_keys(child) for child in value.values()
            )
        if isinstance(value, list):
            return sum(count_keys(child) for child in value)
        return 0

    return count_keys({"events": events, "manifest": manifest}) + sum(
        probe in retained for probe in trajectory["forbiddenProbes"]
    )


def _label(consensus: dict[str, Any], field: str) -> str | None:
    value = consensus["labels"].get(field)
    return value if isinstance(value, str) and value not in {"Unsure", "Unknown"} else None


def _comparison_outcome(
    source_events: list[dict[str, Any]],
    candidate_events: list[dict[str, Any]],
    source_labels: dict[str, Any],
    candidate_labels: dict[str, Any],
    task_id: str,
) -> SemanticOutcome:
    mandatory = ("success", "sideEffect", "looping")
    if any(
        _label(source_labels, field) is None or _label(candidate_labels, field) is None
        for field in mandatory
    ):
        return SemanticOutcome.INCONCLUSIVE
    if _label(source_labels, "sideEffect") == "Yes" or _label(
        candidate_labels, "sideEffect"
    ) == "Yes":
        return SemanticOutcome.UNSAFE
    predicates = [
        OutcomePredicate(
            id=f"expert-{field}",
            event_kind="judge.completed",
            operator=PredicateOperator.EQUALS,
            path=("payload", "labels", field),
            expected=_label(source_labels, field),
        )
        for field in ("success", "looping")
    ]
    decision = decide_reproduction(
        predicates=predicates,
        events=candidate_events,
        source_context={
            "benchmark": "webarena",
            "taskId": task_id,
            "model": SOURCE_MODEL,
            "sourceCommit": SPACE_COMMIT,
        },
        candidate_context={
            "benchmark": "webarena",
            "taskId": task_id,
            "model": CANDIDATE_MODEL,
            "sourceCommit": SPACE_COMMIT,
        },
        context_rules=[
            ContextRule(("benchmark",), ContextMode.EXACT),
            ContextRule(("taskId",), ContextMode.EXACT),
            ContextRule(("sourceCommit",), ContextMode.EXACT),
            ContextRule(("model",), ContextMode.RECORD),
        ],
        safe_to_compare=True,
        evidence_valid=bool(source_events and candidate_events),
    )
    return decision.outcome


def _baseline(
    source_actions: list[dict[str, Any]],
    candidate_actions: list[dict[str, Any]],
    source_labels: dict[str, Any],
    candidate_labels: dict[str, Any],
) -> dict[str, str]:
    source_verbs = [item["verb"] for item in source_actions]
    candidate_verbs = [item["verb"] for item in candidate_actions]
    source_success = _label(source_labels, "success")
    candidate_success = _label(candidate_labels, "success")
    return {
        "exactActionSequence": (
            "equivalent" if source_verbs == candidate_verbs else "divergent"
        ),
        "actionMultiset": (
            "equivalent"
            if Counter(source_verbs) == Counter(candidate_verbs)
            else "divergent"
        ),
        "terminalAction": (
            "equivalent"
            if source_verbs
            and candidate_verbs
            and source_verbs[-1] == candidate_verbs[-1]
            else "divergent"
        ),
        "expertSuccessOnly": (
            "inconclusive"
            if source_success is None or candidate_success is None
            else "equivalent"
            if source_success == candidate_success
            else "divergent"
        ),
    }


def run(trajectory_root: Path, annotations_path: Path) -> dict[str, Any]:
    files = sorted(trajectory_root.resolve().glob("*.json"))
    if len(files) != 22:
        raise RuntimeError(f"expected 22 trajectories, found {len(files)}")
    annotation_groups, annotations_digest = _annotations(annotations_path.resolve())
    trajectories = [_trajectory_record(path) for path in files]
    models = sorted({item["model"] for item in trajectories})
    if models != sorted([SOURCE_MODEL, CANDIDATE_MODEL]):
        raise RuntimeError(f"unexpected model set: {models!r}")
    by_pair = {(item["model"], item["taskId"]): item for item in trajectories}
    source_tasks = {task for model, task in by_pair if model == SOURCE_MODEL}
    candidate_tasks = {task for model, task in by_pair if model == CANDIDATE_MODEL}
    shared_tasks = sorted(source_tasks & candidate_tasks)
    if len(shared_tasks) != 11 or source_tasks != candidate_tasks:
        raise RuntimeError(
            f"expected eleven exact shared tasks: source={source_tasks!r}, "
            f"candidate={candidate_tasks!r}"
        )

    rows: list[dict[str, Any]] = []
    total_privacy_violations = 0
    trace_count = 0
    capsule_count = 0
    with tempfile.TemporaryDirectory(prefix="sova-agentreward-pairs-") as raw:
        work = Path(raw)
        prepared: dict[tuple[str, str], dict[str, Any]] = {}
        for trajectory in trajectories:
            key = (
                trajectory["benchmark"],
                trajectory["taskId"],
                trajectory["model"],
            )
            annotation_rows = annotation_groups.get(key, [])
            if not annotation_rows:
                raise RuntimeError(f"missing external annotations for {key!r}")
            consensus = _consensus(annotation_rows)
            trace, event_count = _write_trace(work, trajectory, consensus)
            capsule = _write_capsule(work, trajectory, trace, consensus)
            violations = _privacy_violations(trajectory, trace, capsule)
            total_privacy_violations += violations
            trace_count += 1
            capsule_count += 1
            prepared[(trajectory["model"], trajectory["taskId"])] = {
                "trajectory": trajectory,
                "consensus": consensus,
                "trace": trace,
                "capsule": capsule,
                "eventCount": event_count,
                "privacyViolations": violations,
            }

        trials: list[TrialRecord] = []
        for task_id in shared_tasks:
            source = prepared[(SOURCE_MODEL, task_id)]
            candidate = prepared[(CANDIDATE_MODEL, task_id)]
            source_events = TraceReader(source["trace"]).events()
            candidate_events = TraceReader(candidate["trace"]).events()
            outcome = _comparison_outcome(
                source_events,
                candidate_events,
                source["consensus"],
                candidate["consensus"],
                task_id,
            )
            trials.append(
                TrialRecord(
                    id=task_id,
                    outcome=outcome,
                    stratum="webarena-cross-model-recorded",
                    judge="AgentRewardBench-expert-consensus+SOVA-observable-rule/0.1",
                    evidence_digest=sha256_digest(
                        (
                            source["trajectory"]["sourceDigest"]
                            + candidate["trajectory"]["sourceDigest"]
                        ).encode()
                    ),
                )
            )
            rows.append(
                {
                    "taskId": task_id,
                    "outcome": outcome.value,
                    "source": {
                        "model": SOURCE_MODEL,
                        "sourceDigest": source["trajectory"]["sourceDigest"],
                        "stepCount": len(source["trajectory"]["actions"]),
                        "actionSequenceDigest": sha256_digest(
                            json.dumps(
                                source["trajectory"]["actions"],
                                sort_keys=True,
                                separators=(",", ":"),
                            ).encode()
                        ),
                        "expert": source["consensus"],
                        "traceEvents": source["eventCount"],
                    },
                    "candidate": {
                        "model": CANDIDATE_MODEL,
                        "sourceDigest": candidate["trajectory"]["sourceDigest"],
                        "stepCount": len(candidate["trajectory"]["actions"]),
                        "actionSequenceDigest": sha256_digest(
                            json.dumps(
                                candidate["trajectory"]["actions"],
                                sort_keys=True,
                                separators=(",", ":"),
                            ).encode()
                        ),
                        "expert": candidate["consensus"],
                        "traceEvents": candidate["eventCount"],
                    },
                    "baselines": _baseline(
                        source["trajectory"]["actions"],
                        candidate["trajectory"]["actions"],
                        source["consensus"],
                        candidate["consensus"],
                    ),
                    "privacyViolations": (
                        source["privacyViolations"] + candidate["privacyViolations"]
                    ),
                }
            )

        estimate = estimate_reproduction(trials)

    baseline_names = (
        "exactActionSequence",
        "actionMultiset",
        "terminalAction",
        "expertSuccessOnly",
    )
    return {
        "artifactType": "sova.private-agentreward-cross-model-study",
        "version": "0.1.0",
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "owner": "Gautam R. Patil",
        "organization": "TRUSCOR Private Limited",
        "source": {
            "space": "McGill-NLP/agent-reward-bench-demo",
            "commit": SPACE_COMMIT,
            "models": models,
            "tasks": shared_tasks,
            "trajectoryFiles": len(trajectories),
            "trajectoryBytes": sum(item["sourceBytes"] for item in trajectories),
            "annotationsDigest": annotations_digest,
            "rawSourceRedistributed": False,
            "sourceLicenseAsserted": False,
        },
        "summary": {
            "pairs": len(rows),
            "tracesVerified": trace_count,
            "capsulesVerified": capsule_count,
            "privacyViolations": total_privacy_violations,
            "outcomes": dict(sorted(Counter(row["outcome"] for row in rows).items())),
            "annotationDisagreementTrajectories": sum(
                any(
                    value != "unanimous"
                    for value in row[side]["expert"]["agreement"].values()
                )
                for row in rows
                for side in ("source", "candidate")
            ),
        },
        "reproductionEstimate": asdict(estimate),
        "baselineExactAgreement": {
            name: {
                "matches": sum(row["baselines"][name] == row["outcome"] for row in rows),
                "total": len(rows),
            }
            for name in baseline_names
        },
        "rows": rows,
        "claimBoundary": (
            "Two externally recorded real-model trajectory cohorts and external expert "
            "labels over eleven shared tasks. The comparison is retrospective and "
            "same-team; environment equivalence, controlled re-execution, blind "
            "SOVA-specific annotation, and generalization are not established."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectory-root", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.trajectory_root, args.annotations)
    if result["summary"]["privacyViolations"] != 0:
        raise RuntimeError("forbidden external content leaked into retained artifacts")
    RESULT.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(RESULT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
