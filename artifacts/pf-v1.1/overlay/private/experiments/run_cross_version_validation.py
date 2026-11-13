"""Collect one isolated supported-Python validation record.

The parent shell invokes this module once per supported Python minor version.
It records only stable decision outputs; wall-clock and benchmark timings are
deliberately excluded from cross-version equality checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
INTEGRATED_RESULT = (
    ROOT
    / "private"
    / "experiments"
    / "results"
    / "integrated-baseline-drift-study-2026-07-31.json"
)
VERTICAL_RESULT = (
    ROOT
    / "private"
    / "experiments"
    / "results"
    / "topic06-no-atlas-vertical-study-2026-07-31.json"
)


def _run(*args: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=900,
    )
    return {
        "returnCode": completed.returncode,
        "stdoutDigest": hashlib.sha256(completed.stdout.encode()).hexdigest(),
        "stderrDigest": hashlib.sha256(completed.stderr.encode()).hexdigest(),
        "stdoutLines": len(completed.stdout.splitlines()),
        "stderrLines": len(completed.stderr.splitlines()),
    }


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _integrated_slice(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "integratedMetrics": value["integratedMetrics"],
        "inspectDirectMetrics": value["inspectDirectMetrics"],
        "driftAndMigration": value["driftAndMigration"],
    }


def _vertical_slice(value: dict[str, Any]) -> dict[str, Any]:
    rows = []
    stable_fields = (
        "scriptedStatus",
        "localStatus",
        "scriptedOracle",
        "localOracle",
        "declaredOutcomeEquivalent",
        "scriptedTraceVerified",
        "localTraceVerified",
        "scriptedTraceIndependent",
        "localTraceIndependent",
        "evidenceCapsuleIndependent",
        "playbackNonEmpty",
        "renderedObjectCount",
    )
    for row in value["rows"]:
        rows.append({key: row.get(key) for key in stable_fields})
    return {
        "cases": value["cases"],
        "traces": value["traces"],
        "capsules": value["capsules"],
        "checks": value["checks"],
        "passed": value["passed"],
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    commands = {
        "researchTests": _run(
            "-m",
            "pytest",
            "-q",
            "private/experiments/test_integrated_research.py",
            "private/experiments/test_research_prototypes.py",
        ),
        "integratedStudy": _run(
            "-m",
            "private.experiments.run_integrated_baseline_study",
        ),
        "verticalStudy": _run(
            "-m",
            "private.experiments.run_no_atlas_vertical_study",
        ),
    }
    if any(result["returnCode"] != 0 for result in commands.values()):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "artifactType": "sova.private-cross-version-run",
                    "python": platform.python_version(),
                    "implementation": platform.python_implementation(),
                    "commands": commands,
                    "passed": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return 1

    integrated = _integrated_slice(
        json.loads(INTEGRATED_RESULT.read_text(encoding="utf-8"))
    )
    vertical = _vertical_slice(
        json.loads(VERTICAL_RESULT.read_text(encoding="utf-8"))
    )
    report = {
        "artifactType": "sova.private-cross-version-run",
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "commands": commands,
        "integrated": integrated,
        "integratedDigest": _canonical_digest(integrated),
        "vertical": vertical,
        "verticalDigest": _canonical_digest(vertical),
        "passed": True,
        "limitations": [
            "The runtimes executed on one physical Windows host.",
            "Subprocess output digests are diagnostic and are not expected to match.",
            "Cross-machine evidence remains public-CI evidence for public mechanisms only.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
