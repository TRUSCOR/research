"""Private end-to-end bridge for the Topics 04-06 research mechanisms.

This module deliberately remains under ``private/`` pending founder/IP review.
It integrates the private semantic, fidelity, and conformance candidates with
the public capsule and trace substrate without changing the public formats.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from private.experiments.prototypes.conformance import (
    ConformanceResult,
    ExecutorSemanticContract,
    ObservationRequirement,
    check_conformance,
)
from private.experiments.prototypes.fidelity import (
    ClaimSupport,
    EvidenceRequirement,
    FidelityReport,
    assess_fidelity,
)
from private.experiments.prototypes.semantic import (
    ContextMode,
    ContextRule,
    OutcomePredicate,
    PredicateOperator,
    ReproductionDecision,
    SemanticOutcome,
    decide_reproduction,
)
from sova.formats import (
    PackageReader,
    PackageWriter,
    canonical_json_bytes,
    sha256_digest,
    strict_json_loads,
)
from sova.formats.errors import FormatError
from sova.trace import TraceReader

EXTENSION_NAME = "x-truscor-research"
EXTENSION_VERSION = "0.1.0"
LEGACY_EXTENSION_VERSION = "0.0.1"
MIGRATION_METHOD = "sova.private-research-extension/0.0.1-to-0.1.0"
ADJUDICATION_STATUSES = frozenset({"not-requested", "pending", "resolved", "unresolved"})
ADJUDICATION_KINDS = frozenset({"human", "model", "rule"})
ADJUDICATION_LABELS = frozenset(
    {
        "exact",
        "equivalent",
        "divergent",
        "inconclusive",
        "unsafe",
        "incompatible",
        "evidence-invalid",
    }
)
SHA256_DIGEST_LENGTH = len("sha256:") + 64


@dataclass(frozen=True, slots=True)
class AdjudicationSummary:
    """Typed, non-authoritative summary of recorded adjudicator disagreement."""

    status: str
    total_records: int
    label_counts: tuple[tuple[str, int], ...]
    agreement: str
    selected_label: str | None
    blinded_records: int
    independent_records: int
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IntegratedResearchReport:
    """One integrity-bound evaluation over a capsule and one trace."""

    capsule_digest: str
    trace_digest: str
    contract_version: str
    semantic: ReproductionDecision
    adjudication: AdjudicationSummary
    fidelity: tuple[FidelityReport, ...]
    conformance: tuple[tuple[str, ConformanceResult], ...]
    limitations: tuple[str, ...]
    method: str = "sova.private-integrated-research/0.1"

    def to_mapping(self) -> dict[str, Any]:
        return _json_safe(asdict(self))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FormatError("SOVA-RESEARCH-CONTRACT", "expected an object", path=path)
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise FormatError("SOVA-RESEARCH-CONTRACT", "expected an array", path=path)
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise FormatError("SOVA-RESEARCH-CONTRACT", "expected a non-empty string", path=path)
    return value


def _boolean(value: Any, path: str, *, default: bool | None = None) -> bool:
    if value is None and default is not None:
        return default
    if not isinstance(value, bool):
        raise FormatError("SOVA-RESEARCH-CONTRACT", "expected a boolean", path=path)
    return value


def _basis_points(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FormatError("SOVA-RESEARCH-CONTRACT", "expected an integer", path=path)
    if not 0 <= value <= 10_000:
        raise FormatError(
            "SOVA-RESEARCH-CONTRACT",
            "basis points must be between zero and 10000",
            path=path,
        )
    return value


def _choice(value: Any, allowed: frozenset[str], path: str) -> str:
    choice = _string(value, path)
    if choice not in allowed:
        raise FormatError(
            "SOVA-RESEARCH-CONTRACT",
            "value is outside the supported vocabulary",
            path=path,
            details={"value": choice, "allowed": sorted(allowed)},
        )
    return choice


def _sha256_digest(value: Any, path: str) -> str:
    digest = _string(value, path)
    if (
        not digest.startswith("sha256:")
        or len(digest) != SHA256_DIGEST_LENGTH
        or any(character not in "0123456789abcdef" for character in digest[7:])
    ):
        raise FormatError(
            "SOVA-RESEARCH-CONTRACT",
            "value must be a lowercase SHA-256 digest",
            path=path,
        )
    return digest


def _strict_keys(
    value: Mapping[str, Any],
    *,
    required: set[str],
    optional: set[str],
    path: str,
) -> None:
    keys = set(value)
    missing = required - keys
    unknown = keys - required - optional
    if missing or unknown:
        raise FormatError(
            "SOVA-RESEARCH-CONTRACT",
            "research contract has missing or unknown fields",
            path=path,
            details={"missing": sorted(missing), "unknown": sorted(unknown)},
        )


def _copy_json(value: Any) -> Any:
    return strict_json_loads(canonical_json_bytes(value))


def validate_research_extension(document: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the current private extension with hostile-input-safe bounds."""
    root = _mapping(_copy_json(document), "$")
    _strict_keys(
        root,
        required={
            "schemaVersion",
            "semanticReproduction",
            "evidenceFidelity",
            "executorConformance",
        },
        optional={"migrationHistory", "extensions"},
        path="$",
    )
    if root["schemaVersion"] != EXTENSION_VERSION:
        raise FormatError(
            "SOVA-RESEARCH-VERSION",
            "unsupported private research extension version",
            path="$.schemaVersion",
            details={"version": root["schemaVersion"], "supported": EXTENSION_VERSION},
        )
    _parse_semantic(root["semanticReproduction"])
    _parse_fidelity(root["evidenceFidelity"])
    _parse_conformance(root["executorConformance"])
    history = root.get("migrationHistory", [])
    for index, item in enumerate(_array(history, "$.migrationHistory")):
        record = _mapping(item, f"$.migrationHistory[{index}]")
        _strict_keys(
            record,
            required={"from", "to", "method"},
            optional=set(),
            path=f"$.migrationHistory[{index}]",
        )
        for key in ("from", "to", "method"):
            _string(record[key], f"$.migrationHistory[{index}].{key}")
    extensions = root.get("extensions", {})
    _mapping(extensions, "$.extensions")
    return root


def _parse_semantic(
    value: Any,
) -> tuple[
    tuple[OutcomePredicate, ...],
    dict[str, Any],
    tuple[ContextRule, ...],
]:
    document = _mapping(value, "$.semanticReproduction")
    _strict_keys(
        document,
        required={"predicates", "sourceContext", "contextRules", "judge"},
        optional={"adjudication"},
        path="$.semanticReproduction",
    )
    predicates: list[OutcomePredicate] = []
    for index, raw in enumerate(
        _array(document["predicates"], "$.semanticReproduction.predicates")
    ):
        item = _mapping(raw, f"$.semanticReproduction.predicates[{index}]")
        _strict_keys(
            item,
            required={"id", "eventKind", "operator"},
            optional={"path", "expected", "minimum", "otherKind", "required"},
            path=f"$.semanticReproduction.predicates[{index}]",
        )
        path = tuple(
            _string(component, f"$.semanticReproduction.predicates[{index}].path")
            for component in _array(
                item.get("path", []), f"$.semanticReproduction.predicates[{index}].path"
            )
        )
        minimum = item.get("minimum", 1)
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
            raise FormatError(
                "SOVA-RESEARCH-CONTRACT",
                "predicate minimum must be a positive integer",
                path=f"$.semanticReproduction.predicates[{index}].minimum",
            )
        predicates.append(
            OutcomePredicate(
                id=_string(item["id"], f"$.semanticReproduction.predicates[{index}].id"),
                event_kind=_string(
                    item["eventKind"],
                    f"$.semanticReproduction.predicates[{index}].eventKind",
                ),
                operator=PredicateOperator(
                    _string(
                        item["operator"],
                        f"$.semanticReproduction.predicates[{index}].operator",
                    )
                ),
                path=path,
                expected=item.get("expected"),
                minimum=minimum,
                other_kind=(
                    _string(
                        item["otherKind"],
                        f"$.semanticReproduction.predicates[{index}].otherKind",
                    )
                    if item.get("otherKind") is not None
                    else None
                ),
                required=_boolean(
                    item.get("required"),
                    f"$.semanticReproduction.predicates[{index}].required",
                    default=True,
                ),
            )
        )
    if not predicates:
        raise FormatError(
            "SOVA-RESEARCH-CONTRACT",
            "semantic reproduction requires at least one predicate",
            path="$.semanticReproduction.predicates",
        )

    rules: list[ContextRule] = []
    for index, raw in enumerate(
        _array(document["contextRules"], "$.semanticReproduction.contextRules")
    ):
        item = _mapping(raw, f"$.semanticReproduction.contextRules[{index}]")
        _strict_keys(
            item,
            required={"path", "mode"},
            optional={"allowed", "tolerance", "required"},
            path=f"$.semanticReproduction.contextRules[{index}]",
        )
        tolerance = item.get("tolerance")
        if tolerance is not None and (
            isinstance(tolerance, bool) or not isinstance(tolerance, (int, float))
        ):
            raise FormatError(
                "SOVA-RESEARCH-CONTRACT",
                "context tolerance must be numeric",
                path=f"$.semanticReproduction.contextRules[{index}].tolerance",
            )
        rules.append(
            ContextRule(
                path=tuple(
                    _string(
                        component,
                        f"$.semanticReproduction.contextRules[{index}].path",
                    )
                    for component in _array(
                        item["path"],
                        f"$.semanticReproduction.contextRules[{index}].path",
                    )
                ),
                mode=ContextMode(
                    _string(
                        item["mode"],
                        f"$.semanticReproduction.contextRules[{index}].mode",
                    )
                ),
                allowed=tuple(
                    _array(
                        item.get("allowed", []),
                        f"$.semanticReproduction.contextRules[{index}].allowed",
                    )
                ),
                tolerance=float(tolerance) if tolerance is not None else None,
                required=_boolean(
                    item.get("required"),
                    f"$.semanticReproduction.contextRules[{index}].required",
                    default=True,
                ),
            )
        )

    judge = _mapping(document["judge"], "$.semanticReproduction.judge")
    _strict_keys(
        judge,
        required={"id", "version", "kind"},
        optional={"calibration", "uncertainty", "limitations"},
        path="$.semanticReproduction.judge",
    )
    for key in ("id", "version", "kind"):
        _string(judge[key], f"$.semanticReproduction.judge.{key}")
    _parse_adjudication(document.get("adjudication"))
    return (
        tuple(predicates),
        _mapping(document["sourceContext"], "$.semanticReproduction.sourceContext"),
        tuple(rules),
    )


def _parse_adjudication_record(raw: Any, index: int) -> tuple[str, str, bool, bool]:
    path = f"$.semanticReproduction.adjudication.records[{index}]"
    record = _mapping(raw, path)
    _strict_keys(
        record,
        required={
            "id",
            "adjudicatorId",
            "kind",
            "label",
            "blinded",
            "independentOfImplementation",
        },
        optional={"confidenceBasisPoints", "rationaleDigest", "createdAt"},
        path=path,
    )
    identifier = _string(record["id"], f"{path}.id")
    _string(record["adjudicatorId"], f"{path}.adjudicatorId")
    _choice(record["kind"], ADJUDICATION_KINDS, f"{path}.kind")
    label = _choice(record["label"], ADJUDICATION_LABELS, f"{path}.label")
    blinded = _boolean(record["blinded"], f"{path}.blinded")
    independent = _boolean(
        record["independentOfImplementation"],
        f"{path}.independentOfImplementation",
    )
    if "confidenceBasisPoints" in record:
        _basis_points(
            record["confidenceBasisPoints"],
            f"{path}.confidenceBasisPoints",
        )
    if "rationaleDigest" in record:
        _sha256_digest(record["rationaleDigest"], f"{path}.rationaleDigest")
    if "createdAt" in record:
        _string(record["createdAt"], f"{path}.createdAt")
    return identifier, label, blinded, independent


def _parse_adjudication_resolution(value: Any, record_ids: set[str]) -> str:
    path = "$.semanticReproduction.adjudication.resolution"
    resolved = _mapping(value, path)
    _strict_keys(
        resolved,
        required={"label", "method", "recordIds"},
        optional=set(),
        path=path,
    )
    selected_label = _choice(
        resolved["label"],
        ADJUDICATION_LABELS,
        f"{path}.label",
    )
    _string(resolved["method"], f"{path}.method")
    cited_ids = [
        _string(item, f"{path}.recordIds")
        for item in _array(resolved["recordIds"], f"{path}.recordIds")
    ]
    if not cited_ids or len(cited_ids) != len(set(cited_ids)):
        raise FormatError(
            "SOVA-RESEARCH-CONTRACT",
            "resolution recordIds must be a non-empty unique list",
            path=f"{path}.recordIds",
        )
    unknown_ids = set(cited_ids) - record_ids
    if unknown_ids:
        raise FormatError(
            "SOVA-RESEARCH-CONTRACT",
            "resolution references unknown adjudication records",
            path=f"{path}.recordIds",
            details={"unknown": sorted(unknown_ids)},
        )
    return selected_label


def _adjudication_agreement(label_counts: Mapping[str, int]) -> str:
    if not label_counts:
        return "not-assessed"
    if len(label_counts) == 1:
        return "unanimous"
    highest = max(label_counts.values())
    leaders = sum(count == highest for count in label_counts.values())
    return "tie" if leaders > 1 else "plurality"


def _parse_adjudication(value: Any) -> AdjudicationSummary:
    if value is None:
        return AdjudicationSummary(
            status="not-requested",
            total_records=0,
            label_counts=(),
            agreement="not-assessed",
            selected_label=None,
            blinded_records=0,
            independent_records=0,
            limitations=("No adjudication records were supplied.",),
        )
    document = _mapping(value, "$.semanticReproduction.adjudication")
    _strict_keys(
        document,
        required={"status", "records"},
        optional={"resolution", "limitations"},
        path="$.semanticReproduction.adjudication",
    )
    status = _choice(
        document["status"],
        ADJUDICATION_STATUSES,
        "$.semanticReproduction.adjudication.status",
    )
    records = _array(document["records"], "$.semanticReproduction.adjudication.records")
    parsed = [_parse_adjudication_record(raw, index) for index, raw in enumerate(records)]
    identifiers = [item[0] for item in parsed]
    if len(identifiers) != len(set(identifiers)):
        raise FormatError(
            "SOVA-RESEARCH-CONTRACT",
            "adjudication record identifiers must be unique",
            path="$.semanticReproduction.adjudication.records",
        )
    label_counts: dict[str, int] = {}
    for _, label, _, _ in parsed:
        label_counts[label] = label_counts.get(label, 0) + 1
    selected_label = (
        _parse_adjudication_resolution(document["resolution"], set(identifiers))
        if "resolution" in document
        else None
    )
    if (status == "resolved") != (selected_label is not None):
        raise FormatError(
            "SOVA-RESEARCH-CONTRACT",
            "resolved status and resolution must be present together",
            path="$.semanticReproduction.adjudication",
        )
    limitations = tuple(
        _string(item, "$.semanticReproduction.adjudication.limitations")
        for item in _array(
            document.get("limitations", []),
            "$.semanticReproduction.adjudication.limitations",
        )
    )
    return AdjudicationSummary(
        status=status,
        total_records=len(records),
        label_counts=tuple(sorted(label_counts.items())),
        agreement=_adjudication_agreement(label_counts),
        selected_label=selected_label,
        blinded_records=sum(item[2] for item in parsed),
        independent_records=sum(item[3] for item in parsed),
        limitations=limitations,
    )


def _parse_fidelity(value: Any) -> tuple[tuple[str, tuple[EvidenceRequirement, ...]], ...]:
    document = _mapping(value, "$.evidenceFidelity")
    _strict_keys(document, required={"claims"}, optional=set(), path="$.evidenceFidelity")
    claims: list[tuple[str, tuple[EvidenceRequirement, ...]]] = []
    for claim_index, raw_claim in enumerate(
        _array(document["claims"], "$.evidenceFidelity.claims")
    ):
        claim = _mapping(raw_claim, f"$.evidenceFidelity.claims[{claim_index}]")
        _strict_keys(
            claim,
            required={"id", "requirements"},
            optional=set(),
            path=f"$.evidenceFidelity.claims[{claim_index}]",
        )
        requirements: list[EvidenceRequirement] = []
        for index, raw in enumerate(
            _array(
                claim["requirements"],
                f"$.evidenceFidelity.claims[{claim_index}].requirements",
            )
        ):
            item = _mapping(
                raw,
                f"$.evidenceFidelity.claims[{claim_index}].requirements[{index}]",
            )
            _strict_keys(
                item,
                required={"id", "eventKind"},
                optional={
                    "minimum",
                    "requireFullContent",
                    "allowRedacted",
                    "mandatory",
                    "parentKind",
                },
                path=f"$.evidenceFidelity.claims[{claim_index}].requirements[{index}]",
            )
            minimum = item.get("minimum", 1)
            if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
                raise FormatError(
                    "SOVA-RESEARCH-CONTRACT",
                    "evidence minimum must be a positive integer",
                    path=(
                        f"$.evidenceFidelity.claims[{claim_index}].requirements[{index}].minimum"
                    ),
                )
            requirements.append(
                EvidenceRequirement(
                    id=_string(
                        item["id"],
                        f"$.evidenceFidelity.claims[{claim_index}].requirements[{index}].id",
                    ),
                    event_kind=_string(
                        item["eventKind"],
                        (
                            f"$.evidenceFidelity.claims[{claim_index}]"
                            f".requirements[{index}].eventKind"
                        ),
                    ),
                    minimum=minimum,
                    require_full_content=_boolean(
                        item.get("requireFullContent"),
                        (
                            f"$.evidenceFidelity.claims[{claim_index}]"
                            f".requirements[{index}].requireFullContent"
                        ),
                        default=True,
                    ),
                    allow_redacted=_boolean(
                        item.get("allowRedacted"),
                        (
                            f"$.evidenceFidelity.claims[{claim_index}]"
                            f".requirements[{index}].allowRedacted"
                        ),
                        default=False,
                    ),
                    mandatory=_boolean(
                        item.get("mandatory"),
                        (
                            f"$.evidenceFidelity.claims[{claim_index}]"
                            f".requirements[{index}].mandatory"
                        ),
                        default=True,
                    ),
                    parent_kind=(
                        _string(
                            item["parentKind"],
                            (
                                f"$.evidenceFidelity.claims[{claim_index}]"
                                f".requirements[{index}].parentKind"
                            ),
                        )
                        if item.get("parentKind") is not None
                        else None
                    ),
                )
            )
        if not requirements:
            raise FormatError(
                "SOVA-RESEARCH-CONTRACT",
                "a fidelity claim requires at least one evidence requirement",
                path=f"$.evidenceFidelity.claims[{claim_index}].requirements",
            )
        claims.append(
            (
                _string(claim["id"], f"$.evidenceFidelity.claims[{claim_index}].id"),
                tuple(requirements),
            )
        )
    if not claims:
        raise FormatError(
            "SOVA-RESEARCH-CONTRACT",
            "evidence fidelity requires at least one claim",
            path="$.evidenceFidelity.claims",
        )
    return tuple(claims)


def _parse_conformance(
    value: Any,
) -> tuple[
    tuple[str, ExecutorSemanticContract, tuple[str, ...]],
    ...,
]:
    document = _mapping(value, "$.executorConformance")
    _strict_keys(
        document,
        required={"contracts"},
        optional=set(),
        path="$.executorConformance",
    )
    contracts: list[tuple[str, ExecutorSemanticContract, tuple[str, ...]]] = []
    for contract_index, raw_contract in enumerate(
        _array(document["contracts"], "$.executorConformance.contracts")
    ):
        item = _mapping(
            raw_contract,
            f"$.executorConformance.contracts[{contract_index}]",
        )
        _strict_keys(
            item,
            required={
                "id",
                "action",
                "sideEffect",
                "allowedTerminalStatuses",
                "requiredEvidenceRoles",
                "observations",
                "trustedObserverIds",
            },
            optional=set(),
            path=f"$.executorConformance.contracts[{contract_index}]",
        )
        observations: list[ObservationRequirement] = []
        for index, raw in enumerate(
            _array(
                item["observations"],
                f"$.executorConformance.contracts[{contract_index}].observations",
            )
        ):
            observation = _mapping(
                raw,
                f"$.executorConformance.contracts[{contract_index}].observations[{index}]",
            )
            _strict_keys(
                observation,
                required={"id", "kind", "path", "expected"},
                optional=set(),
                path=(f"$.executorConformance.contracts[{contract_index}].observations[{index}]"),
            )
            observations.append(
                ObservationRequirement(
                    id=_string(
                        observation["id"],
                        (
                            f"$.executorConformance.contracts[{contract_index}]"
                            f".observations[{index}].id"
                        ),
                    ),
                    kind=_string(
                        observation["kind"],
                        (
                            f"$.executorConformance.contracts[{contract_index}]"
                            f".observations[{index}].kind"
                        ),
                    ),
                    path=tuple(
                        _string(
                            component,
                            (
                                f"$.executorConformance.contracts[{contract_index}]"
                                f".observations[{index}].path"
                            ),
                        )
                        for component in _array(
                            observation["path"],
                            (
                                f"$.executorConformance.contracts[{contract_index}]"
                                f".observations[{index}].path"
                            ),
                        )
                    ),
                    expected=observation["expected"],
                )
            )
        contract = ExecutorSemanticContract(
            action=_string(
                item["action"],
                f"$.executorConformance.contracts[{contract_index}].action",
            ),
            side_effect=_string(
                item["sideEffect"],
                f"$.executorConformance.contracts[{contract_index}].sideEffect",
            ),
            allowed_terminal_statuses=tuple(
                _string(
                    value,
                    (f"$.executorConformance.contracts[{contract_index}].allowedTerminalStatuses"),
                )
                for value in _array(
                    item["allowedTerminalStatuses"],
                    (f"$.executorConformance.contracts[{contract_index}].allowedTerminalStatuses"),
                )
            ),
            required_evidence_roles=tuple(
                _string(
                    value,
                    (f"$.executorConformance.contracts[{contract_index}].requiredEvidenceRoles"),
                )
                for value in _array(
                    item["requiredEvidenceRoles"],
                    (f"$.executorConformance.contracts[{contract_index}].requiredEvidenceRoles"),
                )
            ),
            observations=tuple(observations),
        )
        trusted = tuple(
            _string(
                value,
                (f"$.executorConformance.contracts[{contract_index}].trustedObserverIds"),
            )
            for value in _array(
                item["trustedObserverIds"],
                (f"$.executorConformance.contracts[{contract_index}].trustedObserverIds"),
            )
        )
        contracts.append(
            (
                _string(
                    item["id"],
                    f"$.executorConformance.contracts[{contract_index}].id",
                ),
                contract,
                trusted,
            )
        )
    if not contracts:
        raise FormatError(
            "SOVA-RESEARCH-CONTRACT",
            "executor conformance requires at least one contract",
            path="$.executorConformance.contracts",
        )
    return tuple(contracts)


def load_research_extension(capsule: Path) -> dict[str, Any]:
    reader = PackageReader(capsule)
    reader.verify("sova.capsule")
    manifest = reader.manifest("sova.capsule")
    extensions = _mapping(manifest.get("extensions"), "$.extensions")
    if EXTENSION_NAME not in extensions:
        raise FormatError(
            "SOVA-RESEARCH-EXTENSION-MISSING",
            f"capsule does not carry private extension {EXTENSION_NAME!r}",
            path=f"$.extensions.{EXTENSION_NAME}",
        )
    return validate_research_extension(
        _mapping(extensions[EXTENSION_NAME], f"$.extensions.{EXTENSION_NAME}")
    )


def _availability(
    predicates: Sequence[OutcomePredicate],
    trace_manifest: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
) -> dict[str, bool]:
    policy = _mapping(trace_manifest.get("capturePolicy"), "$.capturePolicy")
    included = _array(policy.get("includedFamilies"), "$.capturePolicy.includedFamilies")
    dropped = policy.get("droppedEventCount")
    if not isinstance(dropped, int) or isinstance(dropped, bool):
        raise FormatError(
            "SOVA-RESEARCH-TRACE-POLICY",
            "trace droppedEventCount must be an integer",
            path="$.capturePolicy.droppedEventCount",
        )
    completion = trace_manifest.get("completion")
    prefix_complete = completion in {"completed", "failed", "cancelled", "timeout"}
    availability: dict[str, bool] = {}
    for predicate in predicates:
        kinds = (predicate.event_kind, predicate.other_kind)
        for kind in kinds:
            if kind is None:
                continue
            captured_by_policy = "*" in included or any(
                isinstance(prefix, str) and kind.startswith(prefix) for prefix in included
            )
            observed = any(event.get("kind") == kind for event in events)
            availability[kind] = bool(
                captured_by_policy and (observed or (dropped == 0 and prefix_complete))
            )
    return availability


def evaluate_integrated_research(
    capsule: Path,
    trace: Path,
    *,
    candidate_context: Mapping[str, Any],
    safe_to_compare: bool = True,
) -> IntegratedResearchReport:
    """Evaluate all private candidates against one verified public trace."""
    extension = load_research_extension(capsule)
    trace_reader = TraceReader(trace)
    verification = trace_reader.verify()
    trace_manifest = trace_reader.manifest()
    events = trace_reader.events()

    predicates, source_context, context_rules = _parse_semantic(extension["semanticReproduction"])
    adjudication = _parse_adjudication(extension["semanticReproduction"].get("adjudication"))
    signature_verified = verification.signature_valid if verification.signature_present else None
    fidelity = tuple(
        assess_fidelity(
            claim_id=claim_id,
            requirements=requirements,
            manifest=trace_manifest,
            events=events,
            integrity_valid=bool(
                verification.package_integrity and verification.event_chain_integrity
            ),
            signature_verified=signature_verified,
        )
        for claim_id, requirements in _parse_fidelity(extension["evidenceFidelity"])
    )
    semantic = decide_reproduction(
        predicates=predicates,
        events=events,
        source_context=source_context,
        candidate_context=_mapping(_copy_json(candidate_context), "$.candidateContext"),
        context_rules=context_rules,
        availability=_availability(predicates, trace_manifest, events),
        safe_to_compare=safe_to_compare,
        evidence_valid=bool(verification.package_integrity and verification.event_chain_integrity),
    )
    if semantic.outcome in {SemanticOutcome.EQUIVALENT, SemanticOutcome.DIVERGENT} and any(
        item.support == ClaimSupport.INCONCLUSIVE for item in fidelity
    ):
        semantic = ReproductionDecision(
            SemanticOutcome.INCONCLUSIVE,
            semantic.contract,
            semantic.context,
            "behavioral predicate result was bounded by insufficient claim evidence",
        )

    conformance_results: list[tuple[str, ConformanceResult]] = []
    for identifier, contract, trusted_observers in _parse_conformance(
        extension["executorConformance"]
    ):
        requests = [
            event
            for event in events
            if event.get("kind") == "tool.requested"
            and isinstance(event.get("payload"), Mapping)
            and isinstance(event["payload"].get("request"), Mapping)
            and event["payload"]["request"].get("action") == contract.action
        ]
        request_event = requests[0] if requests else {}
        request_payload = (
            request_event.get("payload", {}).get("request", {})
            if isinstance(request_event.get("payload"), Mapping)
            else {}
        )
        outcomes = [
            event
            for event in events
            if event.get("kind") in {"tool.completed", "tool.failed"}
            and (
                not request_event
                or request_event.get("id") in event.get("parents", [])
                or event.get("phase") == request_event.get("phase")
            )
        ]
        provider_outcome = (
            outcomes[0].get("payload", {}).get("outcome", {})
            if outcomes and isinstance(outcomes[0].get("payload"), Mapping)
            else {}
        )
        observations: list[dict[str, Any]] = []
        for event in events:
            producer = event.get("producer")
            producer_id = producer.get("id") if isinstance(producer, Mapping) else producer
            if producer_id not in trusted_observers:
                continue
            observations.append(
                {
                    **event,
                    "producer": "sova-observer",
                }
            )
        conformance_results.append(
            (
                identifier,
                check_conformance(
                    contract=contract,
                    request=(dict(request_payload) if isinstance(request_payload, Mapping) else {}),
                    provider_outcome=(
                        dict(provider_outcome) if isinstance(provider_outcome, Mapping) else {}
                    ),
                    observations=observations,
                ),
            )
        )

    return IntegratedResearchReport(
        capsule_digest=sha256_digest(capsule.read_bytes()),
        trace_digest=sha256_digest(trace.read_bytes()),
        contract_version=extension["schemaVersion"],
        semantic=semantic,
        adjudication=adjudication,
        fidelity=fidelity,
        conformance=tuple(conformance_results),
        limitations=(
            "This is a private same-team research implementation, not a released SOVA API.",
            "A valid trace does not establish that the recorder, sensor, "
            "oracle, or signer was truthful.",
            "Categorical deterministic decisions do not establish real-model "
            "or human-judge validity.",
        ),
    )


def render_integrated_report(report: IntegratedResearchReport) -> str:
    """Render one inert Markdown research summary."""
    lines = [
        "# Private SOVA research evaluation",
        "",
        f"- Method: `{report.method}`",
        f"- Contract: `{report.contract_version}`",
        f"- Capsule: `{report.capsule_digest}`",
        f"- Trace: `{report.trace_digest}`",
        f"- Semantic decision: `{report.semantic.outcome.value}`",
        f"- Adjudication: `{report.adjudication.status}` "
        f"({report.adjudication.agreement}, {report.adjudication.total_records} records)",
        "",
        "## Evidence fidelity",
        "",
    ]
    lines.extend(f"- `{item.claim_id}`: `{item.support.value}`" for item in report.fidelity)
    lines.extend(["", "## Executor conformance", ""])
    lines.extend(
        f"- `{identifier}`: `{result.status.value}`" for identifier, result in report.conformance
    )
    lines.extend(["", "## Limitations", ""])
    lines.extend(
        f"- {item.replace('<', '&lt;').replace('>', '&gt;')}" for item in report.limitations
    )
    lines.extend(["", "> Private research output. No capsule content was executed.", ""])
    return "\n".join(lines)


def migrate_research_extension(document: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministically migrate the explicit legacy private extension."""
    source = _mapping(_copy_json(document), "$")
    version = source.get("schemaVersion")
    if version == EXTENSION_VERSION:
        return validate_research_extension(source)
    if version != LEGACY_EXTENSION_VERSION:
        raise FormatError(
            "SOVA-RESEARCH-MIGRATION-VERSION",
            "no deterministic private research migration is registered",
            path="$.schemaVersion",
            details={"source": version, "target": EXTENSION_VERSION},
        )
    required = {"schemaVersion", "semantic", "claims", "executorContracts"}
    missing = required - set(source)
    if missing:
        raise FormatError(
            "SOVA-RESEARCH-MIGRATION-INFORMATION-DEFICIT",
            "legacy extension lacks information required by the destination",
            details={"missing": sorted(missing)},
        )
    unknown = {
        key: value
        for key, value in source.items()
        if key not in required | {"extensions", "migrationHistory"}
    }
    extensions = _mapping(source.get("extensions", {}), "$.extensions")
    if unknown:
        extensions = {**extensions, "x-legacy-unknown": unknown}
    history = list(_array(source.get("migrationHistory", []), "$.migrationHistory"))
    history.append(
        {
            "from": LEGACY_EXTENSION_VERSION,
            "to": EXTENSION_VERSION,
            "method": MIGRATION_METHOD,
        }
    )
    migrated = {
        "schemaVersion": EXTENSION_VERSION,
        "semanticReproduction": source["semantic"],
        "evidenceFidelity": {"claims": source["claims"]},
        "executorConformance": {"contracts": source["executorContracts"]},
        "migrationHistory": history,
        "extensions": extensions,
    }
    return validate_research_extension(migrated)


def migrate_research_capsule(source: Path, destination: Path) -> str:
    """Repackage a capsule with a migrated private extension without overwriting."""
    source = source.resolve()
    destination = destination.resolve()
    if source == destination or destination.exists():
        raise FormatError(
            "SOVA-RESEARCH-MIGRATION-DESTINATION",
            "research migration requires a distinct non-existing destination",
        )
    reader = PackageReader(source)
    descriptors = reader.verify("sova.capsule")
    manifest = reader.manifest("sova.capsule")
    extensions = _mapping(manifest.get("extensions"), "$.extensions")
    if EXTENSION_NAME not in extensions:
        raise FormatError(
            "SOVA-RESEARCH-EXTENSION-MISSING",
            f"capsule does not carry private extension {EXTENSION_NAME!r}",
        )
    migrated_manifest = _copy_json(manifest)
    migrated_manifest.pop("objects")
    migrated_manifest["extensions"][EXTENSION_NAME] = migrate_research_extension(
        _mapping(extensions[EXTENSION_NAME], f"$.extensions.{EXTENSION_NAME}")
    )
    writer = PackageWriter(migrated_manifest)
    for descriptor in descriptors:
        writer.add_bytes(
            role=descriptor.role,
            path=descriptor.path,
            media_type=descriptor.mediaType,
            data=reader.read_object(descriptor),
        )
    return writer.write(destination)


__all__ = [
    "EXTENSION_NAME",
    "EXTENSION_VERSION",
    "IntegratedResearchReport",
    "evaluate_integrated_research",
    "load_research_extension",
    "migrate_research_capsule",
    "migrate_research_extension",
    "render_integrated_report",
    "validate_research_extension",
]
