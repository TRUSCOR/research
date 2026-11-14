"""Deviation D5: run S6b task T10 as the frozen compare_pf_tasks_ext.py does, plus the prices that --max-usd needs.

The frozen call gave --max-usd 4 without --price-in/--price-out, which sova matrix refuses (exit 2).
This run adds --price-in 2.5 --price-out 10 (GPT-4o's Azure list prices, the higher of the two
models, so the cap is conservative) and changes nothing else. Output: s6b/matrix/ and s6b-t10.json.
"""
import json, os, subprocess, sys, time
from pathlib import Path
X = Path(__file__).resolve().parent
sys.path.insert(0, str(X))
from azure_foundry_client import _read_notes
R = X / "results" / "pf-confirmatory-2026-11-14"
SOVA_REPO = X.parents[1]
findings = sorted((X / "results" / "pf-findings-gallery-2026-11-13").glob("*.sova"))
endpoint, key = _read_notes(None)
env = dict(os.environ, SOVA_OPENAI_BASE_URL=endpoint, SOVA_OPENAI_API_KEY=key)
provider = ["--provider", "openai-compatible", "--base-url-env", "SOVA_OPENAI_BASE_URL", "--api-key-env", "SOVA_OPENAI_API_KEY"]
cmd = ["uv", "run", "--project", str(SOVA_REPO), "--with", "agentdojo==0.1.35", "sova", "matrix", *map(str, findings),
       "--baseline", "gpt-4o", "--candidate", "gpt-5.5", *provider, "--trials", "3", "--json", "--authorize",
       "--max-usd", "4", "--price-in", "2.5", "--price-out", "10", "--out", str(R / "s6b" / "matrix")]
start = time.monotonic()
res = subprocess.run(cmd, cwd=str(SOVA_REPO), env=env, capture_output=True, text=True, encoding="utf-8")
doc = json.loads(res.stdout) if res.stdout.strip().startswith("{") else None
out = {"exit": res.returncode, "seconds": round(time.monotonic() - start, 1), "summary": doc,
       "argsAdded": ["--price-in", "2.5", "--price-out", "10"], "stderrTail": res.stderr[-600:].replace(key, "<key>") if key else res.stderr[-600:]}
(R / "s6b-t10.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("exit", res.returncode, "seconds", out["seconds"], "upgrades", (doc or {}).get("upgrades"))
