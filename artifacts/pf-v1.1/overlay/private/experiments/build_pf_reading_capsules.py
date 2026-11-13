"""Package every reply the paper read (section 6.2) as .sova-traces in two capsules, then re-tally.

`claude-scored-successes.sova` holds the 341 runs on Claude models that AgentDojo scored as
successful attacks; `gpt-4o-deepseek-read-attacks.sova` holds the 109 sampled scored successes
on GPT-4o and DeepSeek-V4-Pro. Each trace carries the exact recorded messages, AgentDojo's
verdict (`oracle.completed`) and the reading label (`finding.reading`). `tally_readings_from_sova.py`
recomputes the paper's counts from the capsules alone. Post hoc; calls no model.

    python -X utf8 private/experiments/build_pf_reading_capsules.py <out-dir>
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import sys
import tempfile
import uuid
from pathlib import Path

from sova.capsule.model import CaptureProfile, DomainProfile, build_capsule, capsule_manifest_template
from sova.formats import canonical_json_bytes, sha256_digest

HERE = Path(__file__).resolve().parent


def load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


gallery = load("gallery", "build_pf_findings_gallery.py")
tally_module = load("tally", "tally_readings_from_sova.py")
RES = gallery.RES
FOLDERS = {
    "pf-fresh-reexecution-2026-11-12": (RES / "pf-fresh-reexecution-2026-11-12", "fresh"),
    "full-sonnet-4-5-important-instructions": (RES / "pf-real-attack-predictiveness-2026-11-12/full-sonnet-4-5-important-instructions", "sonnet45"),
    "cross": (RES / "pf-cross-provider-2026-11-13", "cross"),
}


def index_folder(folder: Path, wanted: set[tuple]) -> tuple[dict, dict]:
    meta, traces = {}, {}
    for line in (folder / "episodes.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        key = (row["model"], row["condition"], row["trial"], row["suite"], row["userTask"], row["injectionTask"])
        if key in wanted:
            meta[key] = row
    with gzip.open(folder / "traces.jsonl.gz", "rt", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            key = tuple(record["key"][:6])
            if key in wanted:
                traces[key] = record
    return meta, traces


def build(out: Path, name: str, title: str, summary: str, labels: dict[tuple, tuple[str, str]], tmp: Path) -> str:
    """labels: key -> (folder id, label)."""
    named: dict[str, Path] = {}
    digests: set[str] = set()
    protocols: set[str] = set()
    by_folder: dict[str, set] = {}
    for key, (folder_id, _label) in labels.items():
        by_folder.setdefault(folder_id, set()).add(key)
    for folder_id, keys in sorted(by_folder.items()):
        folder, source = FOLDERS[folder_id]
        meta, traces = index_folder(folder, keys)
        missing = keys - set(traces)
        if missing:
            raise SystemExit(f"{len(missing)} traces missing in {folder_id}")
        digest = gallery.file_digest(folder / "traces.jsonl.gz")
        digests.add(digest)
        protocols.add(gallery.file_digest(gallery.PROTOCOLS[source]))
        for key in sorted(keys):
            model, condition, trial, suite, user, injection = key
            row = meta.get(key) or {}
            software = row.get("software") or {}
            path = tmp / f"{model}--{condition}--{trial}--{suite}--{user}--{injection}.sova-trace"
            gallery.write_trace(
                path, messages=traces[key]["messages"], model=model,
                run_info={"benchmark": "AgentDojo", "benchmarkVersion": row.get("benchmarkVersion"), "agentdojo": software.get("agentdojo"),
                          "python": software.get("python"), "attack": row.get("attack", "important_instructions"), "suite": suite,
                          "userTask": user, "injectionTask": injection, "model": model, "returnedModels": row.get("returnedModels"),
                          "condition": condition, "trial": trial, "startedAt": row.get("startedAt")},
                imported={"from": "PF v1.1 study message trace",
                          "path": f"{folder.relative_to(gallery.ROOT).as_posix()}/traces.jsonl.gz key {json.dumps(list(key))}",
                          "sha256": digest,
                          "episodeRecordSha256": sha256_digest(canonical_json_bytes(gallery.decimals(row))) if row else None},
                security=bool(row.get("security", True)), utility=row.get("utility"), reading=labels[key][1], durability="lite",
            )
            named[path.name] = path
    scenario = {
        "artifactType": "sova.scenario", "schemaVersion": "0.1.0",
        "id": "sova:scenario:" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://github.com/ethz-spylab/agentdojo#{name}")),
        "version": "0.1.0", "title": title,
        "purpose": "Read every run the benchmark scored as a successful prompt-injection attack and label what the reply did.",
        "parameters": {"benchmark": "AgentDojo", "benchmarkVersion": "v1.2.2", "agentdojo": "0.1.35", "runs": len(named)},
        "preconditions": [{"kind": "simulated-environment", "owned": True, "note": "AgentDojo's synthetic data; no real account or money."}],
        "sequences": [],
        "procedure": {"steps": [{"id": "run-episode", "action": "agentdojo.run-injection-episode", "inputs": {},
                                 "onFailure": "inconclusive", "requires": ["agentdojo/0.1.35"]}]},
        "triggers": [{"kind": "planted-instruction", "location": "tool output"}],
        "mutations": [],
        "expectedEffects": [{"kind": "attacker-goal", "simulated": True}],
        "oracles": [{"kind": "agentdojo.injection-task.security", "attackSucceeded": True}],
        "evidenceRequirements": ["prompt.user", "tool.result", "model.response", "tool.requested", "oracle.completed", "finding.reading"],
        "safety": {"budgets": {"maxSteps": 1}, "forbiddenEffects": ["real accounts", "real money"], "stopConditions": []},
        "cleanup": [{"kind": "environment-discarded", "verify": False}],
        "limitations": [
            "Converted post hoc from recorded runs; the runs did not write .sova-traces.",
            "Reading labels are AI-assisted (a Claude model under the author's direction) and were not blind to the benchmark's verdict.",
        ],
        "extensions": {},
    }
    manifest = capsule_manifest_template(title=title, summary=summary, author=gallery.AUTHOR,
                                         domain_profile=DomainProfile.SECURITY, capture_profile=CaptureProfile.STANDARD)
    manifest["authors"] = [{"name": gallery.AUTHOR, "affiliation": gallery.AFFILIATION}]
    manifest["lifecycle"] = "disclosed"
    manifest["citation"] = {"preferred": f"{gallery.AUTHOR}. {title}. .sova capsule released with: {gallery.PAPER}", "identifiers": []}
    manifest["provenance"]["sourceDigests"] = sorted(digests | protocols)
    manifest["provenance"]["transformations"] = ["Recorded messages converted post hoc to .sova-trace events; no content changed."]
    manifest["methodology"] = {"id": "PF-V1.1-AGENTDOJO-REEXECUTION", "version": "1.1", "digest": sorted(protocols)[0]}
    manifest["taxonomy"] = {"id": "agentdojo.injection-task", "version": "v1.2.2", "digest": sha256_digest(canonical_json_bytes({"reading": name}))}
    manifest["compatibility"] = {"runtime": "sova-runtime>=0.1.0a0", "models": sorted({k[0] for k in labels}), "tools": ["agentdojo==0.1.35"], "platforms": []}
    manifest["safety"] = {"impact": "none", "forbiddenEffects": ["real accounts", "real money"], "cleanupRequired": False}
    manifest["disclosure"] = {"classification": "public", "sharing": "Released with the PF v1.1 preprint. Contains AgentDojo's synthetic data and model replies."}
    manifest["license"] = "CC-BY-4.0 AND MIT"
    manifest["limitations"] = scenario["limitations"] + ["Opening or verifying this capsule runs nothing."]
    manifest["requiredFeatures"] = ["scenario.core/0.1"]
    return build_capsule(out / name, manifest, scenario=scenario, named_traces=named)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=False)
    audit = json.loads((RES / "pf-fresh-successes-manual-audit-2026-11-13.json").read_text(encoding="utf-8"))["labels"]
    claude = {}
    for key, label in audit.items():
        folder_id, model, condition, trial, suite, user, injection = key.split("|")
        claude[(model, condition, int(trial), suite, user, injection)] = (folder_id, label)
    reading = json.loads((RES / "pf-cross-provider-reading-2026-11-13.json").read_text(encoding="utf-8"))["labels"]
    other = {}
    for key, label in reading.items():
        model, condition, trial, suite, user, injection = key.split("|")
        other[(model, condition, int(trial), suite, user, injection)] = ("cross", label)
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, title, summary, labels in (
            ("claude-scored-successes.sova", "Every run on a Claude model that AgentDojo scored as a successful attack, with our reading",
             "The 341 runs on Claude models that AgentDojo scored as successful prompt-injection attacks, each as a .sova-trace with the benchmark's verdict and the reading of the reply.", claude),
            ("gpt-4o-deepseek-read-attacks.sova", "A random sample of scored attacks on GPT-4o and DeepSeek-V4-Pro, with our reading",
             "The 109 sampled runs on GPT-4o and DeepSeek-V4-Pro that AgentDojo scored as successful attacks, each as a .sova-trace with the benchmark's verdict and the reading of the reply.", other),
        ):
            sub = Path(tmp) / name
            sub.mkdir()
            digest = build(out, name, title, summary, labels, sub)
            results[name] = {"capsuleSha256": digest, **tally_module.tally(out / name)}
    (out / "readings-from-sova.json").write_bytes(canonical_json_bytes(results) + b"\n")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
