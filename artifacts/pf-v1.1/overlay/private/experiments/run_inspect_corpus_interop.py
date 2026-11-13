"""Pinned official Inspect JSON corpus interoperability study.

Raw external fixtures stay outside the repository and are never redistributed.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from private.experiments.prototypes.inspect_ai_adapter import (
    ADAPTER_VERSION,
    INSPECT_AI_COMMIT,
    import_inspect_json,
)
from sova.formats import FormatError, sha256_digest, strict_json_loads
from sova.trace import TraceReader

ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "private"
    / "experiments"
    / "results"
    / "inspect-corpus-interoperability-2026-07-31.json"
)

EXPECTED_PATHS = (
    "tests/analysis/test_logs/2025-05-12T20-27-36-04-00_browser.json",
    "tests/analysis/test_logs/2025-05-12T20-28-13-04-00_no-samples.json",
    "tests/analysis/test_logs/2025-05-12T20-28-13-04-00_popularity.json",
    "tests/analysis/test_logs/2025-05-12T20-28-26-04-00_security-guide.json",
    "tests/log/test_eval_log/log_formats.json",
    "tests/log/test_eval_log/log_images.json",
    "tests/log/test_eval_log/log_images_tc.json",
    "tests/log/test_eval_log/log_read_sample.json",
    "tests/log/test_eval_log/log_tool_call_error.json",
    "tests/log/test_list_logs/2024-11-05T13-31-45-05-00_input-task_8zXjbRzCWrL9GXiXo2vus9.json",
    "tests/log/test_list_logs/ignore.json",
    "tests/test_eval_set/2024-08-29T15-11-17+00-00_popularity_5EAmX6wjMFqea6WY7XHzZp.json",
    "tests/test_eval_set/2024-08-29T15-11-18+00-00_popularity_5EAmX6wjMFqea6WY7XHzZp.json",
)


def _fixture_path(root: Path, source_path: str) -> Path:
    return root / source_path.replace("/", "__")


def _source_shape(raw: bytes) -> dict[str, int | None]:
    document = strict_json_loads(raw)
    if not isinstance(document, dict):
        return {"version": None, "samples": 0, "events": 0}
    samples = document.get("samples")
    sample_count = len(samples) if isinstance(samples, list) else 0
    event_count = 0
    if isinstance(samples, list):
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            transcript = sample.get("transcript")
            events = (
                transcript.get("events")
                if isinstance(transcript, dict)
                else sample.get("events")
            )
            if isinstance(events, list):
                event_count += len(events)
    version = document.get("version")
    return {
        "version": version if isinstance(version, int) else None,
        "samples": sample_count,
        "events": event_count,
    }


def _omission_probe(events: list[dict[str, Any]]) -> dict[str, int]:
    violations = 0
    checked = 0
    source_object_violations = 0
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        if isinstance(payload.get("source"), (dict, list)):
            source_object_violations += 1
        kind = event["kind"]
        if kind == "prompt.submitted":
            checked += 1
            if payload.get("input") != {"method": "omitted-by-import-policy"}:
                violations += 1
        elif kind == "model.response":
            checked += 1
            if payload.get("output") != {"method": "omitted-by-import-policy"}:
                violations += 1
        elif kind == "tool.requested":
            checked += 1
            request = payload.get("request")
            if not isinstance(request, dict) or request.get("inputs") != {
                "method": "omitted-by-import-policy"
            }:
                violations += 1
        elif kind in {"tool.completed", "tool.failed"}:
            checked += 1
            outcome = payload.get("outcome")
            if not isinstance(outcome, dict) or outcome.get("output") != {
                "method": "omitted-by-import-policy"
            }:
                violations += 1
        elif kind == "judge.completed":
            checked += 1
            if payload.get("score") != {"method": "omitted-by-import-policy"}:
                violations += 1
    return {
        "contentFieldsChecked": checked,
        "contentPolicyViolations": violations,
        "sourceObjectViolations": source_object_violations,
    }


def run(corpus_root: Path) -> dict[str, Any]:
    corpus_root = corpus_root.resolve()
    discovered = sorted(path.name for path in corpus_root.glob("*.json"))
    expected_names = sorted(path.replace("/", "__") for path in EXPECTED_PATHS)
    if discovered != expected_names:
        missing = sorted(set(expected_names) - set(discovered))
        extra = sorted(set(discovered) - set(expected_names))
        raise RuntimeError(f"fixture corpus mismatch: missing={missing!r}, extra={extra!r}")

    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="sova-inspect-corpus-") as raw_work:
        work = Path(raw_work)
        for index, source_path in enumerate(EXPECTED_PATHS):
            source = _fixture_path(corpus_root, source_path)
            raw = source.read_bytes()
            row: dict[str, Any] = {
                "sourcePath": source_path,
                "sourceBytes": len(raw),
                "sourceDigest": sha256_digest(raw),
                "sourceShape": _source_shape(raw),
            }
            trace = work / f"import-{index:03d}.sova-trace"
            try:
                report = import_inspect_json(
                    source,
                    trace,
                    include_content=False,
                )
                verification = TraceReader(trace).verify()
                events = TraceReader(trace).events()
                probe = _omission_probe(events)
                row.update(
                    {
                        "status": "accepted",
                        "traceDigest": report.trace_digest,
                        "sourceSamples": report.samples,
                        "sourceEvents": report.source_events,
                        "emittedEvents": report.emitted_events,
                        "sourceLayouts": list(report.source_layouts),
                        "verifiedEvents": verification.event_count,
                        "completion": verification.completion,
                        "lossless": report.lossless,
                        "omissionProbe": probe,
                    }
                )
            except FormatError as error:
                row.update(
                    {
                        "status": "refused",
                        "issue": {
                            "code": error.issue.code,
                            "path": error.issue.path,
                            "message": error.issue.message,
                        },
                    }
                )
            rows.append(row)

    accepted = [row for row in rows if row["status"] == "accepted"]
    refused = [row for row in rows if row["status"] == "refused"]
    unexpected = [row for row in rows if row["status"] not in {"accepted", "refused"}]
    probe_violations = sum(
        row["omissionProbe"]["contentPolicyViolations"]
        + row["omissionProbe"]["sourceObjectViolations"]
        for row in accepted
    )
    return {
        "artifactType": "sova.private-inspect-corpus-interoperability",
        "version": "0.1.0",
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "owner": "Gautam R. Patil",
        "organization": "TRUSCOR Private Limited",
        "source": {
            "repository": "UKGovernmentBEIS/inspect_ai",
            "commit": INSPECT_AI_COMMIT,
            "adapterVersion": ADAPTER_VERSION,
            "selection": list(EXPECTED_PATHS),
            "rawFixturesRedistributed": False,
        },
        "summary": {
            "files": len(rows),
            "accepted": len(accepted),
            "refused": len(refused),
            "unexpectedErrors": len(unexpected),
            "sourceBytes": sum(row["sourceBytes"] for row in rows),
            "sourceSamplesAccepted": sum(row["sourceSamples"] for row in accepted),
            "sourceEventsAccepted": sum(row["sourceEvents"] for row in accepted),
            "emittedEvents": sum(row["emittedEvents"] for row in accepted),
            "verifiedEvents": sum(row["verifiedEvents"] for row in accepted),
            "contentPolicyViolations": probe_violations,
            "allAcceptedTracesVerified": all(
                row["emittedEvents"] == row["verifiedEvents"] for row in accepted
            ),
            "allAcceptedImportsDeclaredLossy": all(not row["lossless"] for row in accepted),
        },
        "rows": rows,
        "claimBoundary": (
            "Pinned official test-log JSON corpus. Accepted imports are explicitly "
            "lossy; refusals outside version/shape contract are valid outcomes; "
            "binary .eval support and general Inspect interoperability are not claimed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.corpus_root)
    if result["summary"]["unexpectedErrors"] != 0:
        raise RuntimeError("unexpected corpus import errors occurred")
    if result["summary"]["contentPolicyViolations"] != 0:
        raise RuntimeError("content omission policy violation occurred")
    RESULT.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(RESULT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
