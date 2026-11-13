"""Run frozen post-build studies against the shipped Topic 12 and 13 code."""

from __future__ import annotations

import json
import platform
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sova.executors import (
    ActionOutcome,
    ActionRequest,
    CancellationToken,
    Capability,
    ExecutionContext,
    FailureCause,
    OutcomeStatus,
    SideEffect,
)
from sova.mcp import CapabilityExecutionBroker
from sova.replay import semantic_reproduction_study
from sova.trace import TraceWriter


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "private" / "experiments" / "results" / "topics12-13-postbuild-study-2026-08-03.json"


def _trace(path: Path, contract: str, response: str, *, oracle: bool = True) -> None:
    writer = TraceWriter(path)
    writer.append("model.response", {"text": response, "observableContract": contract})
    if oracle:
        writer.append(
            "oracle.completed",
            {"status": "pass", "results": [{"status": "pass", "expected": contract}]},
        )
    writer.finalize()


def _topic12_study(scratch: Path) -> dict[str, Any]:
    scratch.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    classification_counts: dict[str, int] = {}
    for contract_index in range(12):
        contract = f"observable-{contract_index:02d}"
        reference = scratch / f"{contract}-reference.sova-trace"
        _trace(reference, contract, f"reference surface text {contract_index}")
        candidates: list[Path] = []
        expected: list[str] = []
        conditions: list[str] = []
        for index in range(8):
            candidate = scratch / f"{contract}-candidate-{index}.sova-trace"
            if index < 4:
                _trace(candidate, contract, f"non-material text {contract_index}-{index}")
                expected.append("reproduced")
                conditions.append("equivalent-runtime-drift")
            elif index < 6:
                _trace(
                    candidate,
                    f"different-{contract_index}-{index}",
                    f"non-material text {contract_index}-{index}",
                )
                expected.append("not-reproduced")
                conditions.append("material-outcome-drift")
            else:
                _trace(
                    candidate,
                    contract,
                    f"non-material text {contract_index}-{index}",
                    oracle=False,
                )
                expected.append("inconclusive")
                conditions.append("missing-required-evidence")
            candidates.append(candidate)

        report = semantic_reproduction_study(
            reference,
            tuple(candidates),
            conditions=tuple(conditions),
        )
        observed = [
            "inconclusive"
            if trial.reproduced is None
            else ("reproduced" if trial.reproduced else "not-reproduced")
            for trial in report.trials
        ]
        exact_bytes = sum(reference.read_bytes() == candidate.read_bytes() for candidate in candidates)
        report_mapping = report.to_mapping()
        classification_counts[report.classification.value] = (
            classification_counts.get(report.classification.value, 0) + 1
        )
        rows.append(
            {
                "contract": contract,
                "expected": expected,
                "observed": observed,
                "correct": observed == expected,
                "exactByteMatches": exact_bytes,
                "report": {
                    "classification": report_mapping["classification"],
                    "reproduced": report_mapping["reproduced"],
                    "eligible": report_mapping["eligible"],
                    "total": report_mapping["total"],
                    "inconclusive": report_mapping["inconclusive"],
                    "interval95": report_mapping["interval95"],
                    "sensitivity": report_mapping["sensitivity"],
                },
            }
        )
    correct = sum(row["correct"] for row in rows)
    return {
        "contracts": len(rows),
        "candidateTraces": len(rows) * 8,
        "correctContracts": correct,
        "decisionAccuracy": correct / len(rows),
        "acceptedIncompleteAsReproduced": sum(
            observed == "reproduced"
            for row in rows
            for observed, expected in zip(row["observed"], row["expected"], strict=True)
            if expected == "inconclusive"
        ),
        "exactByteMatches": sum(row["exactByteMatches"] for row in rows),
        "classificationCounts": classification_counts,
        "rows": rows,
        "gatePassed": correct == len(rows),
        "limitations": [
            "Synthetic same-team traces test shipped decision semantics only.",
            "No hosted model, independent runtime, or controlled provider re-execution was used.",
            "The public study uses Wilson intervals; it is not the complete private P4 mechanism.",
        ],
    }


@dataclass(slots=True)
class FixtureExecutor:
    executor_name: str
    action: str
    status: OutcomeStatus
    idempotent: bool
    verification: str
    retryable: bool

    @property
    def name(self) -> str:
        return self.executor_name

    def capabilities(self) -> tuple[Capability, ...]:
        return (
            Capability(
                self.action,
                "0.1",
                SideEffect.READ if self.idempotent else SideEffect.MUTATE,
                self.idempotent,
                ("post-observation",),
            ),
        )

    def execute(
        self,
        request: ActionRequest,
        context: ExecutionContext,
        cancellation: CancellationToken,
    ) -> ActionOutcome:
        del context, cancellation
        return ActionOutcome(
            request.id,
            self.status,
            SideEffect.READ if self.idempotent else SideEffect.MUTATE,
            {"executor": self.name},
            verification=self.verification,
            retryable=self.retryable,
            failure_cause=(
                FailureCause.NONE
                if self.status == OutcomeStatus.SUCCEEDED
                else FailureCause.EXECUTOR
            ),
        )


def _topic13_study(scratch: Path) -> dict[str, Any]:
    scratch.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    families = ("browser", "computer", "terminal")
    strata = (
        "verified-first",
        "unverified-then-fallback",
        "failed-retryable-fallback",
        "nonidempotent-stop",
    )
    for family in families:
        for stratum in strata:
            for index in range(6):
                idempotent = stratum != "nonidempotent-stop"
                action = f"{family}.{'snapshot' if idempotent else 'mutate'}"
                if stratum == "verified-first":
                    first = FixtureExecutor(
                        f"{family}-provider-a-{index}",
                        action,
                        OutcomeStatus.SUCCEEDED,
                        idempotent,
                        "post-action-observation",
                        False,
                    )
                    second = FixtureExecutor(
                        f"{family}-provider-b-{index}",
                        action,
                        OutcomeStatus.SUCCEEDED,
                        idempotent,
                        "post-action-observation",
                        False,
                    )
                    expected_status = OutcomeStatus.SUCCEEDED
                    expected_attempts = 1
                elif stratum == "unverified-then-fallback":
                    first = FixtureExecutor(
                        f"{family}-provider-a-{index}",
                        action,
                        OutcomeStatus.SUCCEEDED,
                        idempotent,
                        "provider-result-only",
                        False,
                    )
                    second = FixtureExecutor(
                        f"{family}-provider-b-{index}",
                        action,
                        OutcomeStatus.SUCCEEDED,
                        idempotent,
                        "post-action-observation",
                        False,
                    )
                    expected_status = OutcomeStatus.SUCCEEDED
                    expected_attempts = 2
                elif stratum == "failed-retryable-fallback":
                    first = FixtureExecutor(
                        f"{family}-provider-a-{index}",
                        action,
                        OutcomeStatus.FAILED,
                        idempotent,
                        "not-performed",
                        True,
                    )
                    second = FixtureExecutor(
                        f"{family}-provider-b-{index}",
                        action,
                        OutcomeStatus.SUCCEEDED,
                        idempotent,
                        "post-action-observation",
                        False,
                    )
                    expected_status = OutcomeStatus.SUCCEEDED
                    expected_attempts = 2
                else:
                    first = FixtureExecutor(
                        f"{family}-provider-a-{index}",
                        action,
                        OutcomeStatus.FAILED,
                        idempotent,
                        "not-performed",
                        True,
                    )
                    second = FixtureExecutor(
                        f"{family}-provider-b-{index}",
                        action,
                        OutcomeStatus.SUCCEEDED,
                        idempotent,
                        "post-action-observation",
                        False,
                    )
                    expected_status = OutcomeStatus.FAILED
                    expected_attempts = 1

                broker = CapabilityExecutionBroker((first, second), max_attempts=3)
                secret = f"SYNTHETIC-SECRET-{family}-{stratum}-{index}"
                outcome = broker.execute(
                    ActionRequest(f"request-{len(rows)}", action, {"session": secret}, 5),
                    ExecutionContext(scratch, {"decision": "allowed"}),
                    CancellationToken(),
                )
                broker_data = outcome.output["sovaBroker"]
                attempts = broker_data["attempts"]
                checkpoint = broker_data["checkpoint"]
                unverified_accepted = any(
                    item["verification"]["verified"] is False
                    and item["outcomeStatus"] == "succeeded"
                    and position == len(attempts) - 1
                    and outcome.status == OutcomeStatus.SUCCEEDED
                    for position, item in enumerate(attempts)
                )
                correct = (
                    outcome.status == expected_status
                    and len(attempts) == expected_attempts
                    and secret not in json.dumps(checkpoint)
                    and checkpoint["inputsPersisted"] is False
                    and checkpoint["sessionMaterialPersisted"] is False
                )
                rows.append(
                    {
                        "family": family,
                        "stratum": stratum,
                        "case": index,
                        "expectedStatus": expected_status.value,
                        "observedStatus": outcome.status.value,
                        "expectedAttempts": expected_attempts,
                        "observedAttempts": len(attempts),
                        "correct": correct,
                        "unverifiedAccepted": unverified_accepted,
                        "providerOnlyWouldAccept": first.status == OutcomeStatus.SUCCEEDED,
                        "attempts": attempts,
                        "checkpoint": checkpoint,
                    }
                )
    return {
        "cases": len(rows),
        "correctCases": sum(row["correct"] for row in rows),
        "decisionAccuracy": sum(row["correct"] for row in rows) / len(rows),
        "unverifiedProviderSuccessAccepted": sum(row["unverifiedAccepted"] for row in rows),
        "providerOnlySuccesses": sum(row["providerOnlyWouldAccept"] for row in rows),
        "brokerVerifiedSuccesses": sum(row["observedStatus"] == "succeeded" for row in rows),
        "nonIdempotentFallbackViolations": sum(
            row["stratum"] == "nonidempotent-stop" and row["observedAttempts"] != 1
            for row in rows
        ),
        "secretCheckpointViolations": sum(
            row["checkpoint"]["inputsPersisted"] is not False
            or row["checkpoint"]["sessionMaterialPersisted"] is not False
            for row in rows
        ),
        "rows": rows,
        "gatePassed": all(row["correct"] for row in rows),
        "limitations": [
            "All providers and expected outcomes are deterministic same-team fixtures.",
            "Verification labels are injected by fixture executors; observer truth is not established.",
            "The study tests broker invariants, not full P6 cross-provider conformance.",
        ],
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sova-topics12-13-") as directory:
        scratch = Path(directory)
        result = {
            "artifactType": "sova.private.topics12-13-postbuild-study",
            "schemaVersion": "0.1.0",
            "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "protocol": "private/experiments/topics-12-14-predeclared-protocol-2026-08-03.md",
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "networkUsed": False,
                "modelUsed": False,
                "gpuUsed": False,
            },
            "topic12": _topic12_study(scratch / "topic12"),
            "topic13": _topic13_study(scratch / "topic13"),
        }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "topic12GatePassed": result["topic12"]["gatePassed"],
                "topic13GatePassed": result["topic13"]["gatePassed"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
