"""Quantitative privacy attack study for SOVA redaction strategies.

This same-team study measures concrete leakage and attack surfaces. It does not
constitute an independent privacy audit or a cryptographic proof.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sova.formats import canonical_json_bytes
from sova.trace.redaction import RedactionPolicy, Redactor

ROOT = Path(__file__).resolve().parents[2]
RESULT = (
    ROOT
    / "private"
    / "experiments"
    / "results"
    / "topic05-privacy-attack-study-2026-08-01.json"
)


def _marker(value: Any, *, policy: RedactionPolicy, context: str) -> dict[str, Any]:
    redacted, _records = Redactor(policy, context_id=context).redact({"token": value})
    return redacted["token"]["$redacted"]


def _pearson(left: list[int], right: list[int]) -> float:
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum(
        (x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=True)
    )
    left_scale = math.sqrt(sum((x - left_mean) ** 2 for x in left))
    right_scale = math.sqrt(sum((y - right_mean) ** 2 for y in right))
    return numerator / (left_scale * right_scale)


def _dictionary_recovery() -> dict[str, Any]:
    candidates = [f"synthetic-pin-{index:04d}" for index in range(100)]
    secret = candidates[42]
    unkeyed_target = hashlib.sha256(canonical_json_bytes(secret)).digest()
    unkeyed_matches = [
        candidate
        for candidate in candidates
        if hashlib.sha256(canonical_json_bytes(candidate)).digest() == unkeyed_target
    ]

    policy = RedactionPolicy(
        method="keyed-commitment",
        commitment_key=b"K" * 32,
        key_id="synthetic-study-key",
    )
    target = _marker(secret, policy=policy, context="trace-a")["commitment"]
    compromised_key_matches = [
        candidate
        for candidate in candidates
        if _marker(candidate, policy=policy, context="trace-a")["commitment"] == target
    ]
    naive_unkeyed_matches = [
        candidate
        for candidate in candidates
        if base64.urlsafe_b64encode(hashlib.sha256(canonical_json_bytes(candidate)).digest())
        .decode("ascii")
        == target
    ]
    return {
        "dictionarySize": len(candidates),
        "unkeyedHashRecoveredUniqueCandidate": unkeyed_matches == [secret],
        "keyedCommitmentNaiveUnkeyedMatches": len(naive_unkeyed_matches),
        "compromisedKeyRecoveredUniqueCandidate": compromised_key_matches == [secret],
        "interpretation": (
            "Unkeyed hashes permit direct low-entropy dictionary recovery. HMAC removes "
            "that public oracle only while the high-entropy key remains secret; compromise "
            "restores dictionary recovery. This experiment does not prove HMAC security."
        ),
    }


def _linkage() -> dict[str, Any]:
    policy = RedactionPolicy(
        method="keyed-commitment",
        commitment_key=b"L" * 32,
        key_id="synthetic-study-key",
    )
    same_a = _marker("synthetic-repeat", policy=policy, context="trace-a")["commitment"]
    same_a_again = _marker("synthetic-repeat", policy=policy, context="trace-a")[
        "commitment"
    ]
    same_b = _marker("synthetic-repeat", policy=policy, context="trace-b")["commitment"]
    different_a = _marker("synthetic-other", policy=policy, context="trace-a")["commitment"]
    return {
        "sameValueSameContextLinkable": same_a == same_a_again,
        "sameValueDifferentContextLinkable": same_a == same_b,
        "differentValueSameContextCollision": same_a == different_a,
        "interpretation": (
            "The design intentionally supports equality correlation within one context "
            "and domain-separates different contexts. Context identifiers and paths remain "
            "metadata and can still enable non-cryptographic linkage."
        ),
    }


def _length_and_structure() -> dict[str, Any]:
    lengths = [1, 4, 8, 16, 32, 64, 128]
    encryption = RedactionPolicy(method="encrypted", encryption_key=b"E" * 32)
    omitted = RedactionPolicy(method="omitted")
    padded = RedactionPolicy(
        method="encrypted",
        encryption_key=b"P" * 32,
        encryption_padding_bytes=64,
    )
    plaintext_bytes: list[int] = []
    ciphertext_bytes: list[int] = []
    omitted_bytes: list[int] = []
    encrypted_bytes: list[int] = []
    padded_ciphertext_bytes: list[int] = []
    for length in lengths:
        value = "x" * length
        encrypted_marker = _marker(value, policy=encryption, context="trace-length")
        omitted_marker = _marker(value, policy=omitted, context="trace-length")
        padded_marker = _marker(value, policy=padded, context="trace-length")
        plaintext_bytes.append(len(canonical_json_bytes(value)))
        ciphertext_bytes.append(
            len(base64.urlsafe_b64decode(encrypted_marker["ciphertext"]))
        )
        omitted_bytes.append(len(canonical_json_bytes(omitted_marker)))
        encrypted_bytes.append(len(canonical_json_bytes(encrypted_marker)))
        padded_ciphertext_bytes.append(
            len(base64.urlsafe_b64decode(padded_marker["ciphertext"]))
        )
    return {
        "sourceCharacterLengths": lengths,
        "canonicalPlaintextBytes": plaintext_bytes,
        "decodedCiphertextBytes": ciphertext_bytes,
        "omittedPlaceholderBytes": omitted_bytes,
        "encryptedPlaceholderBytes": encrypted_bytes,
        "paddedDecodedCiphertextBytes": padded_ciphertext_bytes,
        "ciphertextLengthCorrelation": f"{_pearson(plaintext_bytes, ciphertext_bytes):.6f}",
        "omissionSizeConstant": len(set(omitted_bytes)) == 1,
        "encryptionSizeConstant": len(set(encrypted_bytes)) == 1,
        "paddingCreatesLengthBuckets": len(set(padded_ciphertext_bytes)) < len(lengths),
        "pathAndPresenceRemainVisible": True,
        "interpretation": (
            "AES-GCM conceals plaintext but reveals canonical plaintext length plus a fixed "
            "authentication-tag overhead. Authenticated padding reduces exact length to a "
            "declared bucket but does not hide the bucket. Omission hides value length in "
            "this fixture while retaining field presence, class, method, and path records."
        ),
    }


def _nonce_and_detector_limits() -> dict[str, Any]:
    encryption = RedactionPolicy(method="encrypted", encryption_key=b"N" * 32)
    nonces = {
        _marker("synthetic-repeat", policy=encryption, context="trace-nonce")["nonce"]
        for _index in range(512)
    }
    obvious, obvious_records = Redactor().redact(
        {"note": "Bearer abcdefghijklmnopqrstuvwxyz"}
    )
    generic, generic_records = Redactor().redact(
        {"note": "synthetic-private-value-without-secret-shape"}
    )
    return {
        "nonceTrials": 512,
        "uniqueNonces": len(nonces),
        "nonceCollisions": 512 - len(nonces),
        "obviousSecretPatternRedacted": bool(obvious_records) and "$redacted" in obvious["note"],
        "genericUnknownSecretRedacted": bool(generic_records) or "$redacted" in generic["note"],
        "interpretation": (
            "No nonce collision occurred in the bounded sample. The best-effort detector "
            "catches declared key/value shapes but cannot identify arbitrary sensitive text "
            "or a malicious recorder; pre-export review and data minimization remain required."
        ),
    }


def run() -> dict[str, Any]:
    """Run the bounded study and return aggregate, non-secret evidence."""
    result = {
        "artifactType": "sova.private-topic05-privacy-attack-study",
        "version": "0.1.0",
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "owner": "Gautam R. Patil",
        "organization": "TRUSCOR Private Limited",
        "dictionaryRecovery": _dictionary_recovery(),
        "commitmentLinkage": _linkage(),
        "lengthAndStructureLeakage": _length_and_structure(),
        "nonceAndDetectorLimits": _nonce_and_detector_limits(),
        "policyDecision": {
            "publicExportDefault": "omitted",
            "keyedCommitment": "private equality checks with protected key only",
            "encrypted": "recoverable sensitive data; explicit recipient/key policy required",
            "padding": "optional authenticated buckets; bucket and structure leakage remain",
        },
        "claimBoundary": (
            "Same-team bounded attack study. Results quantify specific leakage and negative "
            "controls; they are not an independent privacy audit, anonymity guarantee, "
            "cryptographic proof, or regulatory conclusion."
        ),
    }
    return result


def main() -> int:
    result = run()
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(RESULT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
