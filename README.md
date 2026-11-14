<div align="center">

# TRUSCOR Research

**Papers and R&D from TRUSCOR, released with everything needed to check them.**

Each paper ships with its data, code, protocols, validators, and evidence,<br/>
so a reader can recompute its numbers instead of taking them on trust.

<p>
  <a href="preprints/sova-portable-evidence-reproduction-v1.1.pdf"><img src="https://img.shields.io/badge/LATEST%20PREPRINT-.sova%20v1.1-FFB000?style=for-the-badge" alt="Latest preprint: .sova v1.1" /></a>
  <img src="https://img.shields.io/badge/PEER%20REVIEW-NOT%20YET-D22128?style=for-the-badge" alt="Not peer reviewed" />
  <img src="https://img.shields.io/badge/PAPERS-CC%20BY%204.0-00B8D9?style=for-the-badge" alt="CC BY 4.0" />
  <a href="https://github.com/TRUSCOR/SOVA-OSS"><img src="https://img.shields.io/badge/CODE-TRUSCOR%2FSOVA--OSS-0B8793?style=for-the-badge" alt="Implementation" /></a>
  <a href="artifacts/pf-v1.1/findings/"><img src="https://img.shields.io/badge/EVIDENCE-.sova%20FILES-6554C0?style=for-the-badge" alt="Evidence as .sova files" /></a>
</p>

Gautam R. Patil · [TRUSCOR Private Limited](https://truscor.org) · gautam@truscor.org

</div>

---

## Papers

| Paper | Version | Read | Check it |
|---|---|---|---|
| **Did the Attack Really Work? Auditing, Re-running, and Proving AI-Agent Security Findings with .sova** | 1.1 · 2026-11-14 · preprint, not peer reviewed | [PDF](preprints/sova-portable-evidence-reproduction-v1.1.pdf) · [Markdown](preprints/sova-portable-evidence-reproduction-v1.1.md) | [Artifact](artifacts/pf-v1.1/) · [every run as `.sova` files](artifacts/pf-v1.1/) |

Each released paper keeps its text in `preprints/` and everything needed to
check it in `artifacts/<paper-id>/`:

```
preprints/            released papers, PDF and Markdown, every version
artifacts/pf-v1.1/    data, code, protocols, validators and .sova evidence
                      for the .sova preprint, version 1.1
```

The software lives in **[SOVA OSS](https://github.com/TRUSCOR/SOVA-OSS)**.

---

## The SOVA research programme

AI-agent security findings are usually exchanged as prose reports, screenshots,
logs, or replay scripts. Those artifacts preserve useful observations while
staying ambiguous about three things that decide whether a finding is real:

- **what behaviour** is actually being claimed;
- **which parts of the execution context** must stay equivalent for the claim to hold;
- **whether** capture, conversion, or redaction removed the evidence the claim depends on.

The SOVA research programme attacks that problem from several directions. Its
core output is the `.sova` capsule and the `.sova-trace` evidence record.

---

## The .sova preprint

### [Did the Attack Really Work? Auditing, Re-running, and Proving AI-Agent Security Findings with .sova](preprints/sova-portable-evidence-reproduction-v1.1.pdf)

**Version 1.1 (2026-11-14) · CC BY 4.0 · [PDF](preprints/sova-portable-evidence-reproduction-v1.1.pdf) · [Markdown](preprints/sova-portable-evidence-reproduction-v1.1.md) · [Data, code, protocols, and every run as `.sova` files](artifacts/pf-v1.1/)**
· previous: [version 1.0](preprints/sova-portable-evidence-reproduction-v1.0.pdf)

**In brief.** Tests of whether AI agents can be tricked score each attack with
an automated check, and those scores rank models and decide whether a reported
attack is real. We checked AgentDojo's verdicts against what the agents actually
did, re-ran its attacks on 24 current models from eight developers, and re-ran
100 successful attacks many times, under protocols published before the runs.

- **Did the attack really work?** In 19,381 published runs, the agent carried
  out the attacker's decisive step (for example, sending money to the
  attacker) in 433 runs that the benchmark scored as "no attack". On current
  models the error reverses: the benchmark scores four Claude 5.x models as
  attacked in 10.9% to 12.8% of attacks, yet every one of those runs was the
  model warning the user, and no Claude model carried out an attacker's action.
- **Does it still work, and how often?** Of 100 recorded attacks re-run five or
  ten times, all recurred at least once and 98 at least half the time, but for
  16 the runs could not show a rate of at least 50% with 95% confidence. None of
  40 GPT-4o attacks worked on GPT-5.5, and none of 20 Grok 4.20 attacks on Grok 4.7.
- **Can it be proved to a stranger?** Declared rules for when two runs are
  comparable predicted recurrence by 14.0 points (95% interval 10.2 to 17.8),
  passing a pre-set test; per model they held only on GPT-4o, and rules learned
  on two models did not carry over to a third. `sova verify` caught every
  one-byte tamper we made, where a recent diagnosis tool silently changed its
  verdict.

`.sova` is released with the paper as a free, local tool and file format:
`sova audit` checks a benchmark's verdict against the agent's actual tool
calls, `sova rerun` and `sova matrix` re-run a finding on any model, and
`sova verify` checks a sealed record offline. Every run of the paper's studies
is released as a `.sova` file. **Try it:** [`artifacts/pf-v1.1/`](artifacts/pf-v1.1/).

**This is a preprint. It has not been peer reviewed.** All results come from one
benchmark with simulated apps; two AI models, not people, read the disputed
runs blind; the protocols were published before the runs but held by the
author; and the studies have not yet been re-run independently. The author leads TRUSCOR,
which develops SOVA.

**Check it yourself.** [`artifacts/pf-v1.1/`](artifacts/pf-v1.1/) holds the code,
every result file, the frozen protocols, every run as a `.sova` bundle, and a
validator that recomputes every reported value. A
[GitHub workflow](.github/workflows/verify-pf-v1-1.yml) re-verifies the files,
the capsules, and the audit on GitHub's machines with no model key.

---

## Working drafts

Working drafts of further SOVA papers, and of papers on other projects, are kept
in the author's own repository,
**[Gautam-R-Patil/research-papers](https://github.com/Gautam-R-Patil/research-papers)**.
They are early, not peer reviewed, and not meant to be cited as settled results.
This repository holds only released papers and the material needed to check them.

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

## History

Gautam R. Patil started this repository on 2 November 2026 on a personal GitHub
account, as `Gautam-R-Patil/sova-research`. On 13 November 2026 it moved to the
TRUSCOR organisation and was renamed `TRUSCOR/research`, to hold all of
TRUSCOR's research. Its full commit history moved with it, and both old
addresses redirect here. The six working drafts first published here on
2 November now live, with their history, in
[Gautam-R-Patil/research-papers](https://github.com/Gautam-R-Patil/research-papers).

---

## Licence

Papers in this repository are released under
**[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**, © 2026 Gautam R. Patil.
You may share and adapt them with attribution.

The SOVA OSS source code is separately licensed under Apache-2.0.

## Citing the preprint

```bibtex
@misc{patil2026sova,
  title        = {Did the Attack Really Work? Auditing, Re-running, and
                  Proving {AI}-Agent Security Findings with {.sova}},
  author       = {Patil, Gautam R.},
  year         = {2026},
  note         = {Preprint, version 1.1. Not peer reviewed.},
  howpublished = {\url{https://github.com/TRUSCOR/research}},
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
