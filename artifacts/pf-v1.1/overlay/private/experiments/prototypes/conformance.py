"""Private prototype: evidence-based executor semantic conformance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence


class ConformanceStatus(StrEnum):
    CONFORMANT = "conformant"
    NONCONFORMANT = "nonconformant"
    INCONCLUSIVE = "inconclusive"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ObservationRequirement:
    id: str
    kind: str
    path: tuple[str, ...]
    expected: Any


@dataclass(frozen=True, slots=True)
class ExecutorSemanticContract:
    action: str
    side_effect: str
    allowed_terminal_statuses: tuple[str, ...]
    required_evidence_roles: tuple[str, ...]
    observations: tuple[ObservationRequirement, ...]


@dataclass(frozen=True, slots=True)
class ConformanceResult:
    status: ConformanceStatus
    reasons: tuple[str, ...]
    satisfied_observations: tuple[str, ...]
    missing_observations: tuple[str, ...]


_MISSING = object()


def _at(value: Any, path: Sequence[str]) -> Any:
    current = value
    for component in path:
        if not isinstance(current, Mapping) or component not in current:
            return _MISSING
        current = current[component]
    return current


def check_conformance(
    *,
    contract: ExecutorSemanticContract,
    request: Mapping[str, Any],
    provider_outcome: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
) -> ConformanceResult:
    reasons: list[str] = []
    satisfied: list[str] = []
    missing: list[str] = []
    if request.get("action") != contract.action:
        return ConformanceResult(
            ConformanceStatus.NONCONFORMANT,
            ("portable action intent did not match the semantic contract",),
            (),
            (),
        )
    if not provider_outcome:
        return ConformanceResult(
            ConformanceStatus.INCONCLUSIVE,
            ("no terminal provider outcome was present in the observable trace prefix",),
            (),
            tuple(requirement.id for requirement in contract.observations),
        )
    status = provider_outcome.get("status")
    if status == "unsupported":
        return ConformanceResult(
            ConformanceStatus.UNSUPPORTED,
            ("executor reported the required action as unsupported",),
            (),
            tuple(requirement.id for requirement in contract.observations),
        )
    if status not in contract.allowed_terminal_statuses:
        reasons.append("terminal status was outside the contract")
    if provider_outcome.get("side_effect") != contract.side_effect:
        reasons.append("declared side effect did not match the contract")
    evidence = provider_outcome.get("evidence")
    roles = (
        {item.get("role") for item in evidence if isinstance(item, Mapping)}
        if isinstance(evidence, list)
        else set()
    )
    absent_roles = set(contract.required_evidence_roles) - roles
    if absent_roles:
        reasons.append(f"required evidence roles were absent: {sorted(absent_roles)}")

    sova_observations = [
        observation
        for observation in observations
        if observation.get("producer") == "sova-observer"
    ]
    for requirement in contract.observations:
        candidates = [
            observation
            for observation in sova_observations
            if observation.get("kind") == requirement.kind
        ]
        if not candidates:
            missing.append(requirement.id)
            continue
        if any(_at(observation, requirement.path) == requirement.expected for observation in candidates):
            satisfied.append(requirement.id)
        else:
            reasons.append(f"independent observation {requirement.id!r} contradicted the contract")

    if reasons:
        return ConformanceResult(
            ConformanceStatus.NONCONFORMANT,
            tuple(reasons),
            tuple(satisfied),
            tuple(missing),
        )
    if missing:
        return ConformanceResult(
            ConformanceStatus.INCONCLUSIVE,
            ("provider success was not accepted without required SOVA-owned observations",),
            tuple(satisfied),
            tuple(missing),
        )
    return ConformanceResult(
        ConformanceStatus.CONFORMANT,
        ("all provider constraints and independent observations satisfied the contract",),
        tuple(satisfied),
        (),
    )
