"""Reported values of the cross-provider study (paper section 6.2), computed from the retained
result files. Used by the claim validator; every value is checked against the manuscript text."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PAPERS = ROOT / "private" / "research" / "papers"
RESULTS = ROOT / "private" / "experiments" / "results"
CONDS = ["N1-rerun", "N2-json-tool-output", "N3-paraphrased-system", "M1-other-model", "M2-repeat-user-prompt", "M3-spotlighting"]


def _load(name: str):
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pct(x: float, digits: int = 1) -> str:
    text = f"{100 * x:.{digits}f}"
    if digits and text.endswith("." + "0" * digits) and x in (0.0, 1.0):
        text = text.split(".")[0]
    return text + "%"


def interval(ci) -> str:
    lo, hi = (pct(v) for v in ci)
    return f"{lo[:-1]}-{hi}"


def compute() -> dict[str, object]:
    protocol = PAPERS / "PF-cross-provider-protocol-2026-11-13.md"
    addendum = PAPERS / "PF-cross-provider-predictiveness-addendum-2026-11-13.md"
    cross = _load("pf-cross-provider-2026-11-13.json")
    assert cross["protocolSha256"] == _sha(protocol), "cross-provider protocol changed after episodes"
    assert cross["protocolSha256"] in (PAPERS / "PF-cross-provider-protocol-2026-11-13.sha256").read_text(encoding="utf-8")
    episodes = [json.loads(line) for line in (RESULTS / "pf-cross-provider-2026-11-13" / "episodes.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(episodes) == cross["episodes"] == cross["tracesRetained"]
    m = cross["models"]
    g4, g6, ds = m["gpt-4o"], m["gpt-6.1-sol"], m["DeepSeek-V4-Pro-2"]
    reading = _load("pf-cross-provider-reading-2026-11-13.json")
    labels = Counter(reading["labels"].values())
    assert set(labels) <= {"followed", "followed-endorsed", "followed-rule-false-warning"}, "a read reply was not an attack"
    rec = cross["publishedGpt4oRecurrence"]
    p, s = rec["primary"], rec["secondaryUnchangedText"]
    hotel_pub = rec["byGoal"]["travel/injection_task_6"]
    v: dict[str, object] = {
        "crossEpisodes": f"{len(episodes):,}", "crossCost": f"{cross['costUsdEstimate']:.2f}",
        "g4Returned": ",".join(g4["returnedModels"]), "g4Conclusive": f"{g4['conclusive']:,}", "g4Scored": str(g4["scoredSuccesses"]),
        "g4Rate": pct(g4["scoredRateOverConclusive"]), "g4Goals": str(len(g4["goalsWithScoredSuccesses"])),
        "g4Hotel": str(g4["hotelGoal"]["scored"]), "g4RuleWarnings": str(g4["ruleClasses"].get("warning", 0)),
        "g4Utility": pct(g4["utilityRateOverConclusive"]),
        "dsConclusive": str(ds["conclusive"]), "dsScored": str(ds["scoredSuccesses"]), "dsRate": pct(ds["scoredRateOverConclusive"]),
        "dsGoals": str(len(ds["goalsWithScoredSuccesses"])), "dsHotel": str(ds["hotelGoal"]["scored"]),
        "dsRuleWarnings": str(ds["ruleClasses"].get("warning", 0)), "dsUtility": pct(ds["utilityRateOverConclusive"]),
        "dsInconclusive": str(ds["episodes"] - ds["conclusive"]),
        "dsRateLimit": str(ds["inconclusiveByKind"].get("rate limit", 0)),
        "dsRejected": str(ds["inconclusiveByKind"].get("provider rejected request (other)", 0)),
        "g6Scored": str(g6["scoredSuccesses"]), "g6Conclusive": f"{g6['conclusive']:,}", "g6Utility": pct(g6["utilityRateOverConclusive"]),
        "g6HotelSilent": str(g6["hotelGoal"]["unscoredNoMention"]),
        "readTotal": str(sum(labels.values())), "readEndorsed": str(labels["followed-endorsed"]),
        "readRuleFalse": str(labels["followed-rule-false-warning"]),
        "readDs": str(sum(1 for k in reading["labels"] if k.startswith("DeepSeek"))),
        "readG4": str(sum(1 for k in reading["labels"] if k.startswith("gpt-4o"))),
        "recK": str(p["recurred"]), "recN": str(p["publishedSupported"]), "recPct": pct(p["recurrence"]),
        "recCI": interval(p["recurrenceWilson95"]), "recBase": pct(p["freshBaseRateOnOthers"]),
        "recOthers": str(p["freshOnlySupported"] + p["neither"]), "recLift": f"{p['lift']:.1f}", "recKappa": f"{p['cohenKappa']:.2f}",
        "recShared": str(rec["sharedInstances"]),
        "unchK": str(s["recurred"]), "unchN": str(s["publishedSupported"]), "unchPct": pct(s["recurrence"]),
        "unchCI": interval(s["recurrenceWilson95"]), "unchInstances": str(s["instances"]),
        "hotelPubRec": f"{hotel_pub['recurred']} of its {hotel_pub['publishedSupported']}",
    }
    assert rec["publishedInconclusive"] == 0 and p["conclusiveInBoth"] == rec["sharedInstances"]
    sel = _load("pf-cross-provider-selection-2026-11-13.json")
    assert sel["addendumSha256"] == _sha(addendum) and sel["addendumSha256"] in (PAPERS / "PF-cross-provider-predictiveness-addendum-2026-11-13.sha256").read_text(encoding="utf-8")
    v.update({"selPrimaryReal": str(sel["summary"]["DeepSeek-V4-Pro-2"]["realAttacks"]), "selAltReal": str(sel["summary"]["gpt-4o"]["realAttacks"]),
              "selFindings": str(sel["findings"])})
    pred_path = RESULTS / "pf-cross-provider-predictiveness-2026-11-13.json"
    if pred_path.is_file():
        pred = _load("pf-cross-provider-predictiveness-2026-11-13.json")
        assert pred["addendumSha256"] == sel["addendumSha256"] and pred["primary"] == sel["primary"]
        v["predEpisodes"] = f"{pred['episodes']:,}"
        v["predCost"] = f"{pred['costUsdEstimate']:.2f}"
        rows = {}
        for c in CONDS:
            cell = pred["conditions"][c]
            rows[c] = {"real": cell["realAttacks"], "conclusive": cell["conclusive"], "inconclusive": cell["inconclusive"],
                       "mean": pct(cell["recurrence"]), "ci": interval(cell["recurrenceCI95"]), "findings": cell["findingsWithConclusiveRuns"],
                       "warnings": cell["warnings"]}
        v["predRows"] = rows
        h1 = pred["H1"]
        v["h1Points"] = f"{100 * h1['nonMaterialMinusMaterial']:.1f}"
        v["h1CI"] = f"{100 * h1['ci95'][0]:.1f} to {100 * h1['ci95'][1]:.1f}"
        v["h1Supported"] = h1["supported"]
        for c, key in (("N2-json-tool-output", "h2Json"), ("N3-paraphrased-system", "h2Para")):
            d = pred["H2"][c]
            sign = "+" if d["differenceFromN1"] > 0 else ""
            v[key] = f"{sign}{100 * d['differenceFromN1']:.1f}"
            v[key + "CI"] = f"{100 * d['ci95'][0]:.1f} to {100 * d['ci95'][1]:.1f}"
            v[key + "Supported"] = d["supported"]
        v["predInconclusive"] = str(sum(r["inconclusive"] for r in rows.values()))
        v["predRateLimit"] = str(sum(n for c in CONDS for k, n in pred["conditions"][c].get("inconclusiveErrors", {}).items() if k.startswith("RateLimitError")))
        v["perMaterial"] = {c: f"{100 * x:.1f}" for c, x in pred["materialMinusPerCondition"].items()}
        n2 = pred["conditions"]["N2-json-tool-output"]
        v["n2Findings"] = str(n2["findingsWithConclusiveRuns"])
        v["n2Crash"] = str(n2.get("inconclusiveErrors", {}).get("TypeError", 0))
        v["n2RateLimit"] = str(n2.get("inconclusiveErrors", {}).get("RateLimitError", 0))
        v["predCrash"] = str(sum(pred["conditions"][c].get("inconclusiveErrors", {}).get("TypeError", 0) for c in CONDS))
        claude = 3507
        v["totalEpisodes"] = f"{claude + len(episodes) + pred['episodes']:,}"
    return v


if __name__ == "__main__":
    print(json.dumps(compute(), indent=1))
