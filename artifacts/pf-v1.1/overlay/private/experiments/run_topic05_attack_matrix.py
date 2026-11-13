"""Run the private Topic 05 adversarial trace matrix.

This harness reuses exact public hostile-input tests and adds two deliberate
negative controls: replay and signer equivocation are not detectable from one
offline trace without external freshness or transparency state.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from sova.formats import canonical_json_bytes, sha256_digest
from sova.formats.errors import FormatError
from sova.trace import TraceReader, TraceWriter, generate_ed25519_keypair
from sova.trace.redaction import RedactionPolicy

ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "private"
    / "experiments"
    / "results"
    / "topic05-attack-matrix-2026-07-31.json"
)

PYTEST_CASES = {
    "corrupted-event": [
        "tests/unit/test_trace.py::test_recovery_rejects_corrupt_events",
    ],
    "truncated-trace": [
        "tests/unit/test_trace.py::test_recovery_preserves_only_valid_prefix_and_reports_tail",
    ],
    "reordered-events": [
        "tests/unit/test_trace.py::test_reordering_is_detected_even_if_package_descriptor_is_recomputed",
    ],
    "substituted-content": [
        "tests/unit/test_trace.py::test_package_level_event_substitution_is_detected",
        "tests/integration/test_independent_verifier.py::test_independent_process_fails_visibly_on_substitution",
    ],
    "privacy-leakage": [
        "tests/unit/test_trace_redaction.py::test_default_redaction_omits_secret_values_before_persistence",
        "tests/unit/test_trace_redaction.py::test_redaction_verifier_rejects_inconsistent_or_residual_secrets",
    ],
    "malicious-archive": [
        "tests/unit/test_format_edge_cases.py::test_reader_rejects_empty_duplicate_and_resource_hostile_archives",
        "tests/unit/test_format_edge_cases.py::test_unsafe_package_paths_fail",
    ],
    "parser-differential": [
        "tests/compat/schemas/test_validator_parity.py",
        "tests/unit/test_format_canonical.py",
    ],
    "signature-confusion": [
        "tests/unit/test_trace.py::test_signature_material_failure_modes_are_typed",
        "tests/unit/test_trace.py::test_signature_substitution_is_detected",
        "tests/unit/test_trace.py::test_signed_statement_shape_and_binding_are_verified",
    ],
    "hostile-extension": [
        "tests/unit/test_capsule.py::test_undeclared_member_is_rejected",
        "tests/unit/test_format_edge_cases.py::test_reader_manifest_and_object_index_failure_modes",
    ],
}


def _run_pytest_cases(scratch: Path) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name, node_ids in PYTEST_CASES.items():
        base = scratch / f"{name}-base"
        cache = scratch / f"{name}-cache"
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                *node_ids,
                "--basetemp",
                str(base),
                "-o",
                f"cache_dir={cache}",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        results[name] = {
            "outcome": "detected-or-rejected" if completed.returncode == 0 else "harness-failed",
            "passed": completed.returncode == 0,
            "testNodeIds": node_ids,
            "returnCode": completed.returncode,
        }
    return results


def _low_entropy_commitment() -> dict[str, Any]:
    try:
        RedactionPolicy(method="keyed-commitment", commitment_key=b"guessable")
    except FormatError as error:
        return {
            "outcome": "rejected-before-capture",
            "passed": error.issue.code == "SOVA-REDACTION-KEY",
            "failureCode": error.issue.code,
        }
    return {
        "outcome": "unexpectedly-accepted",
        "passed": False,
        "failureCode": None,
    }


def _replay_and_equivocation_controls(scratch: Path) -> dict[str, Any]:
    key = generate_ed25519_keypair()
    original = scratch / "original.sova-trace"
    replay = scratch / "replay.sova-trace"
    conflicting = scratch / "conflicting.sova-trace"

    writer = TraceWriter(original, signing_key=key)
    writer.append("run.started", {"case": "original"})
    writer.finalize()
    shutil.copyfile(original, replay)

    conflicting_writer = TraceWriter(conflicting, signing_key=key)
    conflicting_writer.append("run.started", {"case": "conflicting"})
    conflicting_writer.finalize()

    original_report = TraceReader(original).verify(require_signature=True)
    replay_report = TraceReader(replay).verify(require_signature=True)
    conflicting_report = TraceReader(conflicting).verify(require_signature=True)
    original_digest = sha256_digest(canonical_json_bytes(TraceReader(original).manifest()))
    replay_digest = sha256_digest(canonical_json_bytes(TraceReader(replay).manifest()))
    conflicting_digest = sha256_digest(canonical_json_bytes(TraceReader(conflicting).manifest()))
    all_valid = bool(
        original_report.signature_valid
        and replay_report.signature_valid
        and conflicting_report.signature_valid
    )
    return {
        "replayed-trace": {
            "outcome": "not-detectable-by-single-trace-offline-verification",
            "passed": all_valid and original_digest == replay_digest,
            "bounded": True,
            "requiredExternalControl": "freshness policy, nonce registry, timestamp service, or transparency log",
        },
        "signer-equivocation": {
            "outcome": "not-detectable-by-single-trace-offline-verification",
            "passed": all_valid and original_digest != conflicting_digest,
            "bounded": True,
            "requiredExternalControl": "trusted transparency log or other consistency monitor",
        },
    }


def main() -> int:
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sova-topic05-attacks-", dir=RESULT.parent) as raw:
        scratch = Path(raw)
        attacks = _run_pytest_cases(scratch)
        attacks["low-entropy-commitment"] = _low_entropy_commitment()
        attacks.update(_replay_and_equivocation_controls(scratch))

    all_passed = all(bool(item["passed"]) for item in attacks.values())
    result = {
        "artifactType": "sova.private-trace-attack-matrix",
        "protocol": "sova.topic05.attacks/0.1",
        "generatedAt": "2026-07-31",
        "allDetectedRejectedOrCorrectlyBounded": all_passed,
        "attackCount": len(attacks),
        "attacks": attacks,
        "limitations": [
            "The matrix is synthetic and team-authored.",
            "A passing public test establishes behavior for its exact fixture, not exhaustive security.",
            "Replay and signer equivocation intentionally remain outside single-trace offline detection.",
            "No external cryptographic or privacy reviewer participated.",
        ],
    }
    RESULT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "result": str(RESULT),
                "attackCount": len(attacks),
                "allDetectedRejectedOrCorrectlyBounded": all_passed,
                "outcomes": {name: item["outcome"] for name, item in attacks.items()},
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
