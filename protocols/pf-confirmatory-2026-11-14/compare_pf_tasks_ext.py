"""PF extension E1, study S6b: the tasks beyond the recurrence decision, measured where a tool runs them.

Frozen by `PF-extension-addendum-2026-11-14.md` before it runs. For each of the paper's three
questions it records what each system does on the paper's own data:

  T8  re-run a recorded finding on a model, and report k of n with an interval
      (.sova: `sova rerun` on the four released findings, 3 trials each on GPT-4o and GPT-5.5);
  T9  check a benchmark verdict against the recorded actions
      (.sova: `sova audit` on every released bundle, from the audit-check files);
  T10 classify known findings across a model upgrade
      (.sova: `sova matrix --baseline gpt-4o --candidate gpt-5.5` on the four findings, 3 trials);
  T11 read and verify a record offline (from S6 T1 and T2, unchanged).

AgentTriage, ClaimReceipt and TRACE are assessed from their released code or papers: a task is
"not supported" when the system has no component for it, with the reason recorded. Nothing is
credited to .sova for a task another system does not attempt; the matrix records scope.

    PF_AZURE_NOTES=<notes file> python compare_pf_tasks_ext.py <out.json>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
R = HERE / "results" / "pf-confirmatory-2026-11-14"
SOVA_REPO = HERE.parents[1]
FINDINGS = Path(os.environ.get("PF_FINDINGS", str(HERE / "results" / "pf-findings-gallery-2026-11-13")))
SOVA = ["uv", "run", "--project", str(SOVA_REPO), "--with", "agentdojo==0.1.35", "sova"]
PRICES = {"gpt-4o": (2.5, 10.0), "gpt-5.5": (1.25, 10.0)}


def _env() -> dict[str, str]:
    from azure_foundry_client import _read_notes

    endpoint, key = _read_notes(None)
    return dict(os.environ, SOVA_OPENAI_BASE_URL=endpoint, SOVA_OPENAI_API_KEY=key)


def _sova(args: list[str], env: dict[str, str]) -> tuple[int, dict | None, float]:
    start = time.monotonic()
    res = subprocess.run([*SOVA, *args], cwd=str(SOVA_REPO), env=env, capture_output=True, text=True, encoding="utf-8")
    seconds = round(time.monotonic() - start, 1)
    doc = None
    for line in reversed(res.stdout.strip().splitlines()):
        try:
            doc = json.loads(line)
            break
        except json.JSONDecodeError:
            continue
    if doc is None and res.stdout.strip().startswith("{"):
        try:
            doc = json.loads(res.stdout)
        except json.JSONDecodeError:
            doc = None
    return res.returncode, doc, seconds


def main() -> int:
    out = Path(sys.argv[1])
    env = _env()
    provider = ["--provider", "openai-compatible", "--base-url-env", "SOVA_OPENAI_BASE_URL", "--api-key-env", "SOVA_OPENAI_API_KEY"]
    work = R / "s6b"
    work.mkdir(parents=True, exist_ok=True)
    findings = sorted(FINDINGS.glob("*.sova"))
    t8 = []
    for f in findings:
        for model in ("gpt-4o", "gpt-5.5"):
            pin, pout = PRICES[model]
            temperature = ["--temperature", "0"] if model == "gpt-4o" else []  # as in the studies
            code, doc, sec = _sova(["rerun", str(f), "--model", model, *provider, *temperature, "--trials", "3", "--json",
                                    "--authorize", "--max-usd", "2", "--price-in", str(pin), "--price-out", str(pout),
                                    "--out", str(work / f"rerun-{f.stem}-{model}")], env)
            t8.append({"finding": f.name, "model": model, "exit": code, "seconds": sec, "summary": doc})
    code, doc, sec = _sova(["matrix", *map(str, findings), "--baseline", "gpt-4o", "--candidate", "gpt-5.5", *provider,
                            "--trials", "3", "--json", "--authorize", "--max-usd", "4",
                            "--out", str(work / "matrix")], env)
    t10 = {"exit": code, "seconds": sec, "summary": doc}
    t9 = {}
    for d in ("s2", "s2-anthropic", "s2-grok-full", "s34", "s5", "s5-anthropic"):
        p = R / "sova" / d / "audit-check.json"
        if p.is_file():
            r = json.loads(p.read_text(encoding="utf-8"))
            t9[d] = {"episodes": r["episodes"], "agree": r["agree"], "other": len(r["otherDifferences"])}
    scope = {
        ".sova": {"T8": "measured", "T9": "measured", "T10": "measured", "T11": "measured (S6 T1, T2)"},
        "AgentTriage": {
            "T8": "not supported: its released drivers run its own Docker scenarios; it has no AgentDojo runner and no k-of-n rerun",
            "T9": "partial: diagnoses a trace given an oracle; with the audit's rules as oracle it reproduces them (S6), without one it has no goal rules",
            "T10": "not supported: no cross-model comparison",
            "T11": "not supported: no integrity check on a record (S6 T2)"},
        "ClaimReceipt": {
            "T8": "not supported: no released code; the paper verifies receipts of runs, it does not re-run them",
            "T9": "replays the benchmark's scorer, so it reproduces the scorer's verdicts, warnings included (S6 T6)",
            "T10": "not supported as released; a causal claim per treatment can be stated (S6)",
            "T11": "targeted by the paper (hash chain, commitments); not runnable, no released format"},
        "TRACE": {
            "T8": "not supported: a Trust Record keeps a digest of the tool transcript, not the scenario",
            "T9": "not supported: no event stream to audit",
            "T10": "not supported",
            "T11": "supported for its own records (signed digests); imported into .sova as a declared trust input"},
    }
    doc = {"artifactType": "sova.pf-s6b-tasks", "frozenBy": "PF-extension-addendum-2026-11-14.md",
           "T8": t8, "T9": t9, "T10": t10, "scope": scope}
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"T8": [(x["finding"], x["model"], x["exit"]) for x in t8], "T10exit": t10["exit"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
