"""Regression tests for the retained Topic 05 privacy attack study."""

from __future__ import annotations

from private.experiments.run_topic05_privacy_attack_study import run


def test_privacy_attack_study_retains_positive_and_negative_results() -> None:
    result = run()
    dictionary = result["dictionaryRecovery"]
    assert dictionary["unkeyedHashRecoveredUniqueCandidate"] is True
    assert dictionary["keyedCommitmentNaiveUnkeyedMatches"] == 0
    assert dictionary["compromisedKeyRecoveredUniqueCandidate"] is True

    linkage = result["commitmentLinkage"]
    assert linkage["sameValueSameContextLinkable"] is True
    assert linkage["sameValueDifferentContextLinkable"] is False
    assert linkage["differentValueSameContextCollision"] is False

    leakage = result["lengthAndStructureLeakage"]
    assert leakage["ciphertextLengthCorrelation"] == "1.000000"
    assert leakage["omissionSizeConstant"] is True
    assert leakage["encryptionSizeConstant"] is False
    assert leakage["paddingCreatesLengthBuckets"] is True
    assert leakage["pathAndPresenceRemainVisible"] is True

    detector = result["nonceAndDetectorLimits"]
    assert detector["nonceCollisions"] == 0
    assert detector["obviousSecretPatternRedacted"] is True
    assert detector["genericUnknownSecretRedacted"] is False
