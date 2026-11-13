"""Recompute the focused flagship paper's headline claims from retained evidence."""

from __future__ import annotations

import argparse
import json
import math
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
RESULTS = ROOT / "private" / "experiments" / "results"
PACKAGE = ROOT / "private" / "research" / "papers" / "arxiv" / "sova-portable-evidence-reproduction"


def load(name: str) -> dict[str, Any]:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def close(actual: float, expected: float, tolerance: float = 1e-12) -> None:
    if not math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance):
        raise AssertionError(f"expected {expected}, observed {actual}")


def wilson(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float]:
    proportion = successes / trials
    denominator = 1 + z * z / trials
    centre = (proportion + z * z / (2 * trials)) / denominator
    radius = (
        z
        * math.sqrt(proportion * (1 - proportion) / trials + z * z / (4 * trials * trials))
        / denominator
    )
    return centre - radius, centre + radius


def cited_urls() -> dict[str, str]:
    main = (PACKAGE / "main.md").read_text(encoding="utf-8")
    bibliography = (PACKAGE / "references.bib").read_text(encoding="utf-8")
    citation_blocks = re.findall(r"\[[^\]]*@[A-Za-z0-9_.:-]+[^\]]*\]", main)
    cited = {key for block in citation_blocks for key in re.findall(r"@([A-Za-z0-9_.:-]+)", block)}
    entries = {
        match.group(1): match.group(2)
        for match in re.finditer(
            r"@[A-Za-z]+\{([^,]+),(.*?)(?=\n@|\Z)",
            bibliography,
            flags=re.DOTALL,
        )
    }
    missing = sorted(cited - entries.keys())
    if missing:
        raise AssertionError(f"missing bibliography entries: {missing}")
    urls: dict[str, str] = {}
    for key in sorted(cited):
        match = re.search(r"\n\s*url\s*=\s*\{([^}]+)\}", entries[key])
        if match is None:
            raise AssertionError(f"cited bibliography entry has no URL: {key}")
        urls[key] = match.group(1)
    return urls


def validate_online(urls: dict[str, str]) -> dict[str, Any]:
    outcomes: dict[str, Any] = {}
    for key, url in urls.items():
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "SOVA-publication-citation-check/0.1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = int(getattr(response, "status", 200))
                final_url = response.geturl()
                response.read(256)
            if status < 200 or status >= 400:
                raise AssertionError(f"{key} returned HTTP {status}")
            outcomes[key] = {"status": status, "finalUrl": final_url}
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                outcomes[key] = {
                    "status": exc.code,
                    "finalUrl": exc.geturl(),
                    "access": "automated retrieval restricted",
                }
                continue
            raise AssertionError(f"citation URL failed for {key}: {exc}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise AssertionError(f"citation URL failed for {key}: {exc}") from exc
    return outcomes


def validate(online: bool) -> dict[str, Any]:
    topics = load("topics-04-06-study-2026-07-31.json")
    public_contract = load("topics12-13-postbuild-study-2026-08-03.json")["topic12"]
    agentreward = load("agentreward-cross-model-study-2026-07-31.json")
    baselines = load("p4-graph-semantic-baselines-2026-08-01.json")
    ablation = load("topic05-component-ablation-study-2026-07-31.json")
    privacy = load("topic05-privacy-attack-study-2026-08-01.json")
    scale = load("p5-incident-collector-scale-2026-08-01.json")

    semantic = topics["semantic"]
    fidelity = topics["fidelity"]
    assert semantic["count"] == 144
    close(semantic["metrics"]["candidate"]["macro_f1"], 1.0)
    close(semantic["metrics"]["exact_trace"]["macro_f1"], 1 / 9)
    close(semantic["wilson"]["minimum_cell_coverage"], 0.914)
    close(semantic["exact_interval"]["minimum_cell_coverage"], 0.955690107191223)

    assert fidelity["count"] == 120
    close(fidelity["metrics"]["candidate"]["accuracy"], 1.0)
    close(fidelity["metrics"]["integrity_only"]["accuracy"], 1 / 3)
    close(fidelity["metrics"]["profile_only"]["accuracy"], 1 / 6)
    close(fidelity["metrics"]["full_share"]["accuracy"], 1 / 6)

    assert public_contract["contracts"] == 12
    assert public_contract["candidateTraces"] == 96
    assert public_contract["correctContracts"] == 12
    assert public_contract["acceptedIncompleteAsReproduced"] == 0
    assert sum(len(row["observed"]) for row in public_contract["rows"]) == 96

    assert agentreward["summary"]["pairs"] == 11
    assert agentreward["summary"]["tracesVerified"] == 22
    assert agentreward["summary"]["outcomes"] == {
        "divergent": 5,
        "equivalent": 2,
        "inconclusive": 4,
    }
    estimate = agentreward["reproductionEstimate"]
    low, high = wilson(2, 7)
    close(estimate["wilson_low"], low)
    close(estimate["wilson_high"], high)
    close(estimate["identification_low"], 2 / 11)
    close(estimate["identification_high"], 6 / 11)

    assert baselines["trajectoryMetrics"]["graph"]["correct"] == 5
    assert baselines["trajectoryMetrics"]["semantic"]["correct"] == 7
    assert baselines["trajectoryMetrics"]["graph"]["totalConclusive"] == 7
    assert baselines["trajectoryMetrics"]["semantic"]["multiValuedOutcomesSupported"] is False

    assert ablation["fidelityPropagation"]["integrityInvalid"] == "inconclusive"
    assert ablation["fidelityPropagation"]["integrityGateAblated"] == "supported"
    assert privacy["dictionaryRecovery"]["unkeyedHashRecoveredUniqueCandidate"] is True
    assert privacy["dictionaryRecovery"]["keyedCommitmentNaiveUnkeyedMatches"] == 0
    assert privacy["lengthAndStructureLeakage"]["pathAndPresenceRemainVisible"] is True

    assert scale["scale"]["largestCase"] == 50_000
    assert scale["scale"]["allSignedRequiredKeyVerified"] is True
    assert scale["scale"]["allCrossLanguageDigestsAgree"] is True
    assert scale["collectorBackend"]["officialChecksumMatched"] is True
    assert scale["collectorBackend"]["submittedSpans"] == 8
    assert scale["collectorBackend"]["backendSpans"] == 8
    assert scale["incidentInteroperability"]["officialParserAccepted"] is True
    assert scale["incidentInteroperability"]["fidelity"]["lossless"] is False

    urls = cited_urls()
    report: dict[str, Any] = {
        "artifactType": "sova.paper-claim-validation",
        "paper": "PF-sova-portable-evidence-reproduction",
        "status": "pass",
        "checks": {
            "semanticCorpus": 144,
            "fidelityCorpus": 120,
            "publicContractDecisions": 96,
            "agentRewardPairs": 11,
            "agentRewardOutcomes": agentreward["summary"]["outcomes"],
            "largestSignedTrace": 50_000,
            "citedSources": len(urls),
        },
    }
    if online:
        report["onlineCitationChecks"] = validate_online(urls)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true")
    args = parser.parse_args()
    print(json.dumps(validate(args.online), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
