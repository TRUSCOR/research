"""Externally maintained deterministic implementation validation.

This same-team harness invokes pinned external libraries. It provides
cross-implementation evidence, not independent human review.
"""

from __future__ import annotations

import base64
import copy
import importlib.metadata
import json
import platform
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from harness_evals import EvalCase, ToolCall, evaluate
from harness_evals.metrics.agent.tool_argument_match import ToolArgumentMatchMetric
from harness_evals.metrics.agent.tool_correctness import ToolCorrectnessMetric
from harness_evals.metrics.deterministic.exact_match import ExactMatchMetric
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.trace.v1.trace_pb2 import Span
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from openinference.instrumentation import OITracer, TraceConfig
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from securesystemslib.dsse import Envelope
from securesystemslib.exceptions import VerificationError
from securesystemslib.signer import SSlibKey

from private.experiments.run_integrated_baseline_study import (
    DIGEST,
    _capsule,
    _context,
    _executor,
    _outcome,
    _run,
)
from sova.formats import FormatError, canonical_json_bytes, strict_json_loads
from sova.trace import TraceReader, TraceWriter, generate_ed25519_keypair
from sova.trace.otel import export_event, import_openinference_span, import_span

ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "private"
    / "experiments"
    / "results"
    / "external-implementation-validation-2026-08-01.json"
)

PACKAGE_PINS = {
    "harness-evals": {
        "version": "0.15.0",
        "commit": "7828ffa93c597c9e66a866a122c62a21e94376e0",
        "license": "Apache-2.0",
    },
    "securesystemslib": {
        "version": "1.4.0",
        "commit": "8416c50ec6814762b32db08ab37fd2e495e771a4",
        "license": "MIT",
    },
    "rfc8785": {
        "version": "0.1.4",
        "commit": "65ecc7d2b065d79a99e7a6a2f9aaa9d689db1c53",
        "license": "Apache-2.0",
    },
    "opentelemetry-proto": {
        "version": "1.44.0",
        "commit": "d2d893fefdbabae63762e328688ea1c97c04cb24",
        "license": "Apache-2.0",
    },
    "openinference-semantic-conventions": {
        "version": "0.1.30",
        "commit": "789d41974c08a9a13147977f28ef4142a07e2106",
        "license": "Apache-2.0",
        "sdistSha256": "81fece76e09c83789e35c393b8b30523481eeabf1008745b955631a53e3221d9",
    },
    "openinference-instrumentation": {
        "version": "0.1.56",
        "commit": "a374cbdcec6bf712a005549d15293c57c27cd109",
        "license": "Apache-2.0",
        "sdistSha256": "c43bea7f1f4460fe13c3c88aff092500cc3397aaffea37188d72246489dcbc9f",
    },
    "opentelemetry-sdk": {
        "version": "1.44.0",
        "commit": "53a5a40c9604583c501bcf13970a635f00e62df4",
        "license": "Apache-2.0",
    },
}


def _actual_versions() -> dict[str, str]:
    return {name: importlib.metadata.version(name) for name in PACKAGE_PINS}


def _terminal_outcome(event: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any] | None:
    terminal = next(
        (
            candidate
            for candidate in events
            if candidate["kind"] in {"tool.completed", "tool.failed"}
            and event["id"] in candidate.get("parents", [])
        ),
        None,
    )
    if terminal is None:
        return None
    payload = terminal.get("payload", {})
    outcome = payload.get("outcome", {}) if isinstance(payload, dict) else {}
    return outcome if isinstance(outcome, dict) else {}


def _interaction_records(trace: Path) -> list[dict[str, Any]]:
    events = TraceReader(trace).events()
    records: list[dict[str, Any]] = []
    for event in events:
        if event["kind"] != "tool.requested":
            continue
        payload = event.get("payload", {})
        request = payload.get("request", {}) if isinstance(payload, dict) else {}
        outcome = _terminal_outcome(event, events)
        records.append(
            {
                "action": request.get("action"),
                "inputs": request.get("inputs", {}),
                "status": outcome.get("status") if outcome is not None else None,
                "output": outcome.get("output") if outcome is not None else None,
            }
        )
    return records


def _tool_calls(trace: Path) -> list[ToolCall]:
    events = TraceReader(trace).events()
    calls: list[ToolCall] = []
    for event in events:
        if event["kind"] != "tool.requested":
            continue
        payload = event.get("payload", {})
        request = payload.get("request", {}) if isinstance(payload, dict) else {}
        outcome = _terminal_outcome(event, events)
        output = outcome.get("output") if outcome is not None else None
        calls.append(
            ToolCall(
                name=str(request.get("action", "unknown")),
                input=request.get("inputs", {}),
                output=output if isinstance(output, (str, dict)) else None,
            )
        )
    return calls


def _harness_prediction(reference: Path, candidate: Path) -> dict[str, Any]:
    expected_calls = _tool_calls(reference)
    actual_calls = _tool_calls(candidate)
    case = EvalCase(
        input={"kind": "sova.trace-comparison"},
        output=_interaction_records(candidate),
        expected=_interaction_records(reference),
        tool_calls=actual_calls,
        expected_tools=[call.name for call in expected_calls],
        expected_tool_calls=expected_calls,
    )
    scores = evaluate(
        case,
        [
            ExactMatchMetric(threshold=1.0),
            ToolCorrectnessMetric(mode="exact", threshold=1.0),
            ToolArgumentMatchMetric(pair="exact", arg_match="exact", threshold=1.0),
        ],
    )
    return {
        score.name: {
            "value": format(score.value, ".6f"),
            "threshold": format(score.threshold, ".6f"),
            "passed": score.passed,
            "prediction": "equivalent" if score.passed else "divergent",
            "reason": score.reason,
            "metadata": score.metadata,
        }
        for score in scores
    }


def _metric_summary(rows: list[dict[str, Any]], metric: str) -> dict[str, Any]:
    predictions = [row["harness"][metric]["prediction"] for row in rows]
    correct = sum(prediction == row["truth"] for prediction, row in zip(predictions, rows))
    false_equivalence = sum(
        prediction == "equivalent" and row["truth"] != "equivalent"
        for prediction, row in zip(predictions, rows)
    )
    false_divergence = sum(
        prediction == "divergent" and row["truth"] == "equivalent"
        for prediction, row in zip(predictions, rows)
    )
    return {
        "correct": correct,
        "total": len(rows),
        "accuracy": format(correct / len(rows), ".6f"),
        "falseEquivalence": false_equivalence,
        "falseDivergence": false_divergence,
        "unsupportedTruthClasses": sorted(
            {
                row["truth"]
                for row in rows
                if row["truth"] not in {"equivalent", "divergent"}
            }
        ),
    }


def _harness_study(work: Path) -> dict[str, Any]:
    capsule = _capsule(work, "external-baseline.sova")
    reference = work / "reference.sova-trace"
    repeated = work / "repeat.sova-trace"
    local = work / "local.sova-trace"
    false_success = work / "false-success.sova-trace"
    _run(capsule, reference, _executor(), work)
    _run(capsule, repeated, _executor(), work)

    from sova.executors import RestrictedLocalExecutor

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
        ("repeat-equivalent", "equivalent", repeated, _context("scripted"), True),
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
    for identifier, truth, trace, context, safe in cases:
        rows.append(
            {
                "id": identifier,
                "truth": truth,
                "candidate": _outcome(capsule, trace, context, safe=safe),
                "harness": _harness_prediction(reference, trace),
            }
        )

    repeated_rows = [
        {
            "id": row["id"],
            "harness": _harness_prediction(
                reference,
                next(trace for identifier, _truth, trace, _context_value, _safe in cases if identifier == row["id"]),
            ),
        }
        for row in rows
    ]
    return {
        "rows": rows,
        "candidateAccuracy": {
            "correct": sum(row["candidate"] == row["truth"] for row in rows),
            "total": len(rows),
        },
        "baselines": {
            metric: _metric_summary(rows, metric)
            for metric in ("exact_match", "tool_correctness", "tool_argument_match")
        },
        "deterministicRerunEqual": all(
            first["harness"] == second["harness"]
            for first, second in zip(rows, repeated_rows)
        ),
        "claimBoundary": (
            "External package implementation over a same-team seven-case corpus; "
            "not independent labels or a state-of-the-art claim."
        ),
    }


def _external_key(public_raw: bytes, key_id: str) -> SSlibKey:
    return SSlibKey.from_crypto(
        Ed25519PublicKey.from_public_bytes(public_raw),
        keyid=key_id,
        scheme="ed25519",
    )


def _expect_external_rejection(envelope: dict[str, Any], keys: list[SSlibKey]) -> bool:
    try:
        Envelope.from_dict(copy.deepcopy(envelope)).verify(keys, 1)
    except (VerificationError, ValueError):
        return True
    return False


def _mutated_b64(value: str) -> str:
    decoded = bytearray(base64.b64decode(value, validate=True))
    decoded[0] ^= 1
    return base64.b64encode(decoded).decode("ascii")


def _canonical_cases() -> list[Any]:
    base: list[Any] = [
        None,
        True,
        False,
        0,
        1,
        -1,
        (1 << 53) - 1,
        -((1 << 53) - 1),
        "",
        "ascii",
        "é",
        "😀",
        [],
        {},
        {"b": 1, "a": 2},
        {"😀": "astral", "\u20ac": "bmp", "\r": "control"},
        [1, "two", False, None],
    ]
    for index in range(48):
        base.append(
            {
                f"k{(index * 7) % 13}": [index, f"value-{index}", index % 2 == 0],
                "nested": {"z": index - 24, "a": None},
            }
        )
    return base


def _integrity_study(work: Path) -> dict[str, Any]:
    keypair = generate_ed25519_keypair()
    trace = work / "external-dsse.sova-trace"
    writer = TraceWriter(
        trace,
        signing_key=keypair,
        verification_material={"timestamp": {"kind": "synthetic-unverified"}},
    )
    writer.append("run.started", {"case": "external-dsse"})
    writer.append("run.completed", {"status": "completed"})
    writer.finalize()

    with zipfile.ZipFile(trace) as archive:
        manifest = strict_json_loads(archive.read("manifest.json"))
    assert isinstance(manifest, dict)
    signature_material = manifest["integrity"]["signature"]
    envelope = signature_material["envelope"]
    public_raw = base64.b64decode(signature_material["publicKey"]["raw"], validate=True)
    external_key = _external_key(public_raw, keypair.key_id)
    accepted = Envelope.from_dict(copy.deepcopy(envelope)).verify([external_key], 1)

    payload_mutant = copy.deepcopy(envelope)
    payload_mutant["payload"] = _mutated_b64(payload_mutant["payload"])
    signature_mutant = copy.deepcopy(envelope)
    signature_mutant["signatures"][0]["sig"] = _mutated_b64(
        signature_mutant["signatures"][0]["sig"]
    )
    wrong_pair = generate_ed25519_keypair()
    wrong_key = _external_key(wrong_pair.public_key, keypair.key_id)
    key_id_mismatch = _external_key(public_raw, "sha256:" + ("0" * 64))
    payload = base64.b64decode(envelope["payload"], validate=True)
    payload_object = strict_json_loads(payload)
    noncanonical_payload = json.dumps(payload_object, indent=2, ensure_ascii=False).encode()
    noncanonical_envelope = copy.deepcopy(envelope)
    noncanonical_envelope["payload"] = base64.b64encode(noncanonical_payload).decode("ascii")

    canonical_cases = _canonical_cases()
    canonical_equal = [
        canonical_json_bytes(value) == rfc8785.dumps(value) for value in canonical_cases
    ]
    sova_float_rejected = False
    try:
        canonical_json_bytes({"binaryFloat": 1.5})
    except FormatError:
        sova_float_rejected = True
    external_float_bytes = rfc8785.dumps({"binaryFloat": 1.5})

    return {
        "dsse": {
            "externalVerifierAccepted": sorted(accepted) == [keypair.key_id],
            "payloadMutationRejected": _expect_external_rejection(
                payload_mutant, [external_key]
            ),
            "signatureMutationRejected": _expect_external_rejection(
                signature_mutant, [external_key]
            ),
            "wrongKeyRejected": _expect_external_rejection(envelope, [wrong_key]),
            "keyIdMismatchRejected": _expect_external_rejection(
                envelope, [key_id_mismatch]
            ),
            "semanticallyEqualNoncanonicalPayloadRejected": _expect_external_rejection(
                noncanonical_envelope, [external_key]
            ),
            "trustBoundary": (
                "Cross-library signature compatibility only; no key ownership, "
                "freshness, transparency, truth, or signer-honesty claim."
            ),
        },
        "canonicalization": {
            "sharedDomainCases": len(canonical_cases),
            "byteEqualCases": sum(canonical_equal),
            "allSharedDomainBytesEqual": all(canonical_equal),
            "sovaBinaryFloatRejected": sova_float_rejected,
            "externalBinaryFloatCanonical": external_float_bytes.decode("utf-8"),
            "boundary": (
                "SOVA deliberately uses an integer/decimal-string subset of RFC 8785 "
                "and does not claim full JCS number serialization."
            ),
        },
    }


def _to_any(value: Any) -> AnyValue:
    result = AnyValue()
    if value is None:
        result.string_value = "null"
    elif isinstance(value, bool):
        result.bool_value = value
    elif isinstance(value, int):
        result.int_value = value
    elif isinstance(value, float):
        result.double_value = value
    elif isinstance(value, bytes):
        result.bytes_value = value
    elif isinstance(value, str):
        result.string_value = value
    elif isinstance(value, list):
        result.array_value.values.extend(_to_any(item) for item in value)
    elif isinstance(value, dict):
        result.kvlist_value.values.extend(
            KeyValue(key=str(key), value=_to_any(child))
            for key, child in sorted(value.items())
        )
    else:
        raise TypeError(f"unsupported OTLP value: {type(value)!r}")
    return result


def _from_any(value: AnyValue) -> Any:
    selected = value.WhichOneof("value")
    if selected == "string_value":
        return value.string_value
    if selected == "bool_value":
        return value.bool_value
    if selected == "int_value":
        return value.int_value
    if selected == "double_value":
        return value.double_value
    if selected == "bytes_value":
        return bytes(value.bytes_value)
    if selected == "array_value":
        return [_from_any(item) for item in value.array_value.values]
    if selected == "kvlist_value":
        return {item.key: _from_any(item.value) for item in value.kvlist_value.values}
    return None


def _otlp_span(projection: dict[str, Any]) -> Span:
    start = datetime.fromisoformat(str(projection["start_time"]).replace("Z", "+00:00"))
    span = Span(
        trace_id=bytes.fromhex(str(projection["trace_id"])),
        span_id=bytes.fromhex(str(projection["span_id"])),
        name=str(projection["name"]),
        start_time_unix_nano=int(start.timestamp() * 1_000_000_000),
    )
    if projection["parent_span_id"] is not None:
        span.parent_span_id = bytes.fromhex(str(projection["parent_span_id"]))
    span.attributes.extend(
        KeyValue(key=key, value=_to_any(value))
        for key, value in sorted(projection["attributes"].items())
    )
    for link in projection["links"]:
        span.links.add(
            trace_id=bytes.fromhex(str(link["trace_id"])),
            span_id=bytes.fromhex(str(link["span_id"])),
            attributes=[
                KeyValue(key=key, value=_to_any(value))
                for key, value in sorted(link["attributes"].items())
            ],
        )
    return span


def _otlp_projection(span: Span) -> dict[str, Any]:
    return {
        "trace_id": bytes(span.trace_id).hex(),
        "span_id": bytes(span.span_id).hex(),
        "parent_span_id": bytes(span.parent_span_id).hex() or None,
        "name": span.name,
        "start_time_unix_nano": span.start_time_unix_nano,
        "attributes": {item.key: _from_any(item.value) for item in span.attributes},
        "links": [
            {
                "trace_id": bytes(link.trace_id).hex(),
                "span_id": bytes(link.span_id).hex(),
                "attributes": {
                    item.key: _from_any(item.value) for item in link.attributes
                },
            }
            for link in span.links
        ],
        "events": [
            {
                "name": event.name,
                "time_unix_nano": event.time_unix_nano,
                "attributes": {
                    item.key: _from_any(item.value) for item in event.attributes
                },
            }
            for event in span.events
        ],
    }


def _otlp_study(work: Path) -> dict[str, Any]:
    trace = work / "otlp.sova-trace"
    writer = TraceWriter(trace)
    parent_a = writer.append("phase.started", {"name": "external-otlp-a"})
    parent_b = writer.append("phase.started", {"name": "external-otlp-b"})
    if parent_a is None or parent_b is None:
        raise AssertionError("forensic capture unexpectedly dropped parent events")
    writer.append(
        "tool.requested",
        {
            "request": {
                "id": "request-1",
                "action": "artifact.read",
                "inputs": {"digest": DIGEST},
            }
        },
        parents=[parent_a, parent_b],
    )
    writer.finalize()
    event = next(
        item for item in TraceReader(trace).events() if item["kind"] == "tool.requested"
    )
    projection, fidelity = export_event(event)
    span = _otlp_span(projection)
    wire = span.SerializeToString(deterministic=True)
    parsed = Span()
    parsed.ParseFromString(wire)
    roundtrip = _otlp_projection(parsed)
    start = datetime.fromisoformat(str(projection["start_time"]).replace("Z", "+00:00"))
    expected_start = int(start.timestamp() * 1_000_000_000)

    native = Span(
        trace_id=b"\x01" * 16,
        span_id=b"\x02" * 8,
        name="gen_ai.chat",
        start_time_unix_nano=1_785_440_000_000_000_000,
    )
    native.attributes.extend(
        [
            KeyValue(key="service.name", value=_to_any("external-fixture")),
            KeyValue(key="gen_ai.request.model", value=_to_any("recorded/model")),
            KeyValue(key="external.unknown", value=_to_any({"preserve": True})),
        ]
    )
    native_wire = native.SerializeToString(deterministic=True)
    native_parsed = Span()
    native_parsed.ParseFromString(native_wire)
    native_projection = _otlp_projection(native_parsed)
    imported, import_fidelity = import_span(
        {
            "name": native_projection["name"],
            "attributes": native_projection["attributes"],
            "events": native_projection["events"],
            "status": None,
        }
    )

    return {
        "serializedBytes": len(wire),
        "traceIdPreserved": roundtrip["trace_id"] == projection["trace_id"],
        "spanIdPreserved": roundtrip["span_id"] == projection["span_id"],
        "parentPreserved": roundtrip["parent_span_id"] == projection["parent_span_id"],
        "namePreserved": roundtrip["name"] == projection["name"],
        "startTimePreserved": roundtrip["start_time_unix_nano"] == expected_start,
        "attributesPreserved": roundtrip["attributes"] == projection["attributes"],
        "linksPreserved": roundtrip["links"] == projection["links"],
        "eventCountPreserved": len(roundtrip["events"]) == 0,
        "exportLossless": fidelity.lossless,
        "exportOmitted": list(fidelity.omitted),
        "externalUnknownAttributePreserved": (
            imported["payload"]["otel"]["attributes"]["external.unknown"]
            == {"preserve": True}
        ),
        "importLossless": import_fidelity.lossless,
        "importUnavailable": list(import_fidelity.unavailable),
        "claimBoundary": (
            "Official protobuf transport compatibility; semantic mapping remains "
            "explicitly lossy and no collector/backend was used."
        ),
    }


def _openinference_study() -> dict[str, Any]:
    expected_constants = {
        "spanKind": "openinference.span.kind",
        "input": "input.value",
        "output": "output.value",
        "model": "llm.model_name",
        "tool": "tool.name",
        "retrieval": "retrieval.documents",
    }
    observed_constants = {
        "spanKind": SpanAttributes.OPENINFERENCE_SPAN_KIND,
        "input": SpanAttributes.INPUT_VALUE,
        "output": SpanAttributes.OUTPUT_VALUE,
        "model": SpanAttributes.LLM_MODEL_NAME,
        "tool": SpanAttributes.TOOL_NAME,
        "retrieval": SpanAttributes.RETRIEVAL_DOCUMENTS,
    }
    expected_kinds = {
        "TOOL",
        "CHAIN",
        "LLM",
        "RETRIEVER",
        "EMBEDDING",
        "AGENT",
        "RERANKER",
        "UNKNOWN",
        "GUARDRAIL",
        "EVALUATOR",
        "PROMPT",
    }
    observed_kinds = {item.value for item in OpenInferenceSpanKindValues}
    sensitive_fixture = "official-openinference-sensitive-fixture"
    exporter = InMemorySpanExporter()
    provider = TracerProvider(
        resource=Resource.create({"service.name": "official-openinference-producer"})
    )
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = OITracer(provider.get_tracer("sova.external-validation"), TraceConfig())
    with tracer.start_as_current_span(
        "ChatCompletion",
        attributes={
            SpanAttributes.LLM_MODEL_NAME: "official/fixture-model",
            SpanAttributes.INPUT_VALUE: sensitive_fixture,
            SpanAttributes.OUTPUT_VALUE: "official-fixture-output",
            SpanAttributes.TAG_TAGS: ["synthetic", "official-tracer"],
        },
        openinference_span_kind=OpenInferenceSpanKindValues.LLM,
    ):
        pass
    if not provider.force_flush(timeout_millis=5_000):
        raise RuntimeError("official OpenInference tracer did not flush")
    finished = exporter.get_finished_spans()
    if len(finished) != 1:
        raise RuntimeError(f"official OpenInference tracer emitted {len(finished)} spans")
    emitted = finished[0]
    emitted_context = emitted.get_span_context()
    external_span = {
        "name": emitted.name,
        "trace_id": f"{emitted_context.trace_id:032x}",
        "span_id": f"{emitted_context.span_id:016x}",
        "start_time": emitted.start_time,
        "end_time": emitted.end_time,
        "status": emitted.status.status_code.name,
        "attributes": dict(emitted.attributes or {}),
        "resource": {"attributes": dict(emitted.resource.attributes)},
        "events": [
            {"name": event.name, "attributes": dict(event.attributes)}
            for event in emitted.events
        ],
    }
    minimized, minimized_fidelity = import_openinference_span(external_span)
    preserved, preserved_fidelity = import_openinference_span(
        external_span,
        content_policy="preserve",
    )
    minimized_text = json.dumps(minimized, sort_keys=True)
    preserved_attributes = preserved["payload"]["openinference"]["attributes"]
    return {
        "officialConstantsExact": observed_constants == expected_constants,
        "officialSpanKindsExact": observed_kinds == expected_kinds,
        "officialTracerSpanCount": len(finished),
        "officialTracerSpanKind": external_span["attributes"].get(
            SpanAttributes.OPENINFERENCE_SPAN_KIND
        ),
        "officialTracerService": external_span["resource"]["attributes"].get("service.name"),
        "officialTracerIdentifiersValid": (
            len(external_span["trace_id"]) == 32
            and len(external_span["span_id"]) == 16
            and int(external_span["trace_id"], 16) != 0
            and int(external_span["span_id"], 16) != 0
        ),
        "observedConstants": observed_constants,
        "observedSpanKinds": sorted(observed_kinds),
        "defaultContentAbsent": sensitive_fixture not in minimized_text,
        "defaultOmittedKeys": list(minimized_fidelity.omitted),
        "explicitContentPreserved": (
            preserved_attributes[SpanAttributes.INPUT_VALUE] == sensitive_fixture
        ),
        "preservedSensitiveKeys": list(preserved_fidelity.sensitive),
        "mappedEventKind": minimized["kind"],
        "claimBoundary": (
            "Official 0.1.56 OITracer and OpenTelemetry SDK emitted the span using "
            "official 0.1.30 conventions; scenario, harness, and interpretation remain "
            "same-team, not an independently operated producer or reviewer."
        ),
    }


def main() -> int:
    actual = _actual_versions()
    expected = {name: item["version"] for name, item in PACKAGE_PINS.items()}
    if actual != expected:
        raise RuntimeError(f"external package pin mismatch: {actual!r} != {expected!r}")

    with tempfile.TemporaryDirectory(prefix="sova-external-implementations-") as raw:
        work = Path(raw)
        result = {
            "artifactType": "sova.private-external-implementation-validation",
            "version": "0.2.0",
            "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "owner": "Gautam R. Patil",
            "organization": "TRUSCOR Private Limited",
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
            },
            "packages": {
                name: {**metadata, "observedVersion": actual[name]}
                for name, metadata in PACKAGE_PINS.items()
            },
            "harnessEvals": _harness_study(work),
            "externalIntegrity": _integrity_study(work),
            "officialOtlp": _otlp_study(work),
            "officialOpenInference": _openinference_study(),
            "overallBoundary": (
                "Independently maintained code and official wire formats exercised by "
                "a same-team harness; not independent human review, publication "
                "clearance, or patentability evidence."
            ),
        }
    RESULT.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(RESULT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
