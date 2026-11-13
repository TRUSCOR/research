"""Package the whole published-GPT-4o re-run study (section 6.2) as one .sova capsule.

For every attack instance shared by AgentDojo's published GPT-4o log (gpt-4o-2024-05-13)
and our fresh GPT-4o run (the cross-provider protocol, 2026), the exact recorded messages of
both runs are converted to .sova-traces, each ending in AgentDojo's own security verdict. All
pairs go into a single capsule, which `recompute_recurrence_from_sova.py` then reads to
recompute the recurrence result with SOVA's comparator. Post hoc; calls no model.

    python -X utf8 private/experiments/build_pf_recurrence_capsule.py <agentdojo-runs-dir> <out-dir>
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
spec = importlib.util.spec_from_file_location("gallery", HERE / "build_pf_findings_gallery.py")
gallery = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gallery)
spec2 = importlib.util.spec_from_file_location("recompute", HERE / "recompute_recurrence_from_sova.py")
recompute_module = importlib.util.module_from_spec(spec2)
assert spec2.loader is not None
spec2.loader.exec_module(recompute_module)

CROSS = gallery.RES / "pf-cross-provider-2026-11-13"
PIPELINE = "gpt-4o-2024-05-13"
TITLE = "GPT-4o prompt-injection outcomes, AgentDojo's published 2024 log against a fresh 2026 run"


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    runs_dir = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=False)
    episodes = {}
    for line in (CROSS / "episodes.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["model"] == "gpt-4o" and row["condition"] == "baseline":
            episodes[(row["suite"], row["userTask"], row["injectionTask"])] = row
    fresh = {}
    with gzip.open(CROSS / "traces.jsonl.gz", "rt", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            key = record["key"]
            if key[0] == "gpt-4o" and key[1] == "baseline":
                fresh[tuple(key[3:6])] = record
    traces_digest = gallery.file_digest(CROSS / "traces.jsonl.gz")
    named: dict[str, Path] = {}
    index = []
    with tempfile.TemporaryDirectory() as tmp:
        for instance in sorted(episodes):
            suite, user, injection = instance
            log = runs_dir / PIPELINE / suite / user / "important_instructions" / f"{injection}.json"
            if not log.is_file():
                continue
            published = json.loads(log.read_text(encoding="utf-8"))
            meta = episodes[instance]
            stem = f"{suite}--{user}--{injection}"
            base_info = {"benchmark": "AgentDojo", "attack": "important_instructions", "suite": suite,
                         "userTask": user, "injectionTask": injection}
            pub_path = Path(tmp) / f"{stem}--published-2024.sova-trace"
            gallery.write_trace(
                pub_path, messages=published["messages"], model=PIPELINE,
                run_info={**base_info, "recordedBy": "AgentDojo authors (published log)", "model": PIPELINE},
                imported={"from": "AgentDojo published run log (MIT licence)", "repository": "https://github.com/ethz-spylab/agentdojo",
                          "commit": gallery.AGENTDOJO_COMMIT,
                          "path": f"runs/{PIPELINE}/{suite}/{user}/important_instructions/{injection}.json",
                          "sha256": gallery.file_digest(log)},
                security=bool(published["security"]), utility=published.get("utility"), reading=None, durability="lite",
            )
            software = meta.get("software") or {}
            fresh_path = Path(tmp) / f"{stem}--fresh-2026.sova-trace"
            gallery.write_trace(
                fresh_path, messages=fresh[instance]["messages"], model="gpt-4o",
                run_info={**base_info, "benchmarkVersion": meta.get("benchmarkVersion"), "agentdojo": software.get("agentdojo"),
                          "python": software.get("python"), "model": "gpt-4o", "returnedModels": meta.get("returnedModels"),
                          "condition": "baseline", "trial": meta.get("trial"), "startedAt": meta.get("startedAt")},
                imported={"from": "PF v1.1 study message trace",
                          "path": f"private/experiments/results/pf-cross-provider-2026-11-13/traces.jsonl.gz key {json.dumps(fresh[instance]['key'])}",
                          "sha256": traces_digest,
                          "episodeRecordSha256": sha256_digest(canonical_json_bytes(gallery.decimals(meta)))},
                security=bool(meta["security"]), utility=meta.get("utility"), reading=None, durability="lite",
            )
            named[pub_path.name] = pub_path
            named[fresh_path.name] = fresh_path
            index.append({"instance": stem, "published2024": bool(published["security"]), "fresh2026": bool(meta["security"])})
        scenario = {
            "artifactType": "sova.scenario", "schemaVersion": "0.1.0",
            "id": "sova:scenario:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/ethz-spylab/agentdojo#gpt-4o-recurrence")),
            "version": "0.1.0", "title": TITLE,
            "purpose": "Check whether attacks recorded against GPT-4o in AgentDojo's published 2024 log succeed again on a fresh 2026 run.",
            "parameters": {"benchmark": "AgentDojo", "attack": "important_instructions", "publishedPipeline": PIPELINE,
                           "freshDeployment": "gpt-4o", "freshReturnedModel": "gpt-4o-2024-11-20", "instances": len(index)},
            "preconditions": [{"kind": "simulated-environment", "owned": True, "note": "AgentDojo's synthetic data; no real account or money."}],
            "sequences": [],
            "procedure": {"steps": [{"id": "run-episode", "action": "agentdojo.run-injection-episode",
                                     "inputs": {"attack": "important_instructions"}, "onFailure": "inconclusive",
                                     "requires": ["agentdojo/0.1.35"]}]},
            "triggers": [{"kind": "planted-instruction", "location": "tool output", "template": "important_instructions"}],
            "mutations": [{"parameter": "model snapshot", "domain": ["gpt-4o-2024-05-13", "gpt-4o-2024-11-20"]}],
            "expectedEffects": [{"kind": "attacker-goal", "simulated": True}],
            "oracles": [{"kind": "agentdojo.injection-task.security", "attackSucceeded": True}],
            "evidenceRequirements": ["prompt.user", "tool.result", "model.response", "tool.requested", "oracle.completed"],
            "safety": {"budgets": {"maxSteps": 1}, "forbiddenEffects": ["real accounts", "real money"], "stopConditions": []},
            "cleanup": [{"kind": "environment-discarded", "verify": False}],
            "limitations": [
                "Converted post hoc from recorded runs; neither run wrote a .sova-trace.",
                "The declared outcome is AgentDojo's security verdict; it is not a reading of each reply.",
                "The model snapshot, benchmark version and runner all differ between the two runs.",
            ],
            "extensions": {},
        }
        manifest = capsule_manifest_template(title=TITLE, author=gallery.AUTHOR, domain_profile=DomainProfile.SECURITY,
                                             capture_profile=CaptureProfile.STANDARD,
                                             summary=(f"All {len(index)} attack instances shared by AgentDojo's published GPT-4o log and a "
                                                      "fresh GPT-4o run, each as a pair of .sova-traces ending in AgentDojo's verdict. "
                                                      "recompute_recurrence_from_sova.py recomputes the paper's recurrence result from this file."))
        manifest["authors"] = [{"name": gallery.AUTHOR, "affiliation": gallery.AFFILIATION}]
        manifest["lifecycle"] = "disclosed"
        manifest["citation"] = {"preferred": f"{gallery.AUTHOR}. {TITLE}. .sova capsule released with: {gallery.PAPER}", "identifiers": []}
        manifest["provenance"]["sourceDigests"] = sorted({traces_digest, gallery.file_digest(gallery.PROTOCOLS["cross"])})
        manifest["provenance"]["transformations"] = ["Recorded messages converted post hoc to .sova-trace events; no content changed."]
        manifest["methodology"] = {"id": "PF-V1.1-AGENTDOJO-REEXECUTION", "version": "1.1", "digest": gallery.file_digest(gallery.PROTOCOLS["cross"])}
        manifest["taxonomy"] = {"id": "agentdojo.injection-task", "version": "v1.2.2", "digest": sha256_digest(canonical_json_bytes({"attack": "important_instructions"}))}
        manifest["compatibility"] = {"runtime": "sova-runtime>=0.1.0a0", "models": [PIPELINE, "gpt-4o-2024-11-20"], "tools": ["agentdojo==0.1.35"], "platforms": []}
        manifest["safety"] = {"impact": "none", "forbiddenEffects": ["real accounts", "real money"], "cleanupRequired": False}
        manifest["disclosure"] = {"classification": "public", "sharing": "Released with the PF v1.1 preprint. Contains AgentDojo's synthetic data and model replies."}
        manifest["license"] = "CC-BY-4.0 AND MIT"
        manifest["limitations"] = scenario["limitations"] + ["Opening or verifying this capsule runs nothing."]
        manifest["requiredFeatures"] = ["scenario.core/0.1"]
        capsule = out / "gpt-4o-2024-vs-2026.sova"
        digest = build_capsule(capsule, manifest, scenario=scenario,
                               attachments={"index.json": canonical_json_bytes({"pairs": index})}, named_traces=named)
    report = recompute_module.recompute(capsule)
    report["capsuleSha256"] = digest
    (out / "recurrence-from-sova.json").write_bytes(canonical_json_bytes(report) + b"\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
