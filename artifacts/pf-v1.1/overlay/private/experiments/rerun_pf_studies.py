"""Re-execute the deterministic PF studies and diff them against the retained results.

Never writes to private/experiments/results. Run from the SOVA-OSS root:

    uv run python private/experiments/rerun_pf_studies.py <output-dir> [study ...]
"""

from __future__ import annotations

import importlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

RESULTS = Path("private/experiments/results")
VOLATILE = {
    "generatedAt", "durationSeconds", "decision_overhead", "elapsedSeconds", "seconds",
    "nanoseconds", "wallSeconds", "timing", "timings", "environment", "python", "platform",
    "mean_microseconds_per_call", "median_microseconds_per_call", "p95_microseconds_per_call",
    "startedAt", "finishedAt", "durationNanoseconds", "verifyNanoseconds",
}
STUDIES = [
    ("run_topics_04_06_study", "RESULT", "topics-04-06-study-2026-07-31.json"),
    ("run_topic05_component_ablation_study", "RESULT", "topic05-component-ablation-study-2026-07-31.json"),
    ("run_topic05_privacy_attack_study", "RESULT", "topic05-privacy-attack-study-2026-08-01.json"),
    ("run_independent_adapter_study", "RESULT", "topic06-independent-adapter-study-2026-07-31.json"),
    ("run_topics12_13_postbuild_study", "OUTPUT", "topics12-13-postbuild-study-2026-08-03.json"),
]


def diff(a: object, b: object, path: str, out: list[str]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key in VOLATILE:
                continue
            if key not in a or key not in b:
                out.append(f"{path}/{key} (missing)")
            else:
                diff(a[key], b[key], f"{path}/{key}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path} (length {len(a)} vs {len(b)})")
        else:
            for index, (x, y) in enumerate(zip(a, b)):
                diff(x, y, f"{path}[{index}]", out)
    elif a != b:
        out.append(path)


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    scratch = Path(sys.argv[1]).resolve()
    scratch.mkdir(parents=True, exist_ok=True)
    selected = sys.argv[2:] or [name for name, _, _ in STUDIES]
    sys.path.insert(0, ".")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    report = {
        "artifactType": "sova.pf-reexecution-check",
        "executedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sovaOssCommit": commit,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "volatileFieldsIgnored": sorted(VOLATILE),
        "studies": [],
    }
    for name, attribute, retained in STUDIES:
        if name not in selected:
            continue
        module = importlib.import_module(f"private.experiments.{name}")
        target = scratch / retained.replace(".json", ".rerun.json")
        setattr(module, attribute, target)
        started = time.perf_counter()
        code = module.main()
        seconds = round(time.perf_counter() - started, 1)
        differences: list[str] = []
        diff(
            json.loads(target.read_text(encoding="utf-8")),
            json.loads((RESULTS / retained).read_text(encoding="utf-8")),
            "",
            differences,
        )
        report["studies"].append(
            {
                "script": f"private/experiments/{name}.py",
                "retainedResult": retained,
                "returnCode": code,
                "seconds": seconds,
                "nonVolatileDifferences": len(differences),
                "differencePaths": differences[:50],
                "identicalApartFromVolatileFields": not differences,
            }
        )
        print(name, "differences:", len(differences), flush=True)
    (scratch / "reexecution-check.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if all(s["identicalApartFromVolatileFields"] for s in report["studies"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
