"""Private prototype: contracted semantic reproduction and rate estimation.

This module is experiment code, not a released SOVA API or novelty claim.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Mapping, Sequence


class PredicateOperator(StrEnum):
    EXISTS = "exists"
    ABSENT = "absent"
    EQUALS = "equals"
    CONTAINS = "contains"
    COUNT_AT_LEAST = "count-at-least"
    ORDERED_BEFORE = "ordered-before"


class PredicateStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


class SemanticOutcome(StrEnum):
    EQUIVALENT = "equivalent"
    DIVERGENT = "divergent"
    INCONCLUSIVE = "inconclusive"
    INCOMPATIBLE = "incompatible"
    UNSAFE = "unsafe"
    EVIDENCE_INVALID = "evidence-invalid"


class ContextMode(StrEnum):
    EXACT = "exact"
    ONE_OF = "one-of"
    TOLERANCE = "tolerance"
    RECORD = "record"
    IGNORE = "ignore"


class ContextStatus(StrEnum):
    COMPATIBLE = "compatible"
    DRIFTED = "drifted"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class OutcomePredicate:
    id: str
    event_kind: str
    operator: PredicateOperator
    path: tuple[str, ...] = ()
    expected: Any = None
    minimum: int = 1
    other_kind: str | None = None
    required: bool = True


@dataclass(frozen=True, slots=True)
class PredicateResult:
    predicate_id: str
    status: PredicateStatus
    evidence_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class ContractEvaluation:
    outcome: SemanticOutcome
    predicate_results: tuple[PredicateResult, ...]
    passed: int
    failed: int
    unknown: int


@dataclass(frozen=True, slots=True)
class ContextRule:
    path: tuple[str, ...]
    mode: ContextMode
    allowed: tuple[Any, ...] = ()
    tolerance: float | None = None
    required: bool = True


@dataclass(frozen=True, slots=True)
class ContextResult:
    path: tuple[str, ...]
    status: ContextStatus
    source: Any
    candidate: Any
    reason: str


@dataclass(frozen=True, slots=True)
class ContextEvaluation:
    status: ContextStatus
    results: tuple[ContextResult, ...]


@dataclass(frozen=True, slots=True)
class ReproductionDecision:
    outcome: SemanticOutcome
    contract: ContractEvaluation | None
    context: ContextEvaluation
    reason: str


@dataclass(frozen=True, slots=True)
class TrialRecord:
    id: str
    outcome: SemanticOutcome
    stratum: str
    judge: str
    evidence_digest: str


@dataclass(frozen=True, slots=True)
class ReproductionEstimate:
    successes: int
    divergences: int
    inconclusive: int
    incompatible: int
    unsafe: int
    evidence_invalid: int
    conclusive_rate: float | None
    wilson_low: float | None
    wilson_high: float | None
    exact_low: float | None
    exact_high: float | None
    identification_low: float | None
    identification_high: float | None
    method: str = "sova.reproduction-rate/exact-wilson-partial-identification-0.2"


_MISSING = object()


def _value_at(value: Any, path: Sequence[str]) -> Any:
    current = value
    for component in path:
        if not isinstance(current, Mapping) or component not in current:
            return _MISSING
        current = current[component]
    return current


def _is_kind_available(kind: str, availability: Mapping[str, bool] | None) -> bool:
    if availability is None:
        return True
    if kind in availability:
        return availability[kind]
    return any(kind.startswith(prefix) and present for prefix, present in availability.items())


def _event_id(event: Mapping[str, Any]) -> str:
    identifier = event.get("id")
    return str(identifier) if identifier is not None else "<unidentified>"


def evaluate_predicate(
    predicate: OutcomePredicate,
    events: Sequence[Mapping[str, Any]],
    *,
    availability: Mapping[str, bool] | None = None,
) -> PredicateResult:
    """Evaluate one deterministic observable predicate without hidden inference."""
    if not _is_kind_available(predicate.event_kind, availability):
        return PredicateResult(
            predicate.id,
            PredicateStatus.UNKNOWN,
            (),
            f"required event family {predicate.event_kind!r} was not observably available",
        )
    selected = [event for event in events if event.get("kind") == predicate.event_kind]
    evidence = tuple(_event_id(event) for event in selected)

    if predicate.operator == PredicateOperator.EXISTS:
        status = PredicateStatus.PASS if selected else PredicateStatus.FAIL
        return PredicateResult(predicate.id, status, evidence, f"observed {len(selected)} event(s)")
    if predicate.operator == PredicateOperator.ABSENT:
        status = PredicateStatus.PASS if not selected else PredicateStatus.FAIL
        return PredicateResult(predicate.id, status, evidence, f"observed {len(selected)} event(s)")
    if predicate.operator == PredicateOperator.COUNT_AT_LEAST:
        status = PredicateStatus.PASS if len(selected) >= predicate.minimum else PredicateStatus.FAIL
        return PredicateResult(
            predicate.id,
            status,
            evidence,
            f"observed {len(selected)}; required at least {predicate.minimum}",
        )
    if predicate.operator == PredicateOperator.ORDERED_BEFORE:
        if predicate.other_kind is None:
            raise ValueError("ordered-before predicate requires other_kind")
        if not _is_kind_available(predicate.other_kind, availability):
            return PredicateResult(
                predicate.id,
                PredicateStatus.UNKNOWN,
                evidence,
                f"comparison family {predicate.other_kind!r} was not observably available",
            )
        other = [event for event in events if event.get("kind") == predicate.other_kind]
        other_ids = tuple(_event_id(event) for event in other)
        if not selected or not other:
            return PredicateResult(
                predicate.id,
                PredicateStatus.FAIL,
                (*evidence, *other_ids),
                "one or both ordered event families were absent",
            )
        left = min(int(event.get("sequence", -1)) for event in selected)
        right = min(int(event.get("sequence", -1)) for event in other)
        status = PredicateStatus.PASS if left < right else PredicateStatus.FAIL
        return PredicateResult(
            predicate.id,
            status,
            (*evidence, *other_ids),
            f"first sequences were {left} and {right}",
        )

    values = [_value_at(event, predicate.path) for event in selected]
    visible = [value for value in values if value is not _MISSING]
    if not visible:
        return PredicateResult(
            predicate.id,
            PredicateStatus.UNKNOWN if selected else PredicateStatus.FAIL,
            evidence,
            "the required observable value was not available",
        )
    if predicate.operator == PredicateOperator.EQUALS:
        matched = any(value == predicate.expected for value in visible)
    elif predicate.operator == PredicateOperator.CONTAINS:
        matched = any(_contains(value, predicate.expected) for value in visible)
    else:
        raise ValueError(f"unsupported predicate operator: {predicate.operator}")
    return PredicateResult(
        predicate.id,
        PredicateStatus.PASS if matched else PredicateStatus.FAIL,
        evidence,
        "at least one observable value matched" if matched else "no observable value matched",
    )


def _contains(container: Any, expected: Any) -> bool:
    if isinstance(container, str) and isinstance(expected, str):
        return expected in container
    if isinstance(container, Mapping):
        return expected in container or expected in container.values()
    if isinstance(container, (list, tuple, set, frozenset)):
        return expected in container
    return False


def evaluate_contract(
    predicates: Sequence[OutcomePredicate],
    events: Sequence[Mapping[str, Any]],
    *,
    availability: Mapping[str, bool] | None = None,
) -> ContractEvaluation:
    results = tuple(
        evaluate_predicate(predicate, events, availability=availability)
        for predicate in predicates
    )
    required = [
        result
        for predicate, result in zip(predicates, results, strict=True)
        if predicate.required
    ]
    failed = sum(result.status == PredicateStatus.FAIL for result in required)
    unknown = sum(result.status == PredicateStatus.UNKNOWN for result in required)
    passed = sum(result.status == PredicateStatus.PASS for result in required)
    if failed:
        outcome = SemanticOutcome.DIVERGENT
    elif unknown:
        outcome = SemanticOutcome.INCONCLUSIVE
    else:
        outcome = SemanticOutcome.EQUIVALENT
    return ContractEvaluation(outcome, results, passed, failed, unknown)


def compare_context(
    source: Mapping[str, Any],
    candidate: Mapping[str, Any],
    rules: Sequence[ContextRule],
) -> ContextEvaluation:
    results: list[ContextResult] = []
    for rule in rules:
        left = _value_at(source, rule.path)
        right = _value_at(candidate, rule.path)
        if rule.mode == ContextMode.IGNORE:
            status = ContextStatus.COMPATIBLE
            reason = "dimension intentionally ignored"
        elif left is _MISSING or right is _MISSING:
            status = ContextStatus.UNKNOWN if rule.required else ContextStatus.DRIFTED
            reason = "one or both context values were not recorded"
        elif rule.mode == ContextMode.RECORD:
            status = ContextStatus.COMPATIBLE if left == right else ContextStatus.DRIFTED
            reason = "dimension is recorded but not compatibility-blocking"
        elif rule.mode == ContextMode.EXACT:
            status = ContextStatus.COMPATIBLE if left == right else ContextStatus.INCOMPATIBLE
            reason = "exact values match" if left == right else "exact values differ"
        elif rule.mode == ContextMode.ONE_OF:
            status = (
                ContextStatus.COMPATIBLE if right in rule.allowed else ContextStatus.INCOMPATIBLE
            )
            reason = "candidate is in the allowed set" if right in rule.allowed else "not allowed"
        elif rule.mode == ContextMode.TOLERANCE:
            if (
                isinstance(left, bool)
                or isinstance(right, bool)
                or not isinstance(left, (int, float))
                or not isinstance(right, (int, float))
                or rule.tolerance is None
            ):
                status = ContextStatus.UNKNOWN
                reason = "tolerance comparison lacked numeric values or tolerance"
            else:
                delta = abs(float(left) - float(right))
                status = (
                    ContextStatus.COMPATIBLE
                    if delta <= rule.tolerance
                    else ContextStatus.INCOMPATIBLE
                )
                reason = f"absolute difference {delta} versus tolerance {rule.tolerance}"
        else:
            raise ValueError(f"unsupported context mode: {rule.mode}")
        results.append(
            ContextResult(
                rule.path,
                status,
                None if left is _MISSING else left,
                None if right is _MISSING else right,
                reason,
            )
        )
    statuses = {result.status for result in results}
    if ContextStatus.INCOMPATIBLE in statuses:
        aggregate = ContextStatus.INCOMPATIBLE
    elif ContextStatus.UNKNOWN in statuses:
        aggregate = ContextStatus.UNKNOWN
    elif ContextStatus.DRIFTED in statuses:
        aggregate = ContextStatus.DRIFTED
    else:
        aggregate = ContextStatus.COMPATIBLE
    return ContextEvaluation(aggregate, tuple(results))


def decide_reproduction(
    *,
    predicates: Sequence[OutcomePredicate],
    events: Sequence[Mapping[str, Any]],
    source_context: Mapping[str, Any],
    candidate_context: Mapping[str, Any],
    context_rules: Sequence[ContextRule],
    availability: Mapping[str, bool] | None = None,
    safe_to_compare: bool = True,
    evidence_valid: bool = True,
) -> ReproductionDecision:
    context = compare_context(source_context, candidate_context, context_rules)
    if not safe_to_compare:
        return ReproductionDecision(SemanticOutcome.UNSAFE, None, context, "comparison unsafe")
    if not evidence_valid:
        return ReproductionDecision(
            SemanticOutcome.EVIDENCE_INVALID,
            None,
            context,
            "evidence integrity or structure was invalid",
        )
    if context.status == ContextStatus.INCOMPATIBLE:
        return ReproductionDecision(
            SemanticOutcome.INCOMPATIBLE,
            None,
            context,
            "a required context dimension was incompatible",
        )
    contract = evaluate_contract(predicates, events, availability=availability)
    if context.status == ContextStatus.UNKNOWN and contract.outcome == SemanticOutcome.EQUIVALENT:
        return ReproductionDecision(
            SemanticOutcome.INCONCLUSIVE,
            contract,
            context,
            "behavior matched but required context equivalence was unknown",
        )
    return ReproductionDecision(contract.outcome, contract, context, "contract evaluated")


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        raise ValueError("Wilson interval requires at least one conclusive trial")
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def _binomial_cdf(observed: int, total: int, probability: float) -> float:
    if observed < 0:
        return 0.0
    if observed >= total:
        return 1.0
    return sum(
        math.comb(total, value)
        * probability**value
        * (1.0 - probability) ** (total - value)
        for value in range(observed + 1)
    )


def _clopper_pearson(
    successes: int,
    total: int,
    alpha: float = 0.05,
) -> tuple[float, float]:
    """Return a two-sided exact binomial interval through tail inversion."""
    if total <= 0:
        raise ValueError("exact interval requires at least one conclusive trial")
    if successes < 0 or successes > total:
        raise ValueError("successes must be between zero and total")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between zero and one")

    if successes == 0:
        lower = 0.0
    else:
        low, high = 0.0, successes / total
        target = 1.0 - alpha / 2.0
        for _ in range(80):
            midpoint = (low + high) / 2.0
            if _binomial_cdf(successes - 1, total, midpoint) > target:
                low = midpoint
            else:
                high = midpoint
        lower = (low + high) / 2.0

    if successes == total:
        upper = 1.0
    else:
        low, high = successes / total, 1.0
        target = alpha / 2.0
        for _ in range(80):
            midpoint = (low + high) / 2.0
            if _binomial_cdf(successes, total, midpoint) > target:
                low = midpoint
            else:
                high = midpoint
        upper = (low + high) / 2.0
    return lower, upper


def estimate_reproduction(trials: Iterable[TrialRecord]) -> ReproductionEstimate:
    records = tuple(trials)
    counts = {outcome: 0 for outcome in SemanticOutcome}
    for record in records:
        counts[record.outcome] += 1
    successes = counts[SemanticOutcome.EQUIVALENT]
    divergences = counts[SemanticOutcome.DIVERGENT]
    inconclusive = counts[SemanticOutcome.INCONCLUSIVE]
    conclusive = successes + divergences
    eligible = conclusive + inconclusive
    if conclusive:
        rate = successes / conclusive
        low, high = _wilson(successes, conclusive)
        exact_low, exact_high = _clopper_pearson(successes, conclusive)
    else:
        rate = low = high = None
        exact_low = exact_high = None
    if eligible:
        identification_low = successes / eligible
        identification_high = (successes + inconclusive) / eligible
    else:
        identification_low = identification_high = None
    return ReproductionEstimate(
        successes=successes,
        divergences=divergences,
        inconclusive=inconclusive,
        incompatible=counts[SemanticOutcome.INCOMPATIBLE],
        unsafe=counts[SemanticOutcome.UNSAFE],
        evidence_invalid=counts[SemanticOutcome.EVIDENCE_INVALID],
        conclusive_rate=rate,
        wilson_low=low,
        wilson_high=high,
        exact_low=exact_low,
        exact_high=exact_high,
        identification_low=identification_low,
        identification_high=identification_high,
    )


def estimate_by_stratum(
    trials: Iterable[TrialRecord],
) -> dict[str, ReproductionEstimate]:
    grouped: dict[str, list[TrialRecord]] = {}
    for trial in trials:
        grouped.setdefault(trial.stratum, []).append(trial)
    return {stratum: estimate_reproduction(records) for stratum, records in sorted(grouped.items())}
