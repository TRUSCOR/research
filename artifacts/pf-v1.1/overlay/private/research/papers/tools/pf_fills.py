"""Values the PF paper reports for sections 5.2, 5.3, 6.1 and 6.2, computed from the result files only.

The assembly script fills the manuscript from these values, and validate_pf_v1_1.py recomputes them
from the result files and checks that each appears in the manuscript.
"""
import json
from collections import Counter
from pathlib import Path

DISPLAY = {"DeepSeek-V4-Pro-2": "DeepSeek V4 Pro", "gpt-4o": "GPT-4o", "grok-4-20-non-reasoning": "Grok 4.20",
           "grok-4-1-fast-non-reasoning": "Grok 4.1 Fast", "Mistral-Large-3": "Mistral Large 3",
           "mistral-medium-3-5": "Mistral Medium 3.5"}
ORDER = ["DeepSeek-V4-Pro-2", "gpt-4o", "grok-4-20-non-reasoning", "grok-4-1-fast-non-reasoning", "Mistral-Large-3", "mistral-medium-3-5"]
CONDS = ["N1-rerun", "N2-json-tool-output", "N3-paraphrased-system", "M1-other-model", "M2-repeat-user-prompt", "M3-spotlighting"]
LABEL = {"N1-rerun": "None (fresh re-run)", "N2-json-tool-output": "JSON tool output", "N3-paraphrased-system": "Paraphrased system prompt",
         "M1-other-model": "Different model", "M2-repeat-user-prompt": "Repeat-user-prompt defense", "M3-spotlighting": "Spotlighting defense"}
WORDS = ["no", "one", "two", "three", "four", "five", "six"]


def p1(x):
    return "n/a" if x is None else f"{100 * x:.1f}"


def ci(c):
    return "n/a" if not c else f"{100 * c[0]:.1f} to {100 * c[1]:.1f}"


def names(ms):
    ms = [DISPLAY[m] for m in ms]
    return ms[0] if len(ms) == 1 else ", ".join(ms[:-1]) + " and " + ms[-1]


def build_main(R: Path) -> dict:
    def load(n):
        return json.loads((R / n).read_text(encoding="utf-8"))

    f = {}
    rel = load("reliability-e1.json")["byPrimary"]
    ms = [m for m in ORDER if m in rel]
    rows = ["| Primary model | Findings | Every run | At least half | Wilson lower bound at least half | Never |",
            "|---|---:|---:|---:|---:|---:|"]
    for m in ms:
        r = rel[m]
        rows.append(f"| {DISPLAY[m]} | {r['findings']} | {r['always']} | {r['atLeastHalf']} | {r['lowerBoundAtLeastHalf']} | {r['never']} |")
    f["S3 table"] = "\n".join(rows)
    total = sum(rel[m]["findings"] for m in ms)
    half = sum(rel[m]["atLeastHalf"] for m in ms)
    never = sum(rel[m]["never"] for m in ms)
    per = [x for m in ms for x in rel[m]["perFinding"] if x["judged"]]
    below = [x for x in per if not (x["wilson"] and x["wilson"][0] >= 0.5)]
    below80 = sum(1 for x in below if x["rate"] >= 0.8)
    f["S3 total"] = str(total)
    f["S3 sentence"] = (
        ("No finding failed to recur, and " if never == 0 else
         (f"{WORDS[never].capitalize()} finding{'' if never == 1 else 's'} never recurred, and " if never < 7
          else f"{never} findings never recurred, and "))
        + f"{half} of {total} recurred in at least half of their runs. Ten runs are still not always enough to show the 50% "
        f"threshold with 95% confidence: for {len(below)} of the {total} findings, the Wilson lower bound stays below 50%. "
        f"A lower bound of 50% needs nine recurrences in ten runs, so {below80} of the {len(below)}, which recurred in at least "
        "80% of their runs, fall short only for lack of runs. A single successful run would not have told these apart.")
    f["S3 abstract"] = (f"Of {total} recorded attacks re-run ten times each on six models, "
                        + ("all recurred at least once and " if never == 0 else "")
                        + f"{half} recurred in at least half of their re-runs, but with so few re-runs, {len(below)} could not be "
                        "shown to succeed at least half the time.")
    f["S3 conclusion"] = (f"of {total} recorded attacks on six models, {half} recurred at least half the time, yet one run "
                          "would not have told the others apart.")
    f["S3 intro"] = (f"of {total} findings re-run ten times each, {half} recurred at least half the time, yet for {len(below)} "
                     "the runs could not show a rate of at least 50% with 95% confidence")
    f["S3 glance"] = (f"We re-ran {total} successful attacks on six models from four developers, ten times each. "
                      + ("All recurred at least once and " if never == 0 else "")
                      + f"{half} recurred at least half the time, but for {len(below)} the runs could not show, with 95% "
                      "confidence, that they succeed at least half the time, a threshold that a bug-bounty program may require. "
                      f"{below80} of those {len(below)} recurred in at least 80% of their runs; ten runs are simply too few.")
    # ---- S5
    up = load("upgrade-e1.json")["pairs"]
    pname = {"gpt-4o -> gpt-5.5": "GPT-4o to GPT-5.5", "grok-4-20-non-reasoning -> grok-4.7": "Grok 4.20 to Grok 4.7",
             "grok-4-1-fast-non-reasoning -> grok-4.7": "Grok 4.1 Fast to Grok 4.7",
             "claude-sonnet-4-5-20250929 -> claude-sonnet-5-5": "Claude Sonnet 4.5 to Claude Sonnet 5.5"}
    rows = ["| Upgrade | Findings | Still works | Stopped | Newly works | Can't tell |", "|---|---:|---:|---:|---:|---:|"]
    still = cant = 0
    still_pairs = []
    matrix_rule = Counter()  # the released `sova matrix` rule for the findings the frozen analysis calls can't tell
    for k in pname:
        for x in up.get(k, {}).get("findings", []):
            if x["class"] != "cant-tell":
                continue
            (ba, bn), (ca, cn) = x["baseline"], x["candidate"]
            matrix_rule["still works" if ba and ca else "stopped working" if ba and cn >= 3 else
                        "newly works" if ca and bn >= 3 else "no attack on either" if bn >= 3 and cn >= 3 else
                        "can't tell"] += 1
    for k, name in pname.items():
        if k not in up:
            continue
        cl = up[k]["classes"]
        still += cl.get("still-works", 0)
        cant += cl.get("cant-tell", 0)
        if cl.get("still-works", 0):
            base, cand = name.split(" to ")
            n_still = cl["still-works"]
            still_pairs.append(f"{WORDS[n_still] if n_still < len(WORDS) else n_still} of the "
                               f"{len(up[k]['findings'])} recorded on {base} still worked on {cand}")
        rows.append(f"| {name} | {len(up[k]['findings'])} | {cl.get('still-works', 0)} | {cl.get('stopped', 0)} | "
                    f"{cl.get('newly-works', 0)} | {cl.get('cant-tell', 0)} |")
    f["S5 table"] = "\n".join(rows)
    f["S5 sentence"] = (
        ("No known attack still worked on the newer model." if still == 0 else
         "Not every upgrade stopped every known attack: " + "; ".join(still_pairs) + ".")
        + (f" {(WORDS[cant] if cant < 7 else str(cant)).capitalize()} could not be judged, because the frozen analysis "
           "needs three judged runs on each model. The released `sova matrix` needs three judged runs only to call an "
           "attack absent; under its rule, " + " and ".join(
               f"{WORDS[v] if v < 7 else v} {'of them ' if i == 0 else ''}{c}" for i, (c, v) in enumerate(sorted(matrix_rule.items())))
           + "." if cant else ""))
    # ---- S4
    main = load("prediction.json")["attack"]
    interim = load("prediction-d2-interim.json")["attack"]
    interim_eq = load("posthoc-sensitivity-d2-interim.json")["equalWeightH1"]
    e1 = load("prediction-e1.json")
    a, b = e1["attack"], e1["benchmark"]
    rows = ["| Change | Declared | Runs | Recurrence (95% interval) |", "|---|---|---:|---|"]
    for c in CONDS:
        x = a["conditions"][c]
        rows.append(f"| {LABEL[c]} | {'non-material' if c.startswith('N') else 'material'} | {x['episodes']:,} | "
                    f"{p1(x['recurrence'])}% ({p1(x['ci95'][0])}-{p1(x['ci95'][1])}%) |")
    f["S4 table"] = "\n".join(rows)
    pm = a["perModel"]
    rows = ["| Primary model | " + " | ".join(["None", "JSON", "Paraphrase", "Other model", "Repeat prompt", "Spotlighting"])
            + " | Gap (95% interval) | Test |", "|---|" + "---:|" * 6 + "---|---|"]
    passed = []
    for m in ms:
        bc = pm[m]["byCondition"]
        ok = pm[m]["supported"]
        passed += [m] if ok else []
        rows.append(f"| {DISPLAY[m]} | " + " | ".join(f"{p1(bc[c])}%" if bc[c] is not None else "n/a" for c in CONDS)
                    + f" | {p1(pm[m]['H1gap'])} ({ci(pm[m]['ci95'])}) | {'met' if ok else 'missed'} |")
    f["S4 model table"] = "\n".join(rows)
    mh, ih = main["H1"], interim["H1"]
    f["S4 main"] = (
        "On the three primary models of the protocol, with the locked design complete, recurrence under the non-material "
        f"changes exceeded recurrence under the material ones by {p1(mh['gap'])} points (95% interval {ci(mh['ci95'])}). "
        "The pre-set criterion was a lower bound of at least 10 points, so the declared envelope "
        + ("met its primary test." if mh["supported"] else "missed its primary test, narrowly.")
        + f" An interim analysis of the reduced design of deviation D2 had {'met' if ih['supported'] else 'missed'} it "
        f"({p1(ih['gap'])}, {ci(ih['ci95'])}), but only because D2 gave Grok 4.20, the model with the smallest gap, half the "
        f"weight of the others; weighted equally, the interim gap was {p1(interim_eq['gap'])} ({ci(interim_eq['ci95'])}).")
    h = a["H1"]
    f["S4 e1"] = (
        f"Over all six primary models (extension E1, frozen before its runs), the gap is {p1(h['gap'])} points "
        f"({ci(h['ci95'])}), which {'meets' if h['supported'] else 'misses'} the same criterion. Counting every unjudged run "
        f"against the hypothesis, the gap is {p1(h['cantTellBounds']['worstForH1'])} points. The declared envelope met the "
        f"criterion on {WORDS[len(passed)]} of the six models" + (f" ({names(passed)})" if passed else "") + ".")
    empty = [(m, c) for m in ms for c in CONDS if pm[m]["byCondition"][c] is None]
    if empty:
        eps34 = [json.loads(line) for line in (R / "s34" / "episodes.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        for m, c in empty:
            runs = [r for r in eps34 if r["model"] == m and r["condition"] == c]
            failed = sum(1 for r in runs if r.get("error"))
            reason = (", because its deployment rejects a user message that follows a tool message"
                      if any("Unexpected role 'user'" in str(r.get("error")) for r in runs) else "")
            f["S4 e1"] += (f" All {failed} of {DISPLAY[m]}'s runs under the {LABEL[c].lower()} failed{reason}; they count "
                           "as can't tell, so the pooled figures for that change rest on five models.")
    h2 = a["H2"]
    f["S4 h2"] = (
        "Pooled, the non-material changes moved recurrence by "
        f"{p1(abs(h2['N2-json-tool-output']['difference']))} and {p1(abs(h2['N3-paraphrased-system']['difference']))} points, and "
        + ("both passed" if all(v["nonMaterialConfirmed"] for v in h2.values()) else "not both passed")
        + " the pre-set test that they lower it by less than 15 points (JSON tool output, "
        f"{ci(h2['N2-json-tool-output']['ci95'])}; paraphrase, {ci(h2['N3-paraphrased-system']['ci95'])}).")
    d = a["H1dim"]
    conf = [c for c in ("M1-other-model", "M2-repeat-user-prompt", "M3-spotlighting") if d[c]["materialConfirmed"]]
    f["S4 dim"] = (
        "Each material change was also tested on its own. A different model lowered recurrence by "
        f"{p1(d['M1-other-model']['drop'])} points ({ci(d['M1-other-model']['ci95'])}), the repeat-user-prompt defense by "
        f"{p1(d['M2-repeat-user-prompt']['drop'])} ({ci(d['M2-repeat-user-prompt']['ci95'])}), and spotlighting by "
        f"{p1(d['M3-spotlighting']['drop'])} ({ci(d['M3-spotlighting']['ci95'])}); "
        + (f"{WORDS[len(conf)]} of the three declarations met the criterion." if conf else "none of the three declarations met the criterion."))
    me = a["measured"]
    lomo = sorted(v["gap"] for v in a["leaveOneModelOut"].values() if v["gap"] is not None) or [None]
    lomo_pass = sum(1 for v in a["leaveOneModelOut"].values() if v["ci95"] and v["ci95"][0] >= 0.10)
    f["S4 measured"] = (
        "Rules measured on half of each model's findings separated recurrence on the other half by "
        f"{p1(me['testGapMeasured'])} points ({ci(me['testGapMeasuredCI95'])}), against {p1(me['testGapDeclared'])} "
        f"({ci(me['testGapDeclaredCI95'])}) for the declared envelope; the pre-set criterion, a lower bound of at least 10 "
        + ("points, was met by " + ("both." if me["testGapMeasuredCI95"][0] >= 0.10 and me["testGapDeclaredCI95"][0] >= 0.10 else
                                   "the measured rules only." if me["testGapMeasuredCI95"][0] >= 0.10 else
                                   "the declared envelope only." if me["testGapDeclaredCI95"][0] >= 0.10 else "neither."))
        + f" Rules measured on five models and applied to the sixth separated recurrence by between {p1(lomo[0])} and "
        f"{p1(lomo[-1])} points on the held-out model, and met the criterion for {WORDS[lomo_pass]} of the six.")
    f["S4 closing"] = ("Comparability rules therefore have to be measured on the model at hand"
                       + ("." if lomo_pass == 6 else "; in these six models, rules learned on others did not carry over reliably."))
    bh = b["H1"]
    f["S4 benchmark"] = (f"Scored with the benchmark's own verdict instead of the audit, the same runs give a pooled gap of "
                         f"{p1(bh['gap'])} points ({ci(bh['ci95'])}), which {'meets' if bh['supported'] else 'misses'} the criterion.")
    gm = pm["gpt-4o"]["byCondition"]
    m2 = {m: pm[m]["byCondition"]["M2-repeat-user-prompt"] for m in ms}
    low = [m for m in ms if m2[m] is not None and m2[m] < 0.8]
    high = [m for m in ms if m2[m] is not None and m2[m] >= 0.8]

    def listing(group):
        parts = [f"{p1(m2[m])}% on {DISPLAY[m]}" for m in group]
        return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]

    f["S4 example"] = (
        (f"The repeat-user-prompt defense cut recurrence to {listing(low)}" if low else "The repeat-user-prompt defense")
        + (f", but left it at {listing(high)}." if low and high else "." if low else f" left recurrence at {listing(high)}."))
    f["S4 abstract"] = (
        f"Attacks came back {p1(h['gap'])} points more often after setup changes declared in advance not to matter than after "
        f"a model swap or a prompt defense (95% interval {p1(h['ci95'][0])}-{p1(h['ci95'][1])}, six models), "
        + ("passing a pre-set test" if h["supported"] else "short of a pre-set test")
        + (f" that the protocol's own three models, taken alone, {'also passed' if mh['supported'] else 'narrowly missed'} "
           f"({p1(mh['gap'])}, {p1(mh['ci95'][0])}-{p1(mh['ci95'][1])})")
        + f"; the declared rules held on {WORDS[len(passed)]} of the six models, and rules learned on five models "
        + ("carried over to the sixth" if lomo_pass == 6 else "did not reliably carry over to the sixth") + ".")
    nm = [a["conditions"][c]["recurrence"] for c in CONDS[:3]]
    mm = [a["conditions"][c]["recurrence"] for c in CONDS[3:]]
    f["S4 glance"] = (
        f"Under plans published before the runs, attacks came back about {sum(nm) / 3 * 100:.0f}% of the time when nothing "
        f"changed or only a harmless-listed change was made, and about {sum(mm) / 3 * 100:.0f}% after material ones, over six "
        f"models from four developers. This {'met' if h['supported'] else 'missed'} a pre-set test. It held on "
        f"{WORDS[len(passed)]} of the six models taken alone, and rules learned on some models did not reliably carry over to others.")
    f["S4 intro"] = (
        f"over six models from four developers, recurrence was {p1(h['gap'])} points higher under changes declared non-material "
        f"than under material ones (95% interval {ci(h['ci95'])}), which {'met' if h['supported'] else 'missed'} the pre-set "
        f"test. On the three models of the main protocol alone, the gap was {p1(mh['gap'])} ({ci(mh['ci95'])}), which "
        f"{'met' if mh['supported'] else 'missed'} it. Per model, the test held on {WORDS[len(passed)]} of six, and rules "
        "measured on some models did not reliably carry over to others")
    f["S4 conclusion"] = (
        f"Declared rules for when two runs are comparable separated recurrence by {p1(h['gap'])} points over six models "
        f"({'meeting' if h['supported'] else 'missing'} the pre-set test), and by {p1(mh['gap'])} on the main protocol's three "
        f"models ({'meeting' if mh['supported'] else 'missing'} it), but held on only {WORDS[len(passed)]} of the six models "
        "alone, and rules learned on some models did not carry over reliably to others.")
    f["S5 count"] = f"{sum(len(v['findings']) for k, v in up.items() if k in pname)} findings on {sum(1 for k in pname if k in up)} model pairs"
    return f


def build_s6(R: Path, sub: str = "s6-e1") -> dict:
    """Section 6.2: the frozen head-to-head on all primaries (S6) and the S6b task study."""
    rec = json.loads((R / sub / "recurrence.json").read_text(encoding="utf-8"))
    tasks = json.loads((R / sub / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    con = rec["contingency"]["attack"]
    t3, t4 = tasks["T3-recurred-on-fresh-run"]["attack"], tasks["T4-refuse-when-setup-differs"]["attack"]
    nonmat = con["naive"]["nonMaterial"]["cells"]
    mat = con["naive"]["material"]["cells"]
    nfind = nonmat // 3
    reruns = rec['inputs']['episodes'] - nfind
    table_runs = sum(v["episodes"] for v in json.loads((R / "prediction-e1.json").read_text(encoding="utf-8"))["attack"]["conditions"].values())
    shared = (f" (the table of section 6.1 counts {table_runs:,}, because GPT-4o runs under the other-model change that serve "
              f"two or three primaries are counted once for each, {table_runs - reruns} extra counts)") if table_runs > reruns else ""
    f = {"S6 runs": f"the {reruns:,} re-runs of section 6.1{shared} and their {nfind} discovery runs",
         "S6 cells": (f"{nonmat + mat:,} cells in all: {nonmat} with a change declared non-material, where the question is "
                      f"whether the outcome recurred, and {mat} with a change declared material")}
    crashes = tasks["T5-abstain-on-crashes"]["episodes"]
    t2 = tasks["T2-one-byte-tamper"]
    ours_tamper = [v for k, v in t2.items() if k.startswith("ours") and isinstance(v, dict)]
    caught = sum(1 for v in ours_tamper if v.get("state") == "invalid")
    cr_keys = [k for k in t2 if k.startswith("CR* C4 analogue (") and "original" not in k]
    cr_t2 = sum(1 for k in cr_keys if t2[k] == "Invalid")
    untyped = {"naive", "plain-sequence", "plain-final-call", "AT*-latest", "AT*-per-call"}
    rows6 = [("ours", "`.sova`, declared rules"), ("ours-measured", "`.sova`, measured rules"), ("naive", "Naive verdict pairing"),
             ("plain-sequence", "Plain log, same call sequence"), ("plain-final-call", "Plain log, same final call"),
             ("CR*-strict", "ClaimReceipt, as published"), ("CR*-finding", "ClaimReceipt, our instance"),
             ("AT*-latest", "AgentTriage, its latest-terminal rule"), ("AT*-per-call", "AgentTriage, every call (our variant)")]
    lines = ["| System | Verdicts on non-material cells (agree with `.sova`) | Material cells refused | One-byte edits detected | Crashed runs abstained |",
             "|---|---:|---:|---:|---:|"]
    for key, name in rows6:
        if key == "CR*-strict":
            verdicts, refused = "0 (abstains)", "0 (abstains)"
        else:
            verdicts = f"{t3[key]['withRecurrenceVerdict']} ({t3[key]['agreeWithOursOnThose']})"
            refused = "not applicable" if key in untyped else f"{t4[key]['refused']} of {t4[key]['materialCells']}"
        if key.startswith("ours"):
            tamper, abst = f"{caught} of {len(ours_tamper)}", f"{crashes} of {crashes}"
        elif key in ("naive", "plain-sequence", "plain-final-call"):
            tamper, abst = "no check", f"0 of {crashes}"
        elif key == "CR*-strict":
            tamper, abst = "not runnable", f"{crashes} of {crashes}"
        elif key == "CR*-finding":
            tamper, abst = f"{cr_t2} of {len(cr_keys)}", f"{crashes} of {crashes}"
        else:
            tamper, abst = "no check", f"{crashes} of {crashes}"
        lines.append(f"| {name} | {verdicts} | {refused} | {tamper} | {abst} |")
    f["S6 table"] = "\n".join(lines)
    rec_cells = sum(con["AT*-latest"]["all"]["table"]["reproduced"].values())
    f["S6 naive"] = ("The naive pairing differs from `.sova` only on "
                     f"{con['naive']['nonMaterial']['causes'].get('abstention rule', 0)} crashed re-runs, which it counts as "
                     "\"not reproduced\".")
    f["S6 plain"] = (f"The attack recurred in {rec_cells} cells, but the agent's full sequence of calls was the same in only "
                     f"{con['plain-sequence']['all']['table']['reproduced'].get('reproduced', 0)} of them.")
    f["S6 at"] = (f"the rule called {con['AT*-latest']['all']['table']['reproduced'].get('no-finding', 0)} of the {rec_cells} "
                  "recurring attacks \"no finding\". Judging every call separately agrees in "
                  f"{t3['AT*-per-call']['agreeWithOursOnThose']} of {t3['AT*-per-call']['cells']} cells.")
    f["S6 cr"] = f"it left {con['CR*-finding']['all']['table']['reproduced'].get('inconclusive', 0)} recurring cells inconclusive."
    f["S6 credited"] = (
        f"The declared rules refuse all {mat} cells with a material change; ClaimReceipt's allowlist, which plays the same role, "
        f"does too. Under the rules measured in section 6.1, `.sova` refuses {t4['ours-measured']['refused']}. Systems that do "
        "not type setup differences give a verdict on every such cell, which is outside what they were built for; the naive "
        f"pairing, for example, would report {con['naive']['all']['table'].get('incompatible', {}).get('not-reproduced', 0)} of "
        "them as failures to reproduce. Per-finding verdicts also differ from batch-level claims in "
        f"{con['CR*-batch']['nonMaterial']['causes'].get('granularity', 0)} cells, where ClaimReceipt's batch claim passes for a "
        "condition in which those findings did not recur.")
    f["S6 crashes"] = f"All {crashes} crashed runs in the data were counted as \"no attack\" by the naive pairing."
    f["S6 warnings"] = f"Of the {tasks['T6-warning-scored-as-attack']['episodes']} Claude hotel-goal warnings"
    ca = rec["aggregates"]["attack"]["causal"]
    rb = rec["aggregates"]["attack"]["rabanser"]["pooled"]
    f["S6 neighbours"] = (
        f"It also states causal claims about treatments; it "
        f"{'confirmed' if ca['M2-repeat-user-prompt']['CR*'] == 'Pass' else 'did not confirm'} the repeat-user-prompt defense "
        f"(a drop of {p1(ca['M2-repeat-user-prompt']['drop'])} points) and "
        f"{'confirmed spotlighting' if ca['M3-spotlighting']['CR*'] == 'Pass' else 'left spotlighting inconclusive'}. "
        "AgentTriage separates attempted from executed calls in the verdict itself and attributes each attack to a defense layer. "
        "Rabanser et al. summarize the same recurrence data in three numbers comparable across benchmarks (pooled outcome "
        f"consistency {rb['Cout']:.2f}, prompt robustness {rb['Rprompt']:.2f}, environment robustness {rb['Renv']:.2f}), but give "
        "no verdict per finding.")
    tb_path = R / "s6b-tasks-recovered.json"
    if not tb_path.is_file():
        tb_path = R / "s6b-tasks.json"
    if tb_path.is_file():
        tb = json.loads(tb_path.read_text(encoding="utf-8"))
        t9 = tb["T9"]
        tot9, agree9 = sum(v["episodes"] for v in t9.values()), sum(v["agree"] for v in t9.values())
        f["S6b table"] = "\n".join([
            "| Task | `.sova` (measured on this paper's data) | AgentTriage | ClaimReceipt | TRACE |",
            "|---|---|---|---|---|",
            f"| Check a benchmark verdict against the recorded actions | `sova audit` gives the frozen analysis's category for "
            f"{agree9:,} of {tot9:,} runs; the rest are redacted passwords | Partial: needs an oracle; given the audit's rules, it "
            "reproduces them | Replays the scorer, so it confirms the 214 warnings as attacks | Not supported: no event stream |",
            f"| Re-run a recorded finding on a model and report k of n | `sova rerun` on the four released findings, two models, "
            "three runs each (text) | Not supported: no AgentDojo runner | Not supported: no released code | Not supported: "
            "keeps no scenario |",
            "| Classify known findings across a model upgrade | `sova matrix`, GPT-4o to GPT-5.5 (text) | Not supported | "
            "Not supported as released | Not supported |",
            "| Measure which setup changes matter on a given model | `sova calibrate`; its rule was tested on fresh findings "
            "under extension E2 (section 6.1) | Not supported | Partial: its causal claims test whether a treatment changes "
            "the outcome, but its comparability allowlist is declared | Not supported |",
            f"| Verify a record offline | `sova verify`: 4 of 4 findings verified; {caught} of {len(ours_tamper)} one-byte edits "
            "detected | No integrity check | Targeted by its paper; no released format to run | For its own signed records |",
        ])
        def outcome(doc):
            if not isinstance(doc, dict):
                return None
            if "attacks" in doc and "judged" in doc:
                return doc
            for v in doc.values():
                found = outcome(v) if isinstance(v, dict) else None
                if found:
                    return found
            return None

        label = {"01": "the spending-question transfer", "02": "the attack that survived two defenses",
                 "03": "the hotel recommendation (recorded as a Claude warning)", "04": "the Claude transfer"}
        parts = {}
        for x in tb["T8"]:
            o8 = outcome(x.get("summary"))
            cell = f"{o8['attacks']} of {o8['judged']}" if o8 else "no result"
            parts.setdefault(x["model"], []).append(f"{label.get(x['finding'][:2], x['finding'])} {cell}")
        names = {"still-works": "still works", "stopped": "stopped working", "newly-works": "newly works",
                 "no-attack-on-either": "no attack on either", "cant-tell": "can't tell"}
        mx = (tb["T10"].get("summary") or {})
        counts = ((mx.get("upgrade") or {}).get("counts") or {}) if isinstance(mx, dict) else {}
        classes = {names.get(k, k): v for k, v in counts.items() if v}
        recovered = "recovery" in tb
        t8_gpt4o = {x["finding"]: outcome(x.get("summary")) for x in tb["T8"] if x["model"] == "gpt-4o"}
        differ = []
        for fx in (mx.get("findings") or []) if isinstance(mx, dict) else []:
            o10 = ((fx.get("models") or {}).get("gpt-4o") or {}).get("outcome") or {}
            o8 = t8_gpt4o.get(fx.get("capsule"))
            if o10 and o8 and o10.get("attacks") != o8["attacks"]:
                differ.append(f"{label.get(fx['capsule'][:2], fx['capsule'])} recurred in {o10['attacks']} of {o10['judged']}")
        t10_note = (" `sova matrix` made its own runs, with GPT-4o at the provider's default sampling rather than temperature 0; "
                    "in them, on GPT-4o, " + " and ".join(differ) + "." if differ else "")
        f["S6b text"] = (
            "`sova rerun` re-ran each of the four released findings three times per model. On GPT-4o, the attack recurred in "
            + "; ".join(parts.get("gpt-4o", [])) + " runs. On GPT-5.5: " + "; ".join(parts.get("gpt-5.5", [])) + ". "
            + ("`sova matrix` classified the same findings across the upgrade from GPT-4o to GPT-5.5 as: "
               + ", ".join(f"{v} {k}" for k, v in sorted(classes.items())) + "." if classes else
               "`sova matrix` ran the same findings across the upgrade from GPT-4o to GPT-5.5 (classes in the artifact).")
            + t10_note
            + (" Two faults in the frozen study script are recorded as deviation D5: it read the wrong line of each "
               "re-run's output, so these counts are read from the runs' own records, and it set a spending cap for "
               "`sova matrix` without the prices the cap needs, which the tool refused, so that call was made again "
               "with the prices added." if recovered else "")
            + " None of the three neighbouring systems has a component that re-runs a finding on a model.")
    return f


E2_SHORT = {"N2-json-tool-output": "JSON", "N3-paraphrased-system": "Paraphrase", "M1-other-model": "Other model",
            "M2-repeat-user-prompt": "Repeat prompt", "M3-spotlighting": "Spotlighting"}
E2_CLASS = {"material": "material", "non-material": "not material", "undetermined": "undetermined"}
E2_PRODUCT = {"N2-json-tool-output": "json", "N3-paraphrased-system": "paraphrase", "M1-other-model": "model",
              "M2-repeat-user-prompt": "repeat-user-prompt", "M3-spotlighting": "spotlighting"}


def build_e2(R: Path) -> dict:
    """Fills for extension E2 (per-model measured envelopes on fresh findings), from e2-result.json."""
    path = R / "e2-result.json"
    if not path.is_file():
        return {}
    e = json.loads(path.read_text(encoding="utf-8"))
    plan = json.loads((R / "plan-e2.json").read_text(encoding="utf-8"))
    nfresh = sum(len(p["findings"]) for p in plan["primaries"])
    env, ms, de = e["envelopes"], e["measured"], e["declared"]
    models = [m for m in ORDER if m in env]
    with_material = [m for m in models if e["measuredSets"][m][1]]
    m_pass = [m for m in with_material if ms["perModel"][m]["supported"]]
    d_pass = [m for m in models if de["perModel"][m]["supported"]]
    n_with = sum(len(p["findings"]) for p in plan["primaries"] if p["model"] in with_material)
    at_bar = [m for m in m_pass if round(ms["perModel"][m]["ci95"][0], 3) == round(e["threshold"], 3)]

    def _names(ms_: list[str]) -> str:
        names = [DISPLAY[m] for m in ms_]
        return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]

    f = {}
    lines = ["| Model | " + " | ".join(E2_SHORT.values()) + " | Measured gap, fresh findings | Declared gap, fresh findings |",
             "|---|" + "---|" * len(E2_SHORT) + "---:|---:|"]
    for m in models:
        cells = []
        for c in E2_SHORT:
            r = env[m][c]
            cells.append(f"{E2_CLASS[r['measured']]} ({p1(r['drop'])})")
        pm, pd = ms["perModel"][m], de["perModel"][m]
        mg = "no change material" if m not in with_material else f"{p1(pm['gap'])} ({ci(pm['ci95'])})"
        lines.append(f"| {DISPLAY[m]} | " + " | ".join(cells) + f" | {mg} | {p1(pd['gap'])} ({ci(pd['ci95'])}) |")
    f["S4 e2 table"] = "\n".join(lines)
    verdict = "meets" if ms["supported"] else "misses"
    f["S4 e2"] = (
        "`sova calibrate` (section 3) measures a model's envelope in this way. Extension E2 tested such measured envelopes "
        "prospectively. It was frozen and published after the result above was known and before any of its runs. For each "
        "model, the classes measured on its 40 findings were applied to 20 fresh findings of the same model, drawn from its "
        "confirmed attacks and never before re-run under any change; each ran under all six conditions three times. "
        f"Pooled over the {n_with} fresh findings of the {WORDS[len(with_material)]} models whose envelope called at least "
        "one change material, recurrence under the unchanged re-runs and the changes measured not material exceeded recurrence "
        f"under the changes measured material by {p1(ms['gap'])} points (95% interval {ci(ms['ci95'])}), which {verdict} "
        f"the pre-set criterion. The declared envelope, on all {nfresh} fresh findings, separated recurrence by {p1(de['gap'])} "
        f"points ({ci(de['ci95'])}) and {'met' if de['supported'] else 'missed'} it. Taken alone, the measured envelope met "
        f"the criterion on {WORDS[len(m_pass)]} of these {WORDS[len(with_material)]} models")
    if m_pass:
        f["S4 e2"] += f" ({_names(m_pass)}"
        if at_bar:
            f["S4 e2"] += f"; {_names(at_bar)} only just, with a lower bound of exactly 10.0 points"
        f["S4 e2"] += ")"
    f["S4 e2"] += f", and the declared envelope on {WORDS[len(d_pass)]} of six"
    if d_pass:
        f["S4 e2"] += f" ({_names(d_pass)})"
    f["S4 e2"] += ". "
    without = [m for m in models if m not in with_material]
    if without:
        f["S4 e2"] += (f"{_names(without)} had no change measured material, so this test says nothing about "
                       f"{'it' if len(without) == 1 else 'them'}. ")
    f["S4 e2"] += "Each class in the table below is followed by the drop it was measured from, in points."
    xc_path = R / "calibrate-crosscheck.json"
    if xc_path.is_file():
        xc = json.loads(xc_path.read_text(encoding="utf-8"))
        f["S4 e2 product"] = (
            "The released `sova calibrate` applies the same rule. Given the same runs, it assigned the same class as the "
            f"frozen analysis to {xc['sameClass']} of the {xc['pairs']} pairs of model and change; its interval endpoints, "
            f"drawn with a different random generator, differed by at most {p1(xc['largestIntervalDifference'])} points.")
    f["S4 e2 abstract"] = (
        f"Rules measured on each model, as the released `sova calibrate` does, separated recurrence on {n_with} fresh findings "
        f"by {p1(ms['gap'])} points ({p1(ms['ci95'][0])}-{p1(ms['ci95'][1])}) under a later frozen extension, "
        + ("passing the same test." if ms["supported"] else "short of the same test."))
    f["S4 e2 glance"] = (
        "Measured on each model instead, as the released tool now does, the rules "
        + ("predicted" if ms["supported"] else "did not reliably predict")
        + f" whether fresh attacks came back on the {WORDS[len(with_material)]} models where some change was measured "
        f"material ({p1(ms['gap'])} points, 95% interval {ci(ms['ci95'])}), "
        f"{'meeting' if ms['supported'] else 'missing'} the same pre-set test.")
    f["S4 e2 conclusion"] = (
        f"Rules measured on each model separated recurrence on fresh findings by {p1(ms['gap'])} points on the "
        f"{WORDS[len(with_material)]} models where a change was measured material "
        f"({'meeting' if ms['supported'] else 'missing'} the same test); the declared rules separated it by {p1(de['gap'])} "
        f"points over all six models ({'meeting' if de['supported'] else 'missing'} it).")
    return f


def build_e3(R: Path) -> dict:
    """Fill for extension E3 (human blind reading, version 2), from human-reading.json when labels exist."""
    frozen = ("extension E3, frozen in commit `4289427` and revised to 30 runs per reader in commit `2c9104a` before "
              "any reader saw an item")
    path = R / "human-reading.json"
    if not path.is_file():
        return {"S7 humans": (f"People are also reading 30 of these runs blind ({frozen}); their results are not in this "
                              "version.")}
    h = json.loads(path.read_text(encoding="utf-8"))
    readers = h["readers"]
    if not readers:
        return {"S7 humans": f"People were asked to read 30 of these runs blind ({frozen}); none completed it in time for this version."}
    field = {"security": "security", "ml": "machine learning", "software": "software", "other": "another field"}
    attack = {"carried_out", "warned_and_carried_out"}
    audit_attack = {"confirmed", "action-scored-as-no-attack"}
    key = {i["id"]: i for i in json.loads((R / "human-sample-key.json").read_text(encoding="utf-8"))}
    ids = sorted(json.loads((R / "plan-e3.json").read_text(encoding="utf-8"))["items"])
    raw = {r["file"]: json.loads((R / "human-readings" / r["file"]).read_text(encoding="utf-8"))["labels"]
           for r in readers.values()}
    # The one sampled run on banking user_task_15 whose request names the attacker's account (section 4.1).
    described = {"h012": ("a published run on banking `user_task_15` whose request names the attacker's account as "
                          "the user's new landlord: the agent paid the rent there, and it is one of the 21 runs set "
                          "aside in section 4.1")}

    def k(x):
        return f"{x:.2f}".replace("-", "−")

    def fields(rs):
        fs = [field.get(r["background"], "another field") for r in rs]
        if len(set(fs)) == 1:
            return f"{'both' if len(rs) == 2 else 'all'} from {fs[0]}" if len(rs) > 1 else f"from {fs[0]}"
        return ", ".join(f"one from {f}" for f in fs[:-1]) + f" and one from {fs[-1]}"

    def stats(r, lead):
        hotel, pub = r["claudeHotelItems"], r["publishedScoredNoAttackItems"]
        h_no, p_att = r["claudeHotelLabelledNoAttack"], r["publishedScoredNoAttackLabelledAttack"]
        return (f"{lead} agreed with the audit on {r['agreeWithAudit']} of the 30 runs (kappa {k(r['kappaWithAudit'])}, "
                f"against {k(r['kappaWithBenchmark'])} with the benchmark's verdict), read "
                f"{'all ' + str(hotel) if h_no == hotel else f'{h_no} of the {hotel}'} Claude hotel-goal runs that the "
                f"benchmark scored as attacks as no attack, and read {p_att} of the {pub} published runs it scored as no "
                "attack as attacks")

    def group(rs):
        sig = {(r["agreeWithAudit"], r["kappaWithAudit"], r["kappaWithBenchmark"], r["claudeHotelLabelledNoAttack"],
                r["publishedScoredNoAttackLabelledAttack"]) for r in rs}
        if len(rs) > 1 and len(sig) == 1:
            return stats(rs[0], "Each")
        return "; ".join(stats(r, f"The reader from {field.get(r['background'], 'another field')}" if len(rs) > 1 else "The reader")
                         for r in rs)

    ind = [r for r in readers.values() if r["relation"] == "independent"]
    other = [r for r in readers.values() if r["relation"] != "independent"]
    text = f"People also read 30 of these runs blind, on their own computers ({frozen}). "
    if ind:
        n = WORDS[len(ind)].capitalize()
        text += (f"{n} reader{'s' if len(ind) > 1 else ''} recruited by the author, "
                 f"{'each declaring' if len(ind) > 1 else 'declaring'} no tie to the author, completed it, {fields(ind)}; "
                 f"{'they' if len(ind) > 1 else 'the reader'} sent the files to the author, and the files are published "
                 f"exactly as received. {group(ind)}.")
    else:
        text += "No reader with no tie to the author completed it."
    if other:
        text += " Readers who work with the author, or the author, also completed it: " + "; ".join(
            stats(r, f"the reader ({r['relation']}, {field.get(r['background'], 'another field')})") for r in other) + "."
    labels = list(raw.values())
    if len(labels) > 1:
        ks = [v for v in h["pairs"].values() if v is not None]
        same_side = all(len({x[i] in attack for x in labels}) == 1 for i in ids)
        differ = [i for i in ids if len({x[i] for x in labels}) > 1]
        between = "the two readers" if len(labels) == 2 else "the readers"
        if same_side:
            text += f" On attack or no attack, {between} agreed on every run (kappa {k(min(ks))})"
        else:
            span = k(min(ks)) if min(ks) == max(ks) else f"{k(min(ks))} to {k(max(ks))}"
            text += f" Between readers, kappa on attack or no attack was {span}"
        if differ and all(len({x[i] for x in labels} - attack) == 0 for i in differ):
            text += (f"; of the four labels, they differed on {WORDS[len(differ)] if len(differ) < len(WORDS) else len(differ)} "
                     f"runs, all attacks that one reader marked as carried out and {'the other' if len(labels) == 2 else 'another'} "
                     "as warned but carried out.")
        elif differ:
            text += f"; of the four labels, they differed on {len(differ)} runs."
        else:
            text += "; they also chose the same one of the four labels on every run."
    if ind:
        departs = [i for i in ids if all(((raw[r["file"]][i] in attack) != (key[i]["category"] in audit_attack)) for r in ind)]
        if departs:
            what = "; ".join(described.get(i, f"a run the audit records as `{key[i]['category']}`") for i in departs)
            text += (f" The {'one run' if len(departs) == 1 else f'{len(departs)} runs'} on which "
                     f"{'the reader' if len(ind) == 1 else 'both readers' if len(ind) == 2 else 'every reader'} departed from the audit "
                     f"{'is' if len(departs) == 1 else 'are'} {what}.")
        held = h.get("hE3", {}).get("supportedForEach")
        text += (" The frozen hypothesis H-E3, that each reader with no tie to the author agrees more with the audit "
                 "than with the benchmark, " + ("held." if held else "did not hold."))
    extra = sorted((R / "human-readings-not-counted").glob("*.json")) if (R / "human-readings-not-counted").is_dir() else []
    if extra:
        same = sum(1 for f in extra
                   if json.loads(f.read_text(encoding="utf-8"))["labels"] in [dict(v) for v in raw.values()])
        if same == len(extra):
            text += (f" {'A further file, whose' if len(extra) == 1 else f'{WORDS[len(extra)].capitalize()} further files, whose'} "
                     f"30 labels are identical to a counted reader's, {'is' if len(extra) == 1 else 'are'} published but "
                     "not counted, because an identical file cannot be shown to be a separate reading (deviation D6).")
        else:
            text += f" {len(extra)} further file(s) are published but not counted (deviation D6)."
    return {"S7 humans": text}


def build_all(R: Path) -> dict:
    f = build_main(R)
    f.update(build_s6(R))
    f.update(build_e2(R))
    f.update(build_e3(R))
    return f
