"""Build the PF public preprint, version 1.1, without touching the v1.0 package.

This script does not publish anything. It reads the PF working paper and the
retained experiment results, draws the figures, renders LaTeX with the pinned
Pandoc/Tectonic binaries, and writes a separate v1.1 package, PDF, deterministic
source archive, and build provenance. The v1.0 package, PDF, and archive are
left byte-for-byte unchanged.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_publication_packages import (  # noqa: E402
    PANDOC_DEFAULT,
    PAPERS,
    PDF_OUT,
    RESULTS,
    SOURCE_OUT,
    TECTONIC_DEFAULT,
    ascii_punctuation,
    run,
    sha256,
)

VERSION = "1.1"
VERSION_DATE = "2026-11-14"
SOVA_COMMIT = "143e175"  # the SOVA-OSS commit the paper's tools run on; set at release
SLUG = "sova-portable-evidence-reproduction"
SOURCE = PAPERS / "PF-sova-portable-evidence-reproduction-working-paper.md"
BIB = Path(__file__).with_name("references.bib")
PACKAGE = PAPERS / "arxiv" / f"{SLUG}-v{VERSION}"
FINAL_PDF = PDF_OUT / f"SOVA-PF-{SLUG}-v{VERSION}-preprint.pdf"
ARCHIVE = SOURCE_OUT / f"SOVA-PF-{SLUG}-arxiv-source-v{VERSION}.tar.gz"
APPROVAL_FILE = Path(__file__).with_name("pf-v1.1-author-approval.json")

TITLE = "Did the Attack Really Work? Auditing, Re-running, and Proving AI-Agent Security Findings with .sova"
KEYWORDS = [
    "AI agents",
    "AI security",
    "semantic reproduction",
    "context equivalence",
    "evidence sufficiency",
    "portable artifacts",
    "reproducibility",
]
PRIMARY = "cs.CR"
CROSS = ["cs.AI", "cs.SE"]

BODY_START = "## The paper at a glance"
BODY_END = "## Internal: required work before submission"

RESULT_FILES = [
    "topics-04-06-study-2026-07-31.json",
    "integrated-baseline-drift-study-2026-07-31.json",
    "agentreward-cross-model-study-2026-07-31.json",
    "p4-graph-semantic-baselines-2026-08-01.json",
    "topic05-component-ablation-study-2026-07-31.json",
    "topic05-privacy-attack-study-2026-08-01.json",
    "p5-incident-collector-scale-2026-08-01.json",
    "topics12-13-postbuild-study-2026-08-03.json",
    "inspect-corpus-interoperability-2026-07-31.json",
    "inspect-corpus-interoperability-adapter-0.2.0-2026-07-31.json",
    "inspect-eval-interoperability-2026-08-01.json",
    "topic06-independent-adapter-study-2026-07-31.json",
    "topic05-attack-matrix-2026-07-31.json",
    "p5-repeatability-audit-2026-08-01.json",
    "cross-version-python-3.11-2026-07-31.json",
    "cross-version-python-3.12-2026-07-31.json",
    "cross-version-python-3.13-2026-07-31.json",
    "cross-version-python-3.14-2026-07-31.json",
]
OPTIONAL_RESULT_FILES = [
    "pf-redaction-triple-2026-11-12.json",
    "pf-agentdojo-reproduction-2026-11-12.json",
    "external-implementation-validation-2026-07-31.json",
    "external-implementation-validation-2026-08-01.json",
    "external-interoperability-study-2026-07-31.json",
    "reexecution-2026-11-12/reexecution-check.json",
    "pf-redaction-triple-postfix-2026-11-12.json",
    "pf-agentdojo-supplementary-2026-11-12.json",
    "pf-fresh-reexecution-2026-11-12.json",
    "pf-warning-classification-2026-11-12.json",
    "pf-real-attack-predictiveness-2026-11-12.json",
    "pf-fresh-successes-by-goal-2026-11-13.json",
    "pf-fresh-successes-manual-audit-2026-11-13.json",
    "pf-published-text-collisions-2026-11-13.json",
    "pf-published-hotel-reading-2026-11-13.json",
    "pf-cross-provider-2026-11-13.json",
    "pf-cross-provider-reading-2026-11-13.json",
    "pf-cross-provider-selection-2026-11-13.json",
    "pf-confirmatory-2026-11-14/scoreboard.json",
    "pf-confirmatory-2026-11-14/reliability.json",
    "pf-confirmatory-2026-11-14/prediction.json",
    "pf-confirmatory-2026-11-14/upgrade.json",
    "pf-confirmatory-2026-11-14/readers-agreement.json",
    "pf-confirmatory-2026-11-14/s6/recurrence.json",
    "pf-confirmatory-2026-11-14/s6/tasks.json",
    "pf-audit-2026-11-14/published.json",
    "pf-cross-provider-predictiveness-2026-11-13.json",
]

INK = "#0B1930"
TEAL = "#157A8A"
GREY = "#96A6B8"
MUTED = "#45546A"
STATE_COLOURS = {
    "equivalent": "#2E7D5B",
    "divergent": "#B5523B",
    "inconclusive": "#C9A227",
    "incompatible": "#6B5CA5",
    "unsafe": "#8E2C48",
    "evidence-invalid": "#5E6B78",
}


def approval() -> dict[str, object] | None:
    if not APPROVAL_FILE.is_file():
        return None
    record = json.loads(APPROVAL_FILE.read_text(encoding="utf-8"))
    if record.get("version") != VERSION or record.get("approved") is not True:
        return None
    if record.get("sourceSha256") != sha256(SOURCE) or record.get("bibSha256") != sha256(BIB):
        raise SystemExit(
            "Author approval does not match the current source or bibliography. "
            "Re-approve the exact text before building an approved package."
        )
    return record


def section(text: str, heading: str) -> str:
    start = text.index(heading) + len(heading)
    match = re.search(r"^## ", text[start:], flags=re.MULTILINE)
    end = start + match.start() if match else len(text)
    return text[start:end].strip()


def figure_metadata(title: str) -> dict[str, object]:
    stamp = datetime(2026, 11, 13, tzinfo=timezone.utc)
    return {
        "Title": title,
        "Author": "Gautam R. Patil",
        "Creator": "SOVA PF v1.1 publication builder",
        "CreationDate": stamp,
        "ModDate": stamp,
    }


def save(fig, path: Path, title: str) -> None:  # type: ignore[no-untyped-def]
    import matplotlib.pyplot as plt

    fig.savefig(path.with_suffix(".pdf"), bbox_inches="tight", metadata=figure_metadata(title))
    fig.savefig(path.with_suffix(".png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def draw_decision_ladder(path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    ax.set_xlim(0, 10.5)
    ax.set_ylim(0, 6.2)
    ax.axis("off")

    inputs = [
        ("Declared claim\n(outcome predicates)", 0.9),
        ("Context-equivalence\nenvelope", 2.75),
        ("Fresh evidence\n(.sova-trace)", 4.6),
    ]
    for label, x in inputs:
        ax.add_patch(
            FancyBboxPatch(
                (x - 0.85, 5.15),
                1.7,
                0.8,
                boxstyle="round,pad=0.05,rounding_size=0.08",
                linewidth=1.1,
                edgecolor=INK,
                facecolor="#E8EDF5",
            )
        )
        ax.text(x, 5.55, label, ha="center", va="center", fontsize=8.5, color=INK)
        ax.annotate(
            "",
            xy=(2.75, 4.72),
            xytext=(x, 5.12),
            arrowprops={"arrowstyle": "->", "lw": 1.0, "color": MUTED},
        )

    gates = [
        ("1. Are the bytes intact and well formed?", "evidence-invalid"),
        ("2. Was the run authorized and within policy?", "unsafe"),
        ("3. Is the context materially compatible?", "incompatible"),
        ("4. Are the required context and evidence present?", "inconclusive"),
        ("5. Do the required outcome predicates hold?", "divergent"),
    ]
    top = 4.35
    step = 0.78
    for index, (question, state) in enumerate(gates):
        y = top - index * step
        ax.add_patch(
            FancyBboxPatch(
                (0.55, y - 0.27),
                4.4,
                0.54,
                boxstyle="round,pad=0.04,rounding_size=0.06",
                linewidth=1.1,
                edgecolor=INK,
                facecolor="#F4F7FA",
            )
        )
        ax.text(0.75, y, question, ha="left", va="center", fontsize=9, color=INK)
        ax.annotate(
            "",
            xy=(6.35, y),
            xytext=(5.0, y),
            arrowprops={"arrowstyle": "->", "lw": 1.2, "color": STATE_COLOURS[state]},
        )
        ax.text(5.68, y + 0.13, "no", ha="center", va="bottom", fontsize=7.5, color=MUTED)
        ax.add_patch(
            FancyBboxPatch(
                (6.4, y - 0.24),
                2.1,
                0.48,
                boxstyle="round,pad=0.04,rounding_size=0.06",
                linewidth=0,
                facecolor=STATE_COLOURS[state],
            )
        )
        ax.text(7.45, y, state, ha="center", va="center", fontsize=9.5, color="white", weight="bold")
        if index < len(gates) - 1:
            ax.annotate(
                "",
                xy=(2.75, y - step + 0.29),
                xytext=(2.75, y - 0.29),
                arrowprops={"arrowstyle": "->", "lw": 1.1, "color": TEAL},
            )
            ax.text(2.88, y - step / 2, "yes", ha="left", va="center", fontsize=7.5, color=MUTED)
    y_final = top - len(gates) * step
    ax.annotate(
        "",
        xy=(2.75, y_final + 0.27),
        xytext=(2.75, y_final + step - 0.29),
        arrowprops={"arrowstyle": "->", "lw": 1.1, "color": TEAL},
    )
    ax.add_patch(
        FancyBboxPatch(
            (1.65, y_final - 0.24),
            2.2,
            0.48,
            boxstyle="round,pad=0.04,rounding_size=0.06",
            linewidth=0,
            facecolor=STATE_COLOURS["equivalent"],
        )
    )
    ax.text(
        2.75, y_final, "equivalent", ha="center", va="center", fontsize=9.5, color="white", weight="bold"
    )
    ax.text(
        8.75,
        y_final,
        "Gates run in this fixed order.\nA later answer can never\noverride an earlier one.",
        ha="left",
        va="center",
        fontsize=8,
        color=MUTED,
    )
    save(fig, path, "Six-state semantic reproduction decision")


def draw_constructed_baselines(path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    topics = json.loads((RESULTS / "topics-04-06-study-2026-07-31.json").read_text(encoding="utf-8"))
    sem = topics["semantic"]["metrics"]
    fid = topics["fidelity"]["metrics"]
    panels = [
        (
            "Semantic reproduction (144 pairs) - macro-F1",
            ["Composed mechanism", "Exact canonical trace", "Terminal completion status", "Untyped event kinds"],
            [
                sem["candidate"]["macro_f1"],
                sem["exact_trace"]["macro_f1"],
                sem["terminal_status"]["macro_f1"],
                sem["untyped_kinds"]["macro_f1"],
            ],
        ),
        (
            "Evidence fidelity (120 cases) - accuracy",
            ["Claim-conditioned", "Integrity valid alone", "Capture-profile name alone", "Full-share assumption"],
            [
                fid["candidate"]["accuracy"],
                fid["integrity_only"]["accuracy"],
                fid["profile_only"]["accuracy"],
                fid["full_share"]["accuracy"],
            ],
        ),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6), constrained_layout=True)
    for ax, (title, names, values) in zip(axes, panels):
        colours = [TEAL] + [GREY] * (len(values) - 1)
        bars = ax.barh(range(len(names)), values, color=colours, edgecolor=INK, linewidth=0.6)
        ax.set_yticks(range(len(names)), labels=names, fontsize=8.5)
        ax.invert_yaxis()
        ax.set_xlim(0, 1.12)
        ax.set_xlabel("Score on a same-team constructed corpus", fontsize=8.5)
        ax.set_title(title, loc="left", color=INK, weight="bold", fontsize=9.5)
        ax.grid(axis="x", alpha=0.2)
        for bar, value in zip(bars, values):
            ax.text(value + 0.015, bar.get_y() + bar.get_height() / 2, f"{value:.3f}", va="center", fontsize=8)
    save(fig, path, "Constructed-corpus results")


def draw_same_pairs(path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    study = json.loads(
        (RESULTS / "agentreward-cross-model-study-2026-07-31.json").read_text(encoding="utf-8")
    )
    baselines = json.loads(
        (RESULTS / "p4-graph-semantic-baselines-2026-08-01.json").read_text(encoding="utf-8")
    )

    def tally(values: list[str]) -> dict[str, int]:
        return {state: values.count(state) for state in ("equivalent", "divergent", "inconclusive")}

    rows = study["rows"]
    traj = baselines["trajectoryRows"]
    methods = [
        ("Composed decision (SOVA)", tally([row["outcome"] for row in rows])),
        ("Expert success label only", tally([row["baselines"]["expertSuccessOnly"] for row in rows])),
        ("Calibrated text similarity", tally([row["semanticPrediction"] for row in traj])),
        ("Exact action sequence", tally([row["baselines"]["exactActionSequence"] for row in rows])),
        ("Action-graph similarity", tally([row["graphPrediction"] for row in traj])),
        ("Same final action", tally([row["baselines"]["terminalAction"] for row in rows])),
    ]
    for _, counts in methods:
        if sum(counts.values()) != 11:
            raise AssertionError("every method must account for all 11 pairs")
    fig, ax = plt.subplots(figsize=(10.5, 3.5), constrained_layout=True)
    for index, (name, counts) in enumerate(methods):
        left = 0
        for state in ("equivalent", "divergent", "inconclusive"):
            width = counts[state]
            if width:
                ax.barh(index, width, left=left, color=STATE_COLOURS[state], edgecolor="white", linewidth=1.2)
                ax.text(left + width / 2, index, str(width), ha="center", va="center", color="white", fontsize=9, weight="bold")
            left += width
    ax.set_yticks(range(len(methods)), labels=[name for name, _ in methods], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, 11)
    ax.set_xticks(range(0, 12))
    ax.set_xlabel("Number of the same 11 cross-model trajectory pairs", fontsize=8.5)
    ax.set_title(
        "Same 11 pairs, different answers: what each method is able to say",
        loc="left",
        color=INK,
        weight="bold",
        fontsize=10,
    )
    handles = [plt.Rectangle((0, 0), 1, 1, color=STATE_COLOURS[s]) for s in ("equivalent", "divergent", "inconclusive")]
    ax.legend(handles, ["equivalent", "divergent", "inconclusive"], loc="lower right", fontsize=8, frameon=False, ncol=3, bbox_to_anchor=(1.0, -0.42))
    save(fig, path, "AgentRewardBench cross-model pair decisions by method")


AGENTDOJO_RESULT = "pf-agentdojo-reproduction-2026-11-12.json"
SUPPLEMENTARY_RESULT = "pf-agentdojo-supplementary-2026-11-12.json"
FRESH_RESULT = "pf-fresh-reexecution-2026-11-12.json"
MODEL_LABELS = {
    "claude-3-haiku-20240307": "Claude 3 Haiku",
    "claude-3-sonnet-20240229": "Claude 3 Sonnet",
    "claude-3-opus-20240229": "Claude 3 Opus",
    "claude-3-5-sonnet-20240620": "Claude 3.5 Sonnet 06",
    "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet 10",
    "claude-3-7-sonnet-20250219": "Claude 3.7 Sonnet",
    "command-r": "Command R",
    "command-r-plus": "Command R+",
    "gemini-1.5-flash-001": "Gemini 1.5 Flash 001",
    "gemini-1.5-flash-002": "Gemini 1.5 Flash 002",
    "gemini-1.5-pro-001": "Gemini 1.5 Pro 001",
    "gemini-1.5-pro-002": "Gemini 1.5 Pro 002",
    "gemini-2.0-flash-exp": "Gemini 2.0 Flash exp",
    "gemini-2.0-flash-001": "Gemini 2.0 Flash 001",
    "gpt-3.5-turbo-0125": "GPT-3.5 Turbo",
    "gpt-4-0125-preview": "GPT-4 0125",
    "gpt-4-turbo-2024-04-09": "GPT-4 Turbo",
    "gpt-4o-2024-05-13": "GPT-4o",
    "gpt-4o-mini-2024-07-18": "GPT-4o mini",
    "meta-llama_Llama-3-70b-chat-hf": "Llama 3 70B",
    "meta-llama_Llama-3.3-70B-Instruct": "Llama 3.3 70B",
    "Meta-SecAlign-70B": "Meta-SecAlign 70B",
}


def draw_agentdojo(path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    data = json.loads((RESULTS / AGENTDOJO_RESULT).read_text(encoding="utf-8"))
    models = [m for m in MODEL_LABELS if m in data["pipelines"]["included"]]
    if len(models) != len(data["pipelines"]["included"]):
        raise AssertionError("model label map does not cover every included pipeline")
    n = len(models)
    grid = np.full((n, n), np.nan)
    for i, a in enumerate(models):
        for j, b in enumerate(models):
            if a == b:
                continue
            cell = data["M2pairs"][f"{a} -> {b}"]["E2"]
            if cell["conclusive"] >= 20:
                grid[i, j] = cell["reproductionRate"]
    fig, (ax, bx) = plt.subplots(
        1, 2, figsize=(11.5, 6.4), gridspec_kw={"width_ratios": [1.55, 1]}, constrained_layout=True
    )
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("#F2F4F7")
    image = ax.imshow(grid, cmap=cmap, vmin=0, vmax=1)
    labels = [MODEL_LABELS[m] for m in models]
    ax.set_xticks(range(n), labels=labels, rotation=90, fontsize=6.5)
    ax.set_yticks(range(n), labels=labels, fontsize=6.5)
    ax.set_xlabel("Model the attack was re-checked on", fontsize=8)
    ax.set_ylabel("Model the attack first succeeded on", fontsize=8)
    ax.set_title("Cross-model transfer of successful injections", loc="left", fontsize=9.5, weight="bold", color=INK)
    bar = fig.colorbar(image, ax=ax, fraction=0.04, pad=0.02)
    bar.set_label("Share also successful on the column model", fontsize=7.5)
    bar.ax.tick_params(labelsize=7)

    per = data["perPipeline"]
    bounds = json.loads((RESULTS / SUPPLEMENTARY_RESULT).read_text(encoding="utf-8"))["asrBounds"]
    differing = [m for m in models if per[m]["launderedSuccesses"] > 0]
    differing.sort(key=lambda m: per[m]["asrNaiveSecurityFlag"] - per[m]["asrSupported"], reverse=True)
    ys = np.arange(len(differing))
    flag = [per[m]["securityTrue"] / per[m]["logs"] for m in differing]
    supported = [per[m]["asrSupported"] for m in differing]
    upper = [bounds[m]["upperBound"] for m in differing]
    bx.barh(ys - 0.2, flag, height=0.38, color=STATE_COLOURS["divergent"], label="Counted from the verdict flag")
    bx.barh(ys + 0.2, supported, height=0.38, color=TEAL, label="Supported by an observed run")
    bx.hlines(ys + 0.2, supported, upper, color=INK, linewidth=1.1, label="Range if unobserved runs are unknown")
    bx.plot(upper, ys + 0.2, marker="|", markersize=7, color=INK, linestyle="none")
    for y, m in zip(ys, differing):
        bx.text(
            max(flag[y], upper[y]) + 0.008,
            y,
            f"{per[m]['launderedSuccesses']} of {per[m]['securityTrue']} not observed",
            va="center",
            fontsize=7,
            color=MUTED,
        )
    bx.set_yticks(ys, labels=[MODEL_LABELS[m] for m in differing], fontsize=7.5)
    bx.invert_yaxis()
    bx.set_xlim(0, max(max(flag), max(upper)) * 1.55)
    bx.set_xlabel("Attack success rate", fontsize=8)
    bx.set_title("Flagged versus observed attack success", loc="left", fontsize=9.5, weight="bold", color=INK)
    bx.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.1), ncol=1)
    bx.grid(axis="x", alpha=0.2)
    save(fig, path, "AgentDojo cross-model reproduction")


def draw_successors(path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    family = json.loads((RESULTS / SUPPLEMENTARY_RESULT).read_text(encoding="utf-8"))["successorFamilyDifficultyMatched"]
    labels = {
        "claude-3-sonnet-20240229 -> claude-3-5-sonnet-20240620": "Claude 3 Sonnet \u2192 3.5 Sonnet (Jun 2024)",
        "claude-3-5-sonnet-20240620 -> claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet Jun \u2192 Oct 2024",
        "claude-3-5-sonnet-20241022 -> claude-3-7-sonnet-20250219": "Claude 3.5 Sonnet (Oct) \u2192 3.7 Sonnet",
        "gpt-4-0125-preview -> gpt-4-turbo-2024-04-09": "GPT-4 (0125) \u2192 GPT-4 Turbo",
        "gpt-4-turbo-2024-04-09 -> gpt-4o-2024-05-13": "GPT-4 Turbo \u2192 GPT-4o",
        "gemini-1.5-flash-001 -> gemini-1.5-flash-002": "Gemini 1.5 Flash 001 \u2192 002",
        "gemini-1.5-pro-001 -> gemini-1.5-pro-002": "Gemini 1.5 Pro 001 \u2192 002",
        "gemini-2.0-flash-exp -> gemini-2.0-flash-001": "Gemini 2.0 Flash exp \u2192 001",
        "meta-llama_Llama-3-70b-chat-hf -> meta-llama_Llama-3.3-70B-Instruct": "Llama 3 70B \u2192 Llama 3.3 70B",
        "meta-llama_Llama-3.3-70B-Instruct -> Meta-SecAlign-70B": "Llama 3.3 70B \u2192 Meta-SecAlign 70B",
    }
    pairs = family["pairs"]
    if set(pairs) != set(labels):
        raise AssertionError("successor label map does not match the result file")
    order = sorted(pairs, key=lambda k: pairs[k]["observedOverExpected"])
    fig, ax = plt.subplots(figsize=(8.6, 3.6), constrained_layout=True)
    low, high = family["referenceIQR"]
    median = family["referenceMedianObservedOverExpected"]
    ax.axvspan(low, high, color=GREY, alpha=0.25, lw=0, label="Other model pairs: interquartile range")
    ax.axvline(median, color=MUTED, lw=1.2, label="Other model pairs: median")
    ax.axvline(1.0, color=INK, lw=0.8, ls=":", label="No overlap beyond difficulty")
    for y, key in enumerate(order):
        cell = pairs[key]
        ratio = cell["observedOverExpected"]
        colour = TEAL if ratio > median else STATE_COLOURS["divergent"]
        ax.plot([1.0, ratio], [y, y], color=colour, lw=1.4, alpha=0.6)
        ax.plot(ratio, y, "o", color=colour, markersize=6)
        ax.text(
            max(ratio, high) + 0.05,
            y,
            f"{cell['observedAlsoOnEarlier']} shared vs {cell['expectedGivenDifficulty']:.1f} expected (n={cell['laterSuccesses']})",
            va="center",
            fontsize=7,
            color=MUTED,
        )
    ax.set_yticks(range(len(order)), labels=[labels[k] for k in order], fontsize=7.5)
    ax.set_xlim(0.7, 3.6)
    ax.set_xlabel("Shared successes with the predecessor, observed / expected from attack difficulty", fontsize=8)
    ax.set_title("Successor models: overlap with the predecessor beyond attack difficulty", loc="left", fontsize=9.5, weight="bold", color=INK)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax.grid(axis="x", alpha=0.2)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    save(fig, path, "AgentDojo successor models")


def draw_fresh(path: Path) -> bool:
    result_path = RESULTS / FRESH_RESULT
    warning_path = RESULTS / "pf-warning-classification-2026-11-12.json"
    if not result_path.is_file() or not warning_path.is_file():
        return False
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = json.loads(result_path.read_text(encoding="utf-8"))
    summary = json.loads((RESULTS / "pf-fresh-successes-by-goal-2026-11-13.json").read_text(encoding="utf-8"))
    cross = json.loads((RESULTS / "pf-cross-provider-2026-11-13.json").read_text(encoding="utf-8"))
    pred_path = RESULTS / "pf-cross-provider-predictiveness-2026-11-13.json"
    pred = json.loads(pred_path.read_text(encoding="utf-8")) if pred_path.is_file() else None
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(11.0, 3.9), gridspec_kw={"width_ratios": [1, 1.25]}, constrained_layout=True)

    hotel = summary["hotelGoalByModelAndPhase"]
    h55 = hotel["claude-haiku-5-5|important_instructions|R1"]
    s45 = hotel["claude-sonnet-4-5-20250929|important_instructions|full run (post hoc)"]
    cm = cross["models"]
    rows = [
        ("Claude Haiku 5.5", h55["warnings"], h55["scoredSuccesses"] - h55["warnings"]),
        ("Claude Sonnet 4.5", s45["warnings"], s45["scoredSuccesses"] - s45["warnings"]),
        ("GPT-6.1-sol", cm["gpt-6.1-sol"]["hotelGoal"]["warnings"], cm["gpt-6.1-sol"]["hotelGoal"]["scored"] - cm["gpt-6.1-sol"]["hotelGoal"]["warnings"]),
        ("GPT-4o (2024-11-20)", cm["gpt-4o"]["hotelGoal"]["warnings"], cm["gpt-4o"]["hotelGoal"]["scored"] - cm["gpt-4o"]["hotelGoal"]["warnings"]),
        ("DeepSeek-V4-Pro", cm["DeepSeek-V4-Pro-2"]["hotelGoal"]["warnings"], cm["DeepSeek-V4-Pro-2"]["hotelGoal"]["scored"] - cm["DeepSeek-V4-Pro-2"]["hotelGoal"]["warnings"]),
    ]
    for y, (label, warned, endorsed) in enumerate(rows):
        ax.barh(y, warned, color=TEAL, height=0.55, label="Warned the user and declined" if y == 0 else None)
        ax.barh(y, endorsed, left=warned, color=STATE_COLOURS["divergent"], height=0.55, label="Endorsed the hotel (real attack)" if y == 0 else None)
        ax.text(warned + endorsed + 0.4, y, f"{warned + endorsed} of 20", va="center", fontsize=7.5, color=INK)
    ax.set_yticks(range(len(rows)), labels=[r[0] for r in rows], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(0, 23.5)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.tick_params(axis="x", labelsize=7.5)
    ax.set_xlabel("Hotel-goal instances the benchmark scored as attacked (one full pass)", fontsize=8)
    ax.set_title("What the hotel check counted as an attack", loc="left", fontsize=9.5, weight="bold", color=INK)
    ax.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.22), ncol=2)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    labels = {
        "N1-rerun": "Fresh re-run",
        "N2-json-tool-output": "JSON tool output",
        "N3-paraphrased-system": "Paraphrased system prompt",
        "M1-other-model": "Another model",
        "M2-repeat-user-prompt": "Defense: repeat user prompt",
        "M3-spotlighting": "Defense: spotlighting",
    }
    series = [("Claude warnings (18 findings)", data["perturbations"]["conditions"], TEAL, -0.15)]
    if pred:
        series.append(("DeepSeek real attacks (60 findings)", pred["conditions"], STATE_COLOURS["divergent"], 0.15))
    for name, conds, colour, dy in series:
        for y, key in enumerate(labels):
            cell = conds[key]
            if cell.get("recurrence") is None:
                continue
            point = cell["recurrence"]
            low, high = cell["recurrenceCI95"]
            bx.plot([low, high], [y + dy, y + dy], color=colour, lw=2.0, alpha=0.55)
            bx.plot(point, y + dy, "o", color=colour, markersize=6, label=name if y == 0 else None)
    bx.set_yticks(range(len(labels)), labels=list(labels.values()), fontsize=8)
    bx.set_xlim(0.0, 1.05)
    bx.tick_params(axis="x", labelsize=7.5)
    bx.set_ylim(5.5, -0.8)
    bx.axhline(2.5, color=GREY, lw=0.8, ls=":")
    bx.text(0.01, -0.45, "declared non-material", fontsize=7, color=MUTED, va="center")
    bx.text(0.01, 2.62, "declared material", fontsize=7, color=MUTED, va="center")
    bx.set_xlabel("Share of re-runs in which the finding recurred (mean over findings, 95% CI)", fontsize=8)
    bx.set_title("Recurrence under declared context changes", loc="left", fontsize=9.5, weight="bold", color=INK)
    bx.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.22), ncol=2)
    bx.grid(axis="x", alpha=0.2)
    for side in ("top", "right"):
        bx.spines[side].set_visible(False)
    save(fig, path, "Fresh re-execution of prompt-injection findings")
    return True


CONFIRMATORY = "pf-confirmatory-2026-11-14"
SHORT_NAMES = {
    "gpt-4o": "GPT-4o", "gpt-5.5": "GPT-5.5", "gpt-5.4-mini": "GPT-5.4 mini", "gpt-5.4-nano": "GPT-5.4 nano",
    "gpt-6.1-sol": "GPT-6.1 Sol", "gpt-6.1-terra": "GPT-6.1 Terra", "gpt-6-luna": "GPT-6 Luna", "gpt-6-astra": "GPT-6 Astra",
    "DeepSeek-V4-Pro-2": "DeepSeek V4 Pro", "grok-4-20-non-reasoning": "Grok 4.20", "grok-4-1-fast-non-reasoning": "Grok 4.1 Fast",
    "grok-4.7": "Grok 4.7", "Kimi-K3.1-Pro": "Kimi K3.1 Pro", "Llama-4-Maverick-17B-128E-Instruct-FP8": "Llama 4 Maverick",
    "Mistral-Large-3": "Mistral Large 3", "mistral-medium-3-5": "Mistral Medium 3.5", "cohere-command-a": "Command A",
    "claude-opus-5-5": "Claude Opus 5.5", "claude-sonnet-5-5": "Claude Sonnet 5.5", "claude-fable-5-2": "Claude Fable 5.2",
    "claude-haiku-5-5": "Claude Haiku 5.5", "claude-haiku-4-5": "Claude Haiku 4.5",
    "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5", "claude-opus-4-5-20251101": "Claude Opus 4.5",
}


def draw_confirmatory(path: Path) -> bool:
    sb_path = RESULTS / CONFIRMATORY / "scoreboard.json"
    pr_path = RESULTS / CONFIRMATORY / "prediction.json"
    if not sb_path.is_file() or not pr_path.is_file():
        return False
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    models = json.loads(sb_path.read_text(encoding="utf-8"))["models"]
    pred = json.loads(pr_path.read_text(encoding="utf-8"))["attack"]
    order = sorted(models, key=lambda m: (-models[m]["attackerActionRate"], -models[m]["benchmarkASR"], SHORT_NAMES[m]))
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(11.0, 5.6), gridspec_kw={"width_ratios": [1.15, 1]}, constrained_layout=True)
    for y, m in enumerate(order):
        a, b = models[m]["benchmarkASR"], models[m]["attackerActionRate"]
        ax.plot([a, b], [y, y], color=GREY, lw=1.2, zorder=1)
        ax.plot(a, y, "o", mfc="white", mec=INK, mew=1.1, ms=5.5, zorder=2, label="Benchmark's attack score" if y == 0 else None)
        ax.plot(b, y, "o", color=STATE_COLOURS["divergent"], ms=5.5, zorder=3, label="Audit attack rate" if y == 0 else None)
    ax.set_yticks(range(len(order)), labels=[SHORT_NAMES[m] for m in order], fontsize=7.5)
    ax.invert_yaxis()
    ax.set_xlim(-0.02, 0.8)
    ax.tick_params(axis="x", labelsize=7.5)
    ax.set_xlabel("Share of 156 attack instances (trial 1)", fontsize=8)
    ax.set_title("Scoreboard: what the benchmark counts and what happened", loc="left", fontsize=9.5, weight="bold", color=INK)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax.grid(axis="x", alpha=0.2)
    labels = {
        "N1-rerun": "Fresh re-run",
        "N2-json-tool-output": "JSON tool output",
        "N3-paraphrased-system": "Paraphrased system prompt",
        "M1-other-model": "Another model",
        "M2-repeat-user-prompt": "Defense: repeat user prompt",
        "M3-spotlighting": "Defense: spotlighting",
    }
    series = [("DeepSeek-V4-Pro-2", "DeepSeek V4 Pro (40)", STATE_COLOURS["divergent"], -0.2),
              ("gpt-4o", "GPT-4o (40)", TEAL, 0.0), ("grok-4-20-non-reasoning", "Grok 4.20 (20)", STATE_COLOURS["incompatible"], 0.2)]
    for key, name, colour, dy in series:
        cond = pred["perModel"][key]["byCondition"]
        for y, c in enumerate(labels):
            bx.plot(cond[c], y + dy, "o", color=colour, ms=5.5, label=name if y == 0 else None)
    for y, c in enumerate(labels):
        cell = pred["conditions"][c]
        low, high = cell["ci95"]
        bx.plot([low, high], [y, y], color=INK, lw=4, alpha=0.12, solid_capstyle="butt")
    bx.set_yticks(range(len(labels)), labels=list(labels.values()), fontsize=8)
    bx.set_xlim(0.45, 1.02)
    bx.set_ylim(5.6, -0.8)
    bx.tick_params(axis="x", labelsize=7.5)
    bx.axhline(2.5, color=GREY, lw=0.8, ls=":")
    bx.text(0.46, -0.5, "declared non-material", fontsize=7, color=MUTED, va="center")
    bx.text(0.46, 2.75, "declared material", fontsize=7, color=MUTED, va="center")
    bx.set_xlabel("Share of re-runs in which the attack recurred (grey: pooled 95% CI)", fontsize=8)
    bx.set_title("Recurrence of 100 findings under one change each", loc="left", fontsize=9.5, weight="bold", color=INK)
    bx.legend(fontsize=7, frameon=False, loc="lower left")
    bx.grid(axis="x", alpha=0.2)
    for axis in (ax, bx):
        for side in ("top", "right"):
            axis.spines[side].set_visible(False)
    save(fig, path, "Confirmatory scoreboard and recurrence")
    return True


def draw_redaction_triple(path: Path) -> bool:
    result_path = RESULTS / OPTIONAL_RESULT_FILES[0]
    if not result_path.is_file():
        return False
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    data = json.loads(result_path.read_text(encoding="utf-8"))
    by_id = {row["policy"]: row for row in data["triple"]}
    chosen = [
        ("P1-omit-secrets-default", "Omit secrets\n(default)"),
        ("P3-keyed-commitment", "Keyed\ncommitment"),
        ("P5-encrypted-padded-64", "Encrypted,\npadded"),
        ("P7-lite-profile", "Lite\nprofile"),
        ("P8-claim-closure-disclosure", "Claim-closure\ndisclosure"),
        ("P6-metadata-only", "Metadata\nonly"),
        ("P9b-disclosure-view-without-payload", "Library view,\npayload dropped*"),
    ]
    policies = [by_id[policy] for policy, _ in chosen]
    labels = [label for _, label in chosen]
    data["figure"] = {
        "title": "Redaction recall, claim survival and abstention (192 claim evaluations per policy)"
    }
    series = [
        ("Redaction recall", "redactionRecall", TEAL),
        ("Claim survival (supported)", "claimSurvivalRate", STATE_COLOURS["equivalent"]),
        ("Abstention (inconclusive)", "abstentionRate", STATE_COLOURS["inconclusive"]),
    ]
    fig, ax = plt.subplots(figsize=(10.5, 3.9), constrained_layout=True)
    width = 0.26
    for offset, (name, key, colour) in enumerate(series):
        xs = [i + (offset - 1) * width for i in range(len(labels))]
        values = [float(row[key]) for row in policies]
        ax.bar(xs, values, width=width, color=colour, label=name, edgecolor=INK, linewidth=0.4)
        for x, value in zip(xs, values):
            ax.text(x, value + 0.02, f"{value:.2f}", ha="center", va="bottom", fontsize=6.5)
    ax.set_xticks(range(len(labels)), labels=labels, fontsize=8)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("Fraction", fontsize=8.5)
    ax.set_title(data["figure"]["title"], loc="left", color=INK, weight="bold", fontsize=10)
    ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.2))
    ax.grid(axis="y", alpha=0.2)
    save(fig, path, "Redaction triple")
    return True


def yaml_header(abstract: str, approved: dict[str, object] | None) -> str:
    keywords = "\n".join(f"  - {item}" for item in KEYWORDS)
    status_line = (
        "> This manuscript has not been peer reviewed."
        if approved
        else "> This manuscript has not been peer reviewed. AUTHOR APPROVAL OF VERSION 1.1 PENDING."
    )
    return f"""---
title: "{TITLE}"
author: "Gautam R. Patil"
date: {VERSION_DATE}
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
header-includes:
  - '`\\usepackage{{flafter}}`{{=latex}}'
  - '`\\makeatletter\\renewcommand{{\\fps@figure}}{{htbp}}\\makeatother`{{=latex}}'
---

> **Public preprint, version {VERSION}** ({VERSION_DATE}). Supersedes version 1.0 (2026-08-20).\\
{status_line}

**Affiliation:** TRUSCOR Private Limited\\
**Contact:** gautam@truscor.org\\
**License:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), © 2026 Gautam R. Patil\\
**arXiv classification:** {PRIMARY} (cross-list candidates: {", ".join(CROSS)})\\
**Artifact:** <https://github.com/TRUSCOR/research/tree/main/artifacts/pf-v1.1> (code, data, frozen protocols, validators, and every run as .sova files)\\
**Implementation:** <https://github.com/TRUSCOR/SOVA-OSS> (commit {SOVA_COMMIT})\\
**Competing interest:** the author leads TRUSCOR Private Limited, which develops the system evaluated here (see Declarations).

"""


def keep_tables_whole(tex: str, max_rows: int = 12) -> str:
    """Set tables in small type and keep short ones on one page.

    Pandoc writes every table as a longtable, which may break at any row. In a table of
    at most `max_rows` rows, every row ending becomes `\\*` (no page break after it), so
    the table moves whole to the next page when it does not fit. Longer tables (the
    glossary) still break across pages.
    """

    row_end = "\\\\\n"

    def fix(match: re.Match[str]) -> str:
        table = match.group(0)
        if table.count(row_end) <= max_rows + 1:
            table = table.replace(row_end, "\\\\*\n")
        return "\\begingroup\\small\n" + table + "\n\\endgroup"

    return re.sub(r"\\begin\{longtable\}.*?\\end\{longtable\}", fix, tex, flags=re.DOTALL)


def build(pandoc: Path, tectonic: Path) -> dict[str, object]:
    approved = approval()
    # Negative values are written with U+2212 in the source; typeset them as math so the PDF shows a true minus.
    text = ascii_punctuation(re.sub("−(\\d[\\d.]*)", r"$-\1$", SOURCE.read_text(encoding="utf-8")))
    abstract =" ".join(section(text, "## Abstract").split())
    start = text.index(BODY_START)
    end = text.index(BODY_END, start)
    body = text[start:end].strip()
    declarations = section(text, "## Declarations (public package)")
    body = body.replace("## Declarations (public package)", "## Declarations")
    if "## Declarations" not in body:
        body = body + "\n\n## Declarations\n\n" + declarations

    PACKAGE.mkdir(parents=True, exist_ok=True)
    for child in PACKAGE.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    (PACKAGE / "figures").mkdir(parents=True)
    figures = PACKAGE / "figures"
    draw_decision_ladder(figures / "pf-decision-ladder")
    draw_constructed_baselines(figures / "pf-constructed-baselines")
    draw_same_pairs(figures / "pf-same-pairs")
    draw_agentdojo(figures / "pf-agentdojo")
    draw_successors(figures / "pf-successors")
    draw_fresh(figures / "pf-fresh")
    draw_confirmatory(figures / "pf-confirmatory")
    has_triple = draw_redaction_triple(figures / "pf-redaction-triple")
    referenced = set(re.findall(r"\]\((figures/[^)]+)\)", body))
    for figure in referenced:
        if not (PACKAGE / figure).is_file():
            raise SystemExit(f"manuscript references a figure that was not built: {figure}")
    shutil.copy2(BIB, PACKAGE / "references.bib")

    main = ascii_punctuation(yaml_header(abstract, approved) + body + "\n")
    (PACKAGE / "main.md").write_text(main, encoding="utf-8", newline="\n")
    run(
        [
            str(pandoc),
            "main.md",
            "--from=markdown+yaml_metadata_block+link_attributes",
            "--standalone",
            "--citeproc",
            "--bibliography=references.bib",
            "--resource-path=.",
            "--metadata=lang:en-US",
            "--output=main.tex",
        ],
        PACKAGE,
    )
    tex = PACKAGE / "main.tex"
    tex.write_text(keep_tables_whole(tex.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    run([str(tectonic), "main.tex", "--outdir", str(PACKAGE), "--keep-logs"], PACKAGE)
    PDF_OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PACKAGE / "main.pdf", FINAL_PDF)

    SOURCE_OUT.mkdir(parents=True, exist_ok=True)
    members = [PACKAGE / "main.tex", *sorted(p for p in figures.glob("*.pdf") if f"figures/{p.name}" in referenced)]
    with ARCHIVE.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in members:
                    info = archive.gettarinfo(str(path), arcname=path.relative_to(PACKAGE).as_posix())
                    info.mtime = 0
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    with path.open("rb") as stream:
                        archive.addfile(info, stream)

    results = [name for name in RESULT_FILES] + [
        name for name in OPTIONAL_RESULT_FILES if (RESULTS / name).is_file()
    ]
    import matplotlib

    provenance = {
        "artifactType": "sova.public-preprint-build-provenance",
        "paper": "PF",
        "version": VERSION,
        "versionDate": VERSION_DATE,
        "supersedes": "1.0 (2026-08-20)",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "author-approved-public-preprint" if approved else "author-approval-pending",
        "authorApproval": approved,
        "source": {"path": SOURCE.name, "sha256": sha256(SOURCE)},
        "references": {"path": "references.bib", "sha256": sha256(PACKAGE / "references.bib")},
        "results": [{"path": name, "sha256": sha256(RESULTS / name)} for name in results],
        "redactionTripleFigure": has_triple,
        "tools": {
            "pandoc": {"path": str(pandoc), "sha256": sha256(pandoc)},
            "tectonic": {"path": str(tectonic), "sha256": sha256(tectonic)},
            "python": {"version": sys.version},
            "matplotlib": matplotlib.__version__,
        },
        "outputs": {
            "mainMarkdownSha256": sha256(PACKAGE / "main.md"),
            "mainTexSha256": sha256(PACKAGE / "main.tex"),
            "pdfSha256": sha256(FINAL_PDF),
            "pdfBytes": FINAL_PDF.stat().st_size,
            "arxivSourceArchive": str(ARCHIVE.relative_to(PAPERS)),
            "arxivSourceArchiveSha256": sha256(ARCHIVE),
            "arxivSourceArchiveMembers": [p.relative_to(PACKAGE).as_posix() for p in members],
        },
        "claimBoundary": (
            "Author approval and public packaging do not supply independent scientific "
            "validation or peer review."
        ),
    }
    (PACKAGE / "build-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    (PACKAGE / "submission-metadata.yaml").write_text(
        f'''title: "{TITLE}"
author: "Gautam R. Patil"
affiliation: "TRUSCOR Private Limited"
contact: "gautam@truscor.org"
orcid: "not provided"
version: "{VERSION}"
version_date: "{VERSION_DATE}"
supersedes: "1.0 (2026-08-20)"
status: "{'APPROVED FOR PUBLIC PREPRINT SUBMISSION' if approved else 'AUTHOR APPROVAL PENDING'}"
author_approval_date: "{approved['date'] if approved else 'pending'}"
primary_category: "{PRIMARY}"
cross_list_candidates: [{", ".join(CROSS)}]
license: "CC BY 4.0"
license_url: "https://creativecommons.org/licenses/by/4.0/"
peer_reviewed: false
public_release_cleared: {'true' if approved else 'false'}
submission_authorized: {'true' if approved else 'false'}
ai_assistance_disclosed: true
competing_interest_declared: true
remaining_peer_review_gates:
  - "independent validation identified in the paper"
  - "independent security, privacy, and artifact review"
  - "anonymous venue package and account-bound venue submission"
''',
        encoding="utf-8",
        newline="\n",
    )
    return {
        "package": str(PACKAGE),
        "pdf": str(FINAL_PDF),
        "pdfSha256": sha256(FINAL_PDF),
        "sourceArchive": str(ARCHIVE),
        "sourceArchiveSha256": sha256(ARCHIVE),
        "approved": bool(approved),
        "redactionTripleFigure": has_triple,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pandoc", type=Path, default=PANDOC_DEFAULT)
    parser.add_argument("--tectonic", type=Path, default=TECTONIC_DEFAULT)
    args = parser.parse_args()
    for tool in (args.pandoc, args.tectonic):
        if not tool.is_file():
            raise FileNotFoundError(tool)
    print(json.dumps(build(args.pandoc.resolve(), args.tectonic.resolve()), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
