"""Re-tally the reading of scored attacks (section 6.2) from a .sova capsule alone.

Verifies the capsule offline, then reads each embedded .sova-trace: AgentDojo's verdict
(`oracle.completed`), the reading label (`finding.reading`) and the attack instance
(`run.started`). Calls no model and needs only the SOVA OSS package.

    python -X utf8 tally_readings_from_sova.py claude-scored-successes.sova
"""

from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

from sova.formats.package import PackageReader
from sova.trace.reader import TraceReader


def tally(capsule: Path) -> dict:
    PackageReader(capsule).verify("sova.capsule")
    labels: Counter[str] = Counter()
    models: Counter[str] = Counter()
    instances: set[tuple[str, str, str]] = set()
    scored = 0
    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(capsule) as package:
        names = sorted(n for n in package.namelist() if n.startswith("traces/") and n.endswith(".sova-trace"))
        for name in names:
            path = Path(tmp) / Path(name).name
            path.write_bytes(package.read(name))
            reader = TraceReader(path)
            reader.verify()
            events = reader.events()
            start = next(e["payload"] for e in events if e["kind"] == "run.started")
            verdict = next(e["payload"] for e in events if e["kind"] == "oracle.completed")
            label = next((e["payload"]["label"] for e in events if e["kind"] == "finding.reading"), "unread")
            scored += bool(verdict["attackSucceeded"])
            labels[label] += 1
            models[start["model"]] += 1
            instances.add((start["suite"], start["userTask"], start["injectionTask"]))
    return {"traces": len(names), "scoredAsAttacked": scored, "labels": dict(sorted(labels.items())),
            "models": dict(sorted(models.items())), "distinctAttackInstances": len(instances)}


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(json.dumps(tally(Path(sys.argv[1])), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
