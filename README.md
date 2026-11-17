<div align="center">

# TRUSCOR Research

**Papers and R&D from TRUSCOR, released with everything needed to check them.**

Each paper ships with its data, code, protocols, validators, and evidence,<br/>
so a reader can recompute its numbers instead of taking them on trust.

<p>
  <a href="preprints/sova-portable-evidence-reproduction-v1.2.pdf"><img src="https://img.shields.io/badge/LATEST%20PREPRINT-.sova%20v1.2-FFB000?style=for-the-badge" alt="Latest preprint: .sova v1.2" /></a>
  <a href="https://doi.org/10.5281/zenodo.24290457"><img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.24290457-1682D4?style=for-the-badge" alt="DOI 10.5281/zenodo.24290457, all versions" /></a>
  <img src="https://img.shields.io/badge/PEER%20REVIEW-NOT%20YET-D22128?style=for-the-badge" alt="Not peer reviewed" />
  <img src="https://img.shields.io/badge/PAPERS-CC%20BY%204.0-00B8D9?style=for-the-badge" alt="CC BY 4.0" />
  <a href="https://github.com/TRUSCOR/SOVA-OSS"><img src="https://img.shields.io/badge/CODE-TRUSCOR%2FSOVA--OSS-0B8793?style=for-the-badge" alt="Implementation" /></a>
  <a href="artifacts/pf-v1.1/findings/"><img src="https://img.shields.io/badge/EVIDENCE-.sova%20FILES-6554C0?style=for-the-badge" alt="Evidence as .sova files" /></a>
</p>

[Gautam R Patil](https://orcid.org/0009-0005-7614-2771) · [TRUSCOR Private Limited](https://truscor.org) · gautam@truscor.org

</div>

---

## Papers

| Paper | Version | Read | Check it |
|---|---|---|---|
| **Did the Attack Really Work? Auditing, Re-running, and Sealing AI-Agent Security Findings with .sova** | 1.2 · 2026-11-17 · short version, preprint, not peer reviewed | [PDF](preprints/sova-portable-evidence-reproduction-v1.2.pdf) · [Markdown](preprints/sova-portable-evidence-reproduction-v1.2.md) · [DOI](https://doi.org/10.5281/zenodo.24321025) | [Artifact](artifacts/pf-v1.1/) · [post hoc analyses](artifacts/pf-v1.2/) |
| | 1.1 · 2026-11-16 · extended version | [PDF](preprints/sova-portable-evidence-reproduction-v1.1.pdf) · [Markdown](preprints/sova-portable-evidence-reproduction-v1.1.md) · [DOI](https://doi.org/10.5281/zenodo.24290458) | [Artifact](artifacts/pf-v1.1/) · [every run as `.sova` files](artifacts/pf-v1.1/) |

Each released paper keeps its text in `preprints/` and everything needed to
check it in `artifacts/<paper-id>/`:

```
preprints/            released papers, PDF and Markdown, every version
artifacts/pf-v1.1/    data, code, protocols, validators and .sova evidence
                      for the .sova preprint (versions 1.1 and 1.2)
artifacts/pf-v1.2/    the post hoc analyses that version 1.2 adds
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

### [Did the Attack Really Work? Auditing, Re-running, and Sealing AI-Agent Security Findings with .sova](preprints/sova-portable-evidence-reproduction-v1.2.pdf)

**Version 1.2 (2026-11-17), the short version · CC BY 4.0 · DOI [10.5281/zenodo.24321025](https://doi.org/10.5281/zenodo.24321025) · [PDF](preprints/sova-portable-evidence-reproduction-v1.2.pdf) · [Markdown](preprints/sova-portable-evidence-reproduction-v1.2.md) · [Post hoc analyses](artifacts/pf-v1.2/)**

**Version 1.1 (2026-11-16), the extended version · CC BY 4.0 · DOI [10.5281/zenodo.24290458](https://doi.org/10.5281/zenodo.24290458) · [PDF](preprints/sova-portable-evidence-reproduction-v1.1.pdf) · [Markdown](preprints/sova-portable-evidence-reproduction-v1.1.md) · [Data, code, protocols, and every run as `.sova` files](artifacts/pf-v1.1/)**
· previous: [version 1.0](preprints/sova-portable-evidence-reproduction-v1.0.pdf)

**In brief.** Tests of whether AI agents can be tricked score each attack with
an automated check, and those scores rank models and decide whether a reported
attack is real. We checked AgentDojo's verdicts against what the agents actually
did, re-ran its attacks on 24 current models from eight developers, and re-ran
240 successful attacks ten times each, under protocols published before the runs.

- **Did the attack really work?** In 19,381 published runs, the benchmark
  scored as "no attack" 433 runs in which the agent carried out the attacker's
  decisive step (for example, sending money to the attacker), 11.9% of the runs
  the audit counts as attacks. On current models the error reverses for one
  goal, whose check looks for a hotel's name in the agent's reply: every
  Claude 5.x run it scored as attacked was the model warning the user, while
  Claude 4.5 models, which ignore the planted text, score 0%. On the paper's
  scoreboard, which oversamples that goal, this lifts four Claude 5.x models
  above models that carried out more attacks; weighted as the benchmark weights
  its goals, it adds about 2 points to their rates and no longer lifts them
  above any model that carried out more attacks.
- **Does it still work, and how often?** Of 240 recorded attacks re-run ten
  times each on six models, 224 recurred in at least half of their runs, but
  only 201 could be shown at 95% confidence to do so. Upgrades stopped most
  known attacks, not all: GPT-5.5 carried out none of 40 GPT-4o attacks in 120
  runs, while 3 of 40 Grok 4.1 Fast attacks still worked on Grok 4.7.
- **When does a failed re-run mean the attack is gone?** Rules declared in
  advance for which setup changes can stop an attack missed their preregistered
  test on the protocol's three models (gap 12.8 points, 95% interval 9.2 to
  16.3, criterion 10), and met it over six models in an extension added after
  interim results (14.7, 11.9 to 17.4). Rules measured on other models
  transferred to a held-out model in 1 of 9 tests.
- **Can a stranger check it?** A `.sova` file seals a recorded run with the
  claim it supports and what is needed to run it again. Anyone holding the
  published checksums can verify offline that it was not altered; whether the
  attack happens can only be shown by running it again, which the file also
  allows.

`.sova` is released with the paper as a free, local tool and file format,
`pip install sova-oss`: `sova audit` checks a benchmark's verdict against the
agent's actual tool calls, `sova rerun` and `sova matrix` re-run a finding on
any model, `sova calibrate` measures which setup changes matter on a model, and
`sova verify` checks a sealed record offline. Every run of the paper's studies
is released as a `.sova` file. **Try it:** [`artifacts/pf-v1.1/`](artifacts/pf-v1.1/).

**This is a preprint. It has not been peer reviewed.** All results come from one
benchmark, one attack template, and simulated apps; three AI models read the
disputed runs blind, and two human readers, recruited by the author but
independent and unpaid, read a fixed sample of 30; the protocols were
published before the runs but held by the author; and the studies have not yet
been re-run independently. The author leads TRUSCOR,
which develops SOVA.

**Check it yourself.** [`artifacts/pf-v1.1/`](artifacts/pf-v1.1/) holds the code,
every result file, the frozen protocols, every run as a `.sova` bundle, and a
validator that recomputes every reported value. A
[GitHub workflow](.github/workflows/verify-pf-v1-1.yml) re-verifies the files,
the capsules, and the audit on GitHub's machines with no model key.
[`artifacts/pf-v1.2/`](artifacts/pf-v1.2/) recomputes the post hoc analyses that
version 1.2 adds, from the released files and without calling a model.

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
reference verifier, examples, and tests. Version 0.1 is on PyPI
(`pip install sova-oss`), with the `.sova` and `.sova-trace` 0.1.0 formats frozen;
the paper's results use `sova-oss` 0.1.0.

The papers specify and test the ideas. The repository is where they are built and
where you can check them. For the preprint, the research code, retained results,
protocols, build provenance, and reviewer packet are public in
[`artifacts/pf-v1.1/`](artifacts/pf-v1.1/). Third-party raw data are pinned by
commit or digest rather than redistributed, apart from small MIT-licensed
AgentDojo excerpts listed in the artifact's `THIRD-PARTY.md`.

---

## History

Gautam R Patil started this repository on 2 November 2026 on a personal GitHub
account, as `Gautam-R-Patil/sova-research`. On 13 November 2026 it moved to the
TRUSCOR organisation and was renamed `TRUSCOR/research`, to hold all of
TRUSCOR's research. Its full commit history moved with it, and both old
addresses redirect here. The six working drafts first published here on
2 November now live, with their history, in
[Gautam-R-Patil/research-papers](https://github.com/Gautam-R-Patil/research-papers).

---

## Licence

Papers in this repository are released under
**[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**, © 2026 Gautam R Patil.
You may share and adapt them with attribution.

The SOVA OSS source code is separately licensed under Apache-2.0.

## Citing the preprint

```bibtex
@misc{patil2026sova,
  title        = {Did the Attack Really Work? Auditing, Re-running, and
                  Sealing {AI}-Agent Security Findings with {.sova}},
  author       = {Patil, Gautam R},
  year         = {2026},
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.24321025},
  url          = {https://doi.org/10.5281/zenodo.24321025},
  note         = {Preprint, version 1.2. Not peer reviewed.},
}
```

The DOI above is version 1.2, the short version. The extended version, 1.1, is
[10.5281/zenodo.24290458](https://doi.org/10.5281/zenodo.24290458). To link to the
paper, use the all-versions DOI
[10.5281/zenodo.24290457](https://doi.org/10.5281/zenodo.24290457), which always
opens the newest version.

## AI-assistance disclosure

Gautam R Patil conceived the research programme, specified the direction and
safety constraints, and directed the work. Implementation, experiment execution,
analysis support, literature discovery, drafting, and AI-assisted review used
AI coding assistants (OpenAI Codex for version 1.0, Anthropic Claude through
Claude Code for versions 1.1 and 1.2) under his direction. He is the sole human author and
is responsible for the text, citations, figures, data, and declarations. No AI
system is listed as an author.

## Contact

Corrections, disagreements, and independent replication attempts are all welcome,
particularly attempts to falsify the results. Open an issue, or write to
gautam@truscor.org.
