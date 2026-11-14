"""Package the new study runs as .sova files with the released tool itself.

Each run is written as an AgentDojo-format log, then `sova record agentdojo --bundle`
seals all runs of one model (or one study cell) into one capsule. Afterwards
`sova audit` on each capsule must give the same categories as the study analysis;
the comparison is written to package-check.json.

    python package_pf_v2_runs.py <run-dir> <out-dir> [--group model|model-condition]
"""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

SOVA_REPO = Path(__file__).resolve().parents[2]


def episodes(run_dir: Path):
    eps = {}
    for line in (run_dir / "episodes.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        eps[(r["model"], r["condition"], r["trial"], r["suite"], r["userTask"], r["injectionTask"])] = r
    with gzip.open(run_dir / "traces.jsonl.gz", "rt", encoding="utf-8") as fh:
        try:
            for line in fh:
                try:
                    t = json.loads(line)
                except json.JSONDecodeError:
                    break
                k = tuple(t["key"])
                if k in eps:
                    yield k, eps[k], t["messages"]
        except EOFError:
            return


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("run_dir")
    p.add_argument("out_dir")
    p.add_argument("--group", choices=["model", "model-condition"], default="model")
    a = p.parse_args()
    run_dir, out = Path(a.run_dir), Path(a.out_dir)
    stage = out / "_logs"
    if stage.exists():
        shutil.rmtree(stage)
    groups: dict[str, list[str]] = defaultdict(list)
    for k, r, messages in episodes(run_dir):
        model, cond, trial, suite, user, inj = k
        group = model if a.group == "model" else f"{model}--{cond}"
        name = f"{suite}--{user}--{inj}--{cond}--t{trial}.json"
        log = {"suite_name": suite, "pipeline_name": model, "user_task_id": user, "injection_task_id": inj,
               "attack_type": r.get("attack", "important_instructions"), "benchmark_version": r.get("benchmarkVersion"),
               "agentdojo_package_version": (r.get("software") or {}).get("agentdojo"), "messages": messages,
               "error": r.get("error"), "duration": r.get("seconds"), "utility": r.get("utility"), "security": r.get("security"),
               "condition": cond, "trial": trial}
        d = stage / group.replace("/", "_")
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(json.dumps(log, default=str), encoding="utf-8")
        groups[group].append(name)
    out.mkdir(parents=True, exist_ok=True)
    made = {}
    for group in sorted(groups):
        safe = group.replace("/", "_")
        cmd = ["uv", "run", "--project", str(SOVA_REPO), "sova", "record", "agentdojo", str(stage / safe),
               "--out", str(out / safe), "--bundle", "--name", safe, "--author", "Gautam R. Patil"]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if res.returncode != 0:
            print("record failed", group, res.stderr[-400:], file=sys.stderr)
            return 1
        made[group] = len(groups[group])
        print(f"{group}: {len(groups[group])} runs sealed", flush=True)
    shutil.rmtree(stage)
    (out / "packaged.json").write_text(json.dumps({"runDir": run_dir.name, "groups": made}, indent=1) + "\n", encoding="utf-8")
    print(Counter({"capsules": len(made), "runs": sum(made.values())}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
