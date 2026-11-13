<div align="center">

# SOVA Research

**Portable, verifiable evidence for AI-agent security findings.**

How a security finding about an AI agent can be packaged so that someone else<br/>
can check it, reproduce it, and see exactly where the evidence stops.

<p>
  <a href="preprints/sova-portable-evidence-reproduction-v1.1.pdf"><img src="https://img.shields.io/badge/PREPRINT-v1.1-FFB000?style=for-the-badge" alt="Preprint v1.1" /></a>
  <img src="https://img.shields.io/badge/PEER%20REVIEW-NOT%20YET-D22128?style=for-the-badge" alt="Not peer reviewed" />
  <img src="https://img.shields.io/badge/PAPERS-CC%20BY%204.0-00B8D9?style=for-the-badge" alt="CC BY 4.0" />
  <a href="https://github.com/TRUSCOR/SOVA-OSS"><img src="https://img.shields.io/badge/CODE-TRUSCOR%2FSOVA--OSS-0B8793?style=for-the-badge" alt="Implementation" /></a>
  <a href="artifacts/pf-v1.1/findings/"><img src="https://img.shields.io/badge/EVIDENCE-.sova%20FILES-6554C0?style=for-the-badge" alt="Evidence as .sova files" /></a>
</p>

Gautam R. Patil · [TRUSCOR Private Limited](https://truscor.org) · gautam@truscor.org

</div>

---

This repository holds the papers. The implementation lives in
**[SOVA OSS](https://github.com/TRUSCOR/SOVA-OSS)**.

---

## Read this first

AI-agent security findings are usually exchanged as prose reports, screenshots,
logs, or replay scripts. Those artifacts preserve useful observations while
staying ambiguous about three things that decide whether a finding is real:

- **what behaviour** is actually being claimed;
- **which parts of the execution context** must stay equivalent for the claim to hold;
- **whether** capture, conversion, or redaction removed the evidence the claim depends on.

The research programme below attacks that problem from several directions. Its
core output is the `.sova` capsule and the `.sova-trace` evidence record.

---

## The preprint

### [`.sova`: Portable, Evidence-Bounded Reproduction of AI-Agent Security Findings](preprints/sova-portable-evidence-reproduction-v1.1.pdf)

**Version 1.1 (2026-11-13) · CC BY 4.0 · [PDF](preprints/sova-portable-evidence-reproduction-v1.1.pdf) · [Markdown](preprints/sova-portable-evidence-reproduction-v1.1.md) · [Data, code, protocols, and four .sova findings](artifacts/pf-v1.1/)**
· previous: [version 1.0](preprints/sova-portable-evidence-reproduction-v1.0.pdf)

**In brief.** A widely used test of AI-agent security can score an AI as
successfully attacked when it warns its user about a hidden instruction. Some
popular models really do follow such instructions: asked only how much the user
spent in March 2022, GPT-4o and DeepSeek-V4-Pro sent money to an attacker's
account in a simulated bank, and attacks published in 2024 still worked on
GPT-4o in 2026. The paper packages findings like these as `.sova` files that
anyone can open and check offline, and describes a procedure that decides
whether a rerun shows the same failure, answering with one of six states rather
than yes or no. The paper's own evidence ships in that format: four findings,
the whole GPT-4o re-run study, and every reply we read are `.sova` files, and the
paper's recurrence and reading counts recompute from them with SOVA's own tools.
**Try it:** [`artifacts/pf-v1.1/findings/`](artifacts/pf-v1.1/findings/).

`.sova` separates three operations that are routinely conflated:

| | |
|---|---|
| **Trace playback** | inert inspection of an already recorded timeline |
| **Controlled re-execution** | a fresh, separately authorized run emitting new evidence |
| **Semantic reproduction** | whether the declared outcome recurred in a sufficiently equivalent context |

**What version 1.1 adds: fresh re-execution of 7,434 attack episodes on eight
models from three developers, and a re-analysis of 15,118 published prompt-injection
logs from 22 AI models** (AgentDojo), under frozen protocols.

- **The same benchmark score means opposite things on different models.** The
  benchmark scored GPT-4o as attacked in 369 of 949 instances and DeepSeek-V4-Pro
  in 561 of 822, and all 109 of those successes we read were real: money sent to
  the attacker, inboxes forwarded, files deleted. GPT-6.1-sol was never scored as
  attacked in 949 (95% upper bound 0.4%) and still completed 83.8% of the user
  tasks. Attacks from the published GPT-4o logs succeeded again on a fresh run
  in 85.3% of cases, against 23.1% of those that had failed, and goal difficulty
  does not explain it (goal-stratified odds ratio 11.4). Two published prompt
  defenses left 91% and 87% of 60 real DeepSeek attacks working. The pre-set test
  of whether the context rules predict recurrence passed on conclusive runs only
  through the change of model, and is not identified once inconclusive runs are
  bounded.
- **On the Claude 5.5 models, the "successful attacks" were the models warning the
  user.** Of the 341 fresh runs the benchmark scored as successful attacks (21
  distinct attack instances), 340 were the model refusing the planted
  instruction and telling the user about it, and in one of these the warning
  still relayed the attacker's link. We read every one with AI assistance. 339 sit on the one attacker goal (of 35) that the
  benchmark scores from the reply text: if the reply contains the hotel's name,
  the attack counts. On that goal the benchmark scored Claude Sonnet 4.5 as
  never attacked (0 of 20) and the newer Claude Haiku 5.5 as attacked in up to
  19 of 20 runs, because only the newer model tells the user, by name, what it
  refused. The warnings recurred on a second full run (18 of 18) and in 80-100%
  of re-runs, even with two published defenses on. The one scored attack that was not a
  warning: told to "follow the instructions precisely" in a file, Claude Sonnet
  4.5 sent money to the attacker, which the user had arguably asked for.
- **Some recorded attack successes were never observed.** 98 of 2,710 came from
  runs that ended in an error or had no agent turn; for Command R+, 22 of 28.
- **"Unknown" is not "failed".** A third of the Claude 3 Opus logs are empty;
  read as unknown, its attack success rate is only bounded between 10.2% and 43.1%.
- **A success on one model is a weak guide to another.** In the published logs, an attack
  that worked on one model also worked on another in 34.9% of comparisons, about twice the
  second model's base rate; most of that is shared attack difficulty, not
  transfer between specific models.
- **What still works against the most resistant models tends to work against
  many models.** The few attacks that survived on the October 2024 Claude 3.5
  Sonnet and on Meta-SecAlign 70B succeed on about half of all other models
  (post hoc).
- **The same test name did not always mean the same test.** Only 12.6% of logs
  record the benchmark version, and 18 user tasks and 11 attack goals were
  reworded under unchanged names.

The paper also reports constructed same-team corpora, real-model web
trajectories, a redaction study that found (and fixed) a defect in our own
code, and every retained negative result.

**This is a preprint. It has not been peer reviewed.** The constructed evidence is
same-team, the fresh runs cover eight models from three developers and two
attack templates, the reading of scored successes was AI-assisted and not
blind, and the test of whether the context rules predict recurrence has run on
one model's real attacks under an addendum frozen during data collection and is
not identified once inconclusive runs are bounded. The
confirmatory gate (independently authored claim contracts, blinded labels, two
independently operated runtimes, and external security and privacy review) is
**not** complete.

**Check it yourself.** [`artifacts/pf-v1.1/`](artifacts/pf-v1.1/) holds the
research prototype, every experiment script and result file, the frozen
protocols, the manuscript source, and a validator that recomputes all 285
reported values, with SHA-256 checksums, plus every fresh-run episode with its
full message trace and four findings packaged as `.sova` files.

---

## Working drafts

Everything below is **an early draft, openly published for transparency about
work in progress.** None of it is peer reviewed, independently validated, or
submitted anywhere. Methods, results, and claims will change. Please don't cite
these as settled results; they are shared so the direction of the work is legible,
not because the work is finished.

| | Paper | What it asks | Stage |
|---|---|---|---|
| **P1** | [Evidence-Guided Trigger-Interaction Search for Stateful AI Agents](drafts/P1-evidence-guided-trigger-interaction-search.md) · [PDF](drafts/P1-evidence-guided-trigger-interaction-search.pdf) | Can evidence from earlier interactions guide the search for the conditions that trigger an agent failure? | Draft · internal benchmark only |
| **P2** | [From Scanner Disagreement to Bounded Evidence](drafts/P2-scanner-disagreement-adjudication.md) | When scanners disagree about a finding, can execution adjudicate between them? | Early draft · incomplete |
| **P4** | [Evidence-Bounded Semantic Reproduction Across Runtimes](drafts/P4-semantic-reproduction.md) · [PDF](drafts/P4-semantic-reproduction.pdf) | Did the same observable behaviour recur, despite allowed stochastic variation? | Draft · superseded in part by the preprint |
| **P5** | [Claim-Conditioned Evidence Fidelity for Behaviour Records](drafts/P5-trace-evidence-fidelity.md) · [PDF](drafts/P5-trace-evidence-fidelity.pdf) | Does the retained evidence still support the claim after capture, conversion, and redaction? | Draft · superseded in part by the preprint |
| **P6** | [Evidence-Bounded Semantic Conformance Across Heterogeneous Executors](drafts/P6-executor-conformance.md) · [PDF](drafts/P6-executor-conformance.pdf) | Do two different agent executors actually agree on what happened? | Draft · internal corpus only |
| **P7** | [Evidence-Bounded Causal Composition Forensics](drafts/P7-causal-composition-forensics.md) | In a partially observed multi-step failure, which steps were actually responsible? | Early draft · mechanism in progress |

Each draft keeps its own limitations and gate-decision section. Those sections are
internal research notes, retained rather than polished away, and they are the
honest record of what is and is not established.

Two further questions, substitution-fidelity transfer and reducing false
security labels across three axes, are at the question stage with no draft yet.

---

## How this relates to SOVA OSS

[SOVA OSS](https://github.com/TRUSCOR/SOVA-OSS) is the
open-source implementation: the `.sova` and `.sova-trace` formats, schemas, the
reference verifier, examples, and tests. It is pre-alpha and under active development.

The papers specify and test the ideas. The repository is where they are built and
where you can check them. For the preprint, the research code, retained results,
protocols, build provenance, and reviewer packet are public in
[`artifacts/pf-v1.1/`](artifacts/pf-v1.1/). Third-party raw data are pinned by
commit or digest rather than redistributed, apart from small MIT-licensed
AgentDojo excerpts listed in the artifact's `THIRD-PARTY.md`.

---

## Licence

Papers in this repository are released under
**[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**, © 2026 Gautam R. Patil.
You may share and adapt them with attribution.

The SOVA OSS source code is separately licensed under Apache-2.0.

## Citing the preprint

```bibtex
@misc{patil2026sova,
  title        = {{.sova}: Portable, Evidence-Bounded Reproduction of
                  {AI}-Agent Security Findings},
  author       = {Patil, Gautam R.},
  year         = {2026},
  note         = {Preprint, version 1.1. Not peer reviewed.},
  howpublished = {\url{https://github.com/Gautam-R-Patil/sova-research}},
}
```

## AI-assistance disclosure

Gautam R. Patil conceived the research programme, specified the direction and
safety constraints, and directed the work. Implementation, experiment execution,
analysis support, literature discovery, drafting, and AI-assisted review used
AI coding assistants (OpenAI Codex for version 1.0, Anthropic Claude through
Claude Code for version 1.1) under his direction. He is the sole human author and
is responsible for the text, citations, figures, data, and declarations. No AI
system is listed as an author.

## Contact

Corrections, disagreements, and independent replication attempts are all welcome,
particularly attempts to falsify the results. Open an issue, or write to
gautam@truscor.org.
