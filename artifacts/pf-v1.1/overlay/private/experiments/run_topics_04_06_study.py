"""Run the predeclared deterministic corrected Topics 04–06 study.

The output is private research evidence. It is not a public benchmark claim.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from sova.formats import canonical_json_bytes

from private.experiments.prototypes.conformance import (
    ConformanceStatus,
    ExecutorSemanticContract,
    ObservationRequirement,
    check_conformance,
)
from private.experiments.prototypes.fidelity import (
    ClaimSupport,
    EvidenceRequirement,
    assess_fidelity,
    build_disclosure_bundle,
    verify_disclosed_events,
)
from private.experiments.prototypes.semantic import (
    ContextMode,
    ContextRule,
    OutcomePredicate,
    PredicateOperator,
    SemanticOutcome,
    TrialRecord,
    _clopper_pearson,
    _wilson,
    decide_reproduction,
    estimate_reproduction,
)

ROOT = REPOSITORY_ROOT
RESULT = ROOT / "private" / "experiments" / "results" / "topics-04-06-study-2026-07-31.json"
SEED = 20_260_731
PROFILES = (
    "security",
    "evaluation",
    "trajectory",
    "interpretability",
    "incident",
    "publication",
)
SEMANTIC_LABELS = tuple(item.value for item in SemanticOutcome)
CONFORMANCE_LABELS = tuple(item.value for item in ConformanceStatus)
FIDELITY_LABELS = tuple(item.value for item in ClaimSupport)


def _event(
    sequence: int,
    kind: str,
    payload: Mapping[str, Any],
    *,
    parents: Sequence[str] = (),
    suffix: str = "",
) -> dict[str, Any]:
    return {
        "id": f"event-{sequence}{suffix}",
        "sequence": sequence,
        "kind": kind,
        "parents": list(parents),
        "payload": dict(payload),
        "redactions": [],
        "surface": {"runtimeNote": f"non-semantic-{sequence}{suffix}"},
    }


def _profile_case(profile: str, index: int) -> tuple[
    list[dict[str, Any]],
    tuple[OutcomePredicate, ...],
    dict[str, Any],
    dict[str, Any],
]:
    kind = {
        "security": "oracle.completed",
        "evaluation": "evaluation.completed",
        "trajectory": "trajectory.completed",
        "interpretability": "oracle.intervention",
        "incident": "finding.created",
        "publication": "evaluation.reproduced",
    }[profile]
    expected = {
        "security": "unsafe-effect-observed",
        "evaluation": "passed",
        "trajectory": "goal-effect",
        "interpretability": "behavior-shift",
        "incident": "incident-confirmed",
        "publication": "result-reproduced",
    }[profile]
    prompt = _event(0, "prompt.sent", {"text": f"case-{profile}-{index}"})
    action = _event(
        1,
        "tool.completed",
        {"outcome": {"status": "succeeded", "artifact": f"artifact-{index % 3}"}},
        parents=(prompt["id"],),
    )
    outcome = _event(2, kind, {"label": expected}, parents=(action["id"],))
    completion = _event(
        3,
        "run.completed",
        {"completion": "completed", "surfaceText": f"variant-{index % 5}"},
        parents=(outcome["id"],),
    )
    predicates = (
        OutcomePredicate(
            f"{profile}-label",
            kind,
            PredicateOperator.EQUALS,
            path=("payload", "label"),
            expected=expected,
        ),
        OutcomePredicate(
            f"{profile}-order",
            "tool.completed",
            PredicateOperator.ORDERED_BEFORE,
            other_kind=kind,
        ),
        OutcomePredicate(
            f"{profile}-no-egress",
            "network.egress",
            PredicateOperator.ABSENT,
        ),
    )
    source_context = {
        "model": {"family": "scripted-family"},
        "runtime": "python",
        "protocol": "0.1",
        "temperature": 0.2,
        "host": "creator",
    }
    candidate_context = {
        **source_context,
        "temperature": 0.2 + (index % 3) * 0.01,
        "host": f"receiver-{index % 4}",
    }
    return [prompt, action, outcome, completion], predicates, source_context, candidate_context


def _context_rules() -> tuple[ContextRule, ...]:
    return (
        ContextRule(("model", "family"), ContextMode.EXACT),
        ContextRule(("runtime",), ContextMode.ONE_OF, allowed=("python", "node")),
        ContextRule(("protocol",), ContextMode.EXACT),
        ContextRule(("temperature",), ContextMode.TOLERANCE, tolerance=0.05),
        ContextRule(("host",), ContextMode.RECORD),
    )


def _behavior_corpus() -> list[dict[str, Any]]:
    corpus: list[dict[str, Any]] = []
    transformations = tuple(SemanticOutcome)
    for profile in PROFILES:
        for index in range(24):
            source, predicates, source_context, candidate_context = _profile_case(profile, index)
            candidate = copy.deepcopy(source)
            label = transformations[index % len(transformations)]
            availability: dict[str, bool] | None = None
            safe = True
            evidence_valid = True
            if label == SemanticOutcome.EQUIVALENT:
                candidate[-1]["payload"]["surfaceText"] = f"different-words-{index}"
                candidate[1]["surface"]["runtimeNote"] = "different-mechanics"
            elif label == SemanticOutcome.DIVERGENT:
                candidate[2]["payload"]["label"] = "materially-different"
            elif label == SemanticOutcome.INCONCLUSIVE:
                availability = {str(candidate[2]["kind"]): False, "tool.": True, "network.": True}
            elif label == SemanticOutcome.INCOMPATIBLE:
                candidate_context["model"] = {"family": "incompatible-family"}
            elif label == SemanticOutcome.UNSAFE:
                safe = False
            elif label == SemanticOutcome.EVIDENCE_INVALID:
                evidence_valid = False
            decision = decide_reproduction(
                predicates=predicates,
                events=candidate,
                source_context=source_context,
                candidate_context=candidate_context,
                context_rules=_context_rules(),
                availability=availability,
                safe_to_compare=safe,
                evidence_valid=evidence_valid,
            )
            no_context = decide_reproduction(
                predicates=predicates,
                events=candidate,
                source_context=source_context,
                candidate_context=candidate_context,
                context_rules=(),
                availability=availability,
                safe_to_compare=safe,
                evidence_valid=evidence_valid,
            )
            no_evidence_gate = decide_reproduction(
                predicates=predicates,
                events=candidate,
                source_context=source_context,
                candidate_context=candidate_context,
                context_rules=_context_rules(),
                availability=availability,
                safe_to_compare=safe,
                evidence_valid=True,
            )
            source_digest = hashlib.sha256(canonical_json_bytes(source)).hexdigest()
            candidate_digest = hashlib.sha256(canonical_json_bytes(candidate)).hexdigest()
            corpus.append(
                {
                    "id": f"{profile}-{index:03d}",
                    "profile": profile,
                    "truth": label.value,
                    "candidate": decision.outcome.value,
                    "exact_trace": (
                        SemanticOutcome.EQUIVALENT.value
                        if source_digest == candidate_digest
                        else SemanticOutcome.DIVERGENT.value
                    ),
                    "final_payload": (
                        SemanticOutcome.EQUIVALENT.value
                        if source[-1]["payload"] == candidate[-1]["payload"]
                        else SemanticOutcome.DIVERGENT.value
                    ),
                    "terminal_status": (
                        SemanticOutcome.EQUIVALENT.value
                        if source[-1]["payload"]["completion"]
                        == candidate[-1]["payload"]["completion"]
                        else SemanticOutcome.DIVERGENT.value
                    ),
                    "untyped_kinds": (
                        SemanticOutcome.EQUIVALENT.value
                        if [event["kind"] for event in source]
                        == [event["kind"] for event in candidate]
                        else SemanticOutcome.DIVERGENT.value
                    ),
                    "no_context_envelope": no_context.outcome.value,
                    "no_evidence_validity": no_evidence_gate.outcome.value,
                    "inconclusive_as_failure": (
                        SemanticOutcome.DIVERGENT.value
                        if decision.outcome == SemanticOutcome.INCONCLUSIVE
                        else decision.outcome.value
                    ),
                    "inconclusive_as_success": (
                        SemanticOutcome.EQUIVALENT.value
                        if decision.outcome == SemanticOutcome.INCONCLUSIVE
                        else decision.outcome.value
                    ),
                }
            )
    return corpus


def _classification(
    rows: Sequence[Mapping[str, Any]],
    *,
    prediction: str,
    labels: Sequence[str],
) -> dict[str, Any]:
    per_class: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    correct = 0
    for label in labels:
        tp = sum(row["truth"] == label and row[prediction] == label for row in rows)
        fp = sum(row["truth"] != label and row[prediction] == label for row in rows)
        fn = sum(row["truth"] == label and row[prediction] != label for row in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
        f1_values.append(f1)
    correct = sum(row["truth"] == row[prediction] for row in rows)
    return {
        "accuracy": correct / len(rows),
        "macro_f1": sum(f1_values) / len(f1_values),
        "per_class": per_class,
        "confusion": {
            truth: {
                predicted: sum(
                    row["truth"] == truth and row[prediction] == predicted for row in rows
                )
                for predicted in labels
            }
            for truth in labels
        },
    }


def _decision_error_rates(
    rows: Sequence[Mapping[str, Any]],
    *,
    prediction: str,
    accepted_label: str,
    rejected_label: str,
) -> dict[str, Any]:
    false_accepts = sum(
        row["truth"] != accepted_label and row[prediction] == accepted_label for row in rows
    )
    accepted_negatives = sum(row["truth"] != accepted_label for row in rows)
    false_rejects = sum(
        row["truth"] == accepted_label and row[prediction] == rejected_label for row in rows
    )
    accepted_positives = sum(row["truth"] == accepted_label for row in rows)
    return {
        "false_accepts": false_accepts,
        "false_accept_rate": false_accepts / accepted_negatives if accepted_negatives else None,
        "false_rejects": false_rejects,
        "false_reject_rate": false_rejects / accepted_positives if accepted_positives else None,
        "denominators": {
            "nonaccepted_truth": accepted_negatives,
            "accepted_truth": accepted_positives,
        },
        "calibration": {
            "applicable": False,
            "reason": (
                "The deterministic prototype emits categorical decisions, not "
                "probabilistic confidence scores."
            ),
        },
    }


def _conformance_overhead() -> dict[str, Any]:
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
                "sha256:" + "a" * 64,
            ),
        ),
    )
    request = {"action": "artifact.materialize"}
    provider = {
        "status": "succeeded",
        "side_effect": "mutate",
        "evidence": [{"role": "artifact"}],
    }
    observations = [
        {
            "producer": "sova-observer",
            "kind": "artifact.observed",
            "payload": {"digest": "sha256:" + "a" * 64},
        }
    ]
    calls_per_batch = 100
    batches = 100
    batch_microseconds: list[float] = []
    for _ in range(batches):
        started = time.perf_counter_ns()
        for _ in range(calls_per_batch):
            result = check_conformance(
                contract=contract,
                request=request,
                provider_outcome=provider,
                observations=observations,
            )
            if result.status != ConformanceStatus.CONFORMANT:
                raise AssertionError("reference conformance case changed during timing")
        elapsed = time.perf_counter_ns() - started
        batch_microseconds.append(elapsed / 1_000 / calls_per_batch)
    ordered = sorted(batch_microseconds)
    return {
        "reference_machine_only": True,
        "calls": calls_per_batch * batches,
        "batches": batches,
        "calls_per_batch": calls_per_batch,
        "mean_microseconds_per_call": sum(ordered) / len(ordered),
        "median_microseconds_per_call": ordered[len(ordered) // 2],
        "p95_microseconds_per_call": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "limitations": [
            "This isolates the in-process decision function and excludes executor, I/O, and trace cost.",
            "The result is engineering evidence from one CPU, not a public performance claim.",
        ],
    }


def _wilson_coverage() -> dict[str, Any]:
    randomizer = random.Random(SEED)
    grid = [(p, n) for p in (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95) for n in (10, 20, 50, 100)]
    repeats = 2_000
    covered = 0
    total = 0
    cells: list[dict[str, Any]] = []
    for probability, sample_size in grid:
        cell_covered = 0
        for _ in range(repeats):
            successes = sum(randomizer.random() < probability for _ in range(sample_size))
            low, high = _wilson(successes, sample_size)
            cell_covered += low <= probability <= high
        coverage = cell_covered / repeats
        covered += cell_covered
        total += repeats
        cells.append({"p": probability, "n": sample_size, "coverage": coverage})
    return {
        "seed": SEED,
        "repeats_per_cell": repeats,
        "aggregate_coverage": covered / total,
        "minimum_cell_coverage": min(cell["coverage"] for cell in cells),
        "cells": cells,
    }


def _analytic_interval_coverage(
    interval: Callable[[int, int], tuple[float, float]],
) -> dict[str, Any]:
    grid = [(p, n) for p in (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95) for n in (10, 20, 50, 100)]
    cells: list[dict[str, Any]] = []
    for probability, sample_size in grid:
        coverage = 0.0
        for successes in range(sample_size + 1):
            low, high = interval(successes, sample_size)
            if low <= probability <= high:
                coverage += (
                    math.comb(sample_size, successes)
                    * probability**successes
                    * (1.0 - probability) ** (sample_size - successes)
                )
        cells.append({"p": probability, "n": sample_size, "coverage": coverage})
    return {
        "aggregate_coverage": sum(cell["coverage"] for cell in cells) / len(cells),
        "minimum_cell_coverage": min(cell["coverage"] for cell in cells),
        "cells": cells,
    }


def _fidelity_corpus() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(120):
        prompt = _event(0, "prompt.sent", {"text": f"case-{index}"})
        tool = _event(
            1,
            "tool.completed",
            {"outcome": {"status": "succeeded"}},
            parents=(prompt["id"],),
        )
        oracle = _event(
            2,
            "oracle.completed",
            {"label": "observed"},
            parents=(tool["id"],),
        )
        events = [prompt, tool, oracle]
        requirements = (
            EvidenceRequirement("tool", "tool.completed", parent_kind="prompt.sent"),
            EvidenceRequirement("oracle", "oracle.completed", parent_kind="tool.completed"),
        )
        variant = index % 6
        integrity_valid = True
        signature_verified: bool | None = True
        included = ["*"]
        truth = ClaimSupport.SUPPORTED
        if variant == 1:
            oracle["redactions"] = [{"path": "$.label", "method": "omitted"}]
            truth = ClaimSupport.INCONCLUSIVE
        elif variant == 2:
            events = events[:2]
            included = ["prompt.", "tool."]
            truth = ClaimSupport.INCONCLUSIVE
        elif variant == 3:
            integrity_valid = False
            truth = ClaimSupport.INCONCLUSIVE
        elif variant == 4:
            oracle["parents"] = []
            truth = ClaimSupport.INCONCLUSIVE
        elif variant == 5:
            signature_verified = False
            truth = ClaimSupport.INCONCLUSIVE
        manifest = {
            "captureProfile": "standard" if index % 2 else "forensic",
            "capturePolicy": {
                "includedFamilies": included,
                "omittedFamilies": [] if "*" in included else ["all-unlisted-families"],
                "droppedEventCount": 0,
            },
        }
        report = assess_fidelity(
            claim_id=f"claim-{index}",
            requirements=requirements,
            manifest=manifest,
            events=events,
            integrity_valid=integrity_valid,
            signature_verified=signature_verified,
        )
        no_causal_requirements = tuple(
            EvidenceRequirement(
                requirement.id,
                requirement.event_kind,
                minimum=requirement.minimum,
                require_full_content=requirement.require_full_content,
                allow_redacted=requirement.allow_redacted,
                mandatory=requirement.mandatory,
            )
            for requirement in requirements
        )
        no_causal = assess_fidelity(
            claim_id=f"claim-{index}-no-causal",
            requirements=no_causal_requirements,
            manifest=manifest,
            events=events,
            integrity_valid=integrity_valid,
            signature_verified=signature_verified,
        )
        no_content_requirements = tuple(
            EvidenceRequirement(
                requirement.id,
                requirement.event_kind,
                minimum=requirement.minimum,
                require_full_content=False,
                allow_redacted=True,
                mandatory=requirement.mandatory,
                parent_kind=requirement.parent_kind,
            )
            for requirement in requirements
        )
        no_content = assess_fidelity(
            claim_id=f"claim-{index}-no-content",
            requirements=no_content_requirements,
            manifest=manifest,
            events=events,
            integrity_valid=integrity_valid,
            signature_verified=signature_verified,
        )
        rows.append(
            {
                "id": f"fidelity-{index:03d}",
                "truth": truth.value,
                "candidate": report.support.value,
                "integrity_only": (
                    ClaimSupport.SUPPORTED.value
                    if integrity_valid
                    else ClaimSupport.INCONCLUSIVE.value
                ),
                "profile_only": (
                    ClaimSupport.SUPPORTED.value
                    if manifest["captureProfile"] in {"standard", "forensic"}
                    else ClaimSupport.INCONCLUSIVE.value
                ),
                "full_share": ClaimSupport.SUPPORTED.value,
                "no_causal_requirements": no_causal.support.value,
                "no_content_requirements": no_content.support.value,
            }
        )
    return rows


def _disclosure_attacks() -> dict[str, Any]:
    events = [
        _event(0, "prompt.sent", {"text": "trigger"}),
        _event(1, "telemetry.unrelated", {"private": "irrelevant"}),
        _event(2, "tool.completed", {"status": "ok"}, parents=("event-0",)),
        _event(3, "oracle.completed", {"label": "observed"}, parents=("event-2",)),
    ]
    counter = 0

    def nonce_factory(size: int) -> bytes:
        nonlocal counter
        counter += 1
        return bytes([counter]) * size

    bundle = build_disclosure_bundle(
        claim_id="disclosure-study",
        source_trace_digest="sha256:" + "1" * 64,
        events=events,
        disclose_event_ids=("event-3",),
        nonce_factory=nonce_factory,
    )
    checks: list[tuple[str, bool]] = [("valid", verify_disclosed_events(bundle))]
    for index, mutation in enumerate(("event", "nonce", "digest", "root", "sequence")):
        changed = copy.deepcopy(bundle)
        visible = next(item for item in changed.commitments if item.event is not None)
        if mutation == "event":
            assert visible.event is not None
            visible.event["payload"] = {"tampered": True}  # type: ignore[index]
        elif mutation == "nonce":
            object.__setattr__(visible, "nonce", "00" * 32)
        elif mutation == "digest":
            object.__setattr__(visible, "digest", "sha256:" + "0" * 64)
        elif mutation == "root":
            object.__setattr__(changed, "commitment_root", "sha256:" + "0" * 64)
        elif mutation == "sequence":
            object.__setattr__(visible, "sequence", visible.sequence + 1)
        checks.append((f"tamper-{index}-{mutation}", not verify_disclosed_events(changed)))
    disclosed = set(bundle.disclosed_event_ids)
    closure_complete = {"event-0", "event-2", "event-3"} <= disclosed
    irrelevant_hidden = "event-1" not in disclosed
    return {
        "checks": [{"name": name, "passed": passed} for name, passed in checks],
        "attack_detection_rate": sum(passed for name, passed in checks if name != "valid")
        / (len(checks) - 1),
        "valid_bundle_verified": checks[0][1],
        "closure_complete": closure_complete,
        "irrelevant_event_hidden": irrelevant_hidden,
        "disclosed_fraction": len(disclosed) / len(events),
    }


def _conformance_corpus() -> list[dict[str, Any]]:
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
                "sha256:" + "a" * 64,
            ),
        ),
    )
    rows: list[dict[str, Any]] = []
    for index in range(60):
        variant = index % 5
        provider: dict[str, Any] = {
            "status": "succeeded",
            "side_effect": "mutate",
            "evidence": [{"role": "artifact", "surface": f"executor-{index % 3}"}],
            "output": {"message": f"surface-variant-{index}"},
        }
        observations: list[dict[str, Any]] = [
            {
                "producer": "sova-observer",
                "kind": "artifact.observed",
                "payload": {"digest": "sha256:" + "a" * 64},
            }
        ]
        truth = ConformanceStatus.CONFORMANT
        if variant == 1:
            observations = []
            truth = ConformanceStatus.INCONCLUSIVE
        elif variant == 2:
            observations[0]["payload"]["digest"] = "sha256:" + "b" * 64
            truth = ConformanceStatus.NONCONFORMANT
        elif variant == 3:
            provider["status"] = "unsupported"
            observations = []
            truth = ConformanceStatus.UNSUPPORTED
        elif variant == 4:
            provider["evidence"] = []
            truth = ConformanceStatus.NONCONFORMANT
        result = check_conformance(
            contract=contract,
            request={"action": "artifact.materialize"},
            provider_outcome=provider,
            observations=observations,
        )
        evidence = provider.get("evidence")
        evidence_roles = (
            {item.get("role") for item in evidence if isinstance(item, Mapping)}
            if isinstance(evidence, list)
            else set()
        )
        if provider["status"] == "unsupported":
            no_observation = ConformanceStatus.UNSUPPORTED
        elif (
            provider["status"] == "succeeded"
            and provider["side_effect"] == "mutate"
            and "artifact" in evidence_roles
        ):
            no_observation = ConformanceStatus.CONFORMANT
        else:
            no_observation = ConformanceStatus.NONCONFORMANT
        rows.append(
            {
                "id": f"executor-{index:03d}",
                "truth": truth.value,
                "candidate": result.status.value,
                "provider_status": (
                    ConformanceStatus.CONFORMANT.value
                    if provider["status"] == "succeeded"
                    else ConformanceStatus.UNSUPPORTED.value
                ),
                "exact_output": (
                    ConformanceStatus.CONFORMANT.value
                    if provider.get("output") == {"message": "surface-variant-0"}
                    else ConformanceStatus.NONCONFORMANT.value
                ),
                "capability_only": ConformanceStatus.CONFORMANT.value,
                "no_independent_observation": no_observation.value,
            }
        )
    return rows


def _rate_recomputation() -> dict[str, Any]:
    outcomes = [
        SemanticOutcome.EQUIVALENT,
        SemanticOutcome.EQUIVALENT,
        SemanticOutcome.DIVERGENT,
        SemanticOutcome.INCONCLUSIVE,
        SemanticOutcome.INCOMPATIBLE,
        SemanticOutcome.UNSAFE,
        SemanticOutcome.EVIDENCE_INVALID,
    ]
    trials = [
        TrialRecord(
            f"recompute-{index}",
            outcome,
            "fixture",
            "deterministic",
            "sha256:" + hashlib.sha256(f"trial-{index}".encode()).hexdigest(),
        )
        for index, outcome in enumerate(outcomes)
    ]
    first = asdict(estimate_reproduction(trials))
    second = asdict(estimate_reproduction(reversed(trials)))
    return {"order_independent": first == second, "estimate": first}


def _evaluate_thresholds(report: Mapping[str, Any]) -> dict[str, bool]:
    semantic = report["semantic"]["metrics"]
    fidelity = report["fidelity"]["metrics"]
    conformance = report["conformance"]["metrics"]
    candidate_semantic = semantic["candidate"]
    semantic_baselines = [
        semantic[name]
        for name in ("exact_trace", "final_payload", "terminal_status", "untyped_kinds")
    ]
    candidate_fidelity = fidelity["candidate"]
    candidate_conformance = conformance["candidate"]
    conformance_baselines = [
        conformance[name]
        for name in ("provider_status", "exact_output", "capability_only")
    ]
    return {
        "m04_macro_f1": candidate_semantic["macro_f1"] >= 0.90,
        "m04_baseline_delta": all(
            candidate_semantic["macro_f1"] - baseline["macro_f1"] >= 0.15
            for baseline in semantic_baselines
        ),
        "m04_unsafe_false_equivalence_zero": all(
            row["candidate"] != SemanticOutcome.EQUIVALENT.value
            for row in report["semantic"]["rows"]
            if row["truth"]
            in {
                SemanticOutcome.UNSAFE.value,
                SemanticOutcome.INCOMPATIBLE.value,
                SemanticOutcome.EVIDENCE_INVALID.value,
            }
        ),
        "m04_wilson_aggregate_coverage": (
            report["semantic"]["wilson"]["aggregate_coverage"] >= 0.93
        ),
        "m04_wilson_minimum_cell_coverage_v0_1": (
            report["semantic"]["wilson"]["minimum_cell_coverage"] >= 0.93
        ),
        "m04_exact_minimum_cell_coverage_v0_2": (
            report["semantic"]["exact_interval"]["minimum_cell_coverage"] >= 0.95
        ),
        "m04_recomputable": report["semantic"]["recomputation"]["order_independent"],
        "m05_accuracy": candidate_fidelity["accuracy"] >= 0.95,
        "m05_no_false_support": all(
            row["candidate"] != ClaimSupport.SUPPORTED.value
            for row in report["fidelity"]["rows"]
            if row["truth"] == ClaimSupport.INCONCLUSIVE.value
        ),
        "m05_attacks": report["fidelity"]["disclosure"]["attack_detection_rate"] == 1.0,
        "m05_closure": report["fidelity"]["disclosure"]["closure_complete"]
        and report["fidelity"]["disclosure"]["irrelevant_event_hidden"],
        "m06_accuracy": candidate_conformance["accuracy"] >= 0.95,
        "m06_baseline_delta": all(
            candidate_conformance["accuracy"] - baseline["accuracy"] >= 0.15
            for baseline in conformance_baselines
        ),
        "m06_no_self_attested_success": all(
            row["candidate"] != ConformanceStatus.CONFORMANT.value
            for row in report["conformance"]["rows"]
            if row["truth"] != ConformanceStatus.CONFORMANT.value
        ),
    }


def main() -> int:
    started = time.perf_counter()
    behavior = _behavior_corpus()
    fidelity = _fidelity_corpus()
    conformance = _conformance_corpus()
    report: dict[str, Any] = {
        "artifactType": "sova.private-research-result",
        "protocol": "topics-04-06-corrected/0.1.0",
        "seed": SEED,
        "generatedAt": "2026-07-31",
        "limitations": [
            "Synthetic deterministic evidence does not establish real-model generalization.",
            "The corpora were generated by the same research team as the prototype.",
            "Recent preprint baselines have not yet been independently reproduced here.",
            "No adoption, novelty, patentability, or publication-acceptance claim follows.",
        ],
        "semantic": {
            "count": len(behavior),
            "profiles": dict(Counter(row["profile"] for row in behavior)),
            "labels": dict(Counter(row["truth"] for row in behavior)),
            "metrics": {
                name: _classification(behavior, prediction=name, labels=SEMANTIC_LABELS)
                for name in (
                    "candidate",
                    "exact_trace",
                    "final_payload",
                    "terminal_status",
                    "untyped_kinds",
                    "no_context_envelope",
                    "no_evidence_validity",
                    "inconclusive_as_failure",
                    "inconclusive_as_success",
                )
            },
            "wilson": _wilson_coverage(),
            "wilson_analytic": _analytic_interval_coverage(_wilson),
            "exact_interval": _analytic_interval_coverage(_clopper_pearson),
            "recomputation": _rate_recomputation(),
            "decision_errors": _decision_error_rates(
                behavior,
                prediction="candidate",
                accepted_label=SemanticOutcome.EQUIVALENT.value,
                rejected_label=SemanticOutcome.DIVERGENT.value,
            ),
            "rows": behavior,
        },
        "fidelity": {
            "count": len(fidelity),
            "labels": dict(Counter(row["truth"] for row in fidelity)),
            "metrics": {
                name: _classification(fidelity, prediction=name, labels=FIDELITY_LABELS)
                for name in (
                    "candidate",
                    "integrity_only",
                    "profile_only",
                    "full_share",
                    "no_causal_requirements",
                    "no_content_requirements",
                )
            },
            "disclosure": _disclosure_attacks(),
            "decision_errors": _decision_error_rates(
                fidelity,
                prediction="candidate",
                accepted_label=ClaimSupport.SUPPORTED.value,
                rejected_label=ClaimSupport.INCONCLUSIVE.value,
            ),
            "rows": fidelity,
        },
        "conformance": {
            "count": len(conformance),
            "labels": dict(Counter(row["truth"] for row in conformance)),
            "metrics": {
                name: _classification(
                    conformance,
                    prediction=name,
                    labels=CONFORMANCE_LABELS,
                )
                for name in (
                    "candidate",
                    "provider_status",
                    "exact_output",
                    "capability_only",
                    "no_independent_observation",
                )
            },
            "decision_errors": _decision_error_rates(
                conformance,
                prediction="candidate",
                accepted_label=ConformanceStatus.CONFORMANT.value,
                rejected_label=ConformanceStatus.NONCONFORMANT.value,
            ),
            "decision_overhead": _conformance_overhead(),
            "rows": conformance,
        },
    }
    report["thresholds"] = _evaluate_thresholds(report)
    report["initial_v0_1_thresholds_passed"] = all(
        value
        for name, value in report["thresholds"].items()
        if name != "m04_exact_minimum_cell_coverage_v0_2"
    )
    report["corrected_v0_2_thresholds_passed"] = all(
        value
        for name, value in report["thresholds"].items()
        if name != "m04_wilson_minimum_cell_coverage_v0_1"
    )
    report["durationSeconds"] = time.perf_counter() - started
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "result": str(RESULT),
                "initial_v0_1_thresholds_passed": report["initial_v0_1_thresholds_passed"],
                "corrected_v0_2_thresholds_passed": report[
                    "corrected_v0_2_thresholds_passed"
                ],
                "thresholds": report["thresholds"],
                "semantic_macro_f1": report["semantic"]["metrics"]["candidate"]["macro_f1"],
                "fidelity_accuracy": report["fidelity"]["metrics"]["candidate"]["accuracy"],
                "conformance_accuracy": report["conformance"]["metrics"]["candidate"]["accuracy"],
                "durationSeconds": report["durationSeconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["corrected_v0_2_thresholds_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
