"""Scan a run folder's traces.jsonl.gz member by member and report (or repair) damage.

Each trace is appended as its own gzip member. Two processes appended to the same file for about an
hour on 2026-11-14 (the locked xAI completion and extension E1 both wrote `s34/`), so some members
may have interleaved. This tool decompresses every member independently, keeps the members that
decode to one complete JSON trace, and lists the episodes whose trace is missing or damaged.

    python repair_pf_traces.py scan   <run-dir>            # report only
    python repair_pf_traces.py repair <run-dir>            # rewrite traces and episodes (exclusive access)

`repair` writes a clean traces.jsonl.gz (one member per valid trace, original order), drops the
episode records that have no valid trace (so the runner re-runs them), keeps the originals as
*.damaged, and writes repair-report.json. Nothing else is changed.
"""

from __future__ import annotations

import gzip
import json
import shutil
import sys
import zlib
from pathlib import Path

MAGIC = b"\x1f\x8b\x08"


def members(data: bytes):
    """Yield (offset, decoded text or None) for each gzip member, parsing sequentially.

    A member is decoded from its start until zlib reports its end; the next member starts where the
    unused bytes begin. On damage, the scan resumes at the next gzip header after the damaged start.
    """
    pos = data.find(MAGIC)
    while pos != -1 and pos < len(data):
        d = zlib.decompressobj(wbits=31)
        out = []
        ok = False
        try:
            step = 1 << 16
            cursor = pos
            while cursor < len(data):
                out.append(d.decompress(data[cursor:cursor + step]))
                cursor += step
                if d.eof:
                    ok = True
                    break
        except zlib.error:
            ok = False
        if ok:
            end = len(data) - len(d.unused_data) if cursor >= len(data) else cursor - len(d.unused_data)
            try:
                yield pos, b"".join(out).decode("utf-8")
            except UnicodeDecodeError:
                yield pos, None
            pos = data.find(MAGIC, end) if data[end:end + 3] != MAGIC else end
        else:
            yield pos, None
            pos = data.find(MAGIC, pos + 1)


def scan(run_dir: Path) -> dict:
    data = (run_dir / "traces.jsonl.gz").read_bytes()
    traces: dict[tuple, str] = {}
    order: list[tuple] = []
    bad = 0
    for _, text in members(data):
        if text is None:
            bad += 1
            continue
        for line in text.splitlines():
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            k = tuple(t["key"])
            if k not in traces:
                order.append(k)
            traces[k] = line
    episodes, broken_lines = [], 0
    for line in (run_dir / "episodes.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            episodes.append(json.loads(line))
        except json.JSONDecodeError:
            broken_lines += 1
    keys = [(r["model"], r["condition"], r["trial"], r["suite"], r["userTask"], r["injectionTask"]) for r in episodes]
    missing = [k for k in dict.fromkeys(keys) if k not in traces]
    return {"traces": traces, "order": order, "episodes": episodes, "keys": keys,
            "report": {"validTraces": len(traces), "badMembersOrLines": bad, "episodeLines": len(episodes),
                       "brokenEpisodeLines": broken_lines, "episodesWithoutTrace": len(missing),
                       "missing": [list(k) for k in missing]}}


def repair(run_dir: Path) -> None:
    res = scan(run_dir)
    traces, order, episodes, keys = res["traces"], res["order"], res["episodes"], res["keys"]
    shutil.copy2(run_dir / "traces.jsonl.gz", run_dir / "traces.jsonl.gz.damaged")
    shutil.copy2(run_dir / "episodes.jsonl", run_dir / "episodes.jsonl.damaged")
    # The frozen loader keeps the last record of a key, so keep the last one here too.
    last: dict[tuple, dict] = {}
    for r, k in zip(episodes, keys):
        if k in traces:
            last[k] = r
    keep, seen = list(last.values()), set(last)
    with gzip.open(run_dir / "traces.jsonl.gz", "wt", encoding="utf-8") as fh:
        for k in order:
            if k in seen:
                fh.write(traces[k] + "\n")
    (run_dir / "episodes.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in keep),
                                            encoding="utf-8", newline="\n")
    report = dict(res["report"], keptEpisodes=len(keep))
    (run_dir / "repair-report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "missing"}, indent=1))


if __name__ == "__main__":
    cmd, run_dir = sys.argv[1], Path(sys.argv[2])
    if cmd == "scan":
        print(json.dumps({k: v for k, v in scan(run_dir)["report"].items() if k != "missing"}, indent=1))
    else:
        repair(run_dir)
