"""Official Inspect ``.eval`` reader to privacy-minimized SOVA study.

Raw external fixtures and intermediate JSON remain in a temporary ignored
directory and are never redistributed. The official Inspect API parses and
converts the binary format; the bounded SOVA adapter consumes that JSON view.
"""

from __future__ import annotations

import importlib.metadata
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from inspect_ai.log import (
    read_eval_log,
    read_eval_log_sample_summaries,
    read_eval_log_samples,
    write_eval_log,
)

from private.experiments.prototypes.inspect_ai_adapter import import_inspect_json
from private.experiments.run_inspect_corpus_interop import _omission_probe
from sova.formats import FormatError, sha256_digest, strict_json_loads
from sova.trace import TraceReader

ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "private"
    / "experiments"
    / "results"
    / "inspect-eval-interoperability-2026-08-01.json"
)

INSPECT_PACKAGE = {
    "name": "inspect-ai",
    "version": "0.3.251",
    "commit": "8f92b6ed30bde33a3c40879492ee8e0900cb26c4",
    "license": "MIT",
    "wheelSha256": "6f18df2f14dd0646db78eaffe0db6d7735334450fdd4e03ec8f45b42a669b0fe",
}
SOURCE_COMMIT = "1ea01a9e1b3c94db3cdf93ce5583ffebf86e159f"
FIXTURES = {
    "custom.eval": {
        "sourcePath": "tests/log/test_list_logs/custom.eval",
        "sha256": "f4a629b66f34ee05fc45be4f933c040fe9f736cb99f8f2793d53791c71ce5f27",
    },
    "input-task.eval": {
        "sourcePath": (
            "tests/log/test_list_logs/"
            "2024-11-05T13-32-37-05-00_input-task_hxs4q9azL3ySGkjJirypKZ.eval"
        ),
        "sha256": "f4a629b66f34ee05fc45be4f933c040fe9f736cb99f8f2793d53791c71ce5f27",
    },
    "log_formats.eval": {
        "sourcePath": "tests/log/test_eval_log/log_formats.eval",
        "sha256": "13274e1d67440bdbd8d88e9400d0dd1e19d9b3b39128e3d9fee91618f116baff",
    },
    "log_message_deduplication.eval": {
        "sourcePath": "tests/log/test_eval_log/log_message_deduplication.eval",
        "sha256": "74d2314a43500fc02aa5f9824dee5ef89cf243c324c960133039f2208db7140a",
    },
    "log_read_sample.eval": {
        "sourcePath": "tests/log/test_eval_log/log_read_sample.eval",
        "sha256": "b5a30c045a3e1af75013f98310c2cc862ea671854692266fe1b2a844417c1756",
    },
    "log_streaming.eval": {
        "sourcePath": "tests/log/test_eval_log/log_streaming.eval",
        "sha256": "2904309c50fd8ca91af5371f45ec897a9b3072d8d9200e8ce335c909b3010ce1",
    },
    "mmlu-no-summary-choices.eval": {
        "sourcePath": "tests/analysis/test_logs_choices/mmlu-no-summary-choices.eval",
        "sha256": "067c9a9bb072fceff80d7e066fd606c46e08699924492c0461db49060508fed5",
    },
    "mmlu-summary-choices.eval": {
        "sourcePath": "tests/analysis/test_logs_choices/mmlu-summary-choices.eval",
        "sha256": "689150645cd8889e940a12fcc6d3889c6442139a9fdd01a1d86d52d5678a206e",
    },
    "popularity-a.eval": {
        "sourcePath": (
            "tests/scorer/logs/"
            "2025-02-11T15-17-00-05-00_popularity_dPiJifoWeEQBrfWsAopzWr.eval"
        ),
        "sha256": "6631813cb3cc25908d760d36677925a0e5753d06602c7d97385a4f448bafd9a1",
    },
    "popularity-b.eval": {
        "sourcePath": (
            "tests/scorer/logs/"
            "2025-02-11T15-18-04-05-00_popularity_mj7khqpMM4GBCfVQozKgzB.eval"
        ),
        "sha256": "f0ed828528c6c09337c0fee69be297a8946c95172f49f7536e7a3b4e2b9379b0",
    },
}


def run(corpus_root: Path) -> dict[str, Any]:
    corpus_root = corpus_root.resolve()
    discovered = {path.name for path in corpus_root.glob("*.eval")}
    if discovered != set(FIXTURES):
        raise RuntimeError(
            "binary fixture corpus mismatch: "
            f"missing={sorted(set(FIXTURES) - discovered)!r}, "
            f"extra={sorted(discovered - set(FIXTURES))!r}"
        )
    observed_version = importlib.metadata.version(INSPECT_PACKAGE["name"])
    if observed_version != INSPECT_PACKAGE["version"]:
        raise RuntimeError(
            f"Inspect package pin mismatch: {observed_version} != {INSPECT_PACKAGE['version']}"
        )

    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="sova-inspect-eval-") as raw_work:
        work = Path(raw_work)
        for index, (name, metadata) in enumerate(sorted(FIXTURES.items())):
            source = corpus_root / name
            source_bytes = source.read_bytes()
            source_hash = sha256_digest(source_bytes).removeprefix("sha256:")
            if source_hash != metadata["sha256"]:
                raise RuntimeError(f"source digest mismatch for {name}")
            row: dict[str, Any] = {
                "name": name,
                "sourcePath": metadata["sourcePath"],
                "sourceBytes": len(source_bytes),
                "sourceSha256": source_hash,
            }
            try:
                header = read_eval_log(source, header_only=True)
                summaries = read_eval_log_sample_summaries(source)
                streamed = list(
                    read_eval_log_samples(
                        source,
                        all_samples_required=False,
                        exclude_fields={"messages", "store", "attachments"},
                    )
                )
                log = read_eval_log(source)
                converted = work / f"{index:03d}.json"
                write_eval_log(log, converted, format="json")
                converted_document = strict_json_loads(converted.read_bytes())
                converted_version = (
                    converted_document.get("version")
                    if isinstance(converted_document, dict)
                    else None
                )
                row.update(
                    {
                        "logVersion": header.version,
                        "logStatus": header.status,
                        "summaryCount": len(summaries),
                        "streamedSampleCount": len(streamed),
                        "fullSampleCount": len(log.samples or []),
                        "convertedLogVersion": converted_version,
                        "convertedJsonBytes": converted.stat().st_size,
                        "convertedJsonSha256": sha256_digest(converted.read_bytes()),
                    }
                )
                trace = work / f"{index:03d}.sova-trace"
                report = import_inspect_json(converted, trace, include_content=False)
                verification = TraceReader(trace).verify()
                probe = _omission_probe(TraceReader(trace).events())
                row.update(
                    {
                        "status": "accepted",
                        "sourceEvents": report.source_events,
                        "emittedEvents": report.emitted_events,
                        "verifiedEvents": verification.event_count,
                        "traceDigest": report.trace_digest,
                        "lossless": report.lossless,
                        "omissionProbe": probe,
                    }
                )
            except FormatError as error:
                row.update(
                    {
                        "status": "typed-refusal",
                        "issue": {
                            "code": error.issue.code,
                            "path": error.issue.path,
                            "message": error.issue.message,
                        },
                    }
                )
            except Exception as error:  # external reader failures are retained
                row.update(
                    {
                        "status": "unexpected-error",
                        "errorType": type(error).__name__,
                        "message": str(error)[:500],
                    }
                )
            rows.append(row)

    accepted = [row for row in rows if row["status"] == "accepted"]
    typed_refusals = [row for row in rows if row["status"] == "typed-refusal"]
    unexpected = [row for row in rows if row["status"] == "unexpected-error"]
    violations = sum(
        row["omissionProbe"]["contentPolicyViolations"]
        + row["omissionProbe"]["sourceObjectViolations"]
        for row in accepted
    )
    return {
        "artifactType": "sova.private-inspect-eval-interoperability",
        "version": "0.1.0",
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "owner": "Gautam R. Patil",
        "organization": "TRUSCOR Private Limited",
        "source": {
            "repository": "UKGovernmentBEIS/inspect_ai",
            "fixtureCommit": SOURCE_COMMIT,
            "package": {**INSPECT_PACKAGE, "observedVersion": observed_version},
            "rawFixturesRedistributed": False,
            "intermediateJsonRetained": False,
        },
        "developmentHistory": [
            {
                "adapterVersion": "0.3.0",
                "files": 10,
                "accepted": 9,
                "typedRefusals": 1,
                "unexpectedErrors": 0,
                "failingFixture": "log_message_deduplication.eval",
                "convertedLogVersion": 3,
                "issueCode": "SOVA-INSPECT-VERSION",
                "disposition": (
                    "Retained failure. Adapter 0.4.0 accepts v3 only when pooled "
                    "events_data is absent or null after official-reader expansion; "
                    "unexpanded condensed data still fails closed."
                ),
            }
        ],
        "summary": {
            "files": len(rows),
            "accepted": len(accepted),
            "typedRefusals": len(typed_refusals),
            "unexpectedErrors": len(unexpected),
            "sourceBytes": sum(row["sourceBytes"] for row in rows),
            "summaries": sum(row["summaryCount"] for row in accepted),
            "streamedSamples": sum(row["streamedSampleCount"] for row in accepted),
            "sourceEvents": sum(row["sourceEvents"] for row in accepted),
            "emittedEvents": sum(row["emittedEvents"] for row in accepted),
            "verifiedEvents": sum(row["verifiedEvents"] for row in accepted),
            "contentPolicyViolations": violations,
            "allAcceptedTracesVerified": all(
                row["emittedEvents"] == row["verifiedEvents"] for row in accepted
            ),
            "allAcceptedImportsDeclaredLossy": all(not row["lossless"] for row in accepted),
        },
        "rows": rows,
        "claimBoundary": (
            "Official Inspect 0.3.251 parsed and converted pinned public .eval fixtures. "
            "SOVA then consumed the official JSON view with content omission. This is "
            "same-team interoperability testing, not general format support, adoption, "
            "privacy certification, or an independently operated evaluation."
        ),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.corpus_root)
    summary = result["summary"]
    if summary["unexpectedErrors"] != 0:
        raise RuntimeError("unexpected Inspect .eval interoperability errors occurred")
    if summary["contentPolicyViolations"] != 0:
        raise RuntimeError("content omission policy violation occurred")
    RESULT.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(RESULT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
