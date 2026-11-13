"""Run the post-result independently structured executor-harness study.

This is private, team-authored research evidence. The foreign provider process
does not import SOVA and its assertions are evaluated separately from a
parent-side filesystem observation.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from private.experiments.prototypes.conformance import (
    ConformanceStatus,
    ExecutorSemanticContract,
    ObservationRequirement,
    check_conformance,
)

RESULT = (
    REPOSITORY_ROOT
    / "private"
    / "experiments"
    / "results"
    / "topic06-independent-adapter-study-2026-07-31.json"
)
EXPECTED = b"portable-observed-effect"
EXPECTED_DIGEST = "sha256:" + hashlib.sha256(EXPECTED).hexdigest()
FOREIGN_PROVIDER = r"""
import json
import pathlib
import sys

request = json.loads(sys.stdin.readline())
variant = request["variant"]
target = pathlib.Path(request["target"])
if variant == "honest":
    target.write_bytes(b"portable-observed-effect")
    response = {
        "status": "succeeded",
        "side_effect": "mutate",
        "evidence": [{"role": "artifact"}],
    }
elif variant == "false-success":
    response = {
        "status": "succeeded",
        "side_effect": "mutate",
        "evidence": [{"role": "artifact"}],
    }
elif variant == "contradictory":
    target.write_bytes(b"different-observed-effect")
    response = {
        "status": "succeeded",
        "side_effect": "mutate",
        "evidence": [{"role": "artifact"}],
    }
elif variant == "unsupported":
    response = {
        "status": "unsupported",
        "side_effect": "mutate",
        "evidence": [],
    }
elif variant == "missing-evidence":
    target.write_bytes(b"portable-observed-effect")
    response = {
        "status": "succeeded",
        "side_effect": "mutate",
        "evidence": [],
    }
else:
    raise SystemExit("unknown variant")
sys.stdout.write(json.dumps(response, sort_keys=True) + "\n")
"""


def _observe(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        {
            "producer": "sova-observer",
            "kind": "artifact.observed",
            "payload": {
                "digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            },
        }
    ]


def _run_case(directory: Path, variant: str, index: int) -> dict[str, Any]:
    target = directory / f"{variant}-{index}.bin"
    request = {
        "action": "artifact.materialize",
        "target": str(target),
        "variant": variant,
    }
    completed = subprocess.run(
        [sys.executable, "-I", "-c", FOREIGN_PROVIDER],
        input=json.dumps(request) + "\n",
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
        cwd=directory,
    )
    if completed.returncode != 0:
        raise RuntimeError("foreign provider failed")
    provider = json.loads(completed.stdout)
    contract = ExecutorSemanticContract(
        action="artifact.materialize",
        side_effect="mutate",
        allowed_terminal_statuses=("succeeded",),
        required_evidence_roles=("artifact",),
        observations=(
            ObservationRequirement(
                "artifact-digest",
                "artifact.observed",
                ("payload", "digest"),
                EXPECTED_DIGEST,
            ),
        ),
    )
    result = check_conformance(
        contract=contract,
        request={"action": "artifact.materialize"},
        provider_outcome=provider,
        observations=_observe(target),
    )
    expected = {
        "honest": ConformanceStatus.CONFORMANT,
        "false-success": ConformanceStatus.INCONCLUSIVE,
        "contradictory": ConformanceStatus.NONCONFORMANT,
        "unsupported": ConformanceStatus.UNSUPPORTED,
        "missing-evidence": ConformanceStatus.NONCONFORMANT,
    }[variant]
    return {
        "id": f"{variant}-{index}",
        "variant": variant,
        "expected": expected.value,
        "observed": result.status.value,
        "passed": result.status == expected,
        "providerStatus": provider["status"],
        "independentObservationPresent": target.is_file(),
        "providerImportedSova": False,
    }


def main() -> int:
    variants = (
        "honest",
        "false-success",
        "contradictory",
        "unsupported",
        "missing-evidence",
    )
    with tempfile.TemporaryDirectory(prefix="sova-foreign-harness-") as raw:
        directory = Path(raw)
        rows = [
            _run_case(directory, variant, index)
            for variant in variants
            for index in range(6)
        ]
    report = {
        "artifactType": "sova.private-independent-adapter-study",
        "protocol": "topics-04-06-corrected/0.4",
        "generatedAt": "2026-07-31",
        "caseCount": len(rows),
        "casesPerVariant": dict(Counter(row["variant"] for row in rows)),
        "allPassed": all(row["passed"] for row in rows),
        "falseSuccessAcceptedAsConformant": any(
            row["variant"] == "false-success"
            and row["observed"] == ConformanceStatus.CONFORMANT.value
            for row in rows
        ),
        "rows": rows,
        "limitations": [
            "The foreign harness and labels were authored by the SOVA team.",
            "Only a local filesystem effect and subprocess boundary were tested.",
            "This is not evidence of third-party adoption or browser/computer portability.",
        ],
    }
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({key: report[key] for key in ("caseCount", "allPassed")}))
    return 0 if report["allPassed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
