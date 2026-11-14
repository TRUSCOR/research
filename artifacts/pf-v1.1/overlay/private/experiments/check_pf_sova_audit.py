"""Check that `sova audit` on the released .sova bundles gives the study analysis's categories.

For one study run directory (episodes.jsonl + traces.jsonl.gz) and the folder of .sova bundles
made from it by package_pf_v2_runs.py, this script
  1. recomputes every episode's category with the frozen research audit (audit_pf.py), and
  2. runs the released `sova audit --json` on each bundle,
then compares the two per instance (suite, user task, injection task, category), summed over
trials. It prints the counts that agree and every difference, and exits 1 if a difference is
not an `evidence-redacted` episode (a value the capture removed, which the product reports
instead of guessing).

    python check_pf_sova_audit.py <run-dir> <sova-dir> [--group model|model-condition] [--out check.json]
"""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_pf import audit_episode  # noqa: E402


def reference(run_dir: Path, group_by: str) -> dict[str, Counter]:
    eps = {}
    for line in (run_dir / "episodes.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        eps[(r["model"], r["condition"], r["trial"], r["suite"], r["userTask"], r["injectionTask"])] = r
    cats: dict[tuple, str] = {}
    with gzip.open(run_dir / "traces.jsonl.gz", "rt", encoding="utf-8") as fh:
        try:
            for line in fh:
                try:
                    t = json.loads(line)
                except json.JSONDecodeError:
                    break
                k = tuple(t["key"])
                if k in eps:
                    cats[k] = audit_episode(k[3], k[5], t["messages"], eps[k].get("security"), eps[k].get("error"))["category"]
        except EOFError:
            pass
    out: dict[str, Counter] = {}
    for k in eps:
        group = k[0] if group_by == "model" else f"{k[0]}--{k[1]}"
        out.setdefault(group.replace("/", "_"), Counter())[(k[3], k[4], k[5], cats.get(k, "crash"))] += 1
    return out


def sova_command() -> list[str]:
    exe = shutil.which("sova")
    return [exe] if exe else [sys.executable, "-m", "sova"]


def product(bundle: Path) -> Counter:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "audit.json"
        res = subprocess.run([*sova_command(), "audit", str(bundle), "--json", str(out)],
                             capture_output=True, text=True, encoding="utf-8")
        if res.returncode != 0 or not out.is_file():
            raise SystemExit(f"sova audit failed on {bundle}: {res.stderr[-400:]}")
        doc = json.loads(out.read_text(encoding="utf-8"))
    return Counter((e["suite"], e["userTask"], e["injectionTask"], e["category"]) for e in doc["episodes"])


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("run_dir")
    p.add_argument("sova_dir")
    p.add_argument("--group", choices=["model", "model-condition"], default="model")
    p.add_argument("--out")
    a = p.parse_args()
    ref = reference(Path(a.run_dir), a.group)
    total = agree = 0
    bad: list[dict] = []
    redacted: list[dict] = []
    per_group = {}
    for group in sorted(ref):
        bundles = sorted(Path(a.sova_dir).glob(f"{group}/*.sova"))
        if len(bundles) != 1:
            raise SystemExit(f"expected one bundle for {group}, found {len(bundles)}")
        got = product(bundles[0])
        want = ref[group]
        same = sum((want & got).values())
        n = sum(want.values())
        total += n
        agree += same
        per_group[group] = {"episodes": n, "agree": same}
        for key in sorted(set(want) | set(got)):
            if want[key] != got[key]:
                row = {"group": group, "suite": key[0], "userTask": key[1], "injectionTask": key[2],
                       "category": key[3], "analysis": want[key], "sova": got[key]}
                (redacted if key[3] == "evidence-redacted" or _paired_with_redacted(key, want, got) else bad).append(row)
        print(f"{group}: {same}/{n} agree", flush=True)
    report = {"runDir": Path(a.run_dir).name, "episodes": total, "agree": agree, "groups": per_group,
              "evidenceRedactedDifferences": redacted, "otherDifferences": bad}
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(f"total {agree}/{total} agree; differences explained by redaction: {len(redacted)}; other: {len(bad)}")
    return 1 if bad else 0


def _paired_with_redacted(key: tuple, want: Counter, got: Counter) -> bool:
    """The analysis side of a redacted episode: same instance, product says evidence-redacted."""
    return got[(key[0], key[1], key[2], "evidence-redacted")] > want[(key[0], key[1], key[2], "evidence-redacted")]


if __name__ == "__main__":
    sys.exit(main())
