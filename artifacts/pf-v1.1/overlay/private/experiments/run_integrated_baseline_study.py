"""Post-result direct-baseline and drift study for the integrated candidate.

This is same-team synthetic evidence. It is not an external validation result.
"""

from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter_ns
from typing import Any

from private.experiments.prototypes.inspect_ai_adapter import (
    INSPECT_AI_COMMIT,
    import_inspect_json,
)
from private.experiments.prototypes.integrated import (
    EXTENSION_NAME,
    evaluate_integrated_research,
    migrate_research_capsule,
)
from sova.capsule import build_capsule, capsule_manifest_template
from sova.executors import (
    OutcomeStatus,
    RestrictedLocalExecutor,
    ScriptedAction,
    ScriptedExecutor,
    SideEffect,
    run_capsule,
)
from sova.formats import PackageReader, canonical_json_bytes, sha256_digest, strict_json_loads
from sova.reproduction import compare_observable_outcomes
from sova.trace import TraceReader, TraceWriter

ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT / "private" / "experiments" / "results" / "integrated-baseline-drift-study-2026-07-31.json"
)
FIXTURE = b"portable fixture"
DIGEST = sha256_digest(FIXTURE)


def _extension() -> dict[str, Any]:
    return {
        "schemaVersion": "0.1.0",
        "semanticReproduction": {
            "predicates": [
                {
                    "id": "oracle-pass",
                    "eventKind": "oracle.completed",
                    "operator": "equals",
                    "path": ["payload", "status"],
                    "expected": "pass",
                }
            ],
            "sourceContext": {
                "fixture": {"digest": DIGEST},
                "executor": {"kind": "source"},
            },
            "contextRules": [
                {"path": ["fixture", "digest"], "mode": "exact"},
                {"path": ["executor", "kind"], "mode": "record"},
            ],
            "judge": {
                "id": "sova.observable-contract",
                "version": "0.1",
                "kind": "deterministic",
                "calibration": {"status": "same-team-synthetic"},
                "uncertainty": {"multiValued": True},
                "limitations": ["No open-ended semantics are inferred."],
            },
        },
        "evidenceFidelity": {
            "claims": [
                {
                    "id": "oracle-backed-read",
                    "requirements": [
                        {
                            "id": "provider-outcome",
                            "eventKind": "tool.completed",
                            "parentKind": "tool.requested",
                        },
                        {
                            "id": "sova-oracle",
                            "eventKind": "oracle.completed",
                        },
                    ],
                }
            ]
        },
        "executorConformance": {
            "contracts": [
                {
                    "id": "artifact-read-0.1",
                    "action": "artifact.read",
                    "sideEffect": "read",
                    "allowedTerminalStatuses": ["succeeded"],
                    "requiredEvidenceRoles": ["artifact"],
                    "observations": [
                        {
                            "id": "oracle-pass",
                            "kind": "oracle.completed",
                            "path": ["payload", "status"],
                            "expected": "pass",
                        }
                    ],
                    "trustedObserverIds": ["sova:actor:oracle"],
                }
            ]
        },
        "extensions": {"x-study": {"protocol": "post-result-0.5"}},
    }


def _legacy_extension() -> dict[str, Any]:
    current = _extension()
    return {
        "schemaVersion": "0.0.1",
        "semantic": current["semanticReproduction"],
        "claims": current["evidenceFidelity"]["claims"],
        "executorContracts": current["executorConformance"]["contracts"],
        "legacyOpaque": {"preserve": True},
    }


def _scenario() -> dict[str, Any]:
    value = strict_json_loads(
        (ROOT / "examples" / "scenarios" / "portable-artifact-read.json").read_bytes()
    )
    assert isinstance(value, dict)
    return value


def _capsule(directory: Path, name: str, extension: dict[str, Any] | None = None) -> Path:
    manifest = capsule_manifest_template(
        title="Integrated baseline fixture",
        summary="Same-team synthetic post-result research fixture.",
        author="Gautam R. Patil",
    )
    manifest["license"] = "NOASSERTION"
    manifest["safety"]["impact"] = "none"
    manifest["requiredFeatures"] = ["scenario.core/0.1"]
    manifest["extensions"][EXTENSION_NAME] = extension or _extension()
    path = directory / name
    build_capsule(
        path,
        manifest,
        scenario=_scenario(),
        attachments={"portable.txt": FIXTURE},
    )
    return path


def _executor(text: str = "portable fixture") -> ScriptedExecutor:
    return ScriptedExecutor(
        [
            ScriptedAction(
                action="artifact.read",
                expected_inputs={"digest": DIGEST, "mediaType": "text/plain"},
                status=OutcomeStatus.SUCCEEDED,
                side_effect=SideEffect.READ,
                output={
                    "digest": DIGEST,
                    "size": len(text.encode()),
                    "mediaType": "text/plain",
                    "text": text,
                },
                evidence=(("artifact", "text/plain", FIXTURE),),
                verification="synthetic-observation",
            )
        ]
    )


def _run(capsule: Path, trace: Path, executor: Any, workspace: Path) -> None:
    result = run_capsule(
        capsule,
        trace,
        executor=executor,
        workspace=workspace,
        authorization={
            "decision": "allowed",
            "scopeDigest": "sha256:" + ("8" * 64),
            "decidedBy": "same-team-synthetic-study",
        },
    )
    if result.trace_path != trace:
        raise AssertionError("runner returned the wrong trace path")


def _context(kind: str, digest: str = DIGEST) -> dict[str, Any]:
    return {"fixture": {"digest": digest}, "executor": {"kind": kind}}


def _outcome(capsule: Path, trace: Path, context: dict[str, Any], *, safe: bool = True) -> str:
    return evaluate_integrated_research(
        capsule,
        trace,
        candidate_context=context,
        safe_to_compare=safe,
    ).semantic.outcome.value


def _observable_baseline(left: Path, right: Path) -> str:
    comparison = compare_observable_outcomes(
        left,
        right,
        kinds=("oracle.completed",),
    )
    return comparison.status


def _terminal_baseline(left: Path, right: Path) -> str:
    return (
        "equivalent"
        if TraceReader(left).verify().completion == TraceReader(right).verify().completion
        else "divergent"
    )


def _transport_interactions(trace: Path) -> tuple[bytes, ...]:
    events = TraceReader(trace).events()
    interactions: list[bytes] = []
    for request_event in events:
        if request_event.get("kind") != "tool.requested":
            continue
        payload = request_event.get("payload", {})
        request = payload.get("request", {}) if isinstance(payload, dict) else {}
        terminal = next(
            (
                event
                for event in events
                if event.get("kind") in {"tool.completed", "tool.failed"}
                and request_event.get("id") in event.get("parents", [])
            ),
            None,
        )
        terminal_payload = terminal.get("payload", {}) if terminal is not None else {}
        outcome = (
            terminal_payload.get("outcome", {})
            if isinstance(terminal_payload, dict)
            else {}
        )
        interactions.append(
            canonical_json_bytes(
                {
                    "action": request.get("action"),
                    "inputs": request.get("inputs"),
                    "status": outcome.get("status"),
                    "output": outcome.get("output"),
                }
            )
        )
    return tuple(interactions)


def _transport_interaction_baseline(left: Path, right: Path) -> str:
    return (
        "equivalent"
        if _transport_interactions(left) == _transport_interactions(right)
        else "divergent"
    )


def _agent_eval_messages(trace: Path) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for event in TraceReader(trace).events():
        kind = event["kind"]
        payload = event.get("payload", {})
        if kind == "tool.requested":
            request = payload.get("request", {})
            request_id = str(request.get("id", event["id"]))
            action = str(request.get("action", "unknown")).replace(".", "_")
            arguments = json.dumps(
                request.get("inputs", {}),
                sort_keys=True,
                separators=(",", ":"),
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": request_id,
                            "type": "function",
                            "function": {
                                "name": action,
                                "arguments": arguments,
                            },
                        }
                    ],
                }
            )
        elif kind in {"tool.completed", "tool.failed"}:
            outcome = payload.get("outcome", {})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": str(outcome.get("request_id", "unknown")),
                    "content": str(outcome.get("status", "unknown")),
                }
            )
    return messages


def _agent_evals_baselines(reference: Path, candidate: Path) -> dict[str, str]:
    try:
        from agentevals.graph_trajectory.strict import graph_trajectory_strict_match
        from agentevals.trajectory.match import create_trajectory_match_evaluator
    except ImportError:
        return {}
    reference_messages = _agent_eval_messages(reference)
    candidate_messages = _agent_eval_messages(candidate)
    results: dict[str, str] = {}
    for mode in ("strict", "unordered", "superset"):
        evaluator = create_trajectory_match_evaluator(
            trajectory_match_mode=mode,
            tool_args_match_mode="exact",
        )
        result = evaluator(
            outputs=candidate_messages,
            reference_outputs=reference_messages,
        )
        results[f"agentEvals{mode.title()}"] = (
            "equivalent" if result["score"] is True else "divergent"
        )
    reference_graph = {
        "results": [],
        "steps": [[event["kind"] for event in TraceReader(reference).events()]],
    }
    candidate_graph = {
        "results": [],
        "steps": [[event["kind"] for event in TraceReader(candidate).events()]],
    }
    graph_result = graph_trajectory_strict_match(
        outputs=candidate_graph,
        reference_outputs=reference_graph,
    )
    results["agentEvalsGraphStrict"] = (
        "equivalent" if graph_result["score"] is True else "divergent"
    )
    return results


def _accuracy(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    correct = sum(row[field] == row["truth"] for row in rows)
    total = len(rows)
    return {
        "correct": correct,
        "total": total,
        "accuracy": format(correct / total, ".6f"),
    }


def _inspect_extension() -> dict[str, Any]:
    return {
        "schemaVersion": "0.1.0",
        "semanticReproduction": {
            "predicates": [
                {
                    "id": "inspect-score-correct",
                    "eventKind": "judge.completed",
                    "operator": "equals",
                    "path": ["payload", "score", "value"],
                    "expected": "C",
                }
            ],
            "sourceContext": {"inspectCommit": INSPECT_AI_COMMIT, "model": "source"},
            "contextRules": [
                {"path": ["inspectCommit"], "mode": "exact"},
                {"path": ["model"], "mode": "record"},
            ],
            "judge": {
                "id": "inspect-imported-score",
                "version": INSPECT_AI_COMMIT,
                "kind": "imported-observable",
                "limitations": ["The adapter does not recalibrate the source scorer."],
            },
        },
        "evidenceFidelity": {
            "claims": [
                {
                    "id": "inspect-score-present",
                    "requirements": [
                        {"id": "score", "eventKind": "judge.completed"},
                    ],
                }
            ]
        },
        "executorConformance": {
            "contracts": [
                {
                    "id": "not-applicable-import",
                    "action": "inspect.import",
                    "sideEffect": "read",
                    "allowedTerminalStatuses": ["succeeded"],
                    "requiredEvidenceRoles": [],
                    "observations": [],
                    "trustedObserverIds": ["external:inspect-ai"],
                }
            ]
        },
    }


def _inspect_log(output: str, score: str | None) -> dict[str, Any]:
    events: list[dict[str, Any]] = [
        {
            "event": "model",
            "uuid": f"model-{output}",
            "span_id": "span-1",
            "timestamp": "2026-07-31T00:00:00Z",
            "model": "mock/model",
            "input": [{"role": "user", "content": "synthetic"}],
            "output": {"completion": output},
            "retries": 0,
        }
    ]
    if score is not None:
        events.append(
            {
                "event": "score",
                "uuid": f"score-{score}",
                "span_id": "span-1",
                "timestamp": "2026-07-31T00:00:01Z",
                "score": {"value": score},
                "scorer": "synthetic",
                "intermediate": False,
            }
        )
    return {
        "version": 2,
        "status": "success",
        "eval": {
            "eval_id": "synthetic",
            "run_id": f"run-{output}-{score}",
            "task": "synthetic",
            "model": "mock/model",
        },
        "samples": [
            {
                "id": "1",
                "epoch": 1,
                "transcript": {"events": events, "content": {}},
            }
        ],
    }


def _model_output(trace: Path) -> Any:
    event = next(TraceReader(trace).query(kind_prefix="model.response"))
    return event["payload"]["output"]


def _write_inspect(path: Path, document: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(document, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sova-integrated-study-") as raw:
        work = Path(raw)
        capsule = _capsule(work, "current.sova")
        scripted = work / "scripted.sova-trace"
        scripted_repeat = work / "scripted-repeat.sova-trace"
        local = work / "local.sova-trace"
        false_success = work / "false-success.sova-trace"
        _run(capsule, scripted, _executor(), work)
        _run(capsule, scripted_repeat, _executor(), work)
        _run(capsule, local, RestrictedLocalExecutor(), work)
        _run(capsule, false_success, _executor("wrong fixture"), work)

        partial = work / "partial.sova-trace"
        writer = TraceWriter(partial)
        writer.append("run.started", {"case": "partial"})
        writer.append(
            "tool.requested",
            {
                "request": {
                    "id": "read",
                    "action": "artifact.read",
                    "inputs": {"digest": DIGEST},
                }
            },
        )
        writer.finalize(completion="partial")

        missing = work / "complete-missing.sova-trace"
        writer = TraceWriter(missing)
        writer.append("run.started", {"case": "complete-missing"})
        writer.append(
            "tool.requested",
            {
                "request": {
                    "id": "read",
                    "action": "artifact.read",
                    "inputs": {"digest": DIGEST},
                }
            },
        )
        writer.append("run.completed", {"completion": "completed"})
        writer.finalize(completion="completed")

        cases = [
            ("cross-executor-equivalent", "equivalent", local, _context("local"), True),
            (
                "repeat-equivalent",
                "equivalent",
                scripted_repeat,
                _context("scripted"),
                True,
            ),
            (
                "required-context-incompatible",
                "incompatible",
                local,
                _context("local", "sha256:" + ("0" * 64)),
                True,
            ),
            ("unsafe-comparison", "unsafe", local, _context("local"), False),
            ("partial-prefix", "inconclusive", partial, _context("partial"), True),
            (
                "provider-success-oracle-failure",
                "divergent",
                false_success,
                _context("scripted"),
                True,
            ),
            (
                "complete-missing-evidence",
                "inconclusive",
                missing,
                _context("missing"),
                True,
            ),
        ]
        rows: list[dict[str, Any]] = []
        for identifier, truth, candidate_trace, context, safe in cases:
            row = {
                "id": identifier,
                "truth": truth,
                "candidate": _outcome(
                    capsule,
                    candidate_trace,
                    context,
                    safe=safe,
                ),
                "exactTransport": (
                    "equivalent"
                    if scripted.read_bytes() == candidate_trace.read_bytes()
                    else "divergent"
                ),
                "declaredObservable": _observable_baseline(scripted, candidate_trace),
                "terminalCompletion": _terminal_baseline(scripted, candidate_trace),
                "transportInteraction": _transport_interaction_baseline(
                    scripted,
                    candidate_trace,
                ),
            }
            row.update(_agent_evals_baselines(scripted, candidate_trace))
            rows.append(row)

        inspect_manifest = capsule_manifest_template(
            title="Inspect direct baseline fixture",
            summary="Pinned same-team synthetic interoperability experiment.",
            author="Gautam R. Patil",
        )
        inspect_manifest["extensions"][EXTENSION_NAME] = _inspect_extension()
        inspect_capsule = work / "inspect-contract.sova"
        build_capsule(inspect_capsule, inspect_manifest)
        inspect_cases = [
            ("surface-a-correct", "answer A", "C", "equivalent"),
            ("surface-b-correct", "answer B", "C", "equivalent"),
            ("surface-a-incorrect", "answer A", "I", "divergent"),
            ("surface-a-unscored", "answer A", None, "inconclusive"),
        ]
        inspect_rows: list[dict[str, Any]] = []
        reference_output: Any = None
        for index, (identifier, output, score, truth) in enumerate(inspect_cases):
            source = work / f"inspect-{index}.json"
            trace = work / f"inspect-{index}.sova-trace"
            _write_inspect(source, _inspect_log(output, score))
            import_report = import_inspect_json(source, trace, include_content=True)
            observed_output = _model_output(trace)
            if reference_output is None:
                reference_output = observed_output
            inspect_rows.append(
                {
                    "id": identifier,
                    "truth": truth,
                    "candidate": _outcome(
                        inspect_capsule,
                        trace,
                        {
                            "inspectCommit": INSPECT_AI_COMMIT,
                            "model": "mock/model",
                        },
                    ),
                    "exactFinalOutput": (
                        "equivalent" if observed_output == reference_output else "divergent"
                    ),
                    "terminalCompletion": (
                        "equivalent"
                        if TraceReader(trace).verify().completion == "completed"
                        else "divergent"
                    ),
                    "adapterLossless": import_report.lossless,
                }
            )

        fixed_manifest = capsule_manifest_template(
            title="Determinism fixture",
            summary="Same manifest and objects must produce identical bytes.",
            author="Gautam R. Patil",
        )
        deterministic_a = work / "deterministic-a.sova"
        deterministic_b = work / "deterministic-b.sova"
        build_capsule(deterministic_a, fixed_manifest, scenario=_scenario())
        build_capsule(deterministic_b, fixed_manifest, scenario=_scenario())

        legacy = _capsule(work, "legacy.sova", _legacy_extension())
        migrated_a = work / "migrated-a.sova"
        migrated_b = work / "migrated-b.sova"
        migrate_research_capsule(legacy, migrated_a)
        migrate_research_capsule(legacy, migrated_b)

        context_file = work / "context.json"
        context_file.write_bytes(canonical_json_bytes(_context("subprocess")))
        process = subprocess.run(
            [
                sys.executable,
                "-m",
                "private.experiments.research_cli",
                "evaluate",
                str(capsule),
                str(scripted),
                "--context",
                str(context_file),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        subprocess_outcome = (
            json.loads(process.stdout)["semantic"]["outcome"]
            if process.returncode == 0
            else "process-error"
        )

        durations: list[int] = []
        for _ in range(250):
            started = perf_counter_ns()
            _outcome(capsule, scripted, _context("benchmark"))
            durations.append(perf_counter_ns() - started)
        durations.sort()

        result = {
            "artifactType": "sova.private-integrated-baseline-study",
            "version": "0.1.0",
            "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "owner": "Gautam R. Patil",
            "organization": "TRUSCOR Private Limited",
            "claimBoundary": (
                "Same-team synthetic post-result evidence; not external validation, "
                "novelty proof, or publication clearance."
            ),
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "inspectAiCommit": INSPECT_AI_COMMIT,
                "agentEvals": (
                    importlib.metadata.version("agentevals")
                    if rows and "agentEvalsStrict" in rows[0]
                    else "unavailable"
                ),
            },
            "integratedCases": rows,
            "integratedMetrics": {
                name: _accuracy(rows, field)
                for name, field in (
                    ("candidate", "candidate"),
                    ("exactTransport", "exactTransport"),
                    ("declaredObservable", "declaredObservable"),
                    ("terminalCompletion", "terminalCompletion"),
                    ("transportInteraction", "transportInteraction"),
                    *(
                        (("agentEvalsStrict", "agentEvalsStrict"),)
                        if "agentEvalsStrict" in rows[0]
                        else ()
                    ),
                    *(
                        (("agentEvalsUnordered", "agentEvalsUnordered"),)
                        if "agentEvalsUnordered" in rows[0]
                        else ()
                    ),
                    *(
                        (("agentEvalsSuperset", "agentEvalsSuperset"),)
                        if "agentEvalsSuperset" in rows[0]
                        else ()
                    ),
                    *(
                        (("agentEvalsGraphStrict", "agentEvalsGraphStrict"),)
                        if "agentEvalsGraphStrict" in rows[0]
                        else ()
                    ),
                )
            },
            "inspectDirectCases": inspect_rows,
            "inspectDirectMetrics": {
                name: _accuracy(inspect_rows, field)
                for name, field in (
                    ("candidate", "candidate"),
                    ("exactFinalOutput", "exactFinalOutput"),
                    ("terminalCompletion", "terminalCompletion"),
                )
            },
            "driftAndMigration": {
                "recordedExecutorDrift": _outcome(
                    capsule,
                    local,
                    _context("restricted-local"),
                ),
                "requiredDigestDrift": _outcome(
                    capsule,
                    local,
                    _context("restricted-local", "sha256:" + ("1" * 64)),
                ),
                "missingRequiredContext": _outcome(
                    capsule,
                    local,
                    {"executor": {"kind": "local"}},
                ),
                "deterministicCapsuleBytes": (
                    deterministic_a.read_bytes() == deterministic_b.read_bytes()
                ),
                "deterministicMigrationBytes": (migrated_a.read_bytes() == migrated_b.read_bytes()),
                "migrationObjectBytesPreserved": (
                    {
                        item.path: PackageReader(legacy).read_object(item)
                        for item in PackageReader(legacy).verify("sova.capsule")
                    }
                    == {
                        item.path: PackageReader(migrated_a).read_object(item)
                        for item in PackageReader(migrated_a).verify("sova.capsule")
                    }
                ),
                "subprocessOutcome": subprocess_outcome,
                "subprocessReturnCode": process.returncode,
            },
            "referencePerformance": {
                "evaluations": len(durations),
                "meanNanoseconds": str(sum(durations) // len(durations)),
                "p95Nanoseconds": str(durations[int(len(durations) * 0.95) - 1]),
                "scope": (
                    "Package and trace verification plus all three private decisions "
                    "on one tiny local fixture; reference host only."
                ),
            },
            "limitations": [
                "Ground truth and fixtures were authored by the same team as the mechanism.",
                "The Inspect adapter consumed synthetic JSON, not a third-party "
                "real evaluation log.",
                "Only the current local Python runtime executed the private bridge.",
                "Public hosted cross-platform CI does not establish private "
                "scientific replication.",
                "No human semantic judge, external model, browser, or computer "
                "executor was tested.",
            ],
        }
        if result["integratedMetrics"]["candidate"]["accuracy"] != "1.000000":
            raise AssertionError("integrated candidate did not recover constructed truth")
        if result["inspectDirectMetrics"]["candidate"]["accuracy"] != "1.000000":
            raise AssertionError("Inspect adapter candidate did not recover constructed truth")
        drift = result["driftAndMigration"]
        if not all(
            drift[key]
            for key in (
                "deterministicCapsuleBytes",
                "deterministicMigrationBytes",
                "migrationObjectBytesPreserved",
            )
        ):
            raise AssertionError("determinism or migration preservation gate failed")
        if drift["subprocessOutcome"] != "equivalent":
            raise AssertionError("subprocess evaluation drifted")

        RESULT.parent.mkdir(parents=True, exist_ok=True)
        RESULT.write_bytes(canonical_json_bytes(result) + b"\n")
        print(RESULT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
