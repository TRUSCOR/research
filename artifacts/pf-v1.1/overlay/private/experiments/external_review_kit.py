"""Offline preparation and scoring for independent Topics 04-06 validation.

The tool validates records, freezes digests, and calculates metrics. It cannot
prove that a named reviewer is independent or that a human assertion is true.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from sova.formats import canonical_json_bytes, sha256_digest, strict_json_loads

PROFILES = (
    "security",
    "evaluation",
    "agent-trajectory",
    "behavioral-interpretability",
    "incident-forensics",
    "research-publication",
)
OUTCOMES = (
    "equivalent",
    "divergent",
    "inconclusive",
    "incompatible",
    "unsafe",
    "evidence-invalid",
)
REQUIRED_STRATA = (
    "version-drift",
    "missing-dependency",
    "partial-evidence",
    "stochastic-response",
    "incompatible-context",
    "unsafe-refusal",
    "evidence-invalid",
)
MINIMUM_CASES = 120
P5_REQUIRED_CATEGORIES = (
    "dictionary-recovery",
    "compromised-key",
    "linkage",
    "length-inference",
    "structure-inference",
    "residual-secret",
    "malformed-placeholder",
    "corruption",
    "truncation",
    "reordering",
    "substitution",
    "parser-differential",
    "archive-resource",
    "signer-equivocation",
    "replay-freshness",
)
P5_REQUIRED_FORMATS = (
    "sova-native",
    "opentelemetry",
    "openinference",
    "inspect-ai",
    "additional-external",
)
P5_DISPOSITIONS = (
    "passes-declared-claim",
    "implementation-defect",
    "specification-defect",
    "privacy-limitation",
    "unsupported-claim",
    "external-trust-requirement",
)
P6_ACTION_FAMILIES = ("terminal", "browser", "computer")
P6_REQUIRED_STRATA = (
    "honest-success",
    "false-success",
    "false-failure",
    "unsupported-action",
    "weaker-capability",
    "evidence-omission",
    "contradictory-observation",
    "retry",
    "duplicate-side-effect",
    "timeout",
    "cancellation",
    "crash",
    "partial-result",
    "orphan-process",
)
P6_OUTCOMES = ("conformant", "nonconformant", "inconclusive", "unsupported")
P6_MINIMUM_CASES = 90
P6_MINIMUM_PER_FAMILY = 30


class ReviewKitError(ValueError):
    """Raised when a review artifact violates the frozen protocol."""


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReviewKitError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewKitError(f"{label} must be non-empty text")
    return value


def _digest(value: Any, label: str) -> str:
    digest = _text(value, label)
    if not digest.startswith("sha256:") or len(digest) != 71:
        raise ReviewKitError(f"{label} must be a sha256:<64 lowercase hex> digest")
    suffix = digest.removeprefix("sha256:")
    if any(character not in "0123456789abcdef" for character in suffix):
        raise ReviewKitError(f"{label} must be a sha256:<64 lowercase hex> digest")
    return digest


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, raw in enumerate(path.read_bytes().splitlines(), start=1):
        if not raw.strip():
            continue
        value = strict_json_loads(raw)
        rows.append(_object(value, f"{path.name}:{number}"))
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> bytes:
    raw = b"".join(canonical_json_bytes(dict(row)) + b"\n" for row in rows)
    path.write_bytes(raw)
    return raw


def _validate_case(row: Mapping[str, Any], *, index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    case_id = _text(row.get("caseId"), f"case {index} caseId")
    profile = _text(row.get("profile"), f"case {case_id} profile")
    stratum = _text(row.get("stratum"), f"case {case_id} stratum")
    expected = _text(row.get("expectedOutcome"), f"case {case_id} expectedOutcome")
    if profile not in PROFILES:
        raise ReviewKitError(f"case {case_id} has unknown profile {profile!r}")
    if expected not in OUTCOMES:
        raise ReviewKitError(f"case {case_id} has unknown outcome {expected!r}")
    authorship = _object(row.get("authorship"), f"case {case_id} authorship")
    reviewer_id = _text(authorship.get("reviewerId"), f"case {case_id} reviewerId")
    if authorship.get("independentOfImplementation") is not True:
        raise ReviewKitError(f"case {case_id} lacks an affirmative independence assertion")
    rationale = _text(row.get("rationale"), f"case {case_id} rationale")
    scenario = _object(row.get("scenario"), f"case {case_id} scenario")
    source = _object(row.get("source"), f"case {case_id} source")
    candidate = _object(row.get("candidate"), f"case {case_id} candidate")
    blinded = {
        "caseId": case_id,
        "profile": profile,
        "stratum": stratum,
        "scenario": scenario,
        "source": source,
        "candidate": candidate,
    }
    label = {
        "caseId": case_id,
        "expectedOutcome": expected,
        "rationaleDigest": sha256_digest(rationale.encode("utf-8")),
        "reviewerId": reviewer_id,
    }
    return blinded, label


def prepare_p4(source: Path, output_directory: Path) -> dict[str, Any]:
    """Freeze a reviewer-authored cohort into separated blinded and label files."""
    rows = _read_jsonl(source)
    if len(rows) < MINIMUM_CASES:
        raise ReviewKitError(f"P4 confirmatory cohort requires at least {MINIMUM_CASES} cases")
    blinded: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for index, row in enumerate(rows, start=1):
        case, label = _validate_case(row, index=index)
        if case["caseId"] in identifiers:
            raise ReviewKitError(f"duplicate caseId {case['caseId']!r}")
        identifiers.add(case["caseId"])
        blinded.append(case)
        labels.append(label)
    profile_counts = Counter(case["profile"] for case in blinded)
    missing_profiles = sorted(set(PROFILES) - profile_counts.keys())
    if missing_profiles:
        raise ReviewKitError(f"P4 cohort omits profiles: {missing_profiles}")
    stratum_counts = Counter(case["stratum"] for case in blinded)
    missing_strata = sorted(set(REQUIRED_STRATA) - stratum_counts.keys())
    if missing_strata:
        raise ReviewKitError(f"P4 cohort omits required strata: {missing_strata}")

    output_directory.mkdir(parents=True, exist_ok=False)
    blinded_raw = _write_jsonl(output_directory / "p4-blinded-cases.jsonl", blinded)
    label_raw = _write_jsonl(output_directory / "p4-sealed-labels.jsonl", labels)
    manifest = {
        "artifactType": "sova.external-review.p4-frozen-cohort",
        "version": "0.1.0",
        "caseCount": len(blinded),
        "profiles": dict(sorted(profile_counts.items())),
        "strata": dict(sorted(stratum_counts.items())),
        "reviewerPseudonyms": sorted({label["reviewerId"] for label in labels}),
        "blindedCasesDigest": sha256_digest(blinded_raw),
        "sealedLabelsDigest": sha256_digest(label_raw),
        "independenceBoundary": (
            "Every source row asserted independent authorship. This tool validates the "
            "assertion's presence but cannot prove identity, independence, or human review."
        ),
        "releaseOrder": [
            "Reviewer retains p4-sealed-labels.jsonl.",
            "SOVA team receives p4-blinded-cases.jsonl and freezes predictions.",
            "Prediction digest is returned to the reviewer.",
            "Reviewer releases sealed labels only after checking the prediction digest.",
        ],
    }
    (output_directory / "p4-cohort-manifest.json").write_bytes(
        canonical_json_bytes(manifest) + b"\n"
    )
    return manifest


def _classification_metrics(
    expected: Sequence[str],
    predicted: Sequence[str],
    *,
    labels: Sequence[str] = OUTCOMES,
) -> dict[str, Any]:
    confusion = {truth: {candidate: 0 for candidate in labels} for truth in labels}
    for truth, candidate in zip(expected, predicted, strict=True):
        confusion[truth][candidate] += 1
    per_class: dict[str, dict[str, str | int]] = {}
    f1_values: list[float] = []
    for label in labels:
        true_positive = confusion[label][label]
        false_positive = sum(confusion[truth][label] for truth in labels if truth != label)
        false_negative = sum(
            confusion[label][candidate] for candidate in labels if candidate != label
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_values.append(f1)
        per_class[label] = {
            "support": sum(confusion[label].values()),
            "precision": f"{precision:.6f}",
            "recall": f"{recall:.6f}",
            "f1": f"{f1:.6f}",
        }
    accuracy = sum(left == right for left, right in zip(expected, predicted, strict=True)) / len(
        expected
    )
    return {
        "accuracy": f"{accuracy:.6f}",
        "macroF1": f"{sum(f1_values) / len(f1_values):.6f}",
        "confusion": confusion,
        "perClass": per_class,
    }


def _calibration(
    predictions: Sequence[Mapping[str, Any]], expected: Sequence[str]
) -> dict[str, Any]:
    available = all(
        isinstance(row.get("confidenceBasisPoints"), int)
        and not isinstance(row.get("confidenceBasisPoints"), bool)
        and 0 <= row["confidenceBasisPoints"] <= 10_000
        for row in predictions
    )
    if not available:
        return {"available": False, "reason": "not every prediction declared confidence"}
    bins: list[list[tuple[float, int]]] = [[] for _index in range(10)]
    for row, truth in zip(predictions, expected, strict=True):
        confidence = int(row["confidenceBasisPoints"]) / 10_000
        correct = int(row["outcome"] == truth)
        bins[min(9, int(confidence * 10))].append((confidence, correct))
    total = len(predictions)
    ece = 0.0
    rendered: list[dict[str, Any]] = []
    for index, values in enumerate(bins):
        if not values:
            continue
        mean_confidence = sum(item[0] for item in values) / len(values)
        accuracy = sum(item[1] for item in values) / len(values)
        ece += len(values) / total * abs(mean_confidence - accuracy)
        rendered.append(
            {
                "bin": index,
                "count": len(values),
                "meanConfidence": f"{mean_confidence:.6f}",
                "accuracy": f"{accuracy:.6f}",
            }
        )
    return {"available": True, "expectedCalibrationError": f"{ece:.6f}", "bins": rendered}


def score_p4(
    manifest_path: Path,
    blinded_path: Path,
    predictions_path: Path,
    labels_path: Path,
) -> dict[str, Any]:
    """Score frozen predictions after an independent author releases labels."""
    manifest = _object(strict_json_loads(manifest_path.read_bytes()), "manifest")
    blinded_raw = blinded_path.read_bytes()
    labels_raw = labels_path.read_bytes()
    if sha256_digest(blinded_raw) != manifest.get("blindedCasesDigest"):
        raise ReviewKitError("blinded case digest does not match the frozen manifest")
    if sha256_digest(labels_raw) != manifest.get("sealedLabelsDigest"):
        raise ReviewKitError("released label digest does not match the frozen manifest")
    blinded = _read_jsonl(blinded_path)
    labels = _read_jsonl(labels_path)
    predictions = _read_jsonl(predictions_path)
    expected_ids = [row["caseId"] for row in blinded]
    label_by_id = {row.get("caseId"): row for row in labels}
    prediction_by_id = {row.get("caseId"): row for row in predictions}
    if len(label_by_id) != len(labels) or len(prediction_by_id) != len(predictions):
        raise ReviewKitError("labels and predictions require unique caseId values")
    if set(expected_ids) != set(label_by_id) or set(expected_ids) != set(prediction_by_id):
        raise ReviewKitError("labels and predictions must cover the exact frozen case set")
    ordered_predictions = [prediction_by_id[identifier] for identifier in expected_ids]
    expected: list[str] = []
    predicted: list[str] = []
    for identifier, prediction in zip(expected_ids, ordered_predictions, strict=True):
        truth = _text(label_by_id[identifier].get("expectedOutcome"), f"label {identifier}")
        outcome = _text(prediction.get("outcome"), f"prediction {identifier}")
        _text(prediction.get("evidenceDigest"), f"prediction {identifier} evidenceDigest")
        if truth not in OUTCOMES or outcome not in OUTCOMES:
            raise ReviewKitError(f"case {identifier} contains an unknown outcome")
        expected.append(truth)
        predicted.append(outcome)
    prediction_digest = sha256_digest(predictions_path.read_bytes())
    metrics = _classification_metrics(expected, predicted)
    metrics.update(
        {
            "falseEquivalence": sum(
                candidate == "equivalent" and truth != "equivalent"
                for truth, candidate in zip(expected, predicted, strict=True)
            ),
            "falseDivergence": sum(
                candidate == "divergent" and truth != "divergent"
                for truth, candidate in zip(expected, predicted, strict=True)
            ),
        }
    )
    return {
        "artifactType": "sova.external-review.p4-score",
        "version": "0.1.0",
        "caseCount": len(expected_ids),
        "predictionDigest": prediction_digest,
        "metrics": metrics,
        "calibration": _calibration(ordered_predictions, expected),
        "claimBoundary": (
            "Scoring proves agreement with the released frozen labels only. Reviewer "
            "identity, independence, construct validity, and evidence truth require human audit."
        ),
    }


def prepare_p5(source: Path, output_directory: Path) -> dict[str, Any]:
    """Freeze the complete P5 hostile/interoperability review case set."""
    rows = _read_jsonl(source)
    identifiers: set[str] = set()
    categories: Counter[str] = Counter()
    formats: Counter[str] = Counter()
    rendered: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        case_id = _text(row.get("caseId"), f"P5 case {index} caseId")
        if case_id in identifiers:
            raise ReviewKitError(f"duplicate caseId {case_id!r}")
        identifiers.add(case_id)
        category = _text(row.get("category"), f"P5 case {case_id} category")
        artifact_format = _text(
            row.get("artifactFormat"),
            f"P5 case {case_id} artifactFormat",
        )
        if category not in P5_REQUIRED_CATEGORIES:
            raise ReviewKitError(f"P5 case {case_id} has unknown category {category!r}")
        if artifact_format not in P5_REQUIRED_FORMATS:
            raise ReviewKitError(
                f"P5 case {case_id} has unknown artifact format {artifact_format!r}"
            )
        categories[category] += 1
        formats[artifact_format] += 1
        rendered.append(
            {
                "caseId": case_id,
                "category": category,
                "artifactFormat": artifact_format,
                "claim": _text(row.get("claim"), f"P5 case {case_id} claim"),
                "inputDigest": _digest(
                    row.get("inputDigest"),
                    f"P5 case {case_id} inputDigest",
                ),
                "procedure": _object(
                    row.get("procedure"),
                    f"P5 case {case_id} procedure",
                ),
                "expectedHandling": _text(
                    row.get("expectedHandling"),
                    f"P5 case {case_id} expectedHandling",
                ),
            }
        )
    missing_categories = sorted(set(P5_REQUIRED_CATEGORIES) - categories.keys())
    missing_formats = sorted(set(P5_REQUIRED_FORMATS) - formats.keys())
    if missing_categories:
        raise ReviewKitError(f"P5 review omits categories: {missing_categories}")
    if missing_formats:
        raise ReviewKitError(f"P5 review omits formats: {missing_formats}")

    output_directory.mkdir(parents=True, exist_ok=False)
    case_raw = _write_jsonl(output_directory / "p5-review-cases.jsonl", rendered)
    manifest = {
        "artifactType": "sova.external-review.p5-frozen-cases",
        "version": "0.1.0",
        "caseCount": len(rendered),
        "categories": dict(sorted(categories.items())),
        "formats": dict(sorted(formats.items())),
        "casesDigest": sha256_digest(case_raw),
        "claimBoundary": (
            "This manifest freezes review inputs and expected handling. It does not "
            "establish reviewer identity, independence, claim truth, or security."
        ),
    }
    (output_directory / "p5-review-manifest.json").write_bytes(
        canonical_json_bytes(manifest) + b"\n"
    )
    return manifest


def score_p5(
    manifest_path: Path,
    cases_path: Path,
    findings_path: Path,
) -> dict[str, Any]:
    """Validate and summarize a reviewer's complete P5 findings without hiding defects."""
    manifest = _object(strict_json_loads(manifest_path.read_bytes()), "P5 manifest")
    if sha256_digest(cases_path.read_bytes()) != manifest.get("casesDigest"):
        raise ReviewKitError("P5 case digest does not match the frozen manifest")
    cases = _read_jsonl(cases_path)
    findings = _read_jsonl(findings_path)
    expected_ids = [row["caseId"] for row in cases]
    finding_by_id = {row.get("caseId"): row for row in findings}
    if len(finding_by_id) != len(findings) or set(expected_ids) != set(finding_by_id):
        raise ReviewKitError("P5 findings must cover the exact frozen case set")
    dispositions: Counter[str] = Counter()
    reviewers: set[str] = set()
    for case_id in expected_ids:
        finding = finding_by_id[case_id]
        disposition = _text(
            finding.get("disposition"),
            f"P5 finding {case_id} disposition",
        )
        if disposition not in P5_DISPOSITIONS:
            raise ReviewKitError(f"P5 finding {case_id} has unknown disposition {disposition!r}")
        if finding.get("independentOfImplementation") is not True:
            raise ReviewKitError(
                f"P5 finding {case_id} lacks an affirmative independence assertion"
            )
        reviewers.add(_text(finding.get("reviewerId"), f"P5 finding {case_id} reviewerId"))
        _digest(finding.get("evidenceDigest"), f"P5 finding {case_id} evidenceDigest")
        _text(finding.get("notes"), f"P5 finding {case_id} notes")
        dispositions[disposition] += 1
    return {
        "artifactType": "sova.external-review.p5-findings",
        "version": "0.1.0",
        "caseCount": len(expected_ids),
        "findingsDigest": sha256_digest(findings_path.read_bytes()),
        "reviewerPseudonyms": sorted(reviewers),
        "dispositions": dict(sorted(dispositions.items())),
        "adverseFindings": sum(
            count
            for disposition, count in dispositions.items()
            if disposition != "passes-declared-claim"
        ),
        "claimBoundary": (
            "The tool validates complete findings and reviewer assertions. It cannot "
            "prove identity, independence, competence, exploitability, or claim truth."
        ),
    }


def _validate_p6_case(
    row: Mapping[str, Any],
    *,
    index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    case_id = _text(row.get("caseId"), f"P6 case {index} caseId")
    action_family = _text(row.get("actionFamily"), f"P6 case {case_id} actionFamily")
    stratum = _text(row.get("failureStratum"), f"P6 case {case_id} failureStratum")
    expected = _text(
        row.get("expectedConformance"),
        f"P6 case {case_id} expectedConformance",
    )
    if action_family not in P6_ACTION_FAMILIES:
        raise ReviewKitError(f"P6 case {case_id} has unknown action family {action_family!r}")
    if stratum not in P6_REQUIRED_STRATA:
        raise ReviewKitError(f"P6 case {case_id} has unknown stratum {stratum!r}")
    if expected not in P6_OUTCOMES:
        raise ReviewKitError(f"P6 case {case_id} has unknown outcome {expected!r}")
    blinded = {
        "caseId": case_id,
        "actionFamily": action_family,
        "providerId": _text(row.get("providerId"), f"P6 case {case_id} providerId"),
        "failureStratum": stratum,
        "scenario": _object(row.get("scenario"), f"P6 case {case_id} scenario"),
        "contract": _object(row.get("contract"), f"P6 case {case_id} contract"),
    }
    label = {
        "caseId": case_id,
        "expectedConformance": expected,
        "rationaleDigest": sha256_digest(
            _text(row.get("rationale"), f"P6 case {case_id} rationale").encode("utf-8")
        ),
    }
    return blinded, label


def prepare_p6(source: Path, output_directory: Path) -> dict[str, Any]:
    """Freeze P6 cases while withholding expected conformance from the adapter author."""
    rows = _read_jsonl(source)
    if len(rows) < P6_MINIMUM_CASES:
        raise ReviewKitError(f"P6 confirmatory cohort requires at least {P6_MINIMUM_CASES} cases")
    blinded: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for index, row in enumerate(rows, start=1):
        case, label = _validate_p6_case(row, index=index)
        if case["caseId"] in identifiers:
            raise ReviewKitError(f"duplicate caseId {case['caseId']!r}")
        identifiers.add(case["caseId"])
        blinded.append(case)
        labels.append(label)
    family_counts = Counter(row["actionFamily"] for row in blinded)
    if any(family_counts[family] < P6_MINIMUM_PER_FAMILY for family in P6_ACTION_FAMILIES):
        raise ReviewKitError(
            f"P6 requires at least {P6_MINIMUM_PER_FAMILY} cases per action family"
        )
    stratum_counts = Counter(row["failureStratum"] for row in blinded)
    missing_strata = sorted(set(P6_REQUIRED_STRATA) - stratum_counts.keys())
    if missing_strata:
        raise ReviewKitError(f"P6 cohort omits required strata: {missing_strata}")
    providers = sorted({row["providerId"] for row in blinded})
    if len(providers) < 2:
        raise ReviewKitError("P6 requires at least two materially different provider identifiers")

    output_directory.mkdir(parents=True, exist_ok=False)
    blinded_raw = _write_jsonl(output_directory / "p6-blinded-cases.jsonl", blinded)
    label_raw = _write_jsonl(output_directory / "p6-sealed-labels.jsonl", labels)
    manifest = {
        "artifactType": "sova.external-review.p6-frozen-cohort",
        "version": "0.1.0",
        "caseCount": len(blinded),
        "actionFamilies": dict(sorted(family_counts.items())),
        "failureStrata": dict(sorted(stratum_counts.items())),
        "providerIds": providers,
        "blindedCasesDigest": sha256_digest(blinded_raw),
        "sealedLabelsDigest": sha256_digest(label_raw),
        "releaseOrder": [
            "Adapter author receives only p6-blinded-cases.jsonl and the public contract.",
            "SOVA predictions and evidence digests are frozen before labels are released.",
            "The case custodian verifies the prediction digest, then releases labels.",
        ],
    }
    (output_directory / "p6-cohort-manifest.json").write_bytes(
        canonical_json_bytes(manifest) + b"\n"
    )
    return manifest


def score_p6(
    manifest_path: Path,
    blinded_path: Path,
    predictions_path: Path,
    labels_path: Path,
    declaration_path: Path,
) -> dict[str, Any]:
    """Score frozen P6 results after label release and validate the adapter declaration."""
    manifest = _object(strict_json_loads(manifest_path.read_bytes()), "P6 manifest")
    if sha256_digest(blinded_path.read_bytes()) != manifest.get("blindedCasesDigest"):
        raise ReviewKitError("P6 blinded case digest does not match the frozen manifest")
    if sha256_digest(labels_path.read_bytes()) != manifest.get("sealedLabelsDigest"):
        raise ReviewKitError("P6 label digest does not match the frozen manifest")
    declaration = _object(
        strict_json_loads(declaration_path.read_bytes()),
        "P6 adapter declaration",
    )
    if declaration.get("independentAdapterImplementation") is not True:
        raise ReviewKitError("P6 adapter author did not affirm independent implementation")
    if declaration.get("receivedPrivateImplementation") is not False:
        raise ReviewKitError(
            "P6 adapter author must affirm private implementation was not received"
        )
    reviewer_id = _text(declaration.get("reviewerId"), "P6 declaration reviewerId")

    blinded = _read_jsonl(blinded_path)
    labels = _read_jsonl(labels_path)
    predictions = _read_jsonl(predictions_path)
    expected_ids = [row["caseId"] for row in blinded]
    label_by_id = {row.get("caseId"): row for row in labels}
    prediction_by_id = {row.get("caseId"): row for row in predictions}
    if len(label_by_id) != len(labels) or len(prediction_by_id) != len(predictions):
        raise ReviewKitError("P6 labels and predictions require unique caseId values")
    if set(expected_ids) != set(label_by_id) or set(expected_ids) != set(prediction_by_id):
        raise ReviewKitError("P6 labels and predictions must cover the exact frozen case set")

    expected: list[str] = []
    predicted: list[str] = []
    stratum_results: dict[str, list[bool]] = {name: [] for name in P6_REQUIRED_STRATA}
    for case in blinded:
        case_id = case["caseId"]
        truth = _text(
            label_by_id[case_id].get("expectedConformance"),
            f"P6 label {case_id}",
        )
        prediction = prediction_by_id[case_id]
        outcome = _text(prediction.get("conformance"), f"P6 prediction {case_id}")
        if truth not in P6_OUTCOMES or outcome not in P6_OUTCOMES:
            raise ReviewKitError(f"P6 case {case_id} contains an unknown outcome")
        _digest(prediction.get("evidenceDigest"), f"P6 prediction {case_id} evidenceDigest")
        _digest(
            prediction.get("adapterRunDigest"),
            f"P6 prediction {case_id} adapterRunDigest",
        )
        expected.append(truth)
        predicted.append(outcome)
        stratum_results[case["failureStratum"]].append(truth == outcome)

    metrics = _classification_metrics(expected, predicted, labels=P6_OUTCOMES)
    metrics.update(
        {
            "falseConformance": sum(
                candidate == "conformant" and truth != "conformant"
                for truth, candidate in zip(expected, predicted, strict=True)
            ),
            "falseNonconformance": sum(
                candidate == "nonconformant" and truth == "conformant"
                for truth, candidate in zip(expected, predicted, strict=True)
            ),
        }
    )
    return {
        "artifactType": "sova.external-review.p6-score",
        "version": "0.1.0",
        "caseCount": len(expected_ids),
        "predictionDigest": sha256_digest(predictions_path.read_bytes()),
        "adapterDeclarationDigest": sha256_digest(declaration_path.read_bytes()),
        "adapterAuthorPseudonym": reviewer_id,
        "metrics": metrics,
        "perStratum": {
            name: {
                "correct": sum(values),
                "count": len(values),
            }
            for name, values in sorted(stratum_results.items())
        },
        "claimBoundary": (
            "The tool verifies artifact consistency and agreement with released labels. "
            "It cannot prove human identity, independence, provider diversity, or effect truth."
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and score external SOVA reviews")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare-p4")
    prepare.add_argument("source", type=Path)
    prepare.add_argument("output_directory", type=Path)
    score = commands.add_parser("score-p4")
    score.add_argument("manifest", type=Path)
    score.add_argument("blinded", type=Path)
    score.add_argument("predictions", type=Path)
    score.add_argument("labels", type=Path)
    score.add_argument("output", type=Path)
    prepare_p5_parser = commands.add_parser("prepare-p5")
    prepare_p5_parser.add_argument("source", type=Path)
    prepare_p5_parser.add_argument("output_directory", type=Path)
    score_p5_parser = commands.add_parser("score-p5")
    score_p5_parser.add_argument("manifest", type=Path)
    score_p5_parser.add_argument("cases", type=Path)
    score_p5_parser.add_argument("findings", type=Path)
    score_p5_parser.add_argument("output", type=Path)
    prepare_p6_parser = commands.add_parser("prepare-p6")
    prepare_p6_parser.add_argument("source", type=Path)
    prepare_p6_parser.add_argument("output_directory", type=Path)
    score_p6_parser = commands.add_parser("score-p6")
    score_p6_parser.add_argument("manifest", type=Path)
    score_p6_parser.add_argument("blinded", type=Path)
    score_p6_parser.add_argument("predictions", type=Path)
    score_p6_parser.add_argument("labels", type=Path)
    score_p6_parser.add_argument("declaration", type=Path)
    score_p6_parser.add_argument("output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "prepare-p4":
        result = prepare_p4(args.source, args.output_directory)
    elif args.command == "score-p4":
        result = score_p4(args.manifest, args.blinded, args.predictions, args.labels)
        args.output.write_bytes(canonical_json_bytes(result) + b"\n")
    elif args.command == "prepare-p5":
        result = prepare_p5(args.source, args.output_directory)
    elif args.command == "score-p5":
        result = score_p5(args.manifest, args.cases, args.findings)
        args.output.write_bytes(canonical_json_bytes(result) + b"\n")
    elif args.command == "prepare-p6":
        result = prepare_p6(args.source, args.output_directory)
    else:
        result = score_p6(
            args.manifest,
            args.blinded,
            args.predictions,
            args.labels,
            args.declaration,
        )
        args.output.write_bytes(canonical_json_bytes(result) + b"\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
