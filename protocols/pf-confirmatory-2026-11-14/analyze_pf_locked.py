"""Re-run the frozen S3, S4 and S5 analyses on the completed locked design.

The results of the reduced design (deviation D2) were analysed first; they are kept under
`*-d2-interim.json` (and `s6-d2-interim/`) and reported as an interim look. This script writes the
final files under the original names, with the frozen functions of analyze_pf_v2.py and the plan
`plan-locked.json`.

    python analyze_pf_locked.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_pf_v2 as an  # noqa: E402

R = HERE / "results" / "pf-confirmatory-2026-11-14"


def keep_interim(name: str) -> None:
    src, dst = R / name, R / name.replace(".json", "-d2-interim.json")
    if src.is_file() and not dst.is_file():
        shutil.copy2(src, dst)


def main() -> int:
    for name in ("reliability.json", "prediction.json", "upgrade.json", "upgrade-pairs.json", "posthoc-sensitivity.json"):
        keep_interim(name)
    if (R / "s6").is_dir() and not (R / "s6-d2-interim").is_dir():
        shutil.copytree(R / "s6", R / "s6-d2-interim")
    plan = R / "plan-locked.json"
    an.reliability(plan, R / "s34", R / "reliability.json")
    an.prediction(plan, R / "s34", R / "prediction.json")
    p = json.loads(plan.read_text(encoding="utf-8"))
    by = {e["model"]: e for e in p["primaries"]}
    sonnet = json.loads((R / "plan-s5-claude.json").read_text(encoding="utf-8"))["primaries"][0]["findings"]
    pairs = [
        {"baseline": "gpt-4o", "candidate": "gpt-5.5", "findings": by["gpt-4o"]["findings"]},
        {"baseline": "grok-4-20-non-reasoning", "candidate": "grok-4.7", "findings": by["grok-4-20-non-reasoning"]["findings"]},
        {"baseline": "claude-sonnet-4-5-20250929", "candidate": "claude-sonnet-5-5", "findings": sonnet},
    ]
    (R / "upgrade-pairs.json").write_text(json.dumps(pairs, indent=1) + "\n", encoding="utf-8")
    an.upgrade(R / "upgrade-pairs.json", R / "upgrade.json", [R / "s34", R / "s5", R / "s5-anthropic"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
