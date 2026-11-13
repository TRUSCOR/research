"""Build reproducible SOVA preprint packages.

This script does not publish anything. It converts the retained working papers
and machine-readable experiment results into review PDFs and arXiv-style source
directories. Packages remain private unless their configuration records the
named human author's explicit public-release approval.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PAPERS = ROOT / "private" / "research" / "papers"
RESULTS = ROOT / "private" / "experiments" / "results"
ARXIV = PAPERS / "arxiv"
PDF_OUT = PAPERS / "output" / "pdf"
SOURCE_OUT = PAPERS / "output" / "source"
REFERENCE_BIB = Path(__file__).with_name("references.bib")

PANDOC_DEFAULT = (
    ROOT / "tmp" / "pdfs" / "tooling" / "pandoc-3.10.1" / "pandoc-3.10.1" / "pandoc.exe"
)
TECTONIC_DEFAULT = ROOT / "tmp" / "pdfs" / "tooling" / "tectonic-0.16.9" / "tectonic.exe"


PAPER_CONFIG = {
    "p1": {
        "source": "P1-evidence-guided-trigger-interaction-search-working-paper.md",
        "slug": "evidence-guided-trigger-interaction-search",
        "title": "Evidence-Guided Trigger-Interaction Search for Stateful AI Agents",
        "short_title": "Evidence-Guided Trigger-Interaction Search",
        "keywords": [
            "AI agents",
            "trigger discovery",
            "combinatorial testing",
            "directed search",
            "behavior reproduction",
            "evidence",
        ],
        "primary_category": "cs.AI",
        "cross_list": ["cs.CR", "cs.SE"],
        "start": "## 1. Research question",
        "end": "## 10. Required work before submission",
        "abstract": (
            "Conditional AI-agent failures can depend on interactions among identity, history, "
            "memory, retrieval, tools, runtime state, and environment. We define a typed trigger "
            "space and introduce an experimental evidence-factor-lattice search that probes "
            "single-factor interventions, ranks bounded near-miss evidence, joins selected "
            "interventions into higher-order candidates, and separately minimizes a discovered "
            "trigger for packaging as a .sova behavior capsule with .sova-trace evidence. On a "
            "predeclared same-team synthetic corpus of 60 monotone triggers over six four-valued "
            "factors, balanced across interaction orders two through four, the method discovered "
            "60/60 within 32 executions and exactly minimized 60/60. Pairwise covering discovered "
            "31/60; eight-seed adaptive evolutionary and random baselines discovered 242/480 and "
            "204/480 trials. The result demonstrates an executable mechanism on a favorable "
            "grey-box corpus whose score exposes partial trigger satisfaction. It does not "
            "establish black-box superiority, real-agent validity, novelty, or resilience to "
            "noisy, deceptive, non-monotone, sequential, or masked signals."
        ),
        "figure_insert": "## 4. Evidence-factor-lattice method",
        "future": (
            "## 10. Future independent validation\n\n"
            "The confirmatory gate requires independently authored or blind real-agent cases "
            "covering tool, memory, and multi-turn state triggers; faithful prompt-fuzzing, "
            "combinatorial, directed-fuzzing, and reduction baselines; noisy, deceptive, masked, "
            "non-monotone, ordered, and incomplete-evidence strata; cost and side-effect measures; "
            "component ablations; and independent security, dual-use, and IP review. The frozen "
            "synthetic result is retained even if the external hypothesis fails.\n"
        ),
        "conclusion": (
            "## 11. Conclusion\n\n"
            "Evidence-factor-lattice search turns typed partial observations into a bounded "
            "intervention schedule and a portable minimized reproduction artifact. On the frozen "
            "mechanism-aligned synthetic corpus it recovered every order-two through order-four "
            "trigger, but that favorable result is not evidence of real-system superiority. The "
            "method remains a falsifiable private research candidate until blind heterogeneous "
            "agent studies establish where its evidence assumptions hold or fail.\n"
        ),
        "citations": [
            ("Sleeper Agents demonstrates", "Sleeper Agents [@hubinger2024sleeper] demonstrates"),
            ("Watch Out for Your Agents and", "Watch Out for Your Agents [@yang2024watch] and"),
            ("Stateful Agent Backdoor extend", "Stateful Agent Backdoor [@dai2026stateful] extend"),
            ("GPTFuzzer and FuzzLLM", "GPTFuzzer [@yu2023gptfuzzer] and FuzzLLM [@yao2023fuzzllm]"),
            ("PAIR iteratively", "PAIR [@chao2023pair] iteratively"),
            ("TAP uses", "TAP [@mehrotra2023tap] uses"),
            (
                "AgentDojo, InjecAgent, Agent Security Bench, and ToolEmu",
                "AgentDojo, InjecAgent, Agent Security Bench, and ToolEmu [@debenedetti2024agentdojo; @zhan2024injecagent; @zhang2025asb; @ruan2024toolemu]",
            ),
            ("NIST SP 800-142 motivates", "NIST SP 800-142 [@kuhn2010combinatorial] motivates"),
            ("Error-locating arrays and", "Error-locating arrays [@colbourn2008locating] and"),
            ("AFLNet applies", "AFLNet [@pham2024aflnet] applies"),
            ("FOX uses", "FOX [@she2024fox] uses"),
            ("Delta Debugging minimizes", "Delta Debugging [@zeller2002delta] minimizes"),
        ],
    },
    "p4": {
        "source": "P4-sova-semantic-reproduction-working-paper.md",
        "slug": "sova-semantic-reproduction",
        "title": ".sova: Evidence-Bounded Semantic Reproduction of Observable AI Behavior Across Runtimes",
        "short_title": "Evidence-Bounded Semantic Reproduction",
        "keywords": [
            "AI agents",
            "behavior reproduction",
            "reproducibility",
            "portable artifacts",
            "semantic evaluation",
            "evidence",
        ],
        "primary_category": "cs.AI",
        "cross_list": ["cs.SE", "cs.CR"],
        "start": "## 1. Research question",
        "end": "## 8. Required experiments before submission",
        "abstract": (
            "Reproducing observable AI behavior across models and runtimes requires more than "
            "byte playback. We introduce an experimental .sova AI-behavior capsule and an "
            "evidence-bounded semantic-reproduction decision that couples typed observable "
            "outcomes, an execution-context equivalence envelope, evidence-sufficiency checks, "
            "multi-valued decisions, and recomputable repeated-trial statistics. Trace playback, "
            "controlled re-execution, and semantic reproduction remain distinct operations; the "
            "method records observable interactions and never claims access to hidden model "
            "reasoning. On a frozen same-team corpus of 144 constructed pairs, the executable "
            "mechanism matched all labels while simple structural baselines achieved macro-F1 "
            "between 0 and 0.111. A preregistered Wilson-interval rule failed its worst-cell "
            "coverage gate (0.914); a disclosed amendment using an exact interval reached 0.956. "
            "A 12-case, 24-trace no-Atlas study completed two-backend execution, packaging, inert "
            "playback, comparison, and offline verification. On eleven retrospective cross-model "
            "pairs derived from 22 AgentRewardBench WebArena trajectories, the mechanism returned "
            "two equivalent, five divergent, and four inconclusive decisions. A post-result graph "
            "baseline matched 5/7 conclusive labels, and a calibrated semantic-text baseline "
            "matched 7/7 but could not represent inconclusive cases. These results establish "
            "implementability and falsifiable boundaries, not independent cross-runtime validity. "
            "A later frozen public-contract study matched all expected decisions for 12 contracts "
            "and 96 traces, accepted zero incomplete traces as reproduced, found zero exact byte "
            "matches, and conservatively kept all 12 aggregates inconclusive because each retained "
            "two mandatory-evidence gaps."
        ),
        "figure_insert": "## 3. Proposed mechanism",
        "future": (
            "## 8. Future independent validation\n\n"
            "The current evidence is same-team and bounded. The next confirmatory study must use "
            "independently authored behavior pairs, blinded labels, at least two independently "
            "operated runtimes, controlled real-model re-execution, and predeclared comparisons "
            "with the strongest applicable graph, semantic, and record/replay baselines. Unsafe "
            "cases must remain refusals, and incompatible or missing-evidence cases must not be "
            "collapsed into binary failure. The external-review packet freezes the cases, digests, "
            "release order, and scoring rules but cannot manufacture reviewer independence.\n"
        ),
        "conclusion": (
            "## 9. Conclusion\n\n"
            "The .sova capsule makes an AI behavior a portable, inspectable research object while "
            "keeping execution mechanics and evidentiary claims explicit. The retained experiments "
            "show that the proposed decision is executable and expose where byte equality, terminal "
            "status, graph similarity, and semantic similarity answer narrower questions. The "
            "mechanism should be treated as a testable architecture, not as established superiority, "
            "until independent cross-runtime validation supports or falsifies it.\n"
        ),
        "citations": [
            ("ReproEvalCard specifies", "ReproEvalCard [@pattnayak2026reproevalcard] specifies"),
            ("`agrepl` records", "`agrepl` [@mudasiru2026agrepl] records"),
            ("WebGraphEval compares", "WebGraphEval [@qian2025webgrapheval] compares"),
            (
                "ContractEval and Phoenix demonstrate",
                "ContractEval [@lim2026contracteval] and Phoenix [@wang2026securityrelative] demonstrate",
            ),
            ("PoC-Adapt uses", "PoC-Adapt [@duy2026pocadapt] uses"),
            ("W3C PROV defines", "W3C PROV [@w3cprovconstraints] defines"),
            ("NIST AI 800-2 and 800-3", "NIST AI 800-2 and 800-3 [@nistai8002; @nistai8003]"),
            ("AgentRewardBench authors'", "AgentRewardBench [@lu2025agentrewardbench] authors'"),
            ("Inspect AI repository", "Inspect AI [@inspectlogs] repository"),
            ("STS Benchmark training labels", "STS Benchmark [@cer2017stsb] training labels"),
        ],
    },
    "p5": {
        "source": "P5-sova-trace-evidence-fidelity-working-paper.md",
        "slug": "sova-trace-evidence-fidelity",
        "title": ".sova-trace: Claim-Conditioned Evidence Fidelity for AI-System Behavior Records",
        "short_title": "Claim-Conditioned Evidence Fidelity",
        "keywords": [
            "AI observability",
            "evidence fidelity",
            "provenance",
            "selective disclosure",
            "tamper evidence",
            "trace interoperability",
        ],
        "primary_category": "cs.CR",
        "cross_list": ["cs.AI", "cs.SE"],
        "start": "## 1. Problem",
        "end": "## 10. Required work before submission",
        "abstract": (
            "AI-system traces are frequently treated as interchangeable logs even when they "
            "capture different event classes, causal structure, redactions, or trust assumptions. "
            "We introduce .sova-trace and a claim-conditioned fidelity envelope that separates "
            "transport integrity from evidentiary sufficiency. A claim declares required event "
            "types, payload paths, causal relations, observation roles, and integrity state; a "
            "multi-valued decision reports supported, weakened, or inconclusive rather than "
            "silently interpreting missing evidence as truth. The format uses canonical events, "
            "content-addressed blobs, segmented streaming, explicit capture profiles, DSSE-compatible "
            "manifests, typed redaction placeholders, and selective-disclosure dependency closure. "
            "On a frozen 120-case constructed corpus, the executable mechanism matched all labels; "
            "integrity-only and profile-only baselines achieved 0.333 and 0.167 accuracy. Same-team "
            "component ablations exposed false support when known integrity invalidity was ignored. "
            "Cross-library tests exercised RFC 8785 canonicalization and DSSE verification; official "
            "OTLP protobuf, OpenTelemetry Collector, Inspect, OpenInference, AgentRewardBench, and "
            "STIX paths were tested with explicit loss accounting. Signed synthetic traces scaled "
            "to 50,000 events, but the performance results come from one host. A bounded privacy "
            "study confirmed dictionary, equality-correlation, length, bucket, path, and presence "
            "leakage under relevant strategies. The construction provides tested tamper evidence "
            "and provenance only within its stated threat model; it does not prove truth, "
            "completeness, non-repudiation, or recorder honesty."
        ),
        "figure_insert": "## 2. Proposed fidelity envelope",
        "future": (
            "## 10. Future independent validation\n\n"
            "A confirmatory evaluation must use independently produced traces and claim contracts, "
            "a cryptographic and privacy review, malicious-recorder cases, differential parsing, "
            "hosted or independently operated telemetry backends, and established authenticated-log "
            "and selective-disclosure baselines. The retained reviewer packet freezes attack cases, "
            "source-format families, adverse findings, digests, and scoring rules. It verifies handoff "
            "integrity but does not establish reviewer independence.\n"
        ),
        "conclusion": (
            "## 11. Conclusion\n\n"
            "A trace can be byte-intact and still be insufficient for a behavioral claim. The "
            "claim-conditioned fidelity envelope makes this distinction executable and propagates "
            "known gaps instead of converting them into unsupported certainty. The current evidence "
            "supports a bounded engineering and research result; independent security, privacy, and "
            "external-corpus studies remain necessary before broader claims.\n"
        ),
        "citations": [
            ("OpenTelemetry supplies", "OpenTelemetry [@opentelemetrysemconv143] supplies"),
            ("W3C PROV formalizes", "W3C PROV [@w3cprovconstraints; @w3cprovaq] formalizes"),
            (
                "in-toto, DSSE, and Sigstore",
                "in-toto, DSSE, and Sigstore [@intoto; @dsse102; @sigstorebundle032]",
            ),
            ("Inspect's evaluation logs", "Inspect's evaluation logs [@inspectlogs]"),
            ("AgentRewardBench WebArena", "AgentRewardBench [@lu2025agentrewardbench] WebArena"),
            ("RFC 8785", "RFC 8785 [@rfc8785]"),
            ("OpenTelemetry protobuf", "OpenTelemetry protobuf [@opentelemetryproto]"),
            ("OpenInference", "OpenInference [@openinference]"),
            ("OASIS STIX", "OASIS STIX [@oasisstix21]"),
        ],
    },
    "pf": {
        "release": "public-v1.0",
        "source": "PF-sova-portable-evidence-reproduction-working-paper.md",
        "slug": "sova-portable-evidence-reproduction",
        "title": ".sova: Portable, Evidence-Bounded Reproduction of AI-Agent Security Findings",
        "short_title": "Portable Evidence-Bounded Reproduction",
        "keywords": [
            "AI agents",
            "security findings",
            "behavior reproduction",
            "evidence fidelity",
            "portable artifacts",
            "observability",
        ],
        "primary_category": "cs.CR",
        "cross_list": ["cs.AI", "cs.SE"],
        "start": "## 1. Introduction",
        "end": "## 10. Conclusion",
        "abstract": (
            "AI-agent security findings are commonly exchanged as prose reports, screenshots, "
            "logs, or replay scripts. These artifacts can preserve useful observations while "
            "remaining ambiguous about the behavior claimed, the execution context that must "
            "remain equivalent, and whether redaction or conversion removed evidence needed to "
            "support the claim. We introduce .sova, an inert-by-default behavior capsule, and "
            ".sova-trace, its canonical observable evidence stream. The proposed decision procedure "
            "composes a typed outcome contract, an execution-context equivalence envelope, "
            "claim-conditioned evidence requirements, integrity and trust checks, multi-valued "
            "reproduction states, and recomputable repeated-trial summaries. On two frozen "
            "same-team corpora, the complete mechanism matched all 144 semantic-reproduction "
            "labels and all 120 evidence-fidelity labels; simple structural, integrity-only, and "
            "profile-only baselines could not represent the same decision space. A separate frozen "
            "public-contract study matched all expected decisions for 12 contracts and 96 candidate "
            "traces while accepting zero incomplete traces as reproduced. On eleven retrospective "
            "cross-model pairs derived from 22 AgentRewardBench WebArena trajectories, the mechanism "
            "returned two equivalent, five divergent, and four inconclusive decisions. A calibrated "
            "semantic-text baseline matched all seven conclusive labels but necessarily forced the "
            "four inconclusive cases into a binary outcome. Interoperability studies exercised "
            "official Inspect fixtures, OTLP protobuf, an OpenTelemetry Collector, STIX 2.1, "
            "cross-language verification, and signed traces up to 50,000 events with explicit loss "
            "accounting. These results establish an executable and falsifiable architecture, not "
            "independent cross-runtime superiority. The confirmatory gate remains independently "
            "authored claims, blinded labels, independently operated runtimes, and external security "
            "and privacy review."
        ),
        "figure_insert": "__NO_AUTOMATIC_FIGURE_INSERT__",
        "future": "",
        "conclusion": (
            "## 10. Conclusion\n\n"
            ".sova makes an AI-agent security finding a portable, inspectable research object, "
            "while .sova-trace makes the evidence boundary explicit. The retained experiments show "
            "that the composed decision is executable and expose where byte equality, terminal "
            "status, trajectory structure, semantic similarity, integrity validity, and capture-"
            "profile names answer narrower questions. The current result is a bounded, falsifiable "
            "architecture with adverse evidence retained. Independent cross-runtime validation must "
            "still support or falsify its broader usefulness.\n"
        ),
        "citations": [],
    },
    "p6": {
        "source": "P6-evidence-based-executor-conformance-working-paper.md",
        "slug": "evidence-bounded-executor-conformance",
        "title": "Evidence-Bounded Semantic Conformance Across Heterogeneous AI-Agent Executors",
        "short_title": "Evidence-Bounded Executor Conformance",
        "keywords": [
            "AI agents",
            "executor interoperability",
            "semantic conformance",
            "side-effect verification",
            "capability contracts",
            "replay",
        ],
        "primary_category": "cs.SE",
        "cross_list": ["cs.AI", "cs.CR"],
        "start": "## 1. Introduction",
        "end": "## 15. Paper and patent gate",
        "abstract": (
            "Agent executors expose heterogeneous actions, capabilities, status vocabularies, and "
            "evidence. We propose an evidence-bounded conformance contract that separates portable "
            "action intent from provider mechanics and classifies an attempted action as conformant, "
            "nonconformant, unsupported, or inconclusive. A conformant result requires an exact "
            "capability match, acceptable normalized outcome, complete side-effect accounting, "
            "required evidence roles, and SOVA-owned post-action observation; provider success alone "
            "is insufficient. The architecture retains retry lineage, cancellation, timeout, partial "
            "results, and observation provenance while keeping policy, judging, signing, and threat "
            "modeling outside adapters. On a frozen 60-case constructed corpus, the executable "
            "decision matched all labels; provider-status, exact-output, capability-only, and "
            "no-independent-observation baselines achieved 0.400, 0.417, 0.200, and 0.600 accuracy. "
            "A foreign subprocess harness exercised 30 cases without importing SOVA and did not "
            "accept false-success cases as conformant. A no-Atlas vertical study completed 24 "
            "capsules and traces across scripted and restricted local executors, including capture, "
            "playback, controlled reproduction, comparison, and offline verification. These studies "
            "show executable specification consistency on one host. A later 72-case browser, "
            "computer, and terminal broker study matched every expected outcome, accepted zero "
            "unverified provider successes, made zero non-idempotent fallback violations, and "
            "stored zero secret checkpoint inputs. Pinned live receipts exercised Playwright MCP, "
            "Windows-MCP, and a policy-blocked MELRA transport. These results do not establish "
            "cross-provider validity or "
            "secure sandboxing. The paper therefore presents a falsifiable architecture and a blind "
            "confirmatory protocol for independently authored adapters, realistic browser/computer "
            "actions, and multiple providers."
        ),
        "figure_insert": "## 3. System model",
        "future": "",
        "conclusion": (
            "## 15. Conclusion\n\n"
            "The contract makes a provider's status one input to conformance rather than its proof. "
            "The retained studies show that capability, output, and provider status are insufficient "
            "on constructed cases, while also showing that same-team fixtures and ordinary process "
            "restriction cannot establish real cross-provider security. Independent adapters, "
            "realistic interaction families, blinded labels, and end-to-end measurements must now "
            "support or falsify the hypothesis.\n"
        ),
        "citations": [
            ("MCP revision 2025-11-25", "MCP revision 2025-11-25 [@mcp2025]"),
            ("WebDriver BiDi's", "WebDriver BiDi's [@webdriverbidi2026]"),
            (
                "OpenTelemetry semantic conventions 1.43.0",
                "OpenTelemetry semantic conventions 1.43.0 [@opentelemetrysemconv143]",
            ),
            ("`agrepl` intercepts", "`agrepl` [@mudasiru2026agrepl] intercepts"),
            ("Shepherd and", "Shepherd [@yu2026shepherd] and"),
            ("execution-lineage work", "execution-lineage work [@rosen2026lineage]"),
            ("Proof of Execution formalizes", "Proof of Execution [@rhodes2026poe] formalizes"),
            (
                "Playwright MCP 0.0.78 supplied",
                "Playwright MCP 0.0.78 [@playwrightmcp0078] supplied",
            ),
            ("Windows-MCP 0.8.2 supplied", "Windows-MCP 0.8.2 [@windowsmcp082] supplied"),
            (
                "MELRA package 0.3.0-alpha.0 reached",
                "MELRA package 0.3.0-alpha.0 [@melra030alpha] reached",
            ),
        ],
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], cwd: Path) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def is_public_release(config: dict[str, object]) -> bool:
    return config.get("release") == "public-v1.0"


def deterministic_source_archive(
    package: Path, key: str, slug: str, config: dict[str, object]
) -> Path:
    """Create an arXiv source archive with normalized metadata."""
    SOURCE_OUT.mkdir(parents=True, exist_ok=True)
    suffix = "arxiv-source-v1.0" if is_public_release(config) else "arxiv-source-private-review"
    destination = SOURCE_OUT / f"SOVA-{key.upper()}-{slug}-{suffix}.tar.gz"
    members = [package / "main.tex", *sorted((package / "figures").glob("*.pdf"))]
    with destination.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in members:
                    relative = path.relative_to(package).as_posix()
                    info = archive.gettarinfo(str(path), arcname=relative)
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    with path.open("rb") as stream:
                        archive.addfile(info, stream)
    return destination


def ascii_punctuation(text: str) -> str:
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
        "\u2026": "...",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def extract_body(config: dict[str, object]) -> str:
    source = PAPERS / str(config["source"])
    text = ascii_punctuation(source.read_text(encoding="utf-8"))
    start = text.index(str(config["start"]))
    end = text.index(str(config["end"]), start)
    body = text[start:end].strip()
    for old, new in config["citations"]:  # type: ignore[index]
        if old in body:
            body = body.replace(old, new, 1)
    figure_key = str(config["slug"])
    architecture = (
        f"![Conceptual architecture for {config['short_title']}. "
        "Boxes show the portable decision boundary; executor or producer mechanics remain outside "
        f"the claim.](figures/{figure_key}-architecture.pdf)\n\n"
    )
    baseline = (
        f"![Constructed-corpus baseline comparison. Values are retained experiment results, not "
        f"field-performance estimates.](figures/{figure_key}-baselines.pdf)\n\n"
    )
    insert = str(config["figure_insert"])
    body = body.replace(insert, architecture + insert, 1)
    results_heading = next(
        (
            heading
            for heading in ("## 6. Results", "## 7. Results", "## 8. Results")
            if heading in body
        ),
        "",
    )
    if results_heading:
        body = body.replace(results_heading, baseline + results_heading, 1)
    return body


def declarations(config: dict[str, object]) -> str:
    if is_public_release(config):
        return """
## Declarations

### Ethics and dual-use statement

The reported machine experiments use synthetic or public research fixtures and safe local actions. They do not target a live third party, use client data, store real credentials, or claim access to private model thoughts or hidden chain-of-thought. The work can support security testing and therefore has dual-use potential. Unsafe reproduction remains subject to explicit authorization, containment, and human review; operational exploit details and novelty-sensitive implementations are outside the scope of this public preprint.

### Data and artifact availability

The generic SOVA implementation, public specifications, safe examples, and tests are available in the [SOVA-OSS repository](https://github.com/Gautam-R-Patil/S.O.V.A---OSS---TRUSCOR). The retained result manifests, preregistrations, source digests, build provenance, and reviewer packet used for this preprint are held by TRUSCOR Private Limited and are not part of this paper-only release. Third-party source artifacts whose redistribution rights are unclear are not redistributed. A venue artifact release requires a separate rights, privacy, security, and IP review.

### Author contributions and AI-assisted work

Gautam R. Patil conceived the SOVA project, specified the research direction and safety constraints, and directed this work. Software implementation, experiment execution, analysis support, literature discovery, and drafting used OpenAI Codex under his direction. Gautam R. Patil is the sole human author and reviewed and approved the final text, citations, figures, data, declarations, and public release. No AI system is listed as an author or inventor.

### Funding and competing interests

This work was conducted for TRUSCOR Private Limited. No external funding was used for the reported machine experiments. The author's affiliation with TRUSCOR Private Limited is a relevant non-financial and potential commercial interest.
""".strip()
    return """
## Declarations

### Ethics and dual-use statement

The reported machine experiments use synthetic or public research fixtures and safe local actions. They do not target a live third party, use client data, store real credentials, or claim access to private model thoughts or hidden chain-of-thought. The work can support security testing and therefore has dual-use potential. Unsafe reproduction remains subject to explicit authorization, containment, and human review; operational exploit details and novelty-sensitive implementations are not part of this private review package.

### Data and artifact availability

The generic SOVA implementation, public specifications, safe examples, and tests are available in the SOVA-OSS repository. Private experiment results, preregistrations, source digests, build provenance, and review packets are retained by TRUSCOR Private Limited. Third-party source artifacts whose redistribution rights are unclear are not redistributed. A release artifact must be assembled only after rights, privacy, security, and IP review.

### Author contributions and AI-assisted work

Gautam R. Patil conceived the SOVA project, specified the research direction and safety constraints, and directed this work. Software implementation, experiment execution, analysis support, literature discovery, and drafting used OpenAI Codex under his direction. Gautam R. Patil is the sole proposed human author and must verify the final text, citations, figures, data, and venue disclosure before submission. No AI system is listed as an author or inventor.

### Funding and competing interests

This work was conducted for TRUSCOR Private Limited. No external funding was used for the reported machine experiments. The author's affiliation with TRUSCOR Private Limited is a relevant non-financial and potential commercial interest. The exact legal entity name and any additional interests must be confirmed before submission.
""".strip()


def yaml_header(config: dict[str, object]) -> str:
    keywords = "\n".join(f"  - {item}" for item in config["keywords"])  # type: ignore[index]
    abstract = str(config["abstract"]).replace("\n", " ")
    if is_public_release(config):
        date = "2026-08-20"
        release_notice = """> **PUBLIC PREPRINT - VERSION 1.0**  
> This manuscript has not been peer reviewed.

**Affiliation:** TRUSCOR Private Limited  
**Contact:** gautam@truscor.org  
**License:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) - (c) 2026 Gautam R. Patil  
**arXiv classification:** {primary} (cross-list candidates: {cross_list})
""".format(primary=config["primary_category"], cross_list=", ".join(config["cross_list"]))
    else:
        date = "2026-08-19"
        release_notice = """> **PRIVATE PREPRINT CANDIDATE - NOT CLEARED FOR PUBLIC DISTRIBUTION**  
> Version 0.99. This document is a review artifact, not a peer-reviewed result.

**Affiliation:** TRUSCOR Private Limited  
**Contact:** gautam@truscor.org  
**Candidate arXiv classification:** {primary} (cross-list candidates: {cross_list})
""".format(primary=config["primary_category"], cross_list=", ".join(config["cross_list"]))
    return f"""---
title: "{config["title"]}"
author: "Gautam R. Patil"
subtitle: "TRUSCOR Private Limited - gautam@truscor.org"
date: {date}
abstract: |
  {abstract}
keywords:
{keywords}
bibliography: references.bib
link-citations: true
reference-section-title: References
papersize: a4
geometry:
  - margin=24mm
fontsize: 10pt
colorlinks: true
---

{release_notice}

"""


def draw_architecture(path: Path, labels: list[str], result: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig, ax = plt.subplots(figsize=(10.5, 2.7))
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 2.7)
    ax.axis("off")
    colors = ["#DDEFF2", "#E8EDF5", "#DCE8E0", "#F3E6D3"]
    centers = [1.2, 3.7, 6.2, 8.7]
    for i, (center, label) in enumerate(zip(centers, labels)):
        box = FancyBboxPatch(
            (center - 1.0, 0.78),
            2.0,
            1.1,
            boxstyle="round,pad=0.08,rounding_size=0.08",
            linewidth=1.3,
            edgecolor="#0B1930",
            facecolor=colors[i],
        )
        ax.add_patch(box)
        ax.text(
            center, 1.33, label, ha="center", va="center", fontsize=9, color="#0B1930", wrap=True
        )
        if i < 3:
            ax.annotate(
                "",
                xy=(centers[i + 1] - 1.08, 1.33),
                xytext=(center + 1.08, 1.33),
                arrowprops={"arrowstyle": "->", "lw": 1.4, "color": "#157A8A"},
            )
    ax.text(
        5.25, 2.25, result, ha="center", va="center", fontsize=11, weight="bold", color="#0B1930"
    )
    ax.text(
        5.25,
        0.25,
        "Portable claim boundary: observable evidence, explicit assumptions, and visible limitations",
        ha="center",
        va="center",
        fontsize=8.5,
        color="#45546A",
    )
    pdf_metadata = {
        "Title": result,
        "Author": "Gautam R. Patil",
        "Creator": "SOVA private publication builder",
        "CreationDate": datetime(2026, 8, 3, tzinfo=timezone.utc),
        "ModDate": datetime(2026, 8, 3, tzinfo=timezone.utc),
    }
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight", metadata=pdf_metadata)
    fig.savefig(path.with_suffix(".png"), dpi=220, bbox_inches="tight")
    plt.close(fig)


def draw_baselines(path: Path, names: list[str], values: list[float], corpus: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8.2, 3.5))
    colors = ["#157A8A"] + ["#96A6B8"] * (len(values) - 1)
    bars = ax.barh(range(len(names)), values, color=colors, edgecolor="#0B1930", linewidth=0.6)
    ax.set_yticks(range(len(names)), labels=names)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.06)
    ax.set_xlabel("Accuracy on constructed corpus")
    ax.set_title(corpus, loc="left", color="#0B1930", weight="bold")
    ax.grid(axis="x", alpha=0.2)
    for bar, value in zip(bars, values):
        ax.text(
            value + 0.015,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.3f}",
            va="center",
            fontsize=8.5,
        )
    pdf_metadata = {
        "Title": corpus,
        "Author": "Gautam R. Patil",
        "Creator": "SOVA private publication builder",
        "CreationDate": datetime(2026, 8, 3, tzinfo=timezone.utc),
        "ModDate": datetime(2026, 8, 3, tzinfo=timezone.utc),
    }
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight", metadata=pdf_metadata)
    fig.savefig(path.with_suffix(".png"), dpi=220, bbox_inches="tight")
    plt.close(fig)


def draw_flagship_baselines(path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    panels = [
        (
            "Semantic reproduction - macro-F1",
            ["Composed", "Exact trace", "Terminal status", "Untyped kinds"],
            [1.0, 0.111, 0.048, 0.048],
        ),
        (
            "Evidence fidelity - accuracy",
            ["Claim-conditioned", "Integrity only", "Profile only", "Full-share"],
            [1.0, 1 / 3, 1 / 6, 1 / 6],
        ),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.7), constrained_layout=True)
    for ax, (title, names, values) in zip(axes, panels):
        colors = ["#157A8A"] + ["#96A6B8"] * (len(values) - 1)
        bars = ax.barh(range(len(names)), values, color=colors, edgecolor="#0B1930", linewidth=0.6)
        ax.set_yticks(range(len(names)), labels=names)
        ax.invert_yaxis()
        ax.set_xlim(0, 1.08)
        ax.set_xlabel("Score on constructed corpus")
        ax.set_title(title, loc="left", color="#0B1930", weight="bold", fontsize=10)
        ax.grid(axis="x", alpha=0.2)
        for bar, value in zip(bars, values):
            ax.text(
                value + 0.015,
                bar.get_y() + bar.get_height() / 2,
                f"{value:.3f}",
                va="center",
                fontsize=8,
            )
    fig.suptitle("Separate frozen same-team evaluation corpora", color="#0B1930", weight="bold")
    pdf_metadata = {
        "Title": "SOVA flagship constructed-corpus results",
        "Author": "Gautam R. Patil",
        "Creator": "SOVA private publication builder",
        "CreationDate": datetime(2026, 8, 19, tzinfo=timezone.utc),
        "ModDate": datetime(2026, 8, 19, tzinfo=timezone.utc),
    }
    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight", metadata=pdf_metadata)
    fig.savefig(path.with_suffix(".png"), dpi=220, bbox_inches="tight")
    plt.close(fig)


def make_figures(key: str, config: dict[str, object], package: Path) -> None:
    figure_dir = package / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    slug = str(config["slug"])
    if key == "p1":
        draw_architecture(
            figure_dir / f"{slug}-architecture",
            [
                "Typed factor\nspace",
                "Evidence-ranked\ninterventions",
                "Progressive\nlattice joins",
                "Minimized .sova +\n.sova-trace",
            ],
            "Evidence-guided trigger-interaction search",
        )
        draw_baselines(
            figure_dir / f"{slug}-baselines",
            [
                "Evidence factor lattice",
                "Pairwise covering",
                "Adaptive evolutionary",
                "Seeded random",
                "Coverage guided",
                "Known signature",
            ],
            [1.0, 31 / 60, 242 / 480, 204 / 480, 19 / 60, 7 / 60],
            "Frozen 60-case synthetic trigger corpus",
        )
    elif key == "p4":
        draw_architecture(
            figure_dir / f"{slug}-architecture",
            [
                "Capsule +\nobservable contract",
                "Context +\nevidence gates",
                "Multi-valued\ncomparison",
                "Repeated-trial\nrecord",
            ],
            ".sova semantic reproduction decision",
        )
        draw_baselines(
            figure_dir / f"{slug}-baselines",
            ["Candidate", "Exact trace", "Final payload", "Terminal status", "Untyped kinds"],
            [1.0, 1 / 6, 0.0, 1 / 6, 1 / 6],
            "Frozen 144-pair semantic corpus",
        )
    elif key == "p5":
        draw_architecture(
            figure_dir / f"{slug}-architecture",
            [
                "Claim evidence\nrequirements",
                "Canonical events +\ncontent addressing",
                "Integrity +\nfidelity checks",
                "Supported / weakened /\ninconclusive",
            ],
            ".sova-trace claim-conditioned fidelity envelope",
        )
        draw_baselines(
            figure_dir / f"{slug}-baselines",
            ["Candidate", "Integrity only", "Profile only", "Full-share assumption"],
            [1.0, 1 / 3, 1 / 6, 1 / 6],
            "Frozen 120-case fidelity corpus",
        )
    elif key == "pf":
        draw_architecture(
            figure_dir / f"{slug}-architecture",
            [
                "Portable claim +\ncontext contract",
                "Canonical trace +\nfidelity report",
                "Integrity, evidence +\nsafety gates",
                "Equivalent / divergent /\ninconclusive",
            ],
            ".sova portable evidence-bounded reproduction",
        )
        draw_flagship_baselines(figure_dir / f"{slug}-baselines")
    else:
        draw_architecture(
            figure_dir / f"{slug}-architecture",
            [
                "Portable action +\nexact capability",
                "Provider outcome +\nattempt lineage",
                "Independent effect\nobservation",
                "Four-state\nconformance",
            ],
            "Evidence-bounded executor conformance",
        )
        draw_baselines(
            figure_dir / f"{slug}-baselines",
            [
                "Candidate",
                "No independent observation",
                "Exact output",
                "Provider status",
                "Capability only",
            ],
            [1.0, 0.6, 5 / 12, 0.4, 0.2],
            "Frozen 60-case conformance corpus",
        )


def package_readme(config: dict[str, object]) -> str:
    if is_public_release(config):
        return f"""# Public arXiv preprint package

Paper: {config["title"]}

Status: **APPROVED BY THE AUTHOR FOR PUBLIC PREPRINT SUBMISSION.**

Gautam R. Patil approved the final scientific text, author identity, affiliation, public email, AI-assistance disclosure, and CC BY 4.0 license on 2026-08-20. The package is a preprint and has not been peer reviewed.

The deterministic arXiv upload archive contains `main.tex` and the two required PDF figures. Submit it through the author's own arXiv account using primary category `{config["primary_category"]}` and optional cross-lists {", ".join(config["cross_list"])}. arXiv moderation, any category endorsement, and account-bound submission remain external steps.

Independent cross-runtime confirmation and external security, privacy, and artifact review remain necessary before making broader scientific or industry claims and before archival venue submission.
"""
    return f"""# Private arXiv/ResearchGate review package

Paper: {config["title"]}

Status: **HOLD - not cleared for public distribution or submission.**

This directory contains a self-contained review source, bibliography, figures, LaTeX rendering, PDF, metadata, and build provenance. It does not contain credentials, confidential planning documents, client evidence, hidden model reasoning, or third-party source corpora.

Before submission Gautam R. Patil must:

1. review and approve every scientific claim, number, citation, figure, declaration, and acknowledgement;
2. complete or explicitly narrow around the independent-validation gates recorded in `submission-metadata.yaml`;
3. confirm the exact TRUSCOR legal entity name, conflicts, funding statement, and venue-required AI-use disclosure;
4. select the arXiv category and an irrevocable arXiv distribution license personally;
5. verify third-party data and artifact redistribution rights;
6. remove the private-review notice only after legal, security, privacy, and IP clearance;
7. submit through the author's own arXiv and ResearchGate accounts.

ResearchGate can host this as a preprint, but that does not make it peer reviewed. arXiv is a moderated preprint repository, not a peer-review venue.
"""


def metadata_yaml(config: dict[str, object]) -> str:
    if is_public_release(config):
        return f"""title: "{config["title"]}"
author: "Gautam R. Patil"
affiliation: "TRUSCOR Private Limited"
contact: "gautam@truscor.org"
orcid: "not provided"
version: "1.0"
status: "APPROVED FOR PUBLIC PREPRINT SUBMISSION"
author_approval_date: "2026-08-20"
primary_category: "{config["primary_category"]}"
cross_list_candidates: [{", ".join(config["cross_list"])}]
arxiv_license: "CC BY 4.0"
license_url: "https://creativecommons.org/licenses/by/4.0/"
peer_reviewed: false
public_release_cleared: true
submission_authorized: true
ai_assistance_disclosed: true
remaining_peer_review_gates:
  - "independent validation identified in the paper"
  - "independent security, privacy, and artifact review"
  - "anonymous venue package and account-bound venue submission"
"""
    return f"""title: "{config["title"]}"
author: "Gautam R. Patil"
affiliation: "TRUSCOR Private Limited"
contact: "gautam@truscor.org"
version: "0.99-private-review"
status: "HOLD"
primary_category_candidate: "{config["primary_category"]}"
cross_list_candidates: [{", ".join(config["cross_list"])}]
arxiv_license: "UNSELECTED - author decision required"
researchgate_item_type: "preprint"
peer_reviewed: false
public_release_cleared: false
submission_authorized: false
ai_assistance_disclosure_required: true
remaining_gates:
  - "human author scientific and citation review"
  - "independent validation identified in the paper"
  - "legal entity, conflict, license, IP, and redistribution review"
  - "venue account, endorsement if required, moderation, and submission"
"""


def build_one(
    key: str, config: dict[str, object], pandoc: Path, tectonic: Path
) -> dict[str, object]:
    package = ARXIV / str(config["slug"])
    if package.exists():
        shutil.rmtree(package)
    package.mkdir(parents=True)
    make_figures(key, config, package)
    shutil.copy2(REFERENCE_BIB, package / "references.bib")

    main = (
        yaml_header(config)
        + extract_body(config)
        + "\n\n"
        + str(config["future"])
        + "\n\n"
        + str(config["conclusion"])
        + "\n\n"
        + declarations(config)
        + "\n"
    )
    main = ascii_punctuation(main)
    (package / "main.md").write_text(main, encoding="utf-8", newline="\n")
    (package / "README.md").write_text(package_readme(config), encoding="utf-8", newline="\n")
    (package / "submission-metadata.yaml").write_text(
        metadata_yaml(config), encoding="utf-8", newline="\n"
    )

    pandoc_command = [
        str(pandoc),
        "main.md",
        "--from=markdown+yaml_metadata_block+link_attributes",
        "--standalone",
        "--citeproc",
        "--bibliography=references.bib",
        "--resource-path=.",
        "--metadata=lang:en-US",
        "--output=main.tex",
    ]
    run(pandoc_command, package)
    run([str(tectonic), "main.tex", "--outdir", str(package), "--keep-logs"], package)
    source_pdf = package / "main.pdf"
    pdf_suffix = "v1.0-preprint" if is_public_release(config) else "private-preprint"
    final_pdf = PDF_OUT / f"SOVA-{key.upper()}-{config['slug']}-{pdf_suffix}.pdf"
    PDF_OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_pdf, final_pdf)
    source_archive = deterministic_source_archive(package, key, str(config["slug"]), config)

    used_results = {
        "p1": [
            "topic14-factor-lattice-study-2026-08-03.json",
        ],
        "p4": [
            "topics-04-06-study-2026-07-31.json",
            "integrated-baseline-drift-study-2026-07-31.json",
            "agentreward-cross-model-study-2026-07-31.json",
            "p4-graph-semantic-baselines-2026-08-01.json",
            "topic06-no-atlas-vertical-study-2026-07-31.json",
            "topics12-13-postbuild-study-2026-08-03.json",
        ],
        "p5": [
            "topics-04-06-study-2026-07-31.json",
            "topic05-component-ablation-study-2026-07-31.json",
            "topic05-privacy-attack-study-2026-08-01.json",
            "p5-incident-collector-scale-2026-08-01.json",
        ],
        "pf": [
            "topics-04-06-study-2026-07-31.json",
            "integrated-baseline-drift-study-2026-07-31.json",
            "agentreward-cross-model-study-2026-07-31.json",
            "p4-graph-semantic-baselines-2026-08-01.json",
            "topic05-component-ablation-study-2026-07-31.json",
            "topic05-privacy-attack-study-2026-08-01.json",
            "p5-incident-collector-scale-2026-08-01.json",
            "topics12-13-postbuild-study-2026-08-03.json",
        ],
        "p6": [
            "topics-04-06-study-2026-07-31.json",
            "topic06-independent-adapter-study-2026-07-31.json",
            "topic06-no-atlas-vertical-study-2026-07-31.json",
            "topics12-13-postbuild-study-2026-08-03.json",
        ],
    }[key]
    provenance = {
        "artifactType": (
            "sova.public-preprint-build-provenance"
            if is_public_release(config)
            else "sova.private-publication-build-provenance"
        ),
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "paper": key.upper(),
        "status": (
            "author-approved-public-preprint"
            if is_public_release(config)
            else "private-review-not-cleared"
        ),
        "source": {"path": str(config["source"]), "sha256": sha256(PAPERS / str(config["source"]))},
        "references": {"path": "references.bib", "sha256": sha256(package / "references.bib")},
        "results": [{"path": name, "sha256": sha256(RESULTS / name)} for name in used_results],
        "tools": {
            "pandoc": {"path": str(pandoc), "sha256": sha256(pandoc)},
            "tectonic": {"path": str(tectonic), "sha256": sha256(tectonic)},
            "python": {"version": sys.version},
        },
        "outputs": {
            "mainMarkdownSha256": sha256(package / "main.md"),
            "mainTexSha256": sha256(package / "main.tex"),
            "pdfSha256": sha256(final_pdf),
            "pdfBytes": final_pdf.stat().st_size,
            "arxivSourceArchive": str(source_archive.relative_to(PAPERS)),
            "arxivSourceArchiveSha256": sha256(source_archive),
            "arxivSourceArchiveBytes": source_archive.stat().st_size,
        },
        "claimBoundary": (
            "Author approval and public packaging do not supply independent scientific validation or peer review."
            if is_public_release(config)
            else "Formatting and packaging do not supply independent scientific validation, peer review, IP clearance, or publication authorization."
        ),
    }
    (package / "build-provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "paper": key.upper(),
        "package": str(package),
        "pdf": str(final_pdf),
        "pdfSha256": sha256(final_pdf),
        "sourceArchive": str(source_archive),
        "sourceArchiveSha256": sha256(source_archive),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pandoc", type=Path, default=PANDOC_DEFAULT)
    parser.add_argument("--tectonic", type=Path, default=TECTONIC_DEFAULT)
    parser.add_argument("--paper", choices=["p1", "p4", "p5", "pf", "p6", "all"], default="all")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for tool in (args.pandoc, args.tectonic):
        if not tool.is_file():
            raise FileNotFoundError(tool)
    selected = PAPER_CONFIG if args.paper == "all" else {args.paper: PAPER_CONFIG[args.paper]}
    outputs = [
        build_one(key, config, args.pandoc.resolve(), args.tectonic.resolve())
        for key, config in selected.items()
    ]
    print(json.dumps({"built": outputs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
