"""Tests for the external reviewer handoff tooling."""

from __future__ import annotations

import json

import pytest

from private.experiments.external_review_kit import (
    OUTCOMES,
    P5_REQUIRED_CATEGORIES,
    P5_REQUIRED_FORMATS,
    P6_ACTION_FAMILIES,
    P6_OUTCOMES,
    P6_REQUIRED_STRATA,
    PROFILES,
    REQUIRED_STRATA,
    ReviewKitError,
    prepare_p4,
    prepare_p5,
    prepare_p6,
    score_p4,
    score_p5,
    score_p6,
)
from sova.formats import canonical_json_bytes


def _cohort() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(120):
        outcome = OUTCOMES[index % len(OUTCOMES)]
        rows.append(
            {
                "caseId": f"external-case-{index:03d}",
                "profile": PROFILES[index % len(PROFILES)],
                "stratum": REQUIRED_STRATA[index % len(REQUIRED_STRATA)],
                "authorship": {
                    "reviewerId": f"fixture-reviewer-{index % 2}",
                    "independentOfImplementation": True,
                },
                "scenario": {"intent": "synthetic review-kit test only"},
                "source": {"observable": index},
                "candidate": {"observable": index},
                "expectedOutcome": outcome,
                "rationale": f"synthetic rationale {index}",
            }
        )
    return rows


def _write_jsonl(path, rows) -> None:  # type: ignore[no-untyped-def]
    path.write_bytes(b"".join(canonical_json_bytes(row) + b"\n" for row in rows))


def test_prepare_and_score_enforce_blind_release_order(tmp_path) -> None:  # type: ignore[no-untyped-def]
    source = tmp_path / "source.jsonl"
    _write_jsonl(source, _cohort())
    frozen = tmp_path / "frozen"
    manifest = prepare_p4(source, frozen)
    assert manifest["caseCount"] == 120
    blinded = frozen / "p4-blinded-cases.jsonl"
    labels = frozen / "p4-sealed-labels.jsonl"
    assert b"expectedOutcome" not in blinded.read_bytes()
    assert b"rationale" not in blinded.read_bytes()

    label_rows = [json.loads(line) for line in labels.read_text().splitlines()]
    predictions = tmp_path / "predictions.jsonl"
    _write_jsonl(
        predictions,
        [
            {
                "caseId": row["caseId"],
                "outcome": row["expectedOutcome"],
                "evidenceDigest": "sha256:" + "1" * 64,
                "confidenceBasisPoints": 10_000,
            }
            for row in label_rows
        ],
    )
    score = score_p4(
        frozen / "p4-cohort-manifest.json",
        blinded,
        predictions,
        labels,
    )
    assert score["metrics"]["macroF1"] == "1.000000"
    assert score["metrics"]["falseEquivalence"] == 0
    assert score["calibration"]["expectedCalibrationError"] == "0.000000"


def test_prepare_refuses_same_team_assertion_and_incomplete_cohort(tmp_path) -> None:  # type: ignore[no-untyped-def]
    source = tmp_path / "source.jsonl"
    rows = _cohort()
    rows[0]["authorship"] = {
        "reviewerId": "same-team",
        "independentOfImplementation": False,
    }
    _write_jsonl(source, rows)
    with pytest.raises(ReviewKitError, match="independence"):
        prepare_p4(source, tmp_path / "rejected")

    _write_jsonl(source, _cohort()[:119])
    with pytest.raises(ReviewKitError, match="at least 120"):
        prepare_p4(source, tmp_path / "too-small")


def test_score_rejects_prediction_after_label_or_case_substitution(tmp_path) -> None:  # type: ignore[no-untyped-def]
    source = tmp_path / "source.jsonl"
    _write_jsonl(source, _cohort())
    frozen = tmp_path / "frozen"
    prepare_p4(source, frozen)
    predictions = tmp_path / "predictions.jsonl"
    _write_jsonl(
        predictions,
        [
            {
                "caseId": f"external-case-{index:03d}",
                "outcome": OUTCOMES[index % len(OUTCOMES)],
                "evidenceDigest": "sha256:" + "2" * 64,
            }
            for index in range(120)
        ],
    )
    labels = frozen / "p4-sealed-labels.jsonl"
    labels.write_bytes(labels.read_bytes().replace(b"equivalent", b"divergent", 1))
    with pytest.raises(ReviewKitError, match="label digest"):
        score_p4(
            frozen / "p4-cohort-manifest.json",
            frozen / "p4-blinded-cases.jsonl",
            predictions,
            labels,
        )


def _p5_cases() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    count = max(len(P5_REQUIRED_CATEGORIES), len(P5_REQUIRED_FORMATS))
    for index in range(count):
        rows.append(
            {
                "caseId": f"p5-case-{index:03d}",
                "category": P5_REQUIRED_CATEGORIES[index % len(P5_REQUIRED_CATEGORIES)],
                "artifactFormat": P5_REQUIRED_FORMATS[index % len(P5_REQUIRED_FORMATS)],
                "claim": "synthetic reviewer-kit claim",
                "inputDigest": "sha256:" + f"{index:064x}",
                "procedure": {"step": "synthetic safe review"},
                "expectedHandling": "reject or report the declared limitation",
            }
        )
    return rows


def test_prepare_and_score_p5_preserve_all_adverse_findings(tmp_path) -> None:  # type: ignore[no-untyped-def]
    source = tmp_path / "p5-source.jsonl"
    _write_jsonl(source, _p5_cases())
    frozen = tmp_path / "p5-frozen"
    manifest = prepare_p5(source, frozen)
    assert manifest["caseCount"] == len(_p5_cases())
    findings = tmp_path / "p5-findings.jsonl"
    _write_jsonl(
        findings,
        [
            {
                "caseId": row["caseId"],
                "disposition": ("implementation-defect" if index == 0 else "passes-declared-claim"),
                "reviewerId": "external-reviewer-fixture",
                "independentOfImplementation": True,
                "evidenceDigest": "sha256:" + f"{index + 100:064x}",
                "notes": "synthetic test finding",
            }
            for index, row in enumerate(_p5_cases())
        ],
    )
    score = score_p5(
        frozen / "p5-review-manifest.json",
        frozen / "p5-review-cases.jsonl",
        findings,
    )
    assert score["adverseFindings"] == 1
    assert score["dispositions"]["implementation-defect"] == 1


def test_prepare_p5_rejects_incomplete_attack_matrix(tmp_path) -> None:  # type: ignore[no-untyped-def]
    source = tmp_path / "p5-source.jsonl"
    _write_jsonl(source, _p5_cases()[1:])
    with pytest.raises(ReviewKitError, match="omits categories"):
        prepare_p5(source, tmp_path / "p5-incomplete")


def _p6_cases() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(90):
        rows.append(
            {
                "caseId": f"p6-case-{index:03d}",
                "actionFamily": P6_ACTION_FAMILIES[index % len(P6_ACTION_FAMILIES)],
                "providerId": f"provider-{index % 2}",
                "failureStratum": P6_REQUIRED_STRATA[index % len(P6_REQUIRED_STRATA)],
                "scenario": {"intent": "synthetic safe adapter test"},
                "contract": {"requiredObservation": "synthetic"},
                "expectedConformance": P6_OUTCOMES[index % len(P6_OUTCOMES)],
                "rationale": f"synthetic rationale {index}",
            }
        )
    return rows


def _p6_declaration(path, *, independent: bool = True) -> None:  # type: ignore[no-untyped-def]
    path.write_bytes(
        canonical_json_bytes(
            {
                "reviewerId": "adapter-author-fixture",
                "independentAdapterImplementation": independent,
                "receivedPrivateImplementation": False,
            }
        )
        + b"\n"
    )


def test_prepare_and_score_p6_enforce_blind_adapter_protocol(tmp_path) -> None:  # type: ignore[no-untyped-def]
    source = tmp_path / "p6-source.jsonl"
    _write_jsonl(source, _p6_cases())
    frozen = tmp_path / "p6-frozen"
    manifest = prepare_p6(source, frozen)
    assert manifest["caseCount"] == 90
    blinded = frozen / "p6-blinded-cases.jsonl"
    labels = frozen / "p6-sealed-labels.jsonl"
    assert b"expectedConformance" not in blinded.read_bytes()
    label_rows = [json.loads(line) for line in labels.read_text().splitlines()]
    predictions = tmp_path / "p6-predictions.jsonl"
    _write_jsonl(
        predictions,
        [
            {
                "caseId": row["caseId"],
                "conformance": row["expectedConformance"],
                "evidenceDigest": "sha256:" + f"{index + 200:064x}",
                "adapterRunDigest": "sha256:" + f"{index + 400:064x}",
            }
            for index, row in enumerate(label_rows)
        ],
    )
    declaration = tmp_path / "p6-declaration.json"
    _p6_declaration(declaration)
    score = score_p6(
        frozen / "p6-cohort-manifest.json",
        blinded,
        predictions,
        labels,
        declaration,
    )
    assert score["metrics"]["macroF1"] == "1.000000"
    assert score["metrics"]["falseConformance"] == 0
    assert score["metrics"]["falseNonconformance"] == 0


def test_score_p6_refuses_same_team_or_private_implementation_assertion(tmp_path) -> None:  # type: ignore[no-untyped-def]
    source = tmp_path / "p6-source.jsonl"
    _write_jsonl(source, _p6_cases())
    frozen = tmp_path / "p6-frozen"
    prepare_p6(source, frozen)
    labels = frozen / "p6-sealed-labels.jsonl"
    label_rows = [json.loads(line) for line in labels.read_text().splitlines()]
    predictions = tmp_path / "p6-predictions.jsonl"
    _write_jsonl(
        predictions,
        [
            {
                "caseId": row["caseId"],
                "conformance": row["expectedConformance"],
                "evidenceDigest": "sha256:" + f"{index + 500:064x}",
                "adapterRunDigest": "sha256:" + f"{index + 700:064x}",
            }
            for index, row in enumerate(label_rows)
        ],
    )
    declaration = tmp_path / "p6-declaration.json"
    _p6_declaration(declaration, independent=False)
    with pytest.raises(ReviewKitError, match="independent implementation"):
        score_p6(
            frozen / "p6-cohort-manifest.json",
            frozen / "p6-blinded-cases.jsonl",
            predictions,
            labels,
            declaration,
        )
