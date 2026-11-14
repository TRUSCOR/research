"""Assemble the public PF v1.1 validation artifact.

Copies, byte for byte, every file that the PF v1.1 preprint's numbers, figures,
protocols and build depend on into `<destination>/overlay/`, mirroring the
SOVA-OSS repository layout so the overlay can be copied into a SOVA-OSS checkout
and validated in place. Writes SHA256SUMS. Refuses to copy a file that matches
a credential pattern. Publishes nothing.

    python assemble_pf_artifact.py <destination-dir>
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
EXP = "private/experiments"
RES = f"{EXP}/results"
RSR = "private/research"
PAP = f"{RSR}/papers"

FILES = [
    # research prototype (all modules used by the PF studies; factor_lattice_search is a separate paper)
    *(f"{EXP}/prototypes/{name}.py" for name in ("__init__", "conformance", "fidelity", "inspect_ai_adapter", "integrated", "semantic")),
    # study scripts
    *(f"{EXP}/{name}.py" for name in (
        "run_topics_04_06_study", "run_agentreward_cross_model_study", "run_p4_graph_semantic_baselines",
        "run_topic05_component_ablation_study", "run_topic05_privacy_attack_study",
        "run_p5_incident_collector_scale", "run_topics12_13_postbuild_study", "run_inspect_corpus_interop",
        "run_inspect_eval_interop", "run_independent_adapter_study", "run_topic05_attack_matrix",
        "run_cross_version_validation", "run_integrated_baseline_study", "run_external_implementation_validation",
        "run_external_interop_study", "run_pf_redaction_triple", "run_pf_agentdojo_reproduction", "run_pf_agentdojo_supplementary",
        "run_pf_fresh_agentdojo", "classify_pf_warning_successes", "analyze_pf_real_attack_predictiveness",
        "summarize_pf_fresh_successes", "check_pf_published_text_collisions", "rerun_pf_studies", "research_cli", "external_review_kit",
        "azure_foundry_client", "analyze_pf_cross_provider", "analyze_pf_cross_provider_predictiveness",
        "build_pf_findings_gallery", "build_pf_recurrence_capsule", "recompute_recurrence_from_sova",
        "build_pf_reading_capsules", "tally_readings_from_sova", "agentdojo_to_sova",
        # 2026-11-14 confirmatory studies S1 to S7
        "run_pf_confirmatory", "audit_pf", "analyze_pf_v2", "read_pf_blind", "drive_pf_remaining",
        "package_pf_v2_runs", "scoreboard_table_pf", "compare_pf_neighbors", "test_compare_pf_neighbors",
        "check_pf_sova_audit", "audit_totals_pf", "posthoc_sensitivity_pf",
    )),
    # tests of the prototype and studies
    *(f"{EXP}/{name}.py" for name in (
        "test_research_prototypes", "test_integrated_research", "test_p4_graph_semantic_baselines",
        "test_p5_incident_collector_scale", "test_topic05_privacy_attack_study", "test_external_review_kit",
    )),
    # retained results cited by the paper
    *(f"{RES}/{name}" for name in (
        "topics-04-06-study-2026-07-31.json", "integrated-baseline-drift-study-2026-07-31.json",
        "agentreward-cross-model-study-2026-07-31.json", "p4-graph-semantic-baselines-2026-08-01.json",
        "topic05-component-ablation-study-2026-07-31.json", "topic05-privacy-attack-study-2026-08-01.json",
        "p5-incident-collector-scale-2026-08-01.json", "p5-repeatability-audit-2026-08-01.json",
        "topics12-13-postbuild-study-2026-08-03.json", "inspect-corpus-interoperability-2026-07-31.json",
        "inspect-corpus-interoperability-adapter-0.2.0-2026-07-31.json", "inspect-eval-interoperability-2026-08-01.json",
        "topic06-independent-adapter-study-2026-07-31.json", "topic05-attack-matrix-2026-07-31.json",
        "cross-version-python-3.11-2026-07-31.json", "cross-version-python-3.12-2026-07-31.json",
        "cross-version-python-3.13-2026-07-31.json", "cross-version-python-3.14-2026-07-31.json",
        "external-implementation-validation-2026-07-31.json", "external-implementation-validation-2026-08-01.json",
        "external-interoperability-study-2026-07-31.json", "pf-redaction-triple-2026-11-12.json",
        "pf-agentdojo-reproduction-2026-11-12.json",
        "pf-agentdojo-supplementary-2026-11-12.json", "pf-redaction-triple-postfix-2026-11-12.json",
        "pf-fresh-reexecution-2026-11-12.json", "pf-warning-classification-2026-11-12.json",
        "pf-real-attack-predictiveness-2026-11-12.json",
        "pf-fresh-successes-by-goal-2026-11-13.json", "pf-fresh-successes-manual-audit-2026-11-13.json",
        "pf-published-text-collisions-2026-11-13.json", "pf-published-hotel-reading-2026-11-13.json",
        "pf-cross-provider-2026-11-13.json", "pf-cross-provider-2026-11-13-reading-list.json",
        "pf-cross-provider-reading-2026-11-13.json", "pf-cross-provider-findings-2026-11-13.json",
        "pf-cross-provider-selection-2026-11-13.json", "pf-cross-provider-predictiveness-2026-11-13.json",
    )),
    # specifications, protocols, preregistrations, source ledgers, reviewer packet
    *(f"{RSR}/specifications/{name}" for name in (
        "semantic-reproduction-contract-0.1.md", "evidence-fidelity-envelope-0.1.md",
        "executor-semantic-conformance-0.1.md", "integrated-research-bridge-0.1.md",
        "research-extension-0.1.schema.json",
    )),
    f"{RSR}/external-validation-protocol-topics-04-06.md",
    f"{RSR}/topics-04-06-falsification-review.md",
    f"{RSR}/topic-04-05-source-ledger.md",
    f"{RSR}/topics-12-14-source-ledger-2026-08-03.md",
    f"{RSR}/reviewer-packets/README.md",
    # manuscript, protocols and build/validation tools
    f"{PAP}/PF-sova-portable-evidence-reproduction-working-paper.md",
    f"{PAP}/PF-agentdojo-reproduction-protocol-2026-11-12.md",
    f"{PAP}/PF-agentdojo-reproduction-protocol-2026-11-12.sha256",
    f"{PAP}/PF-envelope-predictive-validity-preregistration-2026-11-12.md",
    f"{PAP}/PF-fresh-reexecution-protocol-2026-11-12.md",
    f"{PAP}/PF-fresh-reexecution-protocol-2026-11-12.sha256",
    f"{PAP}/PF-real-attack-predictiveness-protocol-2026-11-12.md",
    f"{PAP}/PF-real-attack-predictiveness-protocol-2026-11-12.sha256",
    f"{PAP}/PF-cross-provider-protocol-2026-11-13.md",
    f"{PAP}/PF-cross-provider-protocol-2026-11-13.sha256",
    f"{PAP}/PF-cross-provider-predictiveness-addendum-2026-11-13.md",
    f"{PAP}/PF-cross-provider-predictiveness-addendum-2026-11-13.sha256",
    f"{PAP}/PF-confirmatory-protocol-2026-11-14.md",
    f"{PAP}/PF-head-to-head-addendum-2026-11-14.md",
    f"{PAP}/PF-confirmatory-deviations-2026-11-14.md",
    f"{PAP}/audit-spec-agentdojo-v1.2.2.json",
    *(f"{PAP}/tools/{name}" for name in (
        "build_pf_v1_1.py", "build_publication_packages.py", "validate_pf_v1_1.py", "validate_pf_claims.py",
        "assemble_pf_artifact.py", "references.bib", "README.md", "pf_cross_numbers.py",
    )),
    # v1.0 artifacts (the validator proves they are unchanged) and v1.1 outputs
    f"{PAP}/arxiv/sova-portable-evidence-reproduction/main.md",
    f"{PAP}/output/pdf/SOVA-PF-sova-portable-evidence-reproduction-v1.0-preprint.pdf",
    f"{PAP}/output/source/SOVA-PF-sova-portable-evidence-reproduction-arxiv-source-v1.0.tar.gz",
    f"{PAP}/output/pdf/SOVA-PF-sova-portable-evidence-reproduction-v1.1-preprint.pdf",
    f"{PAP}/output/source/SOVA-PF-sova-portable-evidence-reproduction-arxiv-source-v1.1.tar.gz",
]
DIRECTORIES = [
    f"{RES}/reexecution-2026-11-12",
    f"{RES}/pf-fresh-reexecution-2026-11-12",
    f"{RES}/pf-real-attack-predictiveness-2026-11-12",
    f"{RES}/pf-cross-provider-2026-11-13",
    f"{RES}/pf-cross-provider-perturb-2026-11-13",
    f"{RES}/pf-findings-gallery-2026-11-13",
    f"{RES}/pf-recurrence-in-sova-2026-11-13",
    f"{RES}/pf-readings-in-sova-2026-11-13",
    f"{RES}/pf-confirmatory-2026-11-14",
    f"{RES}/pf-audit-2026-11-14",
    f"{RSR}/reviewer-packets/templates",
    f"{PAP}/arxiv/sova-portable-evidence-reproduction-v1.1",
]
SECRET = re.compile(
    rb"(-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|"
    rb"(?<![A-Za-z0-9_-])sk-(?:proj-|ant-)?(?=[A-Za-z_-]*[0-9])[A-Za-z0-9_-]{32,}|hf_[A-Za-z0-9]{30,}|"
    rb"xox[baprs]-[A-Za-z0-9-]{20,}|AIza[0-9A-Za-z_-]{35})"
)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    destination = Path(sys.argv[1]).resolve()
    overlay = destination / "overlay"
    sources = [ROOT / f for f in FILES]
    for directory in DIRECTORIES:
        sources += [p for p in sorted((ROOT / directory).rglob("*")) if p.is_file() and "__pycache__" not in p.parts]
    missing = [str(p) for p in sources if not p.is_file()]
    if missing:
        raise SystemExit(f"missing files: {missing}")
    flagged = [str(p) for p in sources if SECRET.search(p.read_bytes())]
    if flagged:
        raise SystemExit(f"credential-like content found, nothing copied: {flagged}")
    # Private infrastructure names must never ship (the Azure resource behind the cross-provider runs).
    private_names = [n.encode() for n in os.environ.get("PF_PRIVATE_NAMES", "").split(",") if n]
    leaked = [str(p) for p in sources for n in private_names if n.lower() in p.read_bytes().lower()]
    if leaked:
        raise SystemExit(f"private infrastructure name found, nothing copied: {sorted(set(leaked))}")
    if overlay.exists():
        shutil.rmtree(overlay)
    sums = []
    for source in sources:
        relative = source.relative_to(ROOT).as_posix()
        target = overlay / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        sums.append(f"{hashlib.sha256(source.read_bytes()).hexdigest()}  overlay/{relative}")
    # The four .sova findings, also at the top of the artifact where readers look first.
    gallery = ROOT / RES / "pf-findings-gallery-2026-11-13"
    findings = destination / "findings"
    if findings.exists():
        shutil.rmtree(findings)
    for source in sorted(p for p in gallery.rglob("*") if p.is_file()):
        relative = source.relative_to(gallery).as_posix()
        target = findings / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        sums.append(f"{hashlib.sha256(source.read_bytes()).hexdigest()}  findings/{relative}")
    # The study evidence as .sova capsules, with the two scripts that recompute the counts from them.
    study = [
        *(ROOT / RES / "pf-recurrence-in-sova-2026-11-13").iterdir(),
        *(ROOT / RES / "pf-readings-in-sova-2026-11-13").iterdir(),
        ROOT / EXP / "recompute_recurrence_from_sova.py",
        ROOT / EXP / "tally_readings_from_sova.py",
    ]
    for source in sorted(p for p in study if p.is_file()):
        target = findings / "study" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        sums.append(f"{hashlib.sha256(source.read_bytes()).hexdigest()}  findings/study/{source.name}")
    (destination / "SHA256SUMS").write_text(
        "\n".join(sorted(sums, key=lambda s: s.split("  ")[1])) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"copied {len(sources)} files, {sum(p.stat().st_size for p in sources):,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
