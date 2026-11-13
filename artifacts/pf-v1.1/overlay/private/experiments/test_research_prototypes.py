"""Deterministic tests for private corrected Topics 04–06 prototypes."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from private.experiments.prototypes.conformance import (
    ConformanceStatus,
    ExecutorSemanticContract,
    ObservationRequirement,
    check_conformance,
)
from private.experiments.prototypes.fidelity import (
    ClaimSupport,
    EvidenceRequirement,
    RequirementStatus,
    assess_fidelity,
    build_disclosure_bundle,
    dependency_closure,
    verify_disclosed_events,
)
from private.experiments.prototypes.semantic import (
    ContextMode,
    ContextRule,
    PredicateOperator,
    SemanticOutcome,
    OutcomePredicate,
    TrialRecord,
    _clopper_pearson,
    decide_reproduction,
    estimate_by_stratum,
    estimate_reproduction,
    evaluate_contract,
)


def _events() -> list[dict[str, object]]:
    return [
        {
            "id": "event-0",
            "sequence": 0,
            "kind": "prompt.sent",
            "parents": [],
            "payload": {"text": "blue owl"},
            "redactions": [],
        },
        {
            "id": "event-1",
            "sequence": 1,
            "kind": "tool.completed",
            "parents": ["event-0"],
            "payload": {"outcome": {"status": "succeeded", "artifact": "canary"}},
            "redactions": [],
        },
        {
            "id": "event-2",
            "sequence": 2,
            "kind": "oracle.completed",
            "parents": ["event-1"],
            "payload": {"label": "unsafe-effect-observed"},
            "redactions": [],
        },
    ]


def _manifest(*, included: list[str] | None = None, dropped: int = 0) -> dict[str, object]:
    return {
        "captureProfile": "standard",
        "capturePolicy": {
            "includedFamilies": included or ["*"],
            "omittedFamilies": [],
            "droppedEventCount": dropped,
        },
    }


def _predicates() -> tuple[OutcomePredicate, ...]:
    return (
        OutcomePredicate("p1", "tool.completed", PredicateOperator.EXISTS),
        OutcomePredicate(
            "p2",
            "oracle.completed",
            PredicateOperator.EQUALS,
            path=("payload", "label"),
            expected="unsafe-effect-observed",
        ),
        OutcomePredicate(
            "p3",
            "tool.completed",
            PredicateOperator.ORDERED_BEFORE,
            other_kind="oracle.completed",
        ),
        OutcomePredicate("p4", "network.egress", PredicateOperator.ABSENT),
    )


def test_semantic_contract_distinguishes_equivalent_divergent_and_unknown() -> None:
    events = _events()
    equivalent = evaluate_contract(_predicates(), events)
    assert equivalent.outcome == SemanticOutcome.EQUIVALENT

    divergent_events = copy.deepcopy(events)
    divergent_events[2]["payload"] = {"label": "safe"}
    divergent = evaluate_contract(_predicates(), divergent_events)
    assert divergent.outcome == SemanticOutcome.DIVERGENT

    unknown = evaluate_contract(
        _predicates(),
        events,
        availability={"tool.": True, "oracle.": False, "network.": False},
    )
    assert unknown.outcome == SemanticOutcome.INCONCLUSIVE
    assert unknown.unknown == 3


def test_context_and_safety_precede_semantic_judgment() -> None:
    rules = (
        ContextRule(("model", "family"), ContextMode.EXACT),
        ContextRule(("runtime",), ContextMode.ONE_OF, allowed=("python", "node")),
        ContextRule(("temperature",), ContextMode.TOLERANCE, tolerance=0.05),
        ContextRule(("host",), ContextMode.RECORD),
    )
    source = {
        "model": {"family": "scripted"},
        "runtime": "python",
        "temperature": 0.2,
        "host": "one",
    }
    compatible = {**source, "temperature": 0.22, "host": "two"}
    decision = decide_reproduction(
        predicates=_predicates(),
        events=_events(),
        source_context=source,
        candidate_context=compatible,
        context_rules=rules,
    )
    assert decision.outcome == SemanticOutcome.EQUIVALENT
    assert decision.context.status.value == "drifted"

    incompatible = {**compatible, "model": {"family": "different"}}
    decision = decide_reproduction(
        predicates=_predicates(),
        events=_events(),
        source_context=source,
        candidate_context=incompatible,
        context_rules=rules,
    )
    assert decision.outcome == SemanticOutcome.INCOMPATIBLE
    assert decision.contract is None

    unsafe = decide_reproduction(
        predicates=_predicates(),
        events=_events(),
        source_context=source,
        candidate_context=compatible,
        context_rules=rules,
        safe_to_compare=False,
    )
    assert unsafe.outcome == SemanticOutcome.UNSAFE


def test_reproduction_estimate_retains_all_nonconclusive_categories() -> None:
    outcomes = (
        SemanticOutcome.EQUIVALENT,
        SemanticOutcome.EQUIVALENT,
        SemanticOutcome.DIVERGENT,
        SemanticOutcome.INCONCLUSIVE,
        SemanticOutcome.INCOMPATIBLE,
        SemanticOutcome.UNSAFE,
        SemanticOutcome.EVIDENCE_INVALID,
    )
    trials = [
        TrialRecord(
            f"trial-{index}",
            outcome,
            "windows" if index % 2 else "linux",
            "deterministic",
            "sha256:" + hashlib.sha256(str(index).encode()).hexdigest(),
        )
        for index, outcome in enumerate(outcomes)
    ]
    estimate = estimate_reproduction(trials)
    assert estimate.conclusive_rate == pytest.approx(2 / 3)
    assert estimate.exact_low is not None and estimate.exact_high is not None
    assert estimate.exact_low <= estimate.conclusive_rate <= estimate.exact_high
    assert estimate.identification_low == pytest.approx(1 / 2)
    assert estimate.identification_high == pytest.approx(3 / 4)
    assert estimate.incompatible == estimate.unsafe == estimate.evidence_invalid == 1
    assert set(estimate_by_stratum(trials)) == {"linux", "windows"}


def test_exact_binomial_interval_handles_extreme_counts() -> None:
    zero_low, zero_high = _clopper_pearson(0, 10)
    full_low, full_high = _clopper_pearson(10, 10)
    assert zero_low == 0.0
    assert zero_high == pytest.approx(0.3084971078)
    assert full_low == pytest.approx(0.6915028922)
    assert full_high == 1.0


def test_fidelity_propagates_capture_redaction_integrity_and_relationships() -> None:
    requirements = (
        EvidenceRequirement("tool", "tool.completed", parent_kind="prompt.sent"),
        EvidenceRequirement("oracle", "oracle.completed", parent_kind="tool.completed"),
    )
    supported = assess_fidelity(
        claim_id="claim-1",
        requirements=requirements,
        manifest=_manifest(),
        events=_events(),
        integrity_valid=True,
        signature_verified=True,
    )
    assert supported.support == ClaimSupport.SUPPORTED

    redacted_events = copy.deepcopy(_events())
    redacted_events[2]["redactions"] = [{"path": "$.label", "method": "omitted"}]
    redacted = assess_fidelity(
        claim_id="claim-1",
        requirements=requirements,
        manifest=_manifest(),
        events=redacted_events,
        integrity_valid=True,
    )
    assert redacted.support == ClaimSupport.INCONCLUSIVE
    assert redacted.assessments[1].status == RequirementStatus.REDACTED

    omitted = assess_fidelity(
        claim_id="claim-1",
        requirements=requirements,
        manifest=_manifest(included=["tool."]),
        events=_events()[:2],
        integrity_valid=True,
    )
    assert omitted.support == ClaimSupport.INCONCLUSIVE
    assert omitted.assessments[1].status == RequirementStatus.OMITTED

    invalid = assess_fidelity(
        claim_id="claim-1",
        requirements=requirements,
        manifest=_manifest(),
        events=_events(),
        integrity_valid=False,
    )
    assert invalid.support == ClaimSupport.INCONCLUSIVE
    assert all(item.status == RequirementStatus.INVALID for item in invalid.assessments)


def test_disclosure_dependency_closure_and_commitments() -> None:
    events = _events()
    assert dependency_closure(events, seed_event_ids=["event-2"]) == (
        "event-0",
        "event-1",
        "event-2",
    )
    counter = 0

    def nonce_factory(size: int) -> bytes:
        nonlocal counter
        counter += 1
        return bytes([counter]) * size

    bundle = build_disclosure_bundle(
        claim_id="claim-1",
        source_trace_digest="sha256:" + "0" * 64,
        events=events,
        disclose_event_ids=["event-2"],
        nonce_factory=nonce_factory,
    )
    assert verify_disclosed_events(bundle)
    tampered = copy.deepcopy(bundle)
    visible = next(item for item in tampered.commitments if item.event is not None)
    assert visible.event is not None
    visible.event["payload"] = {"tampered": True}  # type: ignore[index]
    assert not verify_disclosed_events(tampered)


def test_executor_conformance_rejects_adapter_self_attestation() -> None:
    contract = ExecutorSemanticContract(
        action="file.write",
        side_effect="mutate",
        allowed_terminal_statuses=("succeeded",),
        required_evidence_roles=("artifact",),
        observations=(
            ObservationRequirement(
                "written",
                "filesystem.observed",
                ("payload", "digest"),
                "sha256:" + "a" * 64,
            ),
        ),
    )
    request = {"action": "file.write"}
    provider = {
        "status": "succeeded",
        "side_effect": "mutate",
        "evidence": [{"role": "artifact"}],
    }
    no_observation = check_conformance(
        contract=contract,
        request=request,
        provider_outcome=provider,
        observations=[],
    )
    assert no_observation.status == ConformanceStatus.INCONCLUSIVE

    no_terminal_outcome = check_conformance(
        contract=contract,
        request=request,
        provider_outcome={},
        observations=[],
    )
    assert no_terminal_outcome.status == ConformanceStatus.INCONCLUSIVE

    contradicted = check_conformance(
        contract=contract,
        request=request,
        provider_outcome=provider,
        observations=[
            {
                "producer": "sova-observer",
                "kind": "filesystem.observed",
                "payload": {"digest": "sha256:" + "b" * 64},
            }
        ],
    )
    assert contradicted.status == ConformanceStatus.NONCONFORMANT

    conformant = check_conformance(
        contract=contract,
        request=request,
        provider_outcome=provider,
        observations=[
            {
                "producer": "sova-observer",
                "kind": "filesystem.observed",
                "payload": {"digest": "sha256:" + "a" * 64},
            }
        ],
    )
    assert conformant.status == ConformanceStatus.CONFORMANT


def test_private_files_remain_outside_public_git_index() -> None:
    assert Path(__file__).parts[-3:-1] == ("private", "experiments")
