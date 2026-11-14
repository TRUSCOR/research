# Artifact for "Did the Attack Really Work? Auditing, Re-running, and Proving AI-Agent Security Findings with .sova" (v1.1)

Everything needed to check every number, figure, and protocol in preprint
version 1.1 is in this folder. Nothing that the paper relies on is withheld.

- Paper: [`../../preprints/`](../../preprints/)
- Implementation: [SOVA OSS](https://github.com/TRUSCOR/SOVA-OSS), commit `143e175`
- Frozen protocols, published before their runs: [`../../protocols/pf-confirmatory-2026-11-14/`](../../protocols/pf-confirmatory-2026-11-14/)
- Checksums for every file: [`SHA256SUMS`](SHA256SUMS)
- Automatic re-check on GitHub's machines, no model key needed:
  [`../../.github/workflows/verify-pf-v1-1.yml`](../../.github/workflows/verify-pf-v1-1.yml)

## Start here: check the paper's runs in five minutes

Every run of the 2026-11-14 studies (S2 to S5) is released as a `.sova` bundle,
one per model (S2, S5) or per model and change (S3, S4), under
`overlay/private/experiments/results/pf-confirmatory-2026-11-14/sova/`.

```bash
python -m pip install "sova-oss @ git+https://github.com/TRUSCOR/SOVA-OSS@143e1751995e8e76dd8e6a19f67eb21ccc968703"
R=overlay/private/experiments/results/pf-confirmatory-2026-11-14
sova verify $R/sova/s2-anthropic/claude-opus-5-5/claude-opus-5-5.sova     # offline; runs nothing
sova audit  $R/sova/s2-anthropic/claude-opus-5-5/claude-opus-5-5.sova     # benchmark verdict vs. the agent's actual calls
python overlay/private/experiments/check_pf_sova_audit.py $R/s2-anthropic $R/sova/s2-anthropic
```

The last command recomputes every run's category from the raw records with the
frozen research audit and compares it with `sova audit` on the released bundle.
They agree except where the capture redacted a password value; the tool then
says `evidence-redacted` instead of guessing.

With a model key you can re-run any finding (it calls the model and costs money):

```bash
sova rerun <finding.sova> --model <your-deployment> --trials 10 --authorize
```

## The studies of 2026-11-14 (sections 4 to 6)

The protocol, the audit rules, the runner, and the analysis were frozen and
published before the first run (`protocols/pf-confirmatory-2026-11-14/`,
commit `c7e3fb4`, 05:57 UTC; the head-to-head addendum at `5a2ad61`, 06:41 UTC).
Deviations are in `overlay/private/research/papers/PF-confirmatory-deviations-2026-11-14.md`.

| Study | Paper | Result files (under `overlay/private/experiments/results/`) | Script |
|---|---|---|---|
| S1 verdict audit of published and earlier runs | 4.1, 4.2 | `pf-audit-2026-11-14/` | `audit_pf.py published` and `study` |
| S2 scoreboard of current models | 4.3, 5.1 | `pf-confirmatory-2026-11-14/s2/`, `s2-anthropic/`, `scoreboard.json` | `run_pf_confirmatory.py`, `analyze_pf_v2.py scoreboard` |
| S3 reproduction rates | 5.2 | `s34/`, `reliability.json`, `plan.json` | `analyze_pf_v2.py select` and `reliability` |
| S4 prediction test | 6.1 | `s34/`, `prediction.json` | `analyze_pf_v2.py prediction` |
| S5 upgrade checks | 5.3 | `s5/`, `s5-anthropic/`, `upgrade.json` | `analyze_pf_v2.py upgrade` |
| S6 head-to-head | 6.2 | `s6/` | `compare_pf_neighbors.py` |
| S7 blind readers | 4.4 | `readers-items.json`, `readers-*.jsonl`, `readers-agreement.json` | `read_pf_blind.py` |

All are under `pf-confirmatory-2026-11-14/` unless named otherwise. Each run
directory holds `episodes.jsonl` (one record per run: model, returned model
string, verdict, tokens, cost, time) and `traces.jsonl.gz` (every message).
`drive_pf_remaining.py` is the single process that ran the later stages, and
`driver.log` is its log. The runs called Azure AI Foundry deployments and
Anthropic's API; `run_pf_confirmatory.py` reads the Azure endpoint and key from
a local notes file named in `PF_AZURE_NOTES` and the Anthropic key from
`ANTHROPIC_API_KEY`, and never writes either anywhere.

## The studies of the earlier drafts (Appendix C)

Appendix C keeps the studies of the earlier v1.1 drafts unchanged except for
cross-references: what the earlier README called sections 6.1 to 6.6 are now
Appendix C.4 to C.9, and section 5 is C.3. The four findings in
[`findings/`](findings/) come from Appendix C.5:
- GPT-4o and DeepSeek-V4-Pro sending money to an attacker when asked only about
  the user's spending, with GPT-4o doing so in AgentDojo's published 2024 log
  and again in 2026;
- an attack that survived two published prompt defenses;
- a Claude warning that the benchmark scored as an attack;
- the one Claude transfer.
[`findings/README.md`](findings/README.md) has the commands.

## Why the folder is called `overlay/private/...`

The studies were written and run inside a `private/` folder of the SOVA OSS
checkout, and the scripts import their research code as `private.experiments...`.
To keep every file byte-identical to what produced the results (several result
files record digests of the code that made them), the files are released
unchanged under the same paths. Copy `overlay/private` into a SOVA OSS checkout
and everything runs where it ran. The word "private" in paths and in old
document status lines reflects where the material lived at the time; it is all
public now.

## Check it yourself

### 1. Recompute every number in the paper (about one minute, no model calls)

```bash
git clone https://github.com/TRUSCOR/SOVA-OSS sova-oss
cd sova-oss && git checkout 42b4972
cp -r <this-folder>/overlay/private ./private
python -m pip install pypdf            # only needed for --package
python -X utf8 private/research/papers/tools/validate_pf_v1_1.py --package
```

The validator recomputes every reported value from the retained result files,
checks that each appears in the manuscript, checks banned overclaiming phrases, resolves every citation to a URL, verifies the built PDF, source archive, and
provenance digests, and confirms that the published version 1.0 files are
unchanged. (The banned-phrase list is deliberate: it stops words such as
"first", "only" and "revolutionary" from entering the text, and we consider
that good practice rather than something to hide.)

### 2. Re-execute the deterministic studies from the released code (about one minute)

```bash
uv sync --locked
uv run python private/experiments/rerun_pf_studies.py /tmp/pf-rerun
```

This re-runs the 144/120/60-case corpora, the component ablation, the privacy
study, the foreign-process adapter study, and the 12-contract and broker
studies, then diffs every non-timing field against the retained results. Our
own run on 2026-11-12 is in
`overlay/private/experiments/results/reexecution-2026-11-12/` (zero differences).

### 3. Re-run the AgentDojo re-analysis (Appendix C.4)

The protocol was frozen and hashed before any AgentDojo log was read:
`overlay/private/research/papers/PF-agentdojo-reproduction-protocol-2026-11-12.md`
(SHA-256 and UTC time in the adjacent `.sha256` file).

```bash
git clone --filter=blob:none --no-checkout https://github.com/ethz-spylab/agentdojo.git agentdojo
cd agentdojo && git checkout 089ed468cf3ed0322acc66b0211f26d9d90dbf60 -- 'runs/*/*/*/important_instructions/*.json'
cd .. && python -X utf8 sova-oss/private/experiments/run_pf_agentdojo_reproduction.py agentdojo out.json
```

Standard library plus NumPy; it reads the logs as data and runs no AgentDojo or
model code. The post-hoc analyses added after AI-assisted review (attack-success
bounds, symmetric and base-rate-aware statistics, clustered intervals, the
difficulty-matched successor analysis, the content-keyed envelope, and the table
of reworded task texts) run on the same logs:

```bash
python -X utf8 sova-oss/private/experiments/run_pf_agentdojo_supplementary.py agentdojo out.json supplementary.json
python -X utf8 sova-oss/private/experiments/check_pf_published_text_collisions.py agentdojo supplementary.json collisions.json --reading sova-oss/private/experiments/results/pf-published-hotel-reading-2026-11-13.json
```

The last command is the post-hoc check of two text collisions in the published
logs: the banking task whose reworded request names the attacker's account, and
the 93 published hotel-goal replies that are not warnings, with the reading of
each passage (`pf-published-hotel-reading-2026-11-13.json`).

### 4. Re-run the fresh re-execution study (Appendix C.5)

This study calls a model provider and costs money (about USD 38 at list prices
for the 3,507 episodes reported across the two fresh-run protocols). Its protocol was frozen and hashed before any
episode: `overlay/private/research/papers/PF-fresh-reexecution-protocol-2026-11-12.md`
and the adjacent `.sha256`. It runs in its own environment, pinned in
`overlay/private/experiments/results/pf-fresh-reexecution-2026-11-12/requirements-agentdojo-env.txt`
(AgentDojo 0.1.35, Anthropic SDK 0.125.0, NumPy):

```bash
python -m venv adojo && adojo/bin/pip install -r .../requirements-agentdojo-env.txt
export ANTHROPIC_API_KEY=...   # your own key; never written to any file
python private/experiments/run_pf_fresh_agentdojo.py pilot    out/
python private/experiments/run_pf_fresh_agentdojo.py baseline out/ --model claude-haiku-5-5 --trial 1
python private/experiments/run_pf_fresh_agentdojo.py perturb  out/ --model claude-haiku-5-5 --alt-model claude-sonnet-5-5
python private/experiments/run_pf_fresh_agentdojo.py analyze  out/ result.json
python private/experiments/classify_pf_warning_successes.py out/ <agentdojo-repo> warnings.json
python private/experiments/summarize_pf_fresh_successes.py private/experiments/results summary.json --audit private/experiments/results/pf-fresh-successes-manual-audit-2026-11-13.json
```

The second fresh-run protocol (real attacks; Sonnet 4.5 and Opus 4.5, two
attacks) is `PF-real-attack-predictiveness-protocol-2026-11-12.md`; run the same
script with `--protocol <that file> --attack <name> --models <list>` and analyse
with `analyze_pf_real_attack_predictiveness.py <out.json> <run dirs...>`. Its
episodes and traces are in `results/pf-real-attack-predictiveness-2026-11-12/`.

The fourth protocol (other providers) and its addendum (the predictive test on
real attacks) ran on three deployments of an Azure AI Foundry project through its
OpenAI-compatible endpoint. Any endpoint that serves deployments with the same
names works. The runner reads the endpoint and key from a local notes file whose
path is in `PF_AZURE_NOTES` (a line `endpoint = "https://<resource>/openai/v1"` and
a line `API key: <key>`); neither is printed or written anywhere.

```bash
export PF_AZURE_NOTES=/path/to/notes.txt
python private/experiments/run_pf_fresh_agentdojo.py crossprovider out-cross --models gpt-4o,gpt-6.1-sol,DeepSeek-V4-Pro-2 \
    --protocol private/research/papers/PF-cross-provider-protocol-2026-11-13.md --budget 150
python private/experiments/analyze_pf_cross_provider.py out-cross <agentdojo-repo> pf-agentdojo-supplementary-2026-11-12.json cross.json \
    --reading private/experiments/results/pf-cross-provider-reading-2026-11-13.json
python private/experiments/analyze_pf_cross_provider_predictiveness.py select out-cross findings.json selection.json
python private/experiments/run_pf_fresh_agentdojo.py perturb out-perturb --model DeepSeek-V4-Pro-2 --alt-model gpt-4o \
    --findings-file findings.json --protocol private/research/papers/PF-cross-provider-predictiveness-addendum-2026-11-13.md --budget 100
python private/experiments/analyze_pf_cross_provider_predictiveness.py analyze out-cross out-perturb selection.json predictiveness.json
```

Our episodes and traces are in `results/pf-cross-provider-2026-11-13/` (2,847
episodes) and `results/pf-cross-provider-perturb-2026-11-13/` (1,080 episodes).

**Re-test your own model on the same attacks.** The attacks that worked are a
ready regression set: `pf-cross-provider-findings-2026-11-13.json` lists the 60
DeepSeek-V4-Pro real attacks as AgentDojo (suite, user task, injection task)
triples, and the published GPT-4o successes are in AgentDojo's own logs. Any
AgentDojo pipeline can run them. The runner here supports the Anthropic API and
the three OpenAI-compatible deployments named in the protocol; another model
needs its name added to `AZURE_MODELS` and its price to `PRICES` in
`run_pf_fresh_agentdojo.py`. The four packaged findings were built from the
retained traces by `build_pf_findings_gallery.py`, which runs no model:

```bash
python -X utf8 private/experiments/build_pf_findings_gallery.py <agentdojo-repo>/runs findings-rebuilt/
```

Fresh runs are stochastic, so a re-run reproduces the distribution, not the
exact episodes. Every episode we ran, with its full message trace, is in
`overlay/private/experiments/results/pf-fresh-reexecution-2026-11-12/`
(`episodes.jsonl`, `traces.jsonl.gz`), so the analysis and the warning
classification can be recomputed without calling any model. The per-goal
summary (`pf-fresh-successes-by-goal-2026-11-13.json`) and the reading of every
one of the 341 scored successes (`pf-fresh-successes-manual-audit-2026-11-13.json`)
are post hoc and recomputable the same way; the audit file records that the
reading was AI-assisted under the author's direction and not blind to the
keyword rule.

### 5. Re-run the redaction study (Appendix C.8)

```bash
uv run python private/experiments/run_pf_redaction_triple.py /tmp/redaction.json
```

`pf-redaction-triple-2026-11-12.json` is the run that found the payload-omission
defect; `pf-redaction-triple-postfix-2026-11-12.json` is the re-run after the fix
in `prototypes/fidelity.py`.

### 6. Rebuild the PDF

`private/research/papers/tools/build_pf_v1_1.py` rebuilds the figures and PDF
with Pandoc 3.10.1 and Tectonic 0.16.9 (official binaries; checksums in
`tools/README.md`) and matplotlib 3.10.8.

## Where each Appendix C result comes from

| Paper section | Result file (under `overlay/private/experiments/results/`) | Script |
|---|---|---|
| C.7 constructed corpora (144 / 120) | `topics-04-06-study-2026-07-31.json` | `run_topics_04_06_study.py` |
| C.7 public-contract study and broker | `topics12-13-postbuild-study-2026-08-03.json` | `run_topics12_13_postbuild_study.py` |
| C.4 AgentDojo, 22 models (pre-specified protocol) | `pf-agentdojo-reproduction-2026-11-12.json` | `run_pf_agentdojo_reproduction.py` |
| C.4 AgentDojo, post-hoc analyses and reworded-task table | `pf-agentdojo-supplementary-2026-11-12.json` | `run_pf_agentdojo_supplementary.py` |
| C.4 and C.5 text collisions in the published logs; reading of the 93 published hotel-goal non-warnings | `pf-published-text-collisions-2026-11-13.json`, `pf-published-hotel-reading-2026-11-13.json` | `check_pf_published_text_collisions.py` |
| C.5 fresh re-execution on Claude models | `pf-fresh-reexecution-2026-11-12.json`, `pf-fresh-reexecution-2026-11-12/`, `pf-warning-classification-2026-11-12.json`, `pf-real-attack-predictiveness-2026-11-12.json`, `pf-real-attack-predictiveness-2026-11-12/`, `pf-fresh-successes-by-goal-2026-11-13.json`, `pf-fresh-successes-manual-audit-2026-11-13.json` | `run_pf_fresh_agentdojo.py`, `classify_pf_warning_successes.py`, `analyze_pf_real_attack_predictiveness.py`, `summarize_pf_fresh_successes.py` |
| C.5 other providers, the re-run of published GPT-4o findings, and the predictive test on real attacks | `pf-cross-provider-2026-11-13.json`, `pf-cross-provider-2026-11-13/`, `pf-cross-provider-reading-2026-11-13.json`, `pf-cross-provider-selection-2026-11-13.json`, `pf-cross-provider-findings-2026-11-13.json`, `pf-cross-provider-predictiveness-2026-11-13.json`, `pf-cross-provider-perturb-2026-11-13/` | `run_pf_fresh_agentdojo.py`, `azure_foundry_client.py`, `analyze_pf_cross_provider.py`, `analyze_pf_cross_provider_predictiveness.py` |
| C.6 AgentRewardBench pairs | `agentreward-cross-model-study-2026-07-31.json`, `p4-graph-semantic-baselines-2026-08-01.json` | `run_agentreward_cross_model_study.py`, `run_p4_graph_semantic_baselines.py` |
| C.7 provider status (60 cases, foreign process) | `topics-04-06-study-2026-07-31.json`, `topic06-independent-adapter-study-2026-07-31.json` | `run_topics_04_06_study.py`, `run_independent_adapter_study.py` |
| C.8 redaction triple (before and after the fix) | `pf-redaction-triple-2026-11-12.json`, `pf-redaction-triple-postfix-2026-11-12.json` | `run_pf_redaction_triple.py` |
| C.9 attack matrix, privacy, Inspect, OTLP/STIX/Collector, scale, cross-version, repeatability | `topic05-attack-matrix-…`, `topic05-privacy-attack-study-…`, `inspect-*`, `p5-incident-collector-scale-…`, `cross-version-python-3.1*-…`, `p5-repeatability-audit-…`, `external-*` | matching `run_*.py` |
| C.9 statistical correction | `topics-04-06-study-2026-07-31.json` (`semantic.wilson`, `semantic.exact_interval`) | `run_topics_04_06_study.py` |
| C.3 TRACE bridge | SOVA OSS `src/sova/interoperability/trace_attestation.py`, `tests/unit/test_trace_attestation.py` at `42b4972` | `pytest tests/unit/test_trace_attestation.py` |

Specifications of the research prototype are in
`overlay/private/research/specifications/`; the earlier protocol, falsification
review, and source ledgers (with pinned third-party commits and licences) are in
`overlay/private/research/`.

## What is not here, and why

- **Third-party raw data** - AgentDojo run logs (only the reworded task texts are
  quoted, and one published GPT-4o log is converted into a trace in
  `findings/01-...`, under AgentDojo's MIT licence), AgentRewardBench trajectories,
  Inspect fixtures, STS Benchmark sentences, the OpenTelemetry Collector binary.
  The scripts and ledgers pin each source by commit or digest; see
  [`THIRD-PARTY.md`](THIRD-PARTY.md).
- **Material unrelated to this paper** - other draft papers' studies (for example
  the trigger-search factor lattice), company strategy documents, and
  acceptance runs on other targets. None of it is used by any number in the
  paper.

## Historical notes inside released documents

Some older documents (specifications, protocol, source ledgers) carry status
lines written before release and passages about patent or counsel screening.
Two status lines (a source ledger and a prototype specification) were annotated
on 2026-11-13 to say so; the rest are left as written. All of it is historical.
The work is public, no patent application has been filed for it, and none is
planned. The preregistration-style design for the envelope-predictiveness study
also records, candidly, that an earlier owned-target campaign (AI Goat) failed
on infrastructure in 31 of 35 attempts and that the raw AgentRewardBench
trajectories were deleted after their study; the paper now says both.

## Licences

Code: Apache-2.0 ([`LICENSE-CODE`](LICENSE-CODE)). Data, protocols, and text:
CC BY 4.0 (the repository [`LICENSE`](../../LICENSE)). Third-party terms: see
[`THIRD-PARTY.md`](THIRD-PARTY.md).

## Competing interest

The author leads TRUSCOR Private Limited, which develops SOVA. This artifact is
released so that anyone can check the results without trusting the author.
