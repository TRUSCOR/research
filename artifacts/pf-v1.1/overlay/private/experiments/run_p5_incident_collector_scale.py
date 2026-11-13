"""Private P5 incident-format, collector/backend, and scale study.

All fixtures are synthetic and authorized.  The study exercises independently
maintained libraries and an official Collector binary in a same-team harness;
it is not an independent privacy, security, or deployment review.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.metadata
import json
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import tracemalloc
import urllib.request
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter_ns
from typing import Any, Iterable

from sova.formats import PackageReader, sha256_digest
from sova.trace import TraceReader, TraceWriter, generate_ed25519_keypair
from sova.trace.otel import export_event

ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT / "private" / "experiments" / "results" / "p5-incident-collector-scale-2026-08-01.json"
)
PYTHON_VERIFIER = ROOT / "scripts" / "sova_independent_verify.py"
NODE_VERIFIER = ROOT / "scripts" / "sova_independent_verify.mjs"
STIX_VERSION = "3.0.2"
STIX_COMMIT = "679bfe0befae5c39143cedcdc3cacf97ac31c890"
STIX_WHEEL_SHA256 = "f4814d29ebc332c92694fc8ddc96a4a5bfe2eac08494c0dec219719e7e654eb3"
COLLECTOR_VERSION = "0.157.0"
COLLECTOR_RELEASE = "v0.157.0"
OTEL_PROTO_VERSION = "1.44.0"
EXTERNAL_EVENT_SCALE = 483 + 396
SCALE_COUNTS = (1_000, 10_000, 50_000)


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _fixed_time(offset_seconds: int = 0) -> datetime:
    return datetime(2026, 8, 1, tzinfo=UTC) + timedelta(seconds=offset_seconds)


def _safe_trace(destination: Path) -> tuple[Path, str]:
    key = generate_ed25519_keypair()
    writer = TraceWriter(
        destination,
        capture_profile="forensic",
        signing_key=key,
        authorization={
            "decision": "not-required",
            "scopeDigest": None,
            "decidedBy": "synthetic-offline-study",
        },
        reviewed_for_export=True,
    )
    started = writer.append(
        "run.started",
        {"case": "synthetic-p5-incident", "content": "metadata-only"},
        wall_time="2026-08-01T00:00:00Z",
    )
    request = writer.append(
        "model.request",
        {"model": "scripted", "requestDigest": "sha256:" + "1" * 64},
        parents=[started] if started else [],
        wall_time="2026-08-01T00:00:01Z",
    )
    response = writer.append(
        "model.response",
        {"model": "scripted", "responseDigest": "sha256:" + "2" * 64},
        parents=[request] if request else [],
        wall_time="2026-08-01T00:00:02Z",
    )
    tool = writer.append(
        "tool.requested",
        {
            "request": {
                "id": "synthetic-read",
                "action": "artifact.read",
                "inputs": {"digest": "sha256:" + "3" * 64},
            }
        },
        parents=[response] if response else [],
        wall_time="2026-08-01T00:00:03Z",
    )
    completed = writer.append(
        "tool.completed",
        {
            "outcome": {
                "request_id": "synthetic-read",
                "status": "succeeded",
                "output": {"digest": "sha256:" + "3" * 64},
            }
        },
        parents=[tool] if tool else [],
        wall_time="2026-08-01T00:00:04Z",
    )
    oracle = writer.append(
        "oracle.completed",
        {"status": "pass", "basis": "synthetic-observable"},
        parents=[completed] if completed else [],
        wall_time="2026-08-01T00:00:05Z",
    )
    writer.append(
        "finding.created",
        {"severity": "informational", "status": "synthetic"},
        parents=[oracle] if oracle else [],
        wall_time="2026-08-01T00:00:06Z",
    )
    writer.append(
        "run.completed",
        {"status": "completed"},
        parents=[oracle] if oracle else [],
        wall_time="2026-08-01T00:00:07Z",
    )
    writer.finalize(completion="completed")
    report = TraceReader(destination).verify(required_key_id=key.key_id)
    if not report.signature_valid or report.trust_policy != "required-key":
        raise RuntimeError("synthetic source trace did not pass required-key verification")
    return destination, key.key_id


def _incident_study(work: Path, source_trace: Path) -> dict[str, Any]:
    import stix2
    from stix2.v21 import (
        Artifact,
        Bundle,
        Identity,
        Incident,
        Note,
        ObservedData,
        Relationship,
    )

    if importlib.metadata.version("stix2") != STIX_VERSION:
        raise RuntimeError("stix2 dependency drifted from the pinned version")
    reader = TraceReader(source_trace)
    verification = reader.verify()
    trace_manifest = reader.manifest()
    trace_digest = sha256_digest(source_trace.read_bytes())
    chain_root = str(trace_manifest["chainRoot"])

    identity = Identity(
        id="identity--2f36da25-2b0c-4b61-8571-4ab509cfd472",
        name="SOVA synthetic study producer",
        identity_class="organization",
        created=_fixed_time(),
        modified=_fixed_time(),
    )
    incident = Incident(
        id="incident--56fb6918-7fc2-4fec-b153-a4bde3a96d98",
        name="Synthetic observable AI behavior case",
        description="Authorized metadata-only interoperability fixture.",
        created_by_ref=identity.id,
        created=_fixed_time(1),
        modified=_fixed_time(1),
        external_references=[
            {
                "source_name": "sova-trace",
                "external_id": trace_digest,
                "description": "Digest of the source evidence package.",
            }
        ],
        allow_custom=True,
        x_sova_chain_root=chain_root,
        x_sova_capture_profile=str(trace_manifest["captureProfile"]),
        x_sova_event_count=verification.event_count,
    )
    artifact = Artifact(
        id="artifact--00d15166-3b18-4a52-9cda-4845db33524b",
        mime_type="application/vnd.sova.synthetic-observation",
        payload_bin=base64.b64encode(b"synthetic-observable-only").decode("ascii"),
        hashes={"SHA-256": hashlib.sha256(b"synthetic-observable-only").hexdigest()},
    )
    observed = ObservedData(
        id="observed-data--ea28bb20-6371-46c8-9ddf-e58c59578440",
        created_by_ref=identity.id,
        created=_fixed_time(2),
        modified=_fixed_time(2),
        first_observed=_fixed_time(2),
        last_observed=_fixed_time(2),
        number_observed=1,
        object_refs=[artifact.id],
    )
    relationship = Relationship(
        id="relationship--47b8f77f-555f-46b7-8876-72fdda63bfa8",
        created_by_ref=identity.id,
        created=_fixed_time(3),
        modified=_fixed_time(3),
        relationship_type="related-to",
        source_ref=incident.id,
        target_ref=observed.id,
    )
    note = Note(
        id="note--06e2e871-cf86-4b51-b56d-f69db697635d",
        created_by_ref=identity.id,
        created=_fixed_time(4),
        modified=_fixed_time(4),
        content=(
            "This STIX view is privacy-minimized and does not replace the source "
            "trace, authorization record, causal ordering, or replay recipe."
        ),
        object_refs=[incident.id, observed.id],
    )
    bundle = Bundle(
        identity,
        incident,
        artifact,
        observed,
        relationship,
        note,
        allow_custom=True,
    )
    serialized = bundle.serialize(pretty=False).encode("utf-8")
    parsed = stix2.parse(serialized.decode("utf-8"), allow_custom=True, version="2.1")
    object_types = Counter(str(item.type) for item in parsed.objects)
    if object_types["incident"] != 1 or object_types["artifact"] != 1:
        raise RuntimeError("official STIX parser did not preserve the incident bundle")
    parsed_incident = next(item for item in parsed.objects if item.type == "incident")
    if str(parsed_incident.x_sova_chain_root) != chain_root:
        raise RuntimeError("STIX custom integrity reference did not round trip")

    imported_trace = work / "stix-import.sova-trace"
    writer = TraceWriter(
        imported_trace,
        capture_profile="forensic",
        content_capture="metadata-only",
        authorization={
            "decision": "not-required",
            "scopeDigest": None,
            "decidedBy": "offline-format-import",
        },
        reviewed_for_export=True,
    )
    previous: str | None = None
    for item in parsed.objects:
        raw = item.serialize(pretty=False).encode("utf-8")
        previous = writer.append(
            "x.stix.object.imported",
            {
                "type": str(item.type),
                "id": str(item.id),
                "specVersion": str(getattr(item, "spec_version", "2.1")),
                "objectDigest": _digest(raw),
                "rawContentIncluded": False,
            },
            parents=[previous] if previous else [],
            wall_time=(
                _fixed_time(10 + int(getattr(item, "id", "0")[-1], 16) % 10)
                .isoformat()
                .replace("+00:00", "Z")
            ),
        )
    writer.append(
        "export.completed",
        {
            "format": "STIX 2.1",
            "sourceBundleDigest": _digest(serialized),
            "lossless": False,
        },
        parents=[previous] if previous else [],
        wall_time="2026-08-01T00:00:30Z",
    )
    writer.finalize(completion="completed")
    imported = TraceReader(imported_trace).verify()

    return {
        "library": "oasis-open/cti-python-stix2",
        "libraryVersion": importlib.metadata.version("stix2"),
        "libraryCommit": STIX_COMMIT,
        "libraryWheelSha256": STIX_WHEEL_SHA256,
        "libraryLicense": "BSD-3-Clause",
        "standard": "OASIS STIX 2.1",
        "bundleDigest": _digest(serialized),
        "bundleBytes": len(serialized),
        "objects": dict(sorted(object_types.items())),
        "officialParserAccepted": True,
        "customTraceDigestPreserved": str(parsed_incident.external_references[0].external_id)
        == trace_digest,
        "customChainRootPreserved": str(parsed_incident.x_sova_chain_root) == chain_root,
        "importedTraceVerified": imported.package_integrity and imported.event_chain_integrity,
        "importedEvents": imported.event_count,
        "fidelity": {
            "preserved": [
                "incident identity and type",
                "source package digest",
                "source chain root reference",
                "capture profile",
                "source event count",
                "artifact digest",
                "object relationships",
            ],
            "approximated": [
                "SOVA finding and run represented as a STIX incident case",
                "observable evidence represented as STIX Artifact/ObservedData",
            ],
            "omitted": [
                "raw prompts and responses",
                "event payloads",
                "event sequence and complete causal graph",
                "authorization and safety semantics",
                "redaction records and retention policy",
                "replay procedure and environment dependencies",
                "DSSE signature and signer trust policy",
            ],
            "lossless": False,
        },
        "claimBoundary": (
            "A metadata-only, explicitly lossy incident interchange path. STIX "
            "acceptance does not verify SOVA evidence truth or reproducibility."
        ),
    }


def _any_value(value: Any) -> Any:
    from opentelemetry.proto.common.v1.common_pb2 import (
        AnyValue,
        ArrayValue,
        KeyValue,
        KeyValueList,
    )

    if value is None:
        return AnyValue(string_value="null")
    if isinstance(value, bool):
        return AnyValue(bool_value=value)
    if isinstance(value, int):
        return AnyValue(int_value=value)
    if isinstance(value, float):
        return AnyValue(double_value=value)
    if isinstance(value, str):
        return AnyValue(string_value=value)
    if isinstance(value, list):
        return AnyValue(array_value=ArrayValue(values=[_any_value(item) for item in value]))
    if isinstance(value, dict):
        return AnyValue(
            kvlist_value=KeyValueList(
                values=[
                    KeyValue(key=str(key), value=_any_value(child))
                    for key, child in sorted(value.items())
                ]
            )
        )
    raise TypeError(f"unsupported OTLP value: {type(value)!r}")


def _otlp_request(events: Iterable[dict[str, Any]]) -> tuple[bytes, list[str], list[str]]:
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
        ExportTraceServiceRequest,
    )
    from opentelemetry.proto.common.v1.common_pb2 import InstrumentationScope, KeyValue
    from opentelemetry.proto.resource.v1.resource_pb2 import Resource
    from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

    spans: list[Any] = []
    trace_ids: list[str] = []
    span_ids: list[str] = []
    for event in events:
        projection, _fidelity = export_event(event)
        start = datetime.fromisoformat(str(projection["start_time"]).replace("Z", "+00:00"))
        trace_id = str(projection["trace_id"])
        span_id = str(projection["span_id"])
        span = Span(
            trace_id=bytes.fromhex(trace_id),
            span_id=bytes.fromhex(span_id),
            name=str(projection["name"]),
            start_time_unix_nano=int(start.timestamp() * 1_000_000_000),
            end_time_unix_nano=int(start.timestamp() * 1_000_000_000) + 1,
            attributes=[
                KeyValue(key=str(key), value=_any_value(value))
                for key, value in sorted(projection["attributes"].items())
            ],
        )
        if projection["parent_span_id"] is not None:
            span.parent_span_id = bytes.fromhex(str(projection["parent_span_id"]))
        spans.append(span)
        trace_ids.append(trace_id)
        span_ids.append(span_id)
    request = ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=Resource(
                    attributes=[
                        KeyValue(key="service.name", value=_any_value("sova-p5-study")),
                        KeyValue(key="service.version", value=_any_value("0.1")),
                    ]
                ),
                scope_spans=[
                    ScopeSpans(
                        scope=InstrumentationScope(name="sova.trace.otel", version="0.1"),
                        spans=spans,
                    )
                ],
            )
        ]
    )
    return request.SerializeToString(deterministic=True), trace_ids, span_ids


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


def _wait_for_port(port: int, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout is not None else ""
            raise RuntimeError(f"collector exited before listening: {output[-1000:]}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
            handle.settimeout(0.2)
            if handle.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError("collector did not open its local OTLP endpoint")


def _collector_study(
    work: Path,
    source_trace: Path,
    collector: Path,
    expected_collector_digest: str,
) -> dict[str, Any]:
    if not collector.is_file():
        raise RuntimeError("collector executable is missing")
    actual_digest = _digest(collector.read_bytes())
    if actual_digest != expected_collector_digest:
        raise RuntimeError("collector executable digest does not match the official checksum")
    if importlib.metadata.version("opentelemetry-proto") != OTEL_PROTO_VERSION:
        raise RuntimeError("opentelemetry-proto dependency drifted")

    port = _free_port()
    output_path = (work / "collector-output.json").resolve()
    config = work / "otelcol-config.yaml"
    config.write_text(
        "\n".join(
            [
                "receivers:",
                "  otlp:",
                "    protocols:",
                "      http:",
                f"        endpoint: 127.0.0.1:{port}",
                "exporters:",
                "  file:",
                f"    path: '{output_path.as_posix()}'",
                "service:",
                "  telemetry:",
                "    logs:",
                "      level: error",
                "  pipelines:",
                "    traces:",
                "      receivers: [otlp]",
                "      exporters: [file]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    events = TraceReader(source_trace).events()
    wire, trace_ids, span_ids = _otlp_request(events)
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        [str(collector.resolve()), "--config", str(config.resolve())],
        cwd=work,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=creation_flags,
    )
    response_status: int | None = None
    response_bytes = 0
    started = perf_counter_ns()
    try:
        _wait_for_port(port, process)
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/v1/traces",
            data=wire,
            method="POST",
            headers={"Content-Type": "application/x-protobuf"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
            response_status = int(response.status)
            response_bytes = len(response.read())
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if output_path.is_file() and output_path.stat().st_size > 0:
                break
            time.sleep(0.1)
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("collector acknowledged OTLP but produced no backend file")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    elapsed = perf_counter_ns() - started
    output_raw = output_path.read_bytes()
    documents = [json.loads(line) for line in output_raw.splitlines() if line.strip()]
    if not documents:
        raise RuntimeError("collector backend output was not JSONL")
    spans = [
        span
        for document in documents
        for resource in document.get("resourceSpans", [])
        for scope in resource.get("scopeSpans", [])
        for span in scope.get("spans", [])
    ]
    observed_trace_ids = [str(span.get("traceId", "")).lower() for span in spans]
    observed_span_ids = [str(span.get("spanId", "")).lower() for span in spans]
    attribute_keys = {
        str(attribute.get("key")) for span in spans for attribute in span.get("attributes", [])
    }
    if response_status != 200 or len(spans) != len(events):
        raise RuntimeError("collector/backend did not preserve the submitted span count")
    if Counter(observed_trace_ids) != Counter(trace_ids) or Counter(observed_span_ids) != Counter(
        span_ids
    ):
        raise RuntimeError("collector/backend changed OTLP trace or span identifiers")
    if "sova.event.id" not in attribute_keys or "sova.event_hash" not in attribute_keys:
        raise RuntimeError("collector/backend dropped required SOVA projection attributes")

    version = subprocess.run(
        [str(collector.resolve()), "--version"],
        cwd=work,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
        creationflags=creation_flags,
    )
    return {
        "distribution": "otelcol-contrib",
        "release": COLLECTOR_RELEASE,
        "binaryDigest": actual_digest,
        "binaryVersionOutput": (version.stdout or version.stderr).strip()[:300],
        "officialChecksumMatched": True,
        "receiver": "OTLP/HTTP protobuf on 127.0.0.1",
        "backend": "official file exporter JSONL",
        "externalNetworkUsedByPipeline": False,
        "httpStatus": response_status,
        "responseBytes": response_bytes,
        "submittedProtobufBytes": len(wire),
        "submittedSpans": len(events),
        "backendSpans": len(spans),
        "traceIdentifiersPreserved": Counter(observed_trace_ids) == Counter(trace_ids),
        "spanIdentifiersPreserved": Counter(observed_span_ids) == Counter(span_ids),
        "sovaProjectionAttributesPresent": True,
        "backendBytes": len(output_raw),
        "elapsedNanoseconds": elapsed,
        "claimBoundary": (
            "One official local collector/file-exporter path. It does not certify "
            "hosted vendors, production operations, semantic equivalence, privacy, "
            "availability, or SOVA evidence truth."
        ),
    }


def _run_verifier(command: list[str], *, timeout: int = 180) -> tuple[int, int, dict[str, Any]]:
    started = perf_counter_ns()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    elapsed = perf_counter_ns() - started
    report = json.loads(completed.stdout) if completed.returncode == 0 else {}
    return completed.returncode, elapsed, report


def _scale_case(work: Path, count: int) -> dict[str, Any]:
    destination = work / f"scale-{count}.sova-trace"
    key = generate_ed25519_keypair()
    tracemalloc.start()
    capture_started = perf_counter_ns()
    writer = TraceWriter(
        destination,
        capture_profile="forensic",
        segment_events=1_000,
        segment_bytes=4 * 1024 * 1024,
        durability="lite",
        signing_key=key,
        authorization={
            "decision": "not-required",
            "scopeDigest": None,
            "decidedBy": "synthetic-scale-study",
        },
    )
    previous: str | None = None
    for index in range(count):
        kind = "model.response" if index % 2 == 0 else "tool.completed"
        previous = writer.append(
            kind,
            {
                "index": index,
                "bucket": index % 17,
                "digest": "sha256:" + hashlib.sha256(str(index).encode()).hexdigest(),
            },
            parents=[previous] if previous else [],
        )
    capture_elapsed = perf_counter_ns() - capture_started
    finalize_started = perf_counter_ns()
    writer.finalize(completion="completed")
    finalize_elapsed = perf_counter_ns() - finalize_started
    _current, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    reader = TraceReader(destination)
    verify_started = perf_counter_ns()
    verification = reader.verify(required_key_id=key.key_id)
    verify_elapsed = perf_counter_ns() - verify_started
    read_started = perf_counter_ns()
    events = reader.events()
    read_elapsed = perf_counter_ns() - read_started
    query_started = perf_counter_ns()
    selected = list(reader.query(kind_prefix="tool.", start_sequence=count // 2))
    query_elapsed = perf_counter_ns() - query_started
    disclosure_started = perf_counter_ns()
    step = max(1, count // 100)
    disclosure = reader.disclosure_view(
        sequences=set(range(0, count, step)),
        include_payload=False,
    )
    disclosure_elapsed = perf_counter_ns() - disclosure_started
    role_counts = Counter(
        descriptor.role for descriptor in PackageReader(destination).verify("sova.trace")
    )

    python_code, python_elapsed, python_report = _run_verifier(
        [
            sys.executable,
            str(PYTHON_VERIFIER),
            str(destination),
            "--required-key-id",
            key.key_id,
        ]
    )
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js is required for the cross-language scale verifier")
    node_code, node_elapsed, node_report = _run_verifier(
        [
            node,
            str(NODE_VERIFIER),
            str(destination),
            "--required-key-id",
            key.key_id,
        ]
    )
    if python_code != 0 or node_code != 0:
        raise RuntimeError("one independent verifier rejected the signed scale trace")
    if python_report.get("eventCount") != count or node_report.get("eventCount") != count:
        raise RuntimeError("one independent verifier reported the wrong event count")
    if python_report.get("contentDigest") != node_report.get("contentDigest"):
        raise RuntimeError("cross-language verifiers disagreed on the content digest")
    if verification.event_count != len(events) or verification.event_count != count:
        raise RuntimeError("scale trace event count changed")

    return {
        "events": count,
        "externalEventScaleRatio": count / EXTERNAL_EVENT_SCALE,
        "packageBytes": destination.stat().st_size,
        "eventSegments": role_counts["event-segment"],
        "captureNanoseconds": capture_elapsed,
        "captureEventsPerSecond": count / (capture_elapsed / 1_000_000_000),
        "finalizeNanoseconds": finalize_elapsed,
        "readNanoseconds": read_elapsed,
        "verifyNanoseconds": verify_elapsed,
        "queryNanoseconds": query_elapsed,
        "querySelected": len(selected),
        "disclosureNanoseconds": disclosure_elapsed,
        "disclosureSelected": disclosure["selectedEventCount"],
        "disclosureOmitted": disclosure["omittedEventCount"],
        "disclosurePayloadsIncluded": disclosure["payloadsIncluded"],
        "capturePeakTracedBytes": peak_bytes,
        "signatureValid": verification.signature_valid,
        "trustPolicy": verification.trust_policy,
        "pythonVerifier": {
            "returnCode": python_code,
            "nanoseconds": python_elapsed,
            "verifier": python_report.get("verifier"),
            "eventCount": python_report.get("eventCount"),
        },
        "nodeVerifier": {
            "returnCode": node_code,
            "nanoseconds": node_elapsed,
            "verifier": node_report.get("verifier"),
            "eventCount": node_report.get("eventCount"),
        },
        "crossLanguageContentDigestAgrees": python_report.get("contentDigest")
        == node_report.get("contentDigest"),
    }


def _scale_study(work: Path) -> dict[str, Any]:
    rows = [_scale_case(work, count) for count in SCALE_COUNTS]
    return {
        "externalReferenceCounts": {
            "inspectEvalEmittedEvents": 483,
            "agentRewardImportedEvents": 396,
            "combined": EXTERNAL_EVENT_SCALE,
        },
        "cases": rows,
        "largestCase": max(SCALE_COUNTS),
        "largestExternalScaleRatio": max(SCALE_COUNTS) / EXTERNAL_EVENT_SCALE,
        "allSignedRequiredKeyVerified": all(
            row["signatureValid"] and row["trustPolicy"] == "required-key" for row in rows
        ),
        "allCrossLanguageDigestsAgree": all(
            row["crossLanguageContentDigestAgrees"] for row in rows
        ),
        "claimBoundary": (
            "Synthetic size-envelope measurements on one Windows host. The largest "
            "trace exceeds the retained external-event cohort but is not a production "
            "workload, distributed run, independent benchmark, or public performance claim."
        ),
    }


def run(collector: Path, collector_digest: str) -> dict[str, Any]:
    if not collector_digest.startswith("sha256:"):
        raise RuntimeError("collector digest must be an explicit sha256 value")
    with tempfile.TemporaryDirectory(prefix="sova-p5-study-") as raw:
        work = Path(raw)
        source_trace, key_id = _safe_trace(work / "source.sova-trace")
        result = {
            "artifactType": "sova.private-p5-incident-collector-scale-study",
            "version": "0.1.0",
            "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "owner": "Gautam R. Patil",
            "organization": "TRUSCOR Private Limited",
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "cpuOnly": True,
                "workers": 1,
                "externalCredentialsUsed": False,
            },
            "sourceTrace": {
                "digest": _digest(source_trace.read_bytes()),
                "requiredKeyId": key_id,
                "eventCount": TraceReader(source_trace).verify().event_count,
                "retained": False,
            },
            "incidentInteroperability": _incident_study(work, source_trace),
            "collectorBackend": _collector_study(
                work,
                source_trace,
                collector,
                collector_digest,
            ),
            "scale": _scale_study(work),
            "overallBoundary": (
                "External implementations and official formats exercised by same-team "
                "code. This is not an independent review, production certification, "
                "truth guarantee, or non-repudiation evidence."
            ),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collector", type=Path, required=True)
    parser.add_argument("--collector-digest", required=True)
    args = parser.parse_args()
    result = run(args.collector.resolve(), args.collector_digest)
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(
        json.dumps(
            result,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(RESULT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
