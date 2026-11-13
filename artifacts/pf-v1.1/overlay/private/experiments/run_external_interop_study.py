"""Pinned external-format and expert-annotation interoperability study.

The source files are public research fixtures acquired separately and are not
redistributed here. This study records only digests, aggregate labels,
observable action hashes, and explicit fidelity limits.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from private.experiments.prototypes.inspect_ai_adapter import (
    INSPECT_AI_COMMIT,
    import_inspect_json,
    package_imported_trace,
)
from sova.capsule import build_capsule, capsule_manifest_template
from sova.formats import sha256_digest
from sova.trace import TraceReader, TraceWriter

ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT / "private" / "experiments" / "results" / "external-interoperability-study-2026-07-31.json"
)
AGENT_REWARD_BENCH_SPACE_COMMIT = "271f96552e2e6dd13fe8e3572f0e5264039f6fd0"
INSPECT_FIXTURE_SHA256 = "sha256:b36b887e44701701d87a7bd8bac7f9fafb2804731491b3125b3917fb7968a825"
ANNOTATIONS_SHA256 = "sha256:155be0e6530d190c14a056f0195aaafa081c2a45a36e8f72b922c9fdc6838367"
TRAJECTORY_SHA256 = "sha256:1911e612b03bd05f6c2bc336e27ac30e0966661787dd18094b0839d864d2b0e8"
TRAJECTORY_TASK_ID = "webarena.177"
MAX_EXTERNAL_BYTES = 16 * 1024 * 1024
ACTION_VERB = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.-]*)")


def _read_bounded(path: Path, expected_digest: str) -> bytes:
    if path.stat().st_size > MAX_EXTERNAL_BYTES:
        raise ValueError(f"external fixture exceeds {MAX_EXTERNAL_BYTES} bytes: {path}")
    raw = path.read_bytes()
    actual = sha256_digest(raw)
    if actual != expected_digest:
        raise ValueError(
            f"external fixture digest mismatch: expected {expected_digest}, got {actual}"
        )
    return raw


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _array(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    return value


def _external_json(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            raw,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite number in {label}: {token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not valid UTF-8 JSON") from error
    return _object(value, label)


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def _content_probes(inspect_document: Mapping[str, Any]) -> tuple[str, ...]:
    probes: set[str] = set()
    for raw_sample in inspect_document.get("samples", []):
        if not isinstance(raw_sample, Mapping):
            continue
        transcript = raw_sample.get("transcript")
        if not isinstance(transcript, Mapping):
            continue
        for raw_event in transcript.get("events", []):
            if not isinstance(raw_event, Mapping) or raw_event.get("event") != "model":
                continue
            for field in ("input", "output"):
                for text in _strings(raw_event.get(field)):
                    if len(text) >= 8:
                        probes.add(text)
    return tuple(sorted(probes))


def _annotation_rows(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig")
    rows = [dict(row) for row in csv.DictReader(text.splitlines())]
    required = {
        "benchmark",
        "task_id",
        "model_name",
        "exp_name",
        "trajectory_success",
        "trajectory_side_effect",
        "trajectory_looping",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError("AgentRewardBench annotation columns do not match the pinned study")
    return rows


def _label_distribution(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(row[field] for row in rows).items()))


def _consensus(rows: list[dict[str, str]], field: str) -> str:
    values = {row[field] for row in rows}
    return next(iter(values)) if len(values) == 1 else "Disagreement"


def _annotation_for(
    rows: list[dict[str, str]],
    trajectory: Mapping[str, Any],
) -> dict[str, Any]:
    task_id = str(trajectory.get("summary_info", {}).get("task_name", ""))
    if not task_id:
        task_id = str(trajectory.get("goal_object", {}).get("task_id", ""))
    if not task_id:
        task_id = TRAJECTORY_TASK_ID
    experiment = str(trajectory.get("experiment", ""))
    benchmark = str(trajectory.get("benchmark", ""))
    candidates = [
        row
        for row in rows
        if row["benchmark"] == benchmark
        and row["exp_name"] == experiment
        and row["task_id"] == task_id
    ]
    if not candidates:
        raise ValueError("no matching expert annotation")
    first = candidates[0]
    return {
        "benchmark": first["benchmark"],
        "task_id": first["task_id"],
        "model_name": first["model_name"],
        "trajectory_success": _consensus(candidates, "trajectory_success"),
        "trajectory_side_effect": _consensus(candidates, "trajectory_side_effect"),
        "trajectory_looping": _consensus(candidates, "trajectory_looping"),
        "expertLabelCount": len(candidates),
        "labelDistributions": {
            field: _label_distribution(candidates, field)
            for field in (
                "trajectory_success",
                "trajectory_side_effect",
                "trajectory_looping",
            )
        },
    }


def _action_verb(action: str) -> str:
    match = ACTION_VERB.match(action)
    return match.group(1).lower() if match else "unknown"


def _import_agent_reward_trajectory(
    trajectory: dict[str, Any],
    annotation: Mapping[str, Any],
    destination: Path,
) -> tuple[str, int, tuple[str, ...]]:
    steps = _array(trajectory.get("steps"), "AgentRewardBench trajectory.steps")
    writer = TraceWriter(
        destination,
        capture_profile="standard",
        authorization={
            "decision": "not-required",
            "scopeDigest": None,
            "decidedBy": "offline-import",
        },
        environment={
            "platform": "external-agentrewardbench-log",
            "python": "not-recorded",
            "codeDigest": f"sha256:{AGENT_REWARD_BENCH_SPACE_COMMIT}{'0' * 24}",
            "model": {
                "id": str(annotation["model_name"]),
                "source": "agentrewardbench-annotation",
            },
            "dependencies": [],
        },
        executor={
            "id": "external:agentrewardbench",
            "name": "AgentRewardBench imported trajectory",
            "version": AGENT_REWARD_BENCH_SPACE_COMMIT[:12],
            "capabilityDigest": None,
        },
    )
    producer = {
        "id": "external:agentrewardbench",
        "kind": "imported",
        "name": "AgentRewardBench",
    }
    run = writer.append(
        "run.started",
        {
            "source": "AgentRewardBench",
            "sourceCommit": AGENT_REWARD_BENCH_SPACE_COMMIT,
            "benchmark": annotation["benchmark"],
            "taskId": annotation["task_id"],
            "contentPolicy": "observable action digest and verb only",
        },
        producer=producer,
    )
    phase = writer.append(
        "phase.started",
        {"kind": "external-web-trajectory"},
        parents=[run] if run else [],
        producer=producer,
    )
    last = phase
    action_digests: list[str] = []
    for index, raw_step in enumerate(steps):
        step = _object(raw_step, f"AgentRewardBench steps[{index}]")
        action = step.get("action")
        if not isinstance(action, str) or not action:
            continue
        action_digest = sha256_digest(action.encode("utf-8"))
        action_digests.append(action_digest)
        last = writer.append(
            "browser.action.observed",
            {
                "ordinal": index,
                "actionVerb": _action_verb(action),
                "actionDigest": action_digest,
                "content": {"method": "omitted-by-import-policy"},
                "reasoningCaptured": False,
                "screenCaptured": False,
                "accessibilityTreeCaptured": False,
            },
            parents=[last] if last else [],
            producer=producer,
        )
    judge = writer.append(
        "judge.completed",
        {
            "judge": {
                "id": "external:agentrewardbench-expert-annotation",
                "kind": "human-expert-dataset-label",
                "sourceCommit": AGENT_REWARD_BENCH_SPACE_COMMIT,
            },
            "expertLabelCount": annotation["expertLabelCount"],
            "labelDistributions": annotation["labelDistributions"],
            "success": annotation["trajectory_success"],
            "sideEffect": annotation["trajectory_side_effect"],
            "looping": annotation["trajectory_looping"],
            "limitations": [
                "SOVA did not reproduce or independently re-judge this trajectory.",
                "Annotator identity and free-form notes are not imported.",
            ],
        },
        parents=[last] if last else [],
        producer=producer,
    )
    writer.append(
        "phase.completed",
        {"observableActionCount": len(action_digests)},
        parents=[judge] if judge else [],
        producer=producer,
    )
    writer.append(
        "run.completed",
        {"status": "imported", "sourceTruthNotReverified": True},
        producer=producer,
    )
    return writer.finalize(), len(action_digests), tuple(action_digests)


def _trajectory_capsule(
    trace: Path,
    destination: Path,
    *,
    source_digest: str,
    annotation: Mapping[str, Any],
    action_digests: tuple[str, ...],
) -> str:
    manifest = capsule_manifest_template(
        title="Imported AgentRewardBench behavior record",
        summary="Observable-action and expert-label capsule; no reasoning or screens imported.",
        author="Gautam R. Patil",
    )
    manifest["license"] = "NOASSERTION"
    manifest["safety"]["impact"] = "unknown"
    manifest["limitations"].extend(
        [
            "The source trajectory was not re-executed.",
            "Action arguments, reasoning, screens, accessibility trees, and goal text are omitted.",
            "The source expert annotation is carried, not independently verified by SOVA.",
        ]
    )
    manifest["extensions"]["x-agentrewardbench-import"] = {
        "sourceCommit": AGENT_REWARD_BENCH_SPACE_COMMIT,
        "sourceDigest": source_digest,
        "benchmark": annotation["benchmark"],
        "taskId": annotation["task_id"],
        "model": annotation["model_name"],
        "actionDigests": list(action_digests),
        "contentPolicy": "observable action digest and verb only",
        "fidelity": "lossy",
    }
    return build_capsule(destination, manifest, traces=[trace])


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect-log", required=True, type=Path)
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--trajectory", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    inspect_raw = _read_bounded(args.inspect_log, INSPECT_FIXTURE_SHA256)
    annotations_raw = _read_bounded(args.annotations, ANNOTATIONS_SHA256)
    trajectory_raw = _read_bounded(args.trajectory, TRAJECTORY_SHA256)
    inspect_document = _external_json(inspect_raw, "Inspect AI log")
    trajectory = _external_json(trajectory_raw, "AgentRewardBench trajectory")
    annotations = _annotation_rows(annotations_raw)
    annotation = _annotation_for(annotations, trajectory)

    with tempfile.TemporaryDirectory(prefix="sova-external-interop-") as raw_directory:
        directory = Path(raw_directory)
        inspect_trace = directory / "inspect.sova-trace"
        inspect_report = import_inspect_json(args.inspect_log, inspect_trace)
        inspect_verification = TraceReader(inspect_trace).verify()
        inspect_capsule = directory / "inspect.sova"
        inspect_capsule_digest = package_imported_trace(
            args.inspect_log,
            inspect_trace,
            inspect_capsule,
            inspect_report,
            include_source_log=False,
        )
        inspect_trace_bytes = inspect_trace.read_bytes()
        leaked_inspect_probes = [
            probe
            for probe in _content_probes(inspect_document)
            if probe.encode("utf-8") in inspect_trace_bytes
        ]

        reward_trace = directory / "agentrewardbench.sova-trace"
        reward_trace_digest, action_count, action_digests = _import_agent_reward_trajectory(
            trajectory,
            annotation,
            reward_trace,
        )
        reward_verification = TraceReader(reward_trace).verify()
        reward_capsule = directory / "agentrewardbench.sova"
        reward_capsule_digest = _trajectory_capsule(
            reward_trace,
            reward_capsule,
            source_digest=TRAJECTORY_SHA256,
            annotation=annotation,
            action_digests=action_digests,
        )
        reward_bytes = reward_trace.read_bytes()
        forbidden_values = [
            trajectory.get("goal"),
            next(
                (
                    step.get("reasoning")
                    for step in trajectory.get("steps", [])
                    if isinstance(step, dict) and isinstance(step.get("reasoning"), str)
                ),
                None,
            ),
            next(
                (
                    step.get("screenshot_path")
                    for step in trajectory.get("steps", [])
                    if isinstance(step, dict) and isinstance(step.get("screenshot_path"), str)
                ),
                None,
            ),
        ]
        leaked_reward_fields = [
            name
            for name, value in zip(
                ("goal", "reasoning", "screenshotPath"),
                forbidden_values,
                strict=True,
            )
            if isinstance(value, str) and value.encode("utf-8") in reward_bytes
        ]

    result = {
        "artifactType": "sova.private-external-interoperability-study",
        "version": "0.1.0",
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "owner": "Gautam R. Patil",
        "organization": "TRUSCOR Private Limited",
        "claimBoundary": (
            "Pinned authoritative external fixtures; one imported trajectory and one "
            "format fixture do not establish external reproduction validity or "
            "publication readiness."
        ),
        "inspectAi": {
            "sourceCommit": INSPECT_AI_COMMIT,
            "sourceDigest": INSPECT_FIXTURE_SHA256,
            "sourceSamples": inspect_report.samples,
            "sourceEvents": inspect_report.source_events,
            "emittedEvents": inspect_report.emitted_events,
            "verifiedEvents": inspect_verification.event_count,
            "lossless": inspect_report.lossless,
            "contentProbeCount": len(_content_probes(inspect_document)),
            "contentProbeLeaks": leaked_inspect_probes,
            "capsuleDigest": inspect_capsule_digest,
        },
        "agentRewardBench": {
            "sourceCommit": AGENT_REWARD_BENCH_SPACE_COMMIT,
            "annotationsDigest": ANNOTATIONS_SHA256,
            "annotationRows": len(annotations),
            "benchmarks": sorted({row["benchmark"] for row in annotations}),
            "models": sorted({row["model_name"] for row in annotations}),
            "successDistribution": _label_distribution(annotations, "trajectory_success"),
            "sideEffectDistribution": _label_distribution(
                annotations,
                "trajectory_side_effect",
            ),
            "loopingDistribution": _label_distribution(annotations, "trajectory_looping"),
            "trajectoryDigest": TRAJECTORY_SHA256,
            "observableActionCount": action_count,
            "verifiedEvents": reward_verification.event_count,
            "traceDigest": reward_trace_digest,
            "capsuleDigest": reward_capsule_digest,
            "matchedExpertLabel": {
                "success": annotation["trajectory_success"],
                "sideEffect": annotation["trajectory_side_effect"],
                "looping": annotation["trajectory_looping"],
            },
            "matchedExpertLabelCount": annotation["expertLabelCount"],
            "matchedExpertLabelDistributions": annotation["labelDistributions"],
            "captured": ["action verb", "action digest", "expert categorical labels"],
            "omitted": [
                "goal",
                "action arguments",
                "reasoning",
                "screenshots",
                "accessibility trees",
                "chat messages",
                "annotator identity",
            ],
            "forbiddenFieldLeaks": leaked_reward_fields,
        },
        "limitations": [
            "AgentRewardBench source licensing was not asserted by the Space metadata; "
            "source bytes are not redistributed.",
            "Only one trajectory is converted; the complete expert-labeled cohort is "
            "summarized only.",
            "Imported expert labels are carried as provenance and are not SOVA truth attestations.",
            "The Inspect fixture is an official test log, not an independently produced "
            "SOVA reproduction.",
            "No external model, browser, or computer action was executed by this study.",
        ],
    }
    RESULT.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(RESULT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
