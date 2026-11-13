"""Private prototype: claim-conditioned trace evidence fidelity and disclosure."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Mapping, Sequence

from sova.formats import canonical_json_bytes


class RequirementStatus(StrEnum):
    PRESENT = "present"
    REDACTED = "redacted"
    OMITTED = "omitted"
    MISSING = "missing"
    INVALID = "invalid"
    UNVERIFIED = "unverified"


class ClaimSupport(StrEnum):
    SUPPORTED = "supported"
    WEAKENED = "weakened"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class EvidenceRequirement:
    id: str
    event_kind: str
    minimum: int = 1
    require_full_content: bool = True
    allow_redacted: bool = False
    mandatory: bool = True
    parent_kind: str | None = None


@dataclass(frozen=True, slots=True)
class RequirementAssessment:
    requirement_id: str
    status: RequirementStatus
    event_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class FidelityReport:
    claim_id: str
    support: ClaimSupport
    assessments: tuple[RequirementAssessment, ...]
    capture_profile: str
    dropped_events: int
    integrity_valid: bool
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EventCommitment:
    sequence: int
    event_id: str
    digest: str
    nonce: str | None
    event: Mapping[str, Any] | None


@dataclass(frozen=True, slots=True)
class DisclosureBundle:
    claim_id: str
    source_trace_digest: str
    commitment_root: str
    commitments: tuple[EventCommitment, ...]
    disclosed_event_ids: tuple[str, ...]
    limitations: tuple[str, ...]


def _event_id(event: Mapping[str, Any]) -> str:
    value = event.get("id")
    return str(value) if value is not None else "<unidentified>"


def _captured(kind: str, manifest: Mapping[str, Any]) -> bool:
    policy = manifest.get("capturePolicy")
    if not isinstance(policy, Mapping):
        return False
    included = policy.get("includedFamilies")
    if not isinstance(included, list):
        return False
    return "*" in included or any(
        isinstance(prefix, str) and kind.startswith(prefix) for prefix in included
    )


def _redacted(event: Mapping[str, Any]) -> bool:
    redactions = event.get("redactions")
    if isinstance(redactions, list) and redactions:
        return True
    # Fail closed on any absent payload, not only on a typed placeholder. The PF
    # v1.1 redaction study (2026-11-12) found that a payload-free disclosure view
    # marks omission with ``payloadOmitted`` and no placeholder, which this check
    # previously read as full content (32 of 192 false-support evaluations).
    if event.get("payloadOmitted") is True or "payload" not in event:
        return True
    payload = event.get("payload")
    return isinstance(payload, Mapping) and "$redacted" in payload


def _parent_relationship_present(
    event: Mapping[str, Any],
    *,
    parent_kind: str,
    by_id: Mapping[str, Mapping[str, Any]],
) -> bool:
    parents = event.get("parents")
    if not isinstance(parents, list):
        return False
    return any(
        isinstance(parent, str)
        and parent in by_id
        and by_id[parent].get("kind") == parent_kind
        for parent in parents
    )


def assess_fidelity(
    *,
    claim_id: str,
    requirements: Sequence[EvidenceRequirement],
    manifest: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    integrity_valid: bool,
    signature_verified: bool | None = None,
) -> FidelityReport:
    by_id = {_event_id(event): event for event in events}
    assessments: list[RequirementAssessment] = []
    dropped = 0
    policy = manifest.get("capturePolicy")
    if isinstance(policy, Mapping) and isinstance(policy.get("droppedEventCount"), int):
        dropped = int(policy["droppedEventCount"])

    for requirement in requirements:
        selected = [event for event in events if event.get("kind") == requirement.event_kind]
        identifiers = tuple(_event_id(event) for event in selected)
        if not integrity_valid:
            status = RequirementStatus.INVALID
            reason = "trace integrity or structure verification failed"
        elif not _captured(requirement.event_kind, manifest) and not selected:
            status = RequirementStatus.OMITTED
            reason = "capture policy did not include the required event family"
        elif len(selected) < requirement.minimum:
            status = RequirementStatus.MISSING
            reason = f"observed {len(selected)} event(s); required {requirement.minimum}"
        elif requirement.parent_kind and not all(
            _parent_relationship_present(
                event,
                parent_kind=requirement.parent_kind,
                by_id=by_id,
            )
            for event in selected
        ):
            status = RequirementStatus.MISSING
            reason = "required causal parent relationship was absent"
        elif requirement.require_full_content and any(_redacted(event) for event in selected):
            status = RequirementStatus.REDACTED
            reason = "one or more required event payloads were redacted"
        elif signature_verified is False:
            status = RequirementStatus.UNVERIFIED
            reason = "the declared signature trust policy was not verified"
        else:
            status = RequirementStatus.PRESENT
            reason = "required observable evidence was present"
        assessments.append(RequirementAssessment(requirement.id, status, identifiers, reason))

    blocking = []
    weakening = []
    for requirement, assessment in zip(requirements, assessments, strict=True):
        if not requirement.mandatory:
            if assessment.status != RequirementStatus.PRESENT:
                weakening.append(assessment)
            continue
        if assessment.status == RequirementStatus.PRESENT:
            continue
        if assessment.status == RequirementStatus.REDACTED and requirement.allow_redacted:
            weakening.append(assessment)
        else:
            blocking.append(assessment)
    if blocking:
        support = ClaimSupport.INCONCLUSIVE
    elif weakening:
        support = ClaimSupport.WEAKENED
    else:
        support = ClaimSupport.SUPPORTED

    limitations = [
        "Integrity and signatures do not establish that recorded observations are true.",
        "Unobserved producer or sensor failures remain outside this report.",
    ]
    if dropped:
        limitations.append(
            f"The recorder reports {dropped} dropped event(s); unlisted losses may affect conclusions."
        )
    if signature_verified is None:
        limitations.append("No external signer-identity trust decision was supplied.")
    return FidelityReport(
        claim_id,
        support,
        tuple(assessments),
        str(manifest.get("captureProfile", "unknown")),
        dropped,
        integrity_valid,
        tuple(limitations),
    )


def dependency_closure(
    events: Sequence[Mapping[str, Any]],
    *,
    seed_event_ids: Sequence[str],
) -> tuple[str, ...]:
    by_id = {_event_id(event): event for event in events}
    selected = set(seed_event_ids)
    pending = list(seed_event_ids)
    while pending:
        identifier = pending.pop()
        event = by_id.get(identifier)
        if event is None:
            continue
        parents = event.get("parents")
        if not isinstance(parents, list):
            continue
        for parent in parents:
            if isinstance(parent, str) and parent in by_id and parent not in selected:
                selected.add(parent)
                pending.append(parent)
    return tuple(
        identifier
        for identifier, event in sorted(
            by_id.items(),
            key=lambda item: int(item[1].get("sequence", -1)),
        )
        if identifier in selected
    )


def build_disclosure_bundle(
    *,
    claim_id: str,
    source_trace_digest: str,
    events: Sequence[Mapping[str, Any]],
    disclose_event_ids: Sequence[str],
    nonce_factory: Callable[[int], bytes],
) -> DisclosureBundle:
    disclosed = set(dependency_closure(events, seed_event_ids=disclose_event_ids))
    commitments: list[EventCommitment] = []
    root_material = bytearray()
    for event in sorted(events, key=lambda item: int(item.get("sequence", -1))):
        sequence = int(event.get("sequence", -1))
        identifier = _event_id(event)
        nonce = nonce_factory(32)
        if len(nonce) != 32:
            raise ValueError("disclosure nonce factory must return exactly 32 bytes")
        digest = "sha256:" + hashlib.sha256(
            b"sova-disclosure-commitment/0.1\x00" + nonce + canonical_json_bytes(event)
        ).hexdigest()
        root_material.extend(sequence.to_bytes(8, "big", signed=True))
        root_material.extend(bytes.fromhex(digest[7:]))
        reveal = identifier in disclosed
        commitments.append(
            EventCommitment(
                sequence,
                identifier,
                digest,
                nonce.hex() if reveal else None,
                event if reveal else None,
            )
        )
    root = "sha256:" + hashlib.sha256(
        b"sova-disclosure-root/0.1\x00" + bytes(root_material)
    ).hexdigest()
    return DisclosureBundle(
        claim_id,
        source_trace_digest,
        root,
        tuple(commitments),
        tuple(identifier for identifier in dependency_closure(events, seed_event_ids=disclose_event_ids)),
        (
            "Commitments show consistency with a bound source only when the root is independently authenticated.",
            "A commitment does not prove that hidden content was true or complete.",
        ),
    )


def verify_disclosed_events(bundle: DisclosureBundle) -> bool:
    root_material = bytearray()
    for item in bundle.commitments:
        if (item.event is None) != (item.nonce is None):
            return False
        if item.event is not None and item.nonce is not None:
            nonce = bytes.fromhex(item.nonce)
            digest = "sha256:" + hashlib.sha256(
                b"sova-disclosure-commitment/0.1\x00"
                + nonce
                + canonical_json_bytes(item.event)
            ).hexdigest()
            if digest != item.digest or _event_id(item.event) != item.event_id:
                return False
        root_material.extend(item.sequence.to_bytes(8, "big", signed=True))
        root_material.extend(bytes.fromhex(item.digest[7:]))
    root = "sha256:" + hashlib.sha256(
        b"sova-disclosure-root/0.1\x00" + bytes(root_material)
    ).hexdigest()
    return root == bundle.commitment_root

