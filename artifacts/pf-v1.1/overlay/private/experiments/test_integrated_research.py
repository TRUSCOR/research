"""Private end-to-end tests for the Topics 04–06 research bridge."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

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
from sova.formats.errors import FormatError
from sova.trace import TraceReader, TraceWriter

from private.experiments.prototypes.integrated import (
    EXTENSION_NAME,
    EXTENSION_VERSION,
    evaluate_integrated_research,
    load_research_extension,
    migrate_research_capsule,
    migrate_research_extension,
    render_integrated_report,
    validate_research_extension,
)
from private.experiments.prototypes.inspect_ai_adapter import (
    INSPECT_AI_COMMIT,
    import_inspect_json,
    package_imported_trace,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = b"portable fixture"
DIGEST = sha256_digest(FIXTURE)
SCHEMA = ROOT / "private" / "research" / "specifications" / "research-extension-0.1.schema.json"


def _extension() -> dict[str, Any]:
    return {
        "schemaVersion": EXTENSION_VERSION,
        "semanticReproduction": {
            "predicates": [
                {
                    "id": "oracle-pass",
                    "eventKind": "oracle.completed",
                    "operator": "equals",
                    "path": ["payload", "status"],
                    "expected": "pass",
                },
                {
                    "id": "request-before-result",
                    "eventKind": "tool.requested",
                    "operator": "ordered-before",
                    "otherKind": "tool.completed",
                },
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
                "calibration": {
                    "status": "synthetic-only",
                    "result": "144 same-team labelled cases",
                },
                "uncertainty": {
                    "inconclusiveIsNotFailure": True,
                    "contextDriftRetained": True,
                },
                "limitations": [
                    "No hidden model state is observed.",
                    "Synthetic labels do not establish external validity.",
                ],
            },
        },
        "evidenceFidelity": {
            "claims": [
                {
                    "id": "portable-artifact-read-observed",
                    "requirements": [
                        {
                            "id": "provider-outcome",
                            "eventKind": "tool.completed",
                            "parentKind": "tool.requested",
                            "requireFullContent": True,
                        },
                        {
                            "id": "sova-oracle",
                            "eventKind": "oracle.completed",
                            "requireFullContent": True,
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
        "extensions": {"x-study-fixture": {"retained": True}},
    }


def _legacy_extension() -> dict[str, Any]:
    current = _extension()
    return {
        "schemaVersion": "0.0.1",
        "semantic": current["semanticReproduction"],
        "claims": current["evidenceFidelity"]["claims"],
        "executorContracts": current["executorConformance"]["contracts"],
        "extensions": current["extensions"],
        "legacyVendorHint": {"mustSurvive": "opaque"},
    }


def _scenario() -> dict[str, Any]:
    value = strict_json_loads(
        (ROOT / "examples" / "scenarios" / "portable-artifact-read.json").read_bytes()
    )
    assert isinstance(value, dict)
    return value


def _capsule(
    tmp_path: Path,
    *,
    extension: dict[str, Any] | None = None,
    name: str = "integrated.sova",
) -> Path:
    manifest = capsule_manifest_template(
        title="Private integrated research fixture",
        summary="Synthetic artifact read used only for private method validation.",
        author="Gautam R. Patil",
    )
    manifest["license"] = "NOASSERTION"
    manifest["safety"]["impact"] = "none"
    manifest["requiredFeatures"] = ["scenario.core/0.1"]
    manifest["extensions"][EXTENSION_NAME] = extension or _extension()
    path = tmp_path / name
    build_capsule(
        path,
        manifest,
        scenario=_scenario(),
        attachments={"portable.txt": FIXTURE},
    )
    return path


def _scripted() -> ScriptedExecutor:
    return ScriptedExecutor(
        [
            ScriptedAction(
                action="artifact.read",
                expected_inputs={"digest": DIGEST, "mediaType": "text/plain"},
                status=OutcomeStatus.SUCCEEDED,
                side_effect=SideEffect.READ,
                output={
                    "digest": DIGEST,
                    "size": len(FIXTURE),
                    "mediaType": "text/plain",
                    "text": FIXTURE.decode(),
                },
                evidence=(("artifact", "text/plain", FIXTURE),),
                verification="digest-and-size-checked",
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
            "scopeDigest": "sha256:" + ("7" * 64),
            "decidedBy": "private-synthetic-test",
        },
    )
    assert result.completion == "completed"


def _context(kind: str) -> dict[str, Any]:
    return {"fixture": {"digest": DIGEST}, "executor": {"kind": kind}}


def test_schema_and_manual_validator_agree_on_current_contract() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(_extension())
    assert validate_research_extension(_extension()) == _extension()


def test_adjudication_records_preserve_disagreement_without_overriding_evidence(
    tmp_path: Path,
) -> None:
    extension = _extension()
    extension["semanticReproduction"]["adjudication"] = {
        "status": "unresolved",
        "records": [
            {
                "id": "review-1",
                "adjudicatorId": "blind-reviewer-a",
                "kind": "human",
                "label": "equivalent",
                "blinded": True,
                "independentOfImplementation": True,
                "confidenceBasisPoints": 8000,
                "rationaleDigest": "sha256:" + ("a" * 64),
            },
            {
                "id": "review-2",
                "adjudicatorId": "blind-reviewer-b",
                "kind": "human",
                "label": "divergent",
                "blinded": True,
                "independentOfImplementation": True,
                "confidenceBasisPoints": 6000,
                "rationaleDigest": "sha256:" + ("b" * 64),
            },
        ],
        "limitations": ["Two records do not establish population-level agreement."],
    }
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(extension)
    validate_research_extension(extension)

    capsule = _capsule(tmp_path, extension=extension)
    trace = tmp_path / "adjudicated.sova-trace"
    _run(capsule, trace, _scripted(), tmp_path)
    report = evaluate_integrated_research(
        capsule,
        trace,
        candidate_context=_context("scripted"),
    )
    assert report.semantic.outcome.value == "equivalent"
    assert report.adjudication.status == "unresolved"
    assert report.adjudication.agreement == "tie"
    assert report.adjudication.label_counts == (("divergent", 1), ("equivalent", 1))
    assert report.adjudication.blinded_records == 2
    assert report.adjudication.independent_records == 2
    assert report.adjudication.selected_label is None


def test_adjudication_resolution_and_hostile_references_fail_closed() -> None:
    extension = _extension()
    extension["semanticReproduction"]["adjudication"] = {
        "status": "resolved",
        "records": [
            {
                "id": "rule-1",
                "adjudicatorId": "deterministic-oracle",
                "kind": "rule",
                "label": "equivalent",
                "blinded": False,
                "independentOfImplementation": False,
            }
        ],
        "resolution": {
            "label": "equivalent",
            "method": "founder-reviewed-record",
            "recordIds": ["rule-1"],
        },
    }
    validated = validate_research_extension(extension)
    assert validated["semanticReproduction"]["adjudication"]["resolution"]["label"] == "equivalent"

    hostile = copy.deepcopy(extension)
    hostile["semanticReproduction"]["adjudication"]["resolution"]["recordIds"] = ["missing"]
    with pytest.raises(FormatError) as error:
        validate_research_extension(hostile)
    assert error.value.issue.code == "SOVA-RESEARCH-CONTRACT"


@pytest.mark.parametrize(
    ("name", "executor"),
    [
        ("scripted", _scripted),
        ("restricted-local", RestrictedLocalExecutor),
    ],
)
def test_same_contract_is_integrated_across_two_executors(
    tmp_path: Path,
    name: str,
    executor: Any,
) -> None:
    capsule = _capsule(tmp_path, name=f"{name}.sova")
    trace = tmp_path / f"{name}.sova-trace"
    _run(capsule, trace, executor(), tmp_path)

    report = evaluate_integrated_research(
        capsule,
        trace,
        candidate_context=_context(name),
    )
    assert report.semantic.outcome.value == "equivalent"
    assert [item.support.value for item in report.fidelity] == ["supported"]
    assert [item.status.value for _, item in report.conformance] == ["conformant"]
    assert report.capsule_digest == sha256_digest(capsule.read_bytes())
    assert report.trace_digest == sha256_digest(trace.read_bytes())

    rendered = render_integrated_report(report)
    assert "Private SOVA research evaluation" in rendered
    assert "No capsule content was executed." in rendered
    assert "<script>" not in rendered


def test_context_drift_missing_observer_and_unsafe_gate_are_visible(tmp_path: Path) -> None:
    capsule = _capsule(tmp_path)
    complete = tmp_path / "complete.sova-trace"
    _run(capsule, complete, _scripted(), tmp_path)

    incompatible = evaluate_integrated_research(
        capsule,
        complete,
        candidate_context={
            "fixture": {"digest": "sha256:" + ("0" * 64)},
            "executor": {"kind": "scripted"},
        },
    )
    unsafe = evaluate_integrated_research(
        capsule,
        complete,
        candidate_context=_context("scripted"),
        safe_to_compare=False,
    )
    assert incompatible.semantic.outcome.value == "incompatible"
    assert unsafe.semantic.outcome.value == "unsafe"

    partial = tmp_path / "partial.sova-trace"
    writer = TraceWriter(partial)
    writer.append("run.started", {"fixture": "partial-prefix"})
    writer.append(
        "tool.requested",
        {
            "request": {
                "id": "read-fixture",
                "action": "artifact.read",
                "inputs": {"digest": DIGEST, "mediaType": "text/plain"},
                "timeoutSeconds": "5",
                "retryAttempt": 0,
            }
        },
    )
    writer.finalize(completion="partial")
    report = evaluate_integrated_research(
        capsule,
        partial,
        candidate_context=_context("partial"),
    )
    assert report.semantic.outcome.value == "inconclusive"
    assert [item.support.value for item in report.fidelity] == ["inconclusive"]
    assert [item.status.value for _, item in report.conformance] == ["inconclusive"]

    complete_but_evidence_missing = tmp_path / "complete-missing-evidence.sova-trace"
    writer = TraceWriter(complete_but_evidence_missing)
    writer.append("run.started", {"fixture": "complete-but-missing"})
    writer.append(
        "tool.requested",
        {
            "request": {
                "id": "read-fixture",
                "action": "artifact.read",
                "inputs": {"digest": DIGEST, "mediaType": "text/plain"},
                "timeoutSeconds": "5",
                "retryAttempt": 0,
            }
        },
    )
    writer.append("run.completed", {"completion": "completed"})
    writer.finalize(completion="completed")
    missing = evaluate_integrated_research(
        capsule,
        complete_but_evidence_missing,
        candidate_context=_context("complete-missing"),
    )
    assert missing.semantic.outcome.value == "inconclusive"
    assert "insufficient claim evidence" in missing.semantic.reason


def test_migration_is_deterministic_preserves_unknowns_and_object_bytes(
    tmp_path: Path,
) -> None:
    legacy = _legacy_extension()
    first = migrate_research_extension(legacy)
    second = migrate_research_extension(copy.deepcopy(legacy))
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert first["extensions"]["x-study-fixture"] == {"retained": True}
    assert first["extensions"]["x-legacy-unknown"] == {
        "legacyVendorHint": {"mustSurvive": "opaque"}
    }
    assert first["migrationHistory"][-1] == {
        "from": "0.0.1",
        "to": "0.1.0",
        "method": "sova.private-research-extension/0.0.1-to-0.1.0",
    }

    source = _capsule(tmp_path, extension=legacy, name="legacy.sova")
    left = tmp_path / "migrated-left.sova"
    right = tmp_path / "migrated-right.sova"
    migrate_research_capsule(source, left)
    migrate_research_capsule(source, right)
    assert left.read_bytes() == right.read_bytes()
    assert load_research_extension(left)["schemaVersion"] == EXTENSION_VERSION

    source_reader = PackageReader(source)
    target_reader = PackageReader(left)
    source_objects = {
        item.path: source_reader.read_object(item) for item in source_reader.verify("sova.capsule")
    }
    target_objects = {
        item.path: target_reader.read_object(item) for item in target_reader.verify("sova.capsule")
    }
    assert target_objects == source_objects


def test_migration_and_hostile_contracts_fail_closed(tmp_path: Path) -> None:
    deficient = _legacy_extension()
    deficient.pop("claims")
    with pytest.raises(FormatError) as error:
        migrate_research_extension(deficient)
    assert error.value.issue.code == "SOVA-RESEARCH-MIGRATION-INFORMATION-DEFICIT"

    unsupported = _extension()
    unsupported["schemaVersion"] = "9.0.0"
    with pytest.raises(FormatError) as error:
        migrate_research_extension(unsupported)
    assert error.value.issue.code == "SOVA-RESEARCH-MIGRATION-VERSION"

    hostile = _extension()
    hostile["semanticReproduction"]["predicates"][0]["execute"] = "ignored()"
    with pytest.raises(FormatError) as error:
        validate_research_extension(hostile)
    assert error.value.issue.code == "SOVA-RESEARCH-CONTRACT"

    capsule = _capsule(tmp_path, extension=_legacy_extension(), name="legacy.sova")
    destination = tmp_path / "exists.sova"
    destination.write_bytes(b"do-not-overwrite")
    with pytest.raises(FormatError) as error:
        migrate_research_capsule(capsule, destination)
    assert error.value.issue.code == "SOVA-RESEARCH-MIGRATION-DESTINATION"
    assert destination.read_bytes() == b"do-not-overwrite"


def test_private_cli_evaluates_renders_validates_and_migrates(tmp_path: Path) -> None:
    capsule = _capsule(tmp_path)
    trace = tmp_path / "run.sova-trace"
    _run(capsule, trace, _scripted(), tmp_path)
    context = tmp_path / "context.json"
    context.write_bytes(canonical_json_bytes(_context("scripted")))
    extension_path = tmp_path / "extension.json"
    extension_path.write_bytes(canonical_json_bytes(_extension()))

    command = [sys.executable, "-m", "private.experiments.research_cli"]
    validate = subprocess.run(
        [*command, "validate", str(extension_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    evaluate = subprocess.run(
        [
            *command,
            "evaluate",
            str(capsule),
            str(trace),
            "--context",
            str(context),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    render = subprocess.run(
        [
            *command,
            "render",
            str(capsule),
            str(trace),
            "--context",
            str(context),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert validate.returncode == 0
    assert json.loads(validate.stdout) == {"valid": True}
    assert evaluate.returncode == 0
    assert json.loads(evaluate.stdout)["semantic"]["outcome"] == "equivalent"
    assert render.returncode == 0
    assert "Semantic decision: `equivalent`" in render.stdout

    legacy = _capsule(tmp_path, extension=_legacy_extension(), name="legacy.sova")
    migrated = tmp_path / "cli-migrated.sova"
    migration = subprocess.run(
        [*command, "migrate", str(legacy), str(migrated)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert migration.returncode == 0
    assert migrated.exists()
    assert load_research_extension(migrated)["schemaVersion"] == EXTENSION_VERSION


def _inspect_log() -> dict[str, Any]:
    return {
        "version": 2,
        "status": "success",
        "eval": {
            "eval_id": "eval-synthetic",
            "run_id": "run-synthetic",
            "task": "portable-artifact-read",
            "model": "mock/model",
        },
        "samples": [
            {
                "id": "sample-1",
                "epoch": 1,
                "transcript": {
                    "events": [
                        {
                            "event": "model",
                            "uuid": "inspect-model-1",
                            "span_id": "span-1",
                            "timestamp": "2026-07-31T00:00:00Z",
                            "model": "mock/model",
                            "input": [{"role": "user", "content": "read fixture"}],
                            "output": {"completion": "I will inspect the fixture."},
                            "retries": 0,
                            "working_time": 0.125,
                        },
                        {
                            "event": "tool",
                            "uuid": "inspect-tool-1",
                            "span_id": "span-1",
                            "timestamp": "2026-07-31T00:00:01Z",
                            "id": "call-1",
                            "function": "artifact.read",
                            "arguments": {"digest": DIGEST},
                            "result": {"text": "portable fixture", "digest": DIGEST},
                            "failed": False,
                        },
                        {
                            "event": "score",
                            "uuid": "inspect-score-1",
                            "span_id": "span-1",
                            "timestamp": "2026-07-31T00:00:02Z",
                            "score": {
                                "value": "C",
                                "answer": "portable fixture",
                                "explanation": "fixture matched",
                            },
                            "scorer": "synthetic-exact",
                            "intermediate": False,
                        },
                        {
                            "event": "info",
                            "uuid": "inspect-info-1",
                            "timestamp": "2026-07-31T00:00:03Z",
                            "message": "synthetic terminal marker",
                        },
                    ],
                    "content": {},
                },
            }
        ],
    }


def test_pinned_inspect_json_adapter_is_verified_and_loss_explicit(
    tmp_path: Path,
) -> None:
    source = tmp_path / "inspect.json"
    source.write_text(
        json.dumps(_inspect_log(), separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    trace = tmp_path / "inspect.sova-trace"
    report = import_inspect_json(source, trace, include_content=True)

    assert report.source_commit == INSPECT_AI_COMMIT
    assert report.samples == 1
    assert report.source_events == 4
    assert report.source_layouts == ("transcript-events",)
    assert not report.lossless
    reader = TraceReader(trace)
    verification = reader.verify()
    assert verification.event_count == report.emitted_events == 10
    assert verification.completion == "completed"
    assert len(list(reader.query(kind_prefix="prompt."))) == 1
    assert len(list(reader.query(kind_prefix="model."))) == 1
    assert len(list(reader.query(kind_prefix="tool."))) == 2
    score = next(reader.query(kind_prefix="judge."))
    assert score["payload"]["score"]["value"] == "C"
    model = next(reader.query(kind_prefix="model."))
    assert model["payload"]["output"]["completion"] == "I will inspect the fixture."

    capsule = tmp_path / "inspect-import.sova"
    package_imported_trace(
        source,
        trace,
        capsule,
        report,
        include_source_log=False,
    )
    descriptors = PackageReader(capsule).verify("sova.capsule")
    assert [item.role for item in descriptors] == ["trace"]
    manifest = PackageReader(capsule).manifest("sova.capsule")
    imported = manifest["extensions"]["x-inspect-ai-import"]
    assert imported["source_commit"] == INSPECT_AI_COMMIT
    assert imported["unavailable"]


def test_inspect_import_privacy_default_and_version_refusal(tmp_path: Path) -> None:
    source = tmp_path / "inspect.json"
    source.write_text(
        json.dumps(_inspect_log(), separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    trace = tmp_path / "metadata.sova-trace"
    import_inspect_json(source, trace)
    reader = TraceReader(trace)
    reader.verify()
    raw = trace.read_bytes()
    assert b"I will inspect the fixture." not in raw
    assert b"portable fixture" not in raw

    wrong = _inspect_log()
    wrong["version"] = 4
    source.write_text(
        json.dumps(wrong, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    with pytest.raises(FormatError) as error:
        import_inspect_json(source, tmp_path / "wrong.sova-trace")
    assert error.value.issue.code == "SOVA-INSPECT-VERSION"

    expanded_v3 = _inspect_log()
    expanded_v3["version"] = 3
    expanded_v3["samples"][0]["events_data"] = None
    source.write_text(
        json.dumps(expanded_v3, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    v3_trace = tmp_path / "expanded-v3.sova-trace"
    v3_report = import_inspect_json(source, v3_trace)
    assert v3_report.source_log_version == 3
    v3_model = next(TraceReader(v3_trace).query(kind_prefix="model."))
    assert v3_model["links"][0]["version"].startswith("log-3@")

    condensed_v3 = _inspect_log()
    condensed_v3["version"] = 3
    condensed_v3["samples"][0]["events_data"] = {"messages": []}
    source.write_text(
        json.dumps(condensed_v3, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    with pytest.raises(FormatError) as condensed_error:
        import_inspect_json(source, tmp_path / "condensed-v3.sova-trace")
    assert condensed_error.value.issue.code == "SOVA-INSPECT-CONDENSED-EVENTS"

    flat = _inspect_log()
    sample = flat["samples"][0]
    sample["events"] = sample.pop("transcript")["events"]
    source.write_text(
        json.dumps(flat, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    flat_trace = tmp_path / "flat.sova-trace"
    flat_report = import_inspect_json(source, flat_trace)
    assert flat_report.source_layouts == ("legacy-flat-events",)
    assert flat_report.source_events == 4
    TraceReader(flat_trace).verify()

    no_events = _inspect_log()
    no_events["samples"][0].pop("transcript")
    source.write_text(
        json.dumps(no_events, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    empty_trace = tmp_path / "empty-events.sova-trace"
    empty_report = import_inspect_json(source, empty_trace)
    assert empty_report.source_layouts == ("no-event-stream",)
    assert empty_report.source_events == 0
    TraceReader(empty_trace).verify()
