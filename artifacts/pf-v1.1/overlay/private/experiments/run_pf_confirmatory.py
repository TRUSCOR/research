"""Runner for the PF confirmatory protocol (PF-confirmatory-protocol-2026-11-14.md).

It reuses the episode code of run_pf_fresh_agentdojo.py unchanged and adds only:
- the protocol's model registry (deployment, API, sampling, attack-text name, rate limit);
- pacing that keeps every deployment below 70% of its token and request limits, with a
  concurrency cap per deployment, so slow deployments never starve fast ones;
- retries of infrastructure errors only (rate limit, timeout, connection, server error):
  up to 12 per call and 3 attempts per episode, every failed attempt kept in the record;
- AgentDojo 0.1.35's JSON tool-output option made to write dates as ISO-8601 strings
  (unchanged, it fails with "datetime is not JSON serializable");
- the protocol's phases.

    python run_pf_confirmatory.py pilot   <outdir> --models a,b          # benign tasks, no injection
    python run_pf_confirmatory.py pass    <outdir> --models a,b --subset full|breadth
    python run_pf_confirmatory.py perturb <outdir> --plan <plan.json> [--conditions c1,c2]

Credentials are read at run time: the Azure endpoint and key through azure_foundry_client
(PF_AZURE_NOTES), the Anthropic key by the Anthropic SDK from ANTHROPIC_API_KEY. Neither is
written anywhere. Spending is estimated from token counts at the assumed prices below and
the run stops at the protocol's budget per provider.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import sys
import threading
import time
from collections import Counter, defaultdict, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from functools import partial
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_pf_fresh_agentdojo as base  # noqa: E402

PROTOCOL = Path(__file__).resolve().parents[1] / "research" / "papers" / "PF-confirmatory-protocol-2026-11-14.md"
RESULTS = Path(__file__).resolve().parent / "results" / "pf-confirmatory-2026-11-14"
SEED = 20261114
BUDGET = {"azure": 500.0, "anthropic": 250.0}
PACE = 0.70  # fraction of each deployment's limit that the runner may use

# name: provider, api, temperature (None = no sampling parameter), attack-text name,
# tokens and requests per minute (from the deployment's rate-limit headers or listed
# capacity), episodes in flight, assumed USD per million tokens (input, output).
MODELS: dict[str, dict[str, Any]] = {
    # primary candidates (deployments of at least 300,000 tokens per minute)
    "gpt-4o": dict(provider="azure", api="chat", temperature=0.0, display="GPT-4", tpm=7_000_000, rpm=42_000, conc=24, price=(2.5, 10.0)),
    "DeepSeek-V4-Pro-2": dict(provider="azure", api="chat", temperature=0.0, display="DeepSeek", tpm=475_000, rpm=475, conc=16, price=(1.5, 6.0)),
    "grok-4-20-non-reasoning": dict(provider="azure", api="chat", temperature=0.0, display="Grok", tpm=300_000, rpm=300, conc=12, price=(2.0, 10.0)),
    "grok-4-1-fast-non-reasoning": dict(provider="azure", api="chat", temperature=0.0, display="Grok", tpm=300_000, rpm=300, conc=12, price=(0.5, 2.0)),
    # breadth models
    "grok-4.7": dict(provider="azure", api="chat", temperature=None, display="Grok", tpm=315_000, rpm=315, conc=12, price=(3.0, 15.0)),
    "gpt-5.5": dict(provider="azure", api="chat", temperature=None, display="GPT", tpm=150_000, rpm=150, conc=8, price=(1.25, 10.0)),
    "gpt-5.4-mini": dict(provider="azure", api="chat", temperature=None, display="GPT", tpm=100_000, rpm=100, conc=6, price=(0.25, 2.0)),
    "gpt-5.4-nano": dict(provider="azure", api="chat", temperature=None, display="GPT", tpm=100_000, rpm=100, conc=6, price=(0.05, 0.4)),
    "gpt-6.1-sol": dict(provider="azure", api="responses", temperature=None, display="GPT", tpm=300_000, rpm=300, conc=12, price=(5.0, 40.0)),
    "gpt-6.1-terra": dict(provider="azure", api="responses", temperature=None, display="GPT", tpm=500_000, rpm=500, conc=12, price=(5.0, 40.0)),
    "gpt-6-luna": dict(provider="azure", api="responses", temperature=None, display="GPT", tpm=200_000, rpm=200, conc=8, price=(5.0, 40.0)),
    "gpt-6-astra": dict(provider="azure", api="responses", temperature=None, display="GPT", tpm=150_000, rpm=150, conc=6, price=(5.0, 40.0)),
    "Kimi-K3.1-Pro": dict(provider="azure", api="chat", temperature=0.0, display="Kimi", tpm=50_000, rpm=50, conc=3, price=(1.0, 4.0)),
    "Llama-4-Maverick-17B-128E-Instruct-FP8": dict(provider="azure", api="chat", temperature=0.0, display="Llama", tpm=50_000, rpm=50, conc=3, price=(0.35, 1.5)),
    "Mistral-Large-3": dict(provider="azure", api="chat", temperature=0.0, display="Mistral", tpm=50_000, rpm=50, conc=3, price=(2.0, 6.0), plain_messages=True),
    "mistral-medium-3-5": dict(provider="azure", api="chat", temperature=0.0, display="Mistral", tpm=50_000, rpm=50, conc=3, price=(0.4, 2.0), plain_messages=True),
    "cohere-command-a": dict(provider="azure", api="chat", temperature=0.0, display="Command A", tpm=50_000, rpm=50, conc=3, price=(2.5, 10.0), plain_messages=True),
    # Anthropic (no sampling or thinking parameter: the 5.x models run their default adaptive thinking)
    "claude-opus-5-5": dict(provider="anthropic", display="Claude", tpm=2_000_000, rpm=2_000, conc=8, price=(4.0, 20.0)),
    "claude-sonnet-5-5": dict(provider="anthropic", display="Claude", tpm=2_000_000, rpm=2_000, conc=8, price=(2.0, 10.0)),
    "claude-fable-5-2": dict(provider="anthropic", display="Claude", tpm=2_000_000, rpm=2_000, conc=8, price=(8.0, 40.0)),
    "claude-haiku-5-5": dict(provider="anthropic", display="Claude", tpm=2_000_000, rpm=2_000, conc=8, price=(0.10, 0.50)),
    "claude-haiku-4-5": dict(provider="anthropic", display="Claude", tpm=2_000_000, rpm=2_000, conc=8, price=(1.0, 5.0)),
    "claude-sonnet-4-5-20250929": dict(provider="anthropic", display="Claude", tpm=2_000_000, rpm=2_000, conc=8, price=(3.0, 15.0)),
    "claude-opus-4-5-20251101": dict(provider="anthropic", display="Claude", tpm=2_000_000, rpm=2_000, conc=8, price=(5.0, 25.0)),
}
PRIMARY_CANDIDATES = ["gpt-4o", "DeepSeek-V4-Pro-2", "grok-4-20-non-reasoning", "grok-4-1-fast-non-reasoning"]
TRANSIENT = ("RateLimitError", "APITimeoutError", "APIConnectionError", "InternalServerError", "ServiceUnavailableError",
             "OverloadedError", "APIStatusError: 5", "Timeout", "ConnectError", "ReadTimeout")

for _name, _m in MODELS.items():
    base.PRICES[_name] = _m["price"]
    if _m["provider"] == "azure":
        base.AZURE_MODELS[_name] = {"api": _m["api"], "temperature": _m["temperature"], "display": _m["display"]}
base.CONDITIONS["pilot-benign"] = {"defense": None, "tool_output_format": None, "system_message": None}


# ------------------------------------------------------------------ JSON tool output with dates
def _dumps_dates(obj: Any) -> str:
    return json.dumps(obj, default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o))


def _fix_json(element: Any) -> None:
    from agentdojo.agent_pipeline.tool_execution import ToolsExecutor, tool_result_to_str

    if isinstance(element, ToolsExecutor):
        element.output_formatter = partial(tool_result_to_str, dump_fn=_dumps_dates)
    for child in getattr(element, "elements", None) or []:
        _fix_json(child)


_original_build = base.build_pipeline


def _build_pipeline(ad, client, model, condition, usage):
    pipeline = _original_build(ad, client, model, condition, usage)
    if base.CONDITIONS[condition]["tool_output_format"] == "json":
        _fix_json(pipeline)
    return pipeline


base.build_pipeline = _build_pipeline


# ------------------------------------------------------------------ pacing and retries
class Pacer:
    """Sliding 60-second window of tokens and requests per deployment."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.window: dict[str, deque] = defaultdict(deque)

    def acquire(self, model: str, estimate: int) -> None:
        spec = MODELS[model]
        tpm, rpm = spec["tpm"] * PACE, spec["rpm"] * PACE
        while True:
            with self.lock:
                now = time.time()
                w = self.window[model]
                while w and now - w[0][0] > 60:
                    w.popleft()
                tokens = sum(t for _, t in w)
                if (tokens + estimate <= tpm and len(w) + 1 <= rpm) or not w:
                    w.append((now, estimate))
                    return
            time.sleep(0.5)

    def settle(self, model: str, estimate: int, actual: int) -> None:
        with self.lock:
            w = self.window[model]
            for i in range(len(w) - 1, -1, -1):
                if w[i][1] == estimate:
                    w[i] = (w[i][0], max(actual, 1))
                    break


PACER = Pacer()


def _estimate(kwargs: dict) -> int:
    size = len(json.dumps(kwargs.get("messages") or kwargs.get("input") or "", default=str))
    size += len(json.dumps(kwargs.get("tools") or [], default=str)) + len(json.dumps(kwargs.get("system") or "", default=str))
    return int(size / 3.2) + 1200


def _transient(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}"
    status = getattr(exc, "status_code", None)
    return any(t in text for t in TRANSIENT) or (isinstance(status, int) and (status == 429 or status >= 500))


def _paced(model: str, fn, kwargs: dict, usage_of) -> Any:
    estimate = _estimate(kwargs)
    for attempt in range(12):
        PACER.acquire(model, estimate)
        try:
            response = fn(**kwargs)
        except Exception as exc:  # noqa: BLE001
            PACER.settle(model, estimate, estimate)
            if not _transient(exc) or attempt == 11:
                raise
            time.sleep(min(90.0, 4.0 * 2 ** attempt) + random.random() * 3)
            continue
        PACER.settle(model, estimate, usage_of(response))
        return response
    raise RuntimeError("unreachable")


def _plain_messages(messages: list[dict]) -> list[dict]:
    """Same content, standard shape: the 'developer' role sent as 'system', and text parts joined
    into one string. Some deployments (Mistral, Cohere) reject the newer shape with HTTP 422."""
    out = []
    for m in messages:
        m = dict(m)
        if m.get("role") == "developer":
            m["role"] = "system"
        content = m.get("content")
        if isinstance(content, list):
            m["content"] = "".join(str(p.get("text", "")) for p in content if isinstance(p, dict))
        elif content is None and m.get("role") == "assistant":
            m["content"] = ""
        out.append(m)
    return out


class _Create:
    def __init__(self, fn, usage_of) -> None:
        self.fn, self.usage_of = fn, usage_of

    def create(self, **kwargs):
        if MODELS.get(kwargs.get("model"), {}).get("plain_messages") and "messages" in kwargs:
            kwargs = {**kwargs, "messages": _plain_messages(kwargs["messages"])}
        return _paced(kwargs["model"], self.fn, kwargs, self.usage_of)


class PacedOpenAI:
    def __init__(self, client) -> None:
        def chat_usage(r):
            return (r.usage.prompt_tokens + r.usage.completion_tokens) if getattr(r, "usage", None) else 0

        def resp_usage(r):
            return (r.usage.input_tokens + r.usage.output_tokens) if getattr(r, "usage", None) else 0

        self.chat = type("Chat", (), {})()
        self.chat.completions = _Create(client.chat.completions.create, chat_usage)
        self.responses = _Create(client.responses.create, resp_usage)


class PacedAnthropic:
    def __init__(self, client) -> None:
        def usage(r):
            u = r.usage
            return (u.input_tokens or 0) + (u.output_tokens or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0)

        self.messages = _Create(client.messages.create, usage)


# ------------------------------------------------------------------ instances
def breadth_subset(all_instances: list[tuple]) -> list[tuple]:
    """Every hotel-goal instance, plus four user tasks per other attacker goal (seeded)."""
    rng = random.Random(SEED)
    by_goal: dict[tuple, list] = defaultdict(list)
    for k in all_instances:
        by_goal[(k[0], k[2])].append(k)
    chosen = []
    for goal in sorted(by_goal):
        keys = sorted(by_goal[goal])
        chosen += keys if goal == ("travel", "injection_task_6") else sorted(rng.sample(keys, min(4, len(keys))))
    return sorted(chosen)


def pilot_instances(all_instances: list[tuple]) -> list[tuple]:
    first = {}
    for k in sorted(all_instances):
        first.setdefault(k[0], k)
    return [first[s] for s in sorted(first)][:3]


# ------------------------------------------------------------------ execution
def spent(provider: str) -> float:
    total = 0.0
    for path in RESULTS.rglob("episodes.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if MODELS.get(r["model"], {}).get("provider") == provider:
                total += r.get("costUsd") or 0.0
    return total


def run_one(ad, client, job, protocol_sha, pilot):
    model, condition, trial, key = job
    attempts = []
    for _ in range(3):
        record, messages = base.run_episode(ad, client, model, condition, trial, key, protocol_sha)
        if record["error"] is None or not any(t in record["error"] for t in TRANSIENT):
            break
        attempts.append(record["error"])
    record["failedAttempts"] = attempts
    if pilot:
        record.update({"security": None, "evidence": "not-applicable"})
    return record, messages


def execute(jobs: list[tuple], outdir: Path, pilot: bool = False) -> None:
    import importlib.metadata as metadata
    import platform

    providers = {MODELS[j[0]]["provider"] for j in jobs}
    assert len(providers) == 1, "one provider per run"
    provider = providers.pop()
    ad = base.agentdojo()
    if pilot:
        base.injections_for = lambda ad_, client_, key_, model_="": {}
    for name, m in MODELS.items():
        ad["models"].MODEL_NAMES[name] = m["display"]
    for name in base.PRICES:
        if name not in base.AZURE_MODELS and name not in MODELS:
            ad["models"].MODEL_NAMES[name] = "Claude"
    if provider == "azure":
        import openai

        from azure_foundry_client import make_client

        client = PacedOpenAI(make_client())
        base.SOFTWARE.update({"agentdojo": metadata.version("agentdojo"), "openaiSdk": openai.__version__,
                              "python": platform.python_version(), "provider": "Azure AI Foundry, OpenAI-compatible v1 endpoint"})
    else:
        import os

        import anthropic

        if not os.environ.get("ANTHROPIC_API_KEY") and sys.platform == "win32":
            import winreg  # the key set as a Windows user variable after this shell started

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as k:
                os.environ["ANTHROPIC_API_KEY"] = winreg.QueryValueEx(k, "ANTHROPIC_API_KEY")[0]
        client = PacedAnthropic(anthropic.Anthropic(max_retries=2, timeout=300.0))
        base.SOFTWARE.update({"agentdojo": metadata.version("agentdojo"), "anthropicSdk": anthropic.__version__,
                              "python": platform.python_version()})
    protocol_sha = None if pilot else base.sha(PROTOCOL.read_bytes())
    outdir.mkdir(parents=True, exist_ok=True)
    existing = base.done_keys(outdir)
    pending = [j for j in jobs if (j[0], j[1], j[2], *j[3]) not in existing]
    queues: dict[str, deque] = defaultdict(deque)
    for j in pending:
        queues[j[0]].append(j)
    running: Counter = Counter()
    budget_used = spent(provider)
    print(f"{len(jobs)} jobs, {len(pending)} pending across {len(queues)} models; {provider} spent so far ${budget_used:.2f}", flush=True)
    episodes = open(outdir / "episodes.jsonl", "a", encoding="utf-8", newline="\n")
    trace_path = outdir / "traces.jsonl.gz"
    done_count, stopped = 0, False
    workers = sum(MODELS[m]["conc"] for m in queues) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures: dict = {}
        while True:
            if not stopped:
                for model, q in queues.items():
                    while q and running[model] < MODELS[model]["conc"]:
                        if budget_used + base._spent >= BUDGET[provider]:
                            stopped = True
                            print(f"BUDGET STOP for {provider} at ${budget_used + base._spent:.2f}", flush=True)
                            break
                        job = q.popleft()
                        running[model] += 1
                        futures[pool.submit(run_one, ad, client, job, protocol_sha, pilot)] = job
                    if stopped:
                        break
            if not futures:
                break
            finished, _ = wait(list(futures), return_when=FIRST_COMPLETED)
            for f in finished:
                job = futures.pop(f)
                running[job[0]] -= 1
                record, messages = f.result()
                with base._lock:
                    episodes.write(json.dumps(record, sort_keys=True) + "\n")
                    episodes.flush()
                    with gzip.open(trace_path, "at", encoding="utf-8") as traces:
                        traces.write(json.dumps({"key": [record["model"], record["condition"], record["trial"], record["suite"],
                                                         record["userTask"], record["injectionTask"]], "messages": messages},
                                                default=base._jsonable) + "\n")
                done_count += 1
                if done_count % 25 == 0 or done_count == len(pending):
                    left = {m: len(q) + running[m] for m, q in queues.items() if len(q) + running[m]}
                    print(f"{time.strftime('%H:%M:%S')} {done_count}/{len(pending)} done, {provider} ${budget_used + base._spent:.2f}; left {left}", flush=True)
    episodes.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["pilot", "pass", "perturb"])
    parser.add_argument("outdir")
    parser.add_argument("--models")
    parser.add_argument("--subset", choices=["full", "breadth"], default="full")
    parser.add_argument("--plan")
    parser.add_argument("--conditions")
    parser.add_argument("--trials", default="101-103", help="trial numbers, as 'a-b' or 'a,b,c'")
    parser.add_argument("--instances-file", help="JSON list of [suite, user task, injection task] for 'pass'")
    parser.add_argument("--trial", type=int, default=1, help="trial number for 'pass'")
    args = parser.parse_args()
    ad = base.agentdojo()
    all_instances = base.instances(ad)
    outdir = Path(args.outdir)
    if args.phase == "pilot":
        keys = pilot_instances(all_instances)
        jobs = [(m, "pilot-benign", 0, k) for m in args.models.split(",") for k in keys]
        execute(jobs, outdir, pilot=True)
        return 0
    if args.phase == "pass":
        if args.instances_file:
            keys = [tuple(k) for k in json.loads(Path(args.instances_file).read_text(encoding="utf-8"))]
        else:
            keys = all_instances if args.subset == "full" else breadth_subset(all_instances)
        jobs = [(m, "baseline", args.trial, k) for k in keys for m in args.models.split(",")]
        execute(jobs, outdir)
        return 0
    if "-" in args.trials:
        lo, hi = (int(x) for x in args.trials.split("-"))
        trials = list(range(lo, hi + 1))
    else:
        trials = [int(x) for x in args.trials.split(",")]
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    conditions = args.conditions.split(",") if args.conditions else base.NON_MATERIAL + base.MATERIAL
    jobs = []
    for entry in plan["primaries"]:
        for trial in trials:
            for cond in conditions:
                model = entry["alternative"] if cond == "M1-other-model" else entry["model"]
                jobs += [(model, cond, trial, tuple(k)) for k in entry["findings"]]
    execute(jobs, outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
