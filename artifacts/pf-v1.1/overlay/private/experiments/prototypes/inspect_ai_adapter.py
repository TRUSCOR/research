"""Private pinned Inspect AI JSON-log interoperability prototype.

This accepts a bounded JSON dump subset. It does not parse Inspect's binary
``.eval`` container and does not claim complete fidelity.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sova.capsule import build_capsule, capsule_manifest_template
from sova.formats import sha256_digest, strict_json_loads
from sova.formats.errors import FormatError
from sova.trace import TraceWriter

INSPECT_AI_COMMIT = "1ea01a9e1b3c94db3cdf93ce5583ffebf86e159f"
INSPECT_EVAL_LOG_VERSION = 2
INSPECT_EVAL_LOG_VERSIONS = (2, 3)
ADAPTER_VERSION = "0.4.0"
MAX_SAMPLES = 10_000
MAX_EVENTS = 100_000
_SAFE_EVENT = re.compile(r"[^a-z0-9.-]+")


@dataclass(frozen=True, slots=True)
class InspectImportReport:
    source_digest: str
    trace_digest: str
    source_commit: str
    source_log_version: int
    samples: int
    source_events: int
    emitted_events: int
    source_layouts: tuple[str, ...]
    preserved: tuple[str, ...]
    approximated: tuple[str, ...]
    omitted: tuple[str, ...]
    unavailable: tuple[str, ...]

    @property
    def lossless(self) -> bool:
        return not self.approximated and not self.omitted and not self.unavailable

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FormatError("SOVA-INSPECT-IMPORT", "expected an object", path=path)
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise FormatError("SOVA-INSPECT-IMPORT", "expected an array", path=path)
    return value


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise FormatError("SOVA-INSPECT-IMPORT", "expected a non-empty string", path=path)
    return value


def _ijson(value: Any) -> Any:
    """Convert finite source floats to explicit decimal strings for SOVA I-JSON."""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise FormatError(
                "SOVA-INSPECT-NONFINITE",
                "non-finite Inspect numbers require upstream normalization",
            )
        return {"$sourceDecimal": format(value, ".17g")}
    if isinstance(value, Mapping):
        return {str(key): _ijson(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_ijson(item) for item in value]
    return value


def _external_link(event: Mapping[str, Any], *, log_version: int) -> list[dict[str, Any]]:
    identifier = event.get("uuid")
    span = event.get("span_id")
    if identifier is None and span is None:
        return []
    return [
        {
            "relationship": "correlates",
            "scheme": "inspect-ai.eval-log",
            "version": f"log-{log_version}@{INSPECT_AI_COMMIT}",
            "traceId": None,
            "spanId": str(span) if span is not None else None,
            "eventId": str(identifier) if identifier is not None else None,
            "fidelity": "degraded",
            "trusted": False,
        }
    ]


def _source_payload(
    event: Mapping[str, Any],
    *,
    sample_id: str,
    include_content: bool,
) -> dict[str, Any]:
    common = {
        "adapter": f"sova.inspect-json-import/{ADAPTER_VERSION}",
        "commit": INSPECT_AI_COMMIT,
        "sampleId": sample_id,
        "event": event.get("event"),
        "uuid": event.get("uuid"),
        "spanId": event.get("span_id"),
    }
    if include_content:
        common["source"] = _ijson(dict(event))
    else:
        common["content"] = {
            "method": "omitted-by-import-policy",
            "sourceFields": sorted(str(key) for key in event),
        }
    return common


def _event_kind(value: Any) -> str:
    text = str(value or "unknown").lower()
    slug = _SAFE_EVENT.sub("-", text).strip(".-")
    return f"x.inspect.{slug or 'unknown'}"


def import_inspect_json(
    source: Path,
    destination: Path,
    *,
    include_content: bool = False,
) -> InspectImportReport:
    """Import a bounded Inspect JSON dump into a verified SOVA trace."""
    raw = source.read_bytes()
    document = _mapping(strict_json_loads(raw), "$")
    version = document.get("version")
    if version not in INSPECT_EVAL_LOG_VERSIONS:
        raise FormatError(
            "SOVA-INSPECT-VERSION",
            "unsupported Inspect EvalLog version",
            path="$.version",
            details={"actual": version, "supported": list(INSPECT_EVAL_LOG_VERSIONS)},
        )
    spec = _mapping(document.get("eval"), "$.eval")
    status = _text(document.get("status"), "$.status")
    samples_value = document.get("samples")
    samples = [] if samples_value is None else _array(samples_value, "$.samples")
    if len(samples) > MAX_SAMPLES:
        raise FormatError(
            "SOVA-INSPECT-SAMPLE-LIMIT",
            "Inspect log exceeds the import sample limit",
            details={"actual": len(samples), "limit": MAX_SAMPLES},
        )
    if version == 3:
        condensed = [
            index
            for index, sample in enumerate(samples)
            if isinstance(sample, dict) and sample.get("events_data") is not None
        ]
        if condensed:
            raise FormatError(
                "SOVA-INSPECT-CONDENSED-EVENTS",
                "Inspect v3 pooled event data must be expanded by the official reader",
                path=f"$.samples[{condensed[0]}].events_data",
                details={"affectedSamples": condensed},
            )

    completion = {
        "success": "completed",
        "error": "failed",
        "cancelled": "cancelled",
        "started": "partial",
    }.get(status, "partial")
    writer = TraceWriter(
        destination,
        capture_profile="standard",
        authorization={
            "decision": "not-required",
            "scopeDigest": None,
            "decidedBy": "offline-import",
        },
        environment={
            "platform": "external-inspect-log",
            "python": "not-recorded",
            "codeDigest": f"sha256:{INSPECT_AI_COMMIT}{'0' * 24}",
            "model": {
                "id": str(spec.get("model", "not-recorded")),
                "source": "inspect-ai-eval-spec",
            },
            "dependencies": [
                {
                    "name": "inspect_ai",
                    "version": "commit",
                    "digest": f"git:{INSPECT_AI_COMMIT}",
                }
            ],
        },
        executor={
            "id": "external:inspect-ai",
            "name": "Inspect AI imported log",
            "version": f"log-{version}",
            "capabilityDigest": None,
        },
    )
    emitted = 0
    source_events = 0
    source_layouts: set[str] = set()

    writer.append(
        "run.started",
        {
            "source": "Inspect AI EvalLog",
            "sourceCommit": INSPECT_AI_COMMIT,
            "logVersion": version,
            "evalId": spec.get("eval_id"),
            "runId": spec.get("run_id"),
            "task": spec.get("task"),
            "model": spec.get("model"),
            "importOnly": True,
        },
        producer={
            "id": "external:inspect-ai",
            "kind": "importer",
            "name": "SOVA Inspect JSON adapter",
        },
    )
    emitted += 1

    for sample_index, raw_sample in enumerate(samples):
        sample = _mapping(raw_sample, f"$.samples[{sample_index}]")
        sample_id = str(sample.get("id", sample_index))
        transcript_value = sample.get("transcript")
        if isinstance(transcript_value, dict):
            events_path = f"$.samples[{sample_index}].transcript.events"
            events = _array(transcript_value.get("events", []), events_path)
            source_layout = "transcript-events"
        elif "events" in sample:
            events_path = f"$.samples[{sample_index}].events"
            events = _array(sample["events"], events_path)
            source_layout = "legacy-flat-events"
        else:
            events_path = f"$.samples[{sample_index}]"
            events = []
            source_layout = "no-event-stream"
        source_layouts.add(source_layout)
        source_events += len(events)
        if source_events > MAX_EVENTS:
            raise FormatError(
                "SOVA-INSPECT-EVENT-LIMIT",
                "Inspect log exceeds the import event limit",
                details={"limit": MAX_EVENTS},
            )
        phase = f"inspect-sample-{sample_index}"
        phase_start = writer.append(
            "phase.started",
            {
                "sampleId": sample_id,
                "epoch": sample.get("epoch"),
                "inputIncluded": include_content,
                "sourceEventLayout": source_layout,
            },
            phase=phase,
        )
        emitted += 1

        last_parent = phase_start
        for event_index, raw_event in enumerate(events):
            event_path = f"{events_path}[{event_index}]"
            event = _mapping(
                raw_event,
                event_path,
            )
            source_kind = _text(
                event.get("event"),
                f"{event_path}.event",
            )
            timestamp = event.get("timestamp")
            wall_time = timestamp if isinstance(timestamp, str) else None
            links = _external_link(event, log_version=version)
            producer = {
                "id": "external:inspect-ai",
                "kind": "imported",
                "name": "Inspect AI",
            }
            common = {
                "phase": phase,
                "parents": [last_parent] if last_parent else [],
                "wall_time": wall_time,
                "clock_domain": f"inspect-ai:{sample_id}",
                "producer": producer,
                "links": links,
            }
            if source_kind == "model":
                prompt = writer.append(
                    "prompt.submitted",
                    {
                        **_source_payload(
                            event,
                            sample_id=sample_id,
                            include_content=False,
                        ),
                        "model": event.get("model"),
                        "input": (
                            _ijson(event.get("input"))
                            if include_content
                            else {"method": "omitted-by-import-policy"}
                        ),
                    },
                    **common,
                )
                emitted += 1
                response = writer.append(
                    "model.response",
                    {
                        **_source_payload(
                            event,
                            sample_id=sample_id,
                            include_content=False,
                        ),
                        "model": event.get("model"),
                        "output": (
                            _ijson(event.get("output"))
                            if include_content
                            else {"method": "omitted-by-import-policy"}
                        ),
                        "errorPresent": event.get("error") is not None,
                        "retries": event.get("retries"),
                    },
                    phase=phase,
                    parents=[prompt] if prompt else common["parents"],
                    wall_time=wall_time,
                    clock_domain=common["clock_domain"],
                    producer=producer,
                    links=links,
                )
                last_parent = response
                emitted += 1
            elif source_kind == "tool":
                requested = writer.append(
                    "tool.requested",
                    {
                        **_source_payload(
                            event,
                            sample_id=sample_id,
                            include_content=False,
                        ),
                        "request": {
                            "id": event.get("id"),
                            "action": event.get("function"),
                            "inputs": (
                                _ijson(event.get("arguments"))
                                if include_content
                                else {"method": "omitted-by-import-policy"}
                            ),
                        },
                    },
                    **common,
                )
                emitted += 1
                failed = event.get("failed") is True or event.get("error") is not None
                terminal = writer.append(
                    "tool.failed" if failed else "tool.completed",
                    {
                        **_source_payload(
                            event,
                            sample_id=sample_id,
                            include_content=False,
                        ),
                        "outcome": {
                            "request_id": event.get("id"),
                            "status": "failed" if failed else "succeeded",
                            "side_effect": "unknown-imported",
                            "output": (
                                _ijson(event.get("result"))
                                if include_content
                                else {"method": "omitted-by-import-policy"}
                            ),
                            "evidence": [],
                            "verification": "not-performed-imported",
                            "limitations": [
                                "Inspect provider result imported without "
                                "SOVA post-action verification."
                            ],
                        },
                        "truncated": _ijson(event.get("truncated")),
                    },
                    phase=phase,
                    parents=[requested] if requested else common["parents"],
                    wall_time=wall_time,
                    clock_domain=common["clock_domain"],
                    producer=producer,
                    links=links,
                )
                last_parent = terminal
                emitted += 1
            elif source_kind == "score":
                score = writer.append(
                    "judge.completed",
                    {
                        **_source_payload(
                            event,
                            sample_id=sample_id,
                            include_content=False,
                        ),
                        "score": (
                            _ijson(event.get("score"))
                            if include_content
                            else {"method": "omitted-by-import-policy"}
                        ),
                        "scorer": event.get("scorer"),
                        "intermediate": event.get("intermediate", False),
                    },
                    **common,
                )
                last_parent = score
                emitted += 1
            else:
                imported = writer.append(
                    _event_kind(source_kind),
                    _source_payload(
                        event,
                        sample_id=sample_id,
                        include_content=include_content,
                    ),
                    **common,
                )
                last_parent = imported
                emitted += 1

        writer.append(
            "phase.completed",
            {
                "sampleId": sample_id,
                "sourceEventCount": len(events),
                "status": "imported",
            },
            phase=phase,
            parents=[last_parent] if last_parent else [],
        )
        emitted += 1

    writer.append(
        "run.completed" if completion == "completed" else "run.failed",
        {
            "sourceStatus": status,
            "sourceSamples": len(samples),
            "sourceEvents": source_events,
            "importOnly": True,
        },
    )
    emitted += 1
    trace_digest = writer.finalize(completion=completion)
    return InspectImportReport(
        source_digest=sha256_digest(raw),
        trace_digest=trace_digest,
        source_commit=INSPECT_AI_COMMIT,
        source_log_version=version,
        samples=len(samples),
        source_events=source_events,
        emitted_events=emitted,
        source_layouts=tuple(sorted(source_layouts)),
        preserved=(
            "eval identity and status",
            "sample identity and epoch",
            "EvalSample transcript and legacy flat event layouts",
            "event kind",
            "event UUID and span ID as untrusted external links",
            "source timestamps and per-sample clock domain",
            "model/tool/score structure",
        ),
        approximated=(
            "one source model event becomes prompt and response events",
            "one source tool event becomes request and terminal events",
            "finite binary JSON numbers become tagged decimal strings",
            "source parentage is sequentialized within each sample",
            "samples without an event stream are represented as empty phases",
        ),
        omitted=(
            "binary .eval storage details",
            "Inspect attachment resolution",
            "EvalSample transcript content references",
            "source event subtypes without a dedicated mapping",
        ),
        unavailable=(
            "SOVA capture-time authorization and redaction provenance",
            "SOVA-owned post-action observations",
            "truth of source events",
        ),
    )


def package_imported_trace(
    source_log: Path,
    imported_trace: Path,
    destination: Path,
    report: InspectImportReport,
    *,
    include_source_log: bool = False,
) -> str:
    """Package an imported trace with explicit source/fidelity metadata."""
    manifest = capsule_manifest_template(
        title="Imported Inspect AI behavior record",
        summary="Offline interoperability capsule; re-execution recipe not inferred.",
        author="Gautam R. Patil",
    )
    manifest["license"] = "NOASSERTION"
    manifest["safety"]["impact"] = "unknown"
    manifest["limitations"].extend(
        [
            "Inspect JSON import is explicitly lossy.",
            "This capsule contains no inferred replay recipe.",
            "Source content may require independent disclosure review.",
        ]
    )
    manifest["extensions"]["x-inspect-ai-import"] = report.to_mapping()
    attachments = {"inspect-source.json": source_log.read_bytes()} if include_source_log else None
    return build_capsule(
        destination,
        manifest,
        traces=[imported_trace],
        attachments=attachments,
    )


__all__ = [
    "ADAPTER_VERSION",
    "INSPECT_AI_COMMIT",
    "INSPECT_EVAL_LOG_VERSION",
    "INSPECT_EVAL_LOG_VERSIONS",
    "InspectImportReport",
    "import_inspect_json",
    "package_imported_trace",
]
