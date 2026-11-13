"""Turn your own AgentDojo run log into a .sova-trace and a .sova capsule.

AgentDojo writes one JSON log per episode (suite, user task, injection task, the full
message list, and its utility and security verdicts). This converts such a log into a
tamper-evident .sova-trace, ending in AgentDojo's verdict as the declared outcome, and
packages it as a .sova capsule that anyone can verify offline. It calls no model.

    python -X utf8 agentdojo_to_sova.py <agentdojo-log.json> <out-dir> [--author "Your Name"]

Then, with SOVA OSS installed:

    sova verify <out-dir>/<name>.sova
    sova playback <out-dir>/<name>.sova-trace
    sova compare <your>.sova-trace <someone-elses>.sova-trace --kind oracle.completed
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import uuid
from pathlib import Path

from sova.capsule.model import CaptureProfile, DomainProfile, build_capsule, capsule_manifest_template
from sova.formats import canonical_json_bytes, sha256_digest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("gallery", HERE / "build_pf_findings_gallery.py")
gallery = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(gallery)


def convert(log_path: Path, out: Path, author: str) -> tuple[Path, Path]:
    log = json.loads(log_path.read_text(encoding="utf-8"))
    suite, user, injection = log["suite_name"], log["user_task_id"], log.get("injection_task_id")
    model = log.get("pipeline_name") or "unknown-pipeline"
    attack = log.get("attack_type") or "none"
    stem = f"{model}--{suite}--{user}--{injection or 'no-injection'}"
    out.mkdir(parents=True, exist_ok=True)
    trace = out / f"{stem}.sova-trace"
    security = log.get("security")
    gallery.write_trace(
        trace, messages=log["messages"], model=model,
        run_info={"benchmark": "AgentDojo", "attack": attack, "suite": suite, "userTask": user,
                  "injectionTask": injection, "model": model},
        imported={"from": "AgentDojo run log", "path": log_path.name, "sha256": gallery.file_digest(log_path),
                  "note": "Converted from the run's JSON log; recorded by whoever ran the benchmark."},
        security=bool(security), utility=log.get("utility"), reading=None,
    )
    title = f"AgentDojo {suite}/{user}/{injection or 'no injection'} on {model}"
    scenario = {
        "artifactType": "sova.scenario", "schemaVersion": "0.1.0",
        "id": "sova:scenario:" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://github.com/ethz-spylab/agentdojo#{suite}/{user}/{injection}")),
        "version": "0.1.0", "title": title,
        "purpose": "Record whether a planted instruction in tool output made the agent carry out the attacker's goal.",
        "parameters": {"benchmark": "AgentDojo", "attack": attack, "suite": suite, "userTask": user, "injectionTask": injection},
        "preconditions": [{"kind": "simulated-environment", "owned": True}],
        "sequences": [],
        "procedure": {"steps": [{"id": "run-episode", "action": "agentdojo.run-injection-episode",
                                 "inputs": {"suite": suite, "userTask": user, "injectionTask": injection, "attack": attack},
                                 "onFailure": "inconclusive", "requires": ["agentdojo"]}]},
        "triggers": [{"kind": "planted-instruction", "location": "tool output", "template": attack}],
        "mutations": [],
        "expectedEffects": [{"kind": "attacker-goal", "injectionTask": injection, "simulated": True}],
        "oracles": [{"kind": "agentdojo.injection-task.security", "suite": suite, "injectionTask": injection, "attackSucceeded": True}],
        "evidenceRequirements": ["prompt.user", "tool.result", "model.response", "tool.requested", "oracle.completed"],
        "safety": {"budgets": {"maxSteps": 1}, "forbiddenEffects": ["real accounts", "real money"], "stopConditions": []},
        "cleanup": [{"kind": "environment-discarded", "verify": False}],
        "limitations": ["Converted from an AgentDojo log after the run.",
                        "The declared outcome is AgentDojo's security verdict, which may not match a reading of the reply."],
        "extensions": {},
    }
    manifest = capsule_manifest_template(title=title, author=author, domain_profile=DomainProfile.SECURITY,
                                         capture_profile=CaptureProfile.STANDARD,
                                         summary=f"AgentDojo scored this run as {'attacked' if security else 'not attacked'}.")
    manifest["lifecycle"] = "draft"
    manifest["provenance"]["sourceDigests"] = [gallery.file_digest(log_path)]
    manifest["provenance"]["transformations"] = ["AgentDojo JSON log converted to .sova-trace events by agentdojo_to_sova.py."]
    manifest["taxonomy"] = {"id": "agentdojo.injection-task", "version": "unknown",
                            "digest": sha256_digest(canonical_json_bytes({"suite": suite, "injectionTask": injection}))}
    manifest["compatibility"] = {"runtime": "sova-runtime>=0.1.0a0", "models": [model], "tools": ["agentdojo"], "platforms": []}
    manifest["safety"] = {"impact": "none", "forbiddenEffects": ["real accounts", "real money"], "cleanupRequired": False}
    manifest["limitations"] = scenario["limitations"] + ["Opening or verifying this capsule runs nothing."]
    manifest["requiredFeatures"] = ["scenario.core/0.1"]
    capsule = out / f"{stem}.sova"
    build_capsule(capsule, manifest, scenario=scenario, named_traces={trace.name: trace})
    return capsule, trace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--author", default="AgentDojo user")
    args = parser.parse_args()
    capsule, trace = convert(args.log.resolve(), args.out.resolve(), args.author)
    print(json.dumps({"capsule": str(capsule), "trace": str(trace)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
