"""Run every remaining stage of the PF confirmatory protocol in ONE resumable process.

Stages (each resumes from what is already on disk; a finished stage is recorded in
driver-state.json and skipped on restart):
  1  S2 Azure scoreboard (breadth subset + hotel trials 2, 3), Grok full passes, and the
     DeepSeek / GPT-4o S3-S4 runs, concurrently in threads of this one process.
  2  Selection (analyze_pf_v2.select); check DeepSeek / GPT-4o findings equal plan-run1;
     then the xAI primary's S3-S4 runs, GPT-4o's M1 run, and the xAI -> grok-4.7 upgrade check.
  3  S7 blind readers (gpt-5.5 and grok-4.7).
  4  Frozen analyses: scoreboard, reliability, prediction, upgrade, reader agreement.

    python drive_pf_remaining.py
"""

from __future__ import annotations

import json
import sys
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_pf_v2 as an  # noqa: E402
import read_pf_blind as rb  # noqa: E402
import run_pf_confirmatory as rc  # noqa: E402
import run_pf_fresh_agentdojo as base  # noqa: E402

R = rc.RESULTS
STATE = R / "driver-state.json"
# Deviation D2 (2026-11-14): grok-4-20-non-reasoning averages about 99,000 tokens per episode,
# so at 70% of its rate limit it runs about two episodes a minute. The pace is raised to 92%
# for all deployments, its full pass is stopped once the xAI selection is decided, and the
# xAI primary runs a reduced design (20 findings, N1 x5, other conditions x2).
rc.PACE = 0.92
XAI_FINDINGS = 20
CROSS = HERE / "results" / "pf-cross-provider-2026-11-13"
AZ = ["gpt-4o", "DeepSeek-V4-Pro-2", "grok-4-20-non-reasoning", "grok-4-1-fast-non-reasoning", "grok-4.7", "gpt-5.5",
      "gpt-5.4-mini", "gpt-5.4-nano", "gpt-6.1-sol", "gpt-6.1-terra", "gpt-6-luna", "gpt-6-astra", "Kimi-K3.1-Pro",
      "Llama-4-Maverick-17B-128E-Instruct-FP8", "Mistral-Large-3", "mistral-medium-3-5", "cohere-command-a"]
GROK = ["grok-4-20-non-reasoning", "grok-4-1-fast-non-reasoning"]
FOUR = ["N2-json-tool-output", "N3-paraphrased-system", "M2-repeat-user-prompt", "M3-spotlighting"]


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} DRIVER {msg}", flush=True)


def state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.is_file() else {"done": []}


def mark(name: str) -> None:
    s = state()
    if name not in s["done"]:
        s["done"].append(name)
    STATE.write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8")
    log(f"stage done: {name}")


def perturb_jobs(plan: dict, conditions: list[str], trials) -> list[tuple]:
    jobs = []
    for entry in plan["primaries"]:
        for trial in trials:
            for cond in conditions:
                model = entry["alternative"] if cond == "M1-other-model" else entry["model"]
                jobs += [(model, cond, trial, tuple(k)) for k in entry["findings"]]
    return jobs


def run_parallel(stages: list[tuple[str, list[tuple], Path]]) -> None:
    errors = []

    def go(name, jobs, out):
        try:
            log(f"start {name}: {len(jobs)} jobs -> {out.name}")
            rc.execute(jobs, out)
            log(f"finished {name}")
        except Exception:  # noqa: BLE001
            errors.append(name)
            log(f"ERROR in {name}:\n{traceback.format_exc()}")

    threads = [threading.Thread(target=go, args=s, daemon=False) for s in stages if s[1]]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise SystemExit(f"stages failed: {errors}")


def stage1(ad, all_instances) -> None:
    sub = rc.breadth_subset(all_instances)
    hotel = [tuple(k) for k in json.loads((R / "hotel-instances.json").read_text(encoding="utf-8"))]
    s2 = [(m, "baseline", 1, k) for k in sub for m in AZ] + [(m, "baseline", t, k) for t in (2, 3) for k in hotel for m in AZ]
    grok = [(m, "baseline", 1, k) for k in all_instances for m in GROK]
    plan1 = json.loads((R / "plan-run1.json").read_text(encoding="utf-8"))
    ds_only = {"primaries": [e for e in plan1["primaries"] if e["model"] == "DeepSeek-V4-Pro-2"]}
    s34 = (perturb_jobs(plan1, ["N1-rerun"], range(101, 111)) + perturb_jobs(plan1, FOUR, range(101, 104))
           + perturb_jobs(ds_only, ["M1-other-model"], range(101, 104)))
    del grok  # D2: the Grok full pass stops here; the xAI selection is already decided
    xai_jobs, g4_m1, s5 = stage2_jobs()
    run_parallel([("s2", s2, R / "s2"), ("s34", s34 + xai_jobs + g4_m1, R / "s34"), ("s5-xai", s5, R / "s5")])


def stage2_jobs() -> tuple[list[tuple], list[tuple], list[tuple]]:
    plan_path = R / "plan.json"
    if not plan_path.is_file():
        an.select(plan_path, [CROSS, R / "s2-grok-full"])
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        for e in plan["primaries"]:
            if e["model"] not in ("DeepSeek-V4-Pro-2", "gpt-4o"):
                half = XAI_FINDINGS // 2
                e["calibration"], e["test"] = e["calibration"][:half], e["test"][:half]
                e["findings"] = sorted(e["calibration"] + e["test"])
                e["deviation"] = ("D2: reduced to the first 10 of each locked half; N1 trials 101-105, "
                                  "other conditions 101-102; eligibility from the 659 of 949 full-pass runs completed")
        plan_path.write_text(json.dumps(plan, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    run1 = {e["model"]: e for e in json.loads((R / "plan-run1.json").read_text(encoding="utf-8"))["primaries"]}
    for e in plan["primaries"]:
        if e["model"] in run1:
            same = e["findings"] == run1[e["model"]]["findings"] and e["calibration"] == run1[e["model"]]["calibration"]
            log(f"deviation D1 check for {e['model']}: findings identical = {same}")
            if not same:
                raise SystemExit("D1 check failed: findings differ from the runs already made")
    xai = [e for e in plan["primaries"] if e["model"] not in ("DeepSeek-V4-Pro-2", "gpt-4o")]
    g4 = [e for e in plan["primaries"] if e["model"] == "gpt-4o"]
    jobs: list[tuple] = []
    if xai:
        x = {"primaries": xai}
        jobs += perturb_jobs(x, ["N1-rerun"], range(101, 106)) + perturb_jobs(x, FOUR + ["M1-other-model"], range(101, 103))
    g4_m1 = perturb_jobs({"primaries": g4}, ["M1-other-model"], range(101, 104)) if g4 else []
    s5 = [("grok-4.7", "N1-rerun", t, tuple(k)) for t in range(101, 104) for k in xai[0]["findings"]] if xai else []
    log(f"xAI primary: {xai[0]['model'] if xai else 'none'} ({len(xai[0]['findings']) if xai else 0} findings); "
        f"gpt-4o alternative: {g4[0]['alternative'] if g4 else '-'}; jobs xai={len(jobs)} g4m1={len(g4_m1)} s5={len(s5)}")
    return jobs, g4_m1, s5


def stage3() -> None:
    items = R / "readers-items.json"
    if not items.is_file():
        published = Path(r"C:\Users\HP\AppData\Local\Temp\claude\d14c60c273c43e16\bba749ec-d310-4413-8b94-c4aa57af8151\scratchpad\agentdojo-runs\repo\runs")
        rb.sample(items, published, [R / "s2", R / "s2-anthropic", R / "s34"], [HERE / "results" / "pf-fresh-reexecution-2026-11-12"])
    errors = []

    def go(reader):
        try:
            rb.read(items, R / f"readers-{reader}.jsonl", reader)
        except Exception:  # noqa: BLE001
            errors.append(reader)
            log(f"ERROR reader {reader}:\n{traceback.format_exc()}")

    threads = [threading.Thread(target=go, args=(r,)) for r in ("gpt-5.5", "grok-4.7")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise SystemExit(f"readers failed: {errors}")


def stage4() -> None:
    plan = R / "plan.json"
    an.scoreboard(R / "scoreboard.json", [R / "s2", R / "s2-anthropic"])
    an.reliability(plan, R / "s34", R / "reliability.json")
    an.prediction(plan, R / "s34", R / "prediction.json")
    p = json.loads(plan.read_text(encoding="utf-8"))
    by = {e["model"]: e for e in p["primaries"]}
    pairs = [{"baseline": "gpt-4o", "candidate": "gpt-5.5", "findings": by["gpt-4o"]["findings"]}]
    xai = [m for m in by if m not in ("DeepSeek-V4-Pro-2", "gpt-4o")]
    if xai:
        pairs.append({"baseline": xai[0], "candidate": "grok-4.7", "findings": by[xai[0]]["findings"]})
    sonnet = json.loads((R / "plan-s5-claude.json").read_text(encoding="utf-8"))["primaries"][0]["findings"]
    pairs.append({"baseline": "claude-sonnet-4-5-20250929", "candidate": "claude-sonnet-5-5", "findings": sonnet})
    (R / "upgrade-pairs.json").write_text(json.dumps(pairs, indent=1) + "\n", encoding="utf-8")
    an.upgrade(R / "upgrade-pairs.json", R / "upgrade.json", [R / "s34", R / "s5", R / "s5-anthropic"])
    rb.agree(R / "readers-items.json", [R / "readers-gpt-5.5.jsonl", R / "readers-grok-4.7.jsonl"], R / "readers-agreement.json")


def main() -> int:
    ad = base.agentdojo()
    all_instances = base.instances(ad)
    for name, fn in (("stage1+2", lambda: stage1(ad, all_instances)), ("stage3", stage3), ("stage4", stage4)):
        if name in state()["done"]:
            log(f"skip {name} (done)")
            continue
        log(f"begin {name}")
        fn()
        mark(name)
    log("ALL STAGES DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
