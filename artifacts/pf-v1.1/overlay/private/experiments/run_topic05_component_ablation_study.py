"""Post-result component ablations for the Topic 05 evidence mechanism."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from private.experiments.prototypes.conformance import (
    ExecutorSemanticContract,
    ObservationRequirement,
    check_conformance,
)
from private.experiments.prototypes.fidelity import (
    EvidenceRequirement,
    assess_fidelity,
    build_disclosure_bundle,
    verify_disclosed_events,
)
from sova.formats import (
    PackageReader,
    PackageWriter,
    canonical_json_bytes,
    sha256_digest,
    strict_json_loads,
)
from sova.formats.errors import FormatError
from sova.trace import TraceReader, TraceWriter, generate_ed25519_keypair
from sova.trace.integrity import unsigned_manifest_digest

ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "private"
    / "experiments"
    / "results"
    / "topic05-component-ablation-study-2026-07-31.json"
)
INDEPENDENT = ROOT / "scripts" / "sova_independent_verify.py"
NODE_INDEPENDENT = ROOT / "scripts" / "sova_independent_verify.mjs"


def _trace(
    path: Path,
    *,
    profile: str = "standard",
    signed: bool = False,
) -> tuple[str | None, str]:
    key = generate_ed25519_keypair() if signed else None
    writer = TraceWriter(
        path,
        capture_profile=profile,
        signing_key=key,
        verification_material=(
            {"timestamp": {"kind": "synthetic-unverified"}} if key is not None else None
        ),
    )
    started = writer.append("run.started", {"case": "component-ablation"})
    requested = writer.append(
        "tool.requested",
        {"request": {"id": "write", "action": "file.write", "inputs": {}}},
        parents=[started] if started else [],
    )
    observed = writer.append(
        "filesystem.observed",
        {"digest": "sha256:" + ("a" * 64), "effect": "created"},
        parents=[requested] if requested else [],
        producer={
            "id": "sova:actor:observer",
            "kind": "observer",
            "name": "SOVA fixture observer",
        },
    )
    completed = writer.append(
        "tool.completed",
        {
            "outcome": {
                "status": "succeeded",
                "side_effect": "mutate",
                "evidence": [{"role": "artifact"}],
            }
        },
        parents=[requested] if requested else [],
        producer={
            "id": "external:provider",
            "kind": "executor",
            "name": "Synthetic provider",
        },
    )
    oracle = writer.append(
        "oracle.completed",
        {"status": "pass"},
        parents=[item for item in (observed, completed) if item],
        producer={
            "id": "sova:actor:oracle",
            "kind": "observer",
            "name": "SOVA deterministic oracle",
        },
    )
    writer.append(
        "run.completed",
        {"status": "completed"},
        parents=[oracle] if oracle else [],
    )
    writer.add_blob(b"content-addressed-fixture")
    writer.finalize()
    return (key.key_id if key is not None else None), sha256_digest(b"content-addressed-fixture")


def _repack(
    source: Path,
    destination: Path,
    mutate: Callable[[str, bytes], bytes],
) -> None:
    reader = PackageReader(source)
    manifest = reader.manifest("sova.trace")
    descriptors = reader.verify("sova.trace")
    base = strict_json_loads(canonical_json_bytes(manifest))
    assert isinstance(base, dict)
    base.pop("objects")
    base["integrity"]["manifestDigest"] = None
    base["integrity"]["signature"] = None
    objects = [
        (
            descriptor.role,
            descriptor.path,
            descriptor.mediaType,
            mutate(descriptor.path, reader.read_object(descriptor)),
        )
        for descriptor in descriptors
    ]
    initial = PackageWriter(base)
    for role, object_path, media_type, data in objects:
        initial.add_bytes(
            role=role,
            path=object_path,
            media_type=media_type,
            data=data,
        )
    complete = initial.finalized_manifest()
    complete["segments"] = [item for item in complete["objects"] if item["role"] == "event-segment"]
    complete["integrity"]["manifestDigest"] = unsigned_manifest_digest(complete)
    complete.pop("objects")
    final = PackageWriter(complete)
    for role, object_path, media_type, data in objects:
        final.add_bytes(
            role=role,
            path=object_path,
            media_type=media_type,
            data=data,
        )
    final.write(destination)


def _mutate_first_event(_path: str, data: bytes) -> bytes:
    if not _path.startswith("events/"):
        return data
    lines = data.splitlines()
    event = strict_json_loads(lines[0])
    assert isinstance(event, dict)
    event["payload"]["case"] = "modified-without-rehashing-event"
    lines[0] = canonical_json_bytes(event)
    return b"\n".join(lines) + b"\n"


def _substitute_blob(source: Path, destination: Path) -> None:
    with (
        zipfile.ZipFile(source) as original,
        zipfile.ZipFile(
            destination,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as changed,
    ):
        for info in original.infolist():
            data = original.read(info)
            if info.filename.startswith("blobs/sha256/"):
                data = b"substituted-same-ish-bytes"
            changed.writestr(info, data)


def _failure_code(operation: Callable[[], Any]) -> str | None:
    try:
        operation()
    except FormatError as error:
        return error.issue.code
    return None


def _independent(path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INDEPENDENT), str(path), *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _independent_node(
    path: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str] | None:
    node = shutil.which("node")
    if node is None:
        return None
    return subprocess.run(
        [node, str(NODE_INDEPENDENT), str(path), *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sova-topic05-ablation-") as raw:
        work = Path(raw)
        standard = work / "standard.sova-trace"
        lite = work / "lite.sova-trace"
        signed = work / "signed.sova-trace"
        key_id, _blob_digest = _trace(standard)
        _trace(lite, profile="lite")
        signed_key_id, _ = _trace(signed, signed=True)
        assert key_id is None
        assert signed_key_id is not None

        requirements = (
            EvidenceRequirement(
                "provider-outcome",
                "tool.completed",
                parent_kind="tool.requested",
            ),
            EvidenceRequirement(
                "filesystem-effect",
                "filesystem.observed",
            ),
            EvidenceRequirement(
                "oracle",
                "oracle.completed",
            ),
        )
        standard_reader = TraceReader(standard)
        standard_reader.verify()
        standard_fidelity = assess_fidelity(
            claim_id="verified-write",
            requirements=requirements,
            manifest=standard_reader.manifest(),
            events=standard_reader.events(),
            integrity_valid=True,
        )
        invalid_fidelity = assess_fidelity(
            claim_id="verified-write",
            requirements=requirements,
            manifest=standard_reader.manifest(),
            events=standard_reader.events(),
            integrity_valid=False,
        )
        ablated_integrity = assess_fidelity(
            claim_id="verified-write",
            requirements=requirements,
            manifest=standard_reader.manifest(),
            events=standard_reader.events(),
            integrity_valid=True,
        )
        lite_reader = TraceReader(lite)
        lite_fidelity = assess_fidelity(
            claim_id="verified-write",
            requirements=requirements,
            manifest=lite_reader.manifest(),
            events=lite_reader.events(),
            integrity_valid=True,
        )

        chain_mutant = work / "chain-mutant.sova-trace"
        _repack(standard, chain_mutant, _mutate_first_event)
        package_only_accepts = bool(PackageReader(chain_mutant).verify("sova.trace"))
        chain_rejection = _failure_code(lambda: TraceReader(chain_mutant).verify())

        blob_mutant = work / "blob-mutant.sova-trace"
        _substitute_blob(standard, blob_mutant)
        blob_rejection = _failure_code(lambda: PackageReader(blob_mutant).verify("sova.trace"))

        events = standard_reader.events()
        oracle = next(item for item in events if item["kind"] == "oracle.completed")
        bundle = build_disclosure_bundle(
            claim_id="verified-write",
            source_trace_digest=sha256_digest(standard.read_bytes()),
            events=events,
            disclose_event_ids=[oracle["id"]],
            nonce_factory=lambda count: b"\x42" * count,
        )
        missing_without_closure = [
            parent for parent in oracle["parents"] if parent not in {oracle["id"]}
        ]
        closure_contains_parents = all(
            parent in bundle.disclosed_event_ids for parent in oracle["parents"]
        )
        disclosed = list(bundle.commitments)
        visible = next(index for index, item in enumerate(disclosed) if item.event is not None)
        tampered_item = disclosed[visible]
        assert tampered_item.event is not None
        changed_event = json.loads(json.dumps(tampered_item.event))
        changed_event["payload"] = {"tampered": True}
        disclosed[visible] = type(tampered_item)(
            tampered_item.sequence,
            tampered_item.event_id,
            tampered_item.digest,
            tampered_item.nonce,
            changed_event,
        )
        tampered_bundle = type(bundle)(
            bundle.claim_id,
            bundle.source_trace_digest,
            bundle.commitment_root,
            tuple(disclosed),
            bundle.disclosed_event_ids,
            bundle.limitations,
        )

        contract = ExecutorSemanticContract(
            action="file.write",
            side_effect="mutate",
            allowed_terminal_statuses=("succeeded",),
            required_evidence_roles=("artifact",),
            observations=(
                ObservationRequirement(
                    "effect",
                    "filesystem.observed",
                    ("payload", "effect"),
                    "created",
                ),
            ),
        )
        provider_outcome = {
            "status": "succeeded",
            "side_effect": "mutate",
            "evidence": [{"role": "artifact"}],
        }
        trusted_observations = [
            {**event, "producer": "sova-observer"}
            for event in events
            if event["producer"]["id"] == "sova:actor:observer"
        ]
        conformance_with_provenance = check_conformance(
            contract=contract,
            request={"action": "file.write"},
            provider_outcome=provider_outcome,
            observations=trusted_observations,
        )
        conformance_without_provenance = check_conformance(
            contract=contract,
            request={"action": "file.write"},
            provider_outcome=provider_outcome,
            observations=[],
        )

        signed_reader = TraceReader(signed)
        included = signed_reader.verify(require_signature=True)
        required = signed_reader.verify(
            require_signature=True,
            required_key_id=signed_key_id,
        )
        wrong_key = _failure_code(
            lambda: signed_reader.verify(
                require_signature=True,
                required_key_id="sha256:" + ("0" * 64),
            )
        )
        independent_signed = _independent(
            signed,
            "--required-key-id",
            signed_key_id,
        )
        independent_chain = _independent(chain_mutant)
        node_signed = _independent_node(
            signed,
            "--required-key-id",
            signed_key_id,
        )
        node_chain = _independent_node(chain_mutant)

        result = {
            "artifactType": "sova.private-topic05-component-ablation",
            "version": "0.1.0",
            "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "owner": "Gautam R. Patil",
            "organization": "TRUSCOR Private Limited",
            "claimBoundary": (
                "Same-team post-result component tests; not a cryptographic proof "
                "or independent privacy review."
            ),
            "hashChain": {
                "repackedPackageDescriptorLayerAccepted": package_only_accepts,
                "fullVerifierRejection": chain_rejection,
                "interpretation": (
                    "After an attacker recomputes package descriptors and the unsigned "
                    "manifest digest, the stale event hash remains detectable."
                ),
            },
            "contentAddressing": {
                "blobSubstitutionRejection": blob_rejection,
                "deduplicatedBlobCount": len(
                    [
                        item
                        for item in PackageReader(standard).verify("sova.trace")
                        if item.role == "blob"
                    ]
                ),
                "interpretation": (
                    "Object addressing detects byte substitution only while an expected "
                    "digest remains authenticated; a fully re-authored manifest is a new artifact."
                ),
            },
            "provenance": {
                "withTrustedObserver": conformance_with_provenance.status.value,
                "withoutTrustedObserver": conformance_without_provenance.status.value,
                "providerStatusOnlyWouldSay": "conformant",
            },
            "fidelityPropagation": {
                "fullEvidence": standard_fidelity.support.value,
                "integrityInvalid": invalid_fidelity.support.value,
                "integrityGateAblated": ablated_integrity.support.value,
                "interpretation": (
                    "Ignoring known invalidity creates a false supported conclusion."
                ),
            },
            "selectiveDisclosure": {
                "naiveSeedOnlyMissingParentCount": len(missing_without_closure),
                "dependencyClosureContainsAllDirectParents": closure_contains_parents,
                "bundleVerifies": verify_disclosed_events(bundle),
                "tamperedDisclosureRejected": not verify_disclosed_events(tampered_bundle),
                "disclosedCount": len(bundle.disclosed_event_ids),
                "totalEventCount": len(events),
            },
            "captureProfiles": {
                "standardClaim": standard_fidelity.support.value,
                "liteClaim": lite_fidelity.support.value,
                "liteDroppedEvents": lite_reader.manifest()["capturePolicy"]["droppedEventCount"],
                "profileNameOnlyWouldSay": "unknown-without-claim-contract",
            },
            "externalTrust": {
                "includedKey": included.trust_policy,
                "requiredKey": required.trust_policy,
                "wrongRequiredKeyRejection": wrong_key,
                "verificationMaterialPresent": included.verification_material_present,
                "verificationMaterialVerified": included.verification_material_verified,
                "independentVerifierReturnCode": independent_signed.returncode,
                "independentVerifierTrustPolicy": (
                    json.loads(independent_signed.stdout)["trustPolicy"]
                    if independent_signed.returncode == 0
                    else None
                ),
            },
            "independentVerifier": {
                "importsSova": "from sova" in INDEPENDENT.read_text(encoding="utf-8"),
                "chainMutantReturnCode": independent_chain.returncode,
                "chainMutantRejected": independent_chain.returncode == 2,
                "nodeAvailable": node_signed is not None,
                "nodeSignedReturnCode": (
                    node_signed.returncode if node_signed is not None else None
                ),
                "nodeChainMutantRejected": (
                    node_chain.returncode == 2 if node_chain is not None else None
                ),
                "crossLanguageContentDigestAgrees": (
                    json.loads(node_signed.stdout)["contentDigest"]
                    == json.loads(independent_signed.stdout)["contentDigest"]
                    if node_signed is not None
                    and node_signed.returncode == 0
                    and independent_signed.returncode == 0
                    else None
                ),
            },
            "limitations": [
                "The independent verifier is same-team code even though it imports no SOVA module.",
                "Included-key validity is not external identity or non-repudiation.",
                "Timestamp material was bound but deliberately not externally verified.",
                "Disclosure commitments do not prove hidden plaintext truth or completeness.",
                "Privacy usability, correlation, dictionary, and traffic-analysis "
                "attacks remain external work.",
            ],
        }
        gates = [
            package_only_accepts,
            chain_rejection == "SOVA-TRACE-EVENT-HASH",
            blob_rejection == "SOVA-PACKAGE-INTEGRITY",
            conformance_with_provenance.status.value == "conformant",
            conformance_without_provenance.status.value == "inconclusive",
            standard_fidelity.support.value == "supported",
            invalid_fidelity.support.value == "inconclusive",
            closure_contains_parents,
            verify_disclosed_events(bundle),
            not verify_disclosed_events(tampered_bundle),
            lite_fidelity.support.value == "inconclusive",
            wrong_key == "SOVA-INTEGRITY-UNTRUSTED-SIGNER",
            independent_signed.returncode == 0,
            independent_chain.returncode == 2,
            (
                node_signed is None
                or (
                    node_signed.returncode == 0
                    and node_chain is not None
                    and node_chain.returncode == 2
                    and json.loads(node_signed.stdout)["contentDigest"]
                    == json.loads(independent_signed.stdout)["contentDigest"]
                )
            ),
        ]
        if not all(gates):
            raise AssertionError(f"Topic 05 component gate failed: {gates}")
        RESULT.parent.mkdir(parents=True, exist_ok=True)
        RESULT.write_bytes(canonical_json_bytes(result) + b"\n")
        print(RESULT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
