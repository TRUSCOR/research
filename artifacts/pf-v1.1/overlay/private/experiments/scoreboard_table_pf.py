"""Render the S2 scoreboard table for the paper from scoreboard.json (and nothing else).

    python scoreboard_table_pf.py results/pf-confirmatory-2026-11-14/scoreboard.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

NAMES = {
    "gpt-4o": ("OpenAI", "GPT-4o"), "gpt-5.5": ("OpenAI", "GPT-5.5"), "gpt-5.4-mini": ("OpenAI", "GPT-5.4 mini"),
    "gpt-5.4-nano": ("OpenAI", "GPT-5.4 nano"), "gpt-6.1-sol": ("OpenAI", "GPT-6.1 Sol"), "gpt-6.1-terra": ("OpenAI", "GPT-6.1 Terra"),
    "gpt-6-luna": ("OpenAI", "GPT-6 Luna"), "gpt-6-astra": ("OpenAI", "GPT-6 Astra"),
    "DeepSeek-V4-Pro-2": ("DeepSeek", "DeepSeek V4 Pro"),
    "grok-4-20-non-reasoning": ("xAI", "Grok 4.20"), "grok-4-1-fast-non-reasoning": ("xAI", "Grok 4.1 Fast"), "grok-4.7": ("xAI", "Grok 4.7"),
    "Kimi-K3.1-Pro": ("Moonshot AI", "Kimi K3.1 Pro"), "Llama-4-Maverick-17B-128E-Instruct-FP8": ("Meta", "Llama 4 Maverick"),
    "Mistral-Large-3": ("Mistral AI", "Mistral Large 3"), "mistral-medium-3-5": ("Mistral AI", "Mistral Medium 3.5"),
    "cohere-command-a": ("Cohere", "Command A"),
    "claude-opus-5-5": ("Anthropic", "Claude Opus 5.5"), "claude-sonnet-5-5": ("Anthropic", "Claude Sonnet 5.5"),
    "claude-fable-5-2": ("Anthropic", "Claude Fable 5.2"), "claude-haiku-5-5": ("Anthropic", "Claude Haiku 5.5"),
    "claude-haiku-4-5": ("Anthropic", "Claude Haiku 4.5"), "claude-sonnet-4-5-20250929": ("Anthropic", "Claude Sonnet 4.5"),
    "claude-opus-4-5-20251101": ("Anthropic", "Claude Opus 4.5"),
}


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def main() -> int:
    doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    rows = doc["models"]
    order = sorted(rows, key=lambda m: (-rows[m]["attackerActionRate"], -rows[m]["benchmarkASR"], NAMES[m][1]))
    out = ["| Developer | Model | Benchmark rate | Audit attack rate (95% CI) | Hotel runs scored / warnings | Can't tell |",
           "|------------|--------------------|-------:|----------------------|--------:|-----:|"]
    for m in order:
        r = rows[m]
        dev, name = NAMES[m]
        lo, hi = r["attackerActionCI95"]
        ci = f"{pct(r['attackerActionRate'])} ({100 * lo:.1f}-{100 * hi:.1f}%)"
        out.append(f"| {dev} | {name} | {pct(r['benchmarkASR'])} | {ci} | {r['hotelScored']} / {r['hotelWarningsScored']} | {r['crashes']} |")
    print("\n".join(out))
    print(f"\nKendall tau between the two rankings: {doc['kendallTauASRvsAction']:.2f}; models: {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
