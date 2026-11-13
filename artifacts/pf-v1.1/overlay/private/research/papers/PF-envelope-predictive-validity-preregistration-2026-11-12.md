# PF Experiment B - is the context-equivalence envelope predictive?

Preregistration-style design. Drafted 2026-11-12. **No data collected, no runs
performed, no model or provider calls made.** Executing it needs fresh
re-executions, which are not authorised now.

## 0. Question

If the envelope (paper section 4.2) says a candidate context is **compatible**
with the context of a source finding, does the finding's observable outcome
recur more often than when it says **incompatible**? Put another way: do the
envelope's materiality declarations predict recurrence, rather than only
reproducing the labels used to build the corpus?

The envelope implementation under test is
`private/experiments/prototypes/semantic.py: compare_context` (modes `exact`,
`one-of`, `tolerance`, `record`, `ignore`; statuses `compatible`, `drifted`,
`incompatible`, `unknown`). It sits inside `decide_reproduction` in the same
module. It is a private prototype. The shipped `sova` package and its schemas
have no envelope. `sova.reproduction.compare_observable_outcomes` does not
compare context.

## 1. Audit: local data cannot support a non-circular test

| Retained source | What it has | Why it cannot test predictiveness |
|---|---|---|
| 144-pair semantic corpus (`run_topics_04_06_study.py`) | Constructed pairs with labels such as `incompatible` | **Circular.** An `incompatible` label means the builder changed `model.family`, and the envelope rule is `model.family: exact`. The label and the verdict come from the same rule. |
| Integrated drift study (`integrated-baseline-drift-study-2026-07-31.json`) | 7 + 4 hand-labelled cases, including `required-context-incompatible` and `requiredDigestDrift` | **Circular.** The authors set the truth to the envelope's own verdict. |
| 12-contract / 96-trace study (`run_topics12_13_postbuild_study.py`) | One host. Only response text and oracle presence vary. | **Degenerate.** Context never varies, so the envelope's verdict is constant. `semantic_reproduction_study` calls `compare_observable_outcomes` and never consults an envelope. |
| Factor-lattice study (`topic14-factor-lattice-study-2026-08-03.json`) | 60 synthetic targets. An attack triggers only when the candidate matches the target on all `order` factors. | **Circular.** The outcome is a conjunction of factor equalities, which is the same kind of function an `exact` envelope encodes. The result also keeps only search-run rows, not per-candidate context and outcome. |
| AgentRewardBench pairs (`agentreward-cross-model-study-2026-07-31.json`) | 11 cross-model WebArena pairs with expert labels | **Degenerate.** `benchmark`, `taskId` and `sourceCommit` are `exact` and equal for every pair by selection. `model` is `record`. So the verdict is `drifted` for all 11 pairs and cannot predict anything. The raw trajectories and the 1,408-row annotation table were deleted after the study (`private/research/topic-04-05-source-ledger.md`), and downloading them again needs network access, which is not authorised. Even the full table has one trajectory per (model, task), so no task contains a compatible-versus-incompatible contrast. |
| AI Goat retained runs (`private/acceptance/aigoat-*`) | Real model runs against an owned target, with a deterministic oracle | **Not circular, but too small and confounded.** `aigoat-full-20260820` has 27 suite reports covering 35 challenge attempts: 31 `error` (provider, MCP timeout, snapshot and harness faults), 3 `not-observed`, and 1 `pass`. That pass is v16, a scripted replay of sealed Qwen-v10 actions, not a fresh model trial. 5 more runs have no suite report. `aigoat-20260818` has 11 arena runs, but only 3 have reports (1 `pass`, 2 `not-confirmed`). The headed replays re-run recorded actions. That leaves at most about 6 conclusive fresh-model outcomes with 1 fresh positive. Context changes (provider, model, harness v1 to v16) happened together with bug fixes. Any analysis would be post hoc, unblinded and same-team. |

**Conclusion.** Every local test is either circular (labels built from the
envelope's own rules) or degenerate or underpowered (constant verdict, about
6 conclusive outcomes). The paper should say that the envelope's predictive
validity is **untested**. The AI Goat campaign's infrastructure failure rate
(31 of 35 challenge attempts, about 0.89) is useful only as a planning input
(section 6).

## 2. Hypotheses

Frozen before any run.

- **H1 (discrimination).** RD = P(recur | compatible or drifted) -
  P(recur | incompatible) is greater than 0.
- **H2 (no over-promising).** P(recur | compatible or drifted) >=
  P(recur | unperturbed source-context control) - 0.15. This is a
  non-inferiority test: a "compatible" verdict should not be issued where
  recurrence materially drops.
- **H0.** The envelope verdict carries no information about recurrence beyond
  the marginal recurrence rate.

## 3. Design

**Units.** A *finding* is a source run on an owned or licensed target whose
deterministic oracle observed the outcome. A *cell* is one finding under one
context perturbation. A *trial* is one fresh, authorised re-execution in a
cell.

**Inclusion.** A finding enters the study only if the outcome recurs in at
least 3 of 5 fresh trials under its unperturbed source context. This control
cell is kept and analysed.

**Context dimensions and envelope.** For each finding, an envelope author
writes the envelope before any perturbed run. The author must not have seen
any perturbed outcome. The envelope declares a mode for each dimension:
model family and version, provider or runtime, decoding temperature, system
prompt and tool-schema version, tool version, target build, permission set,
memory or seed state, and browser or runtime version. The envelope is frozen
by SHA-256 digest.

**Perturbations.** Each finding gets 8 single-dimension perturbations: 4 on
dimensions the envelope declares non-material (`record`, `ignore`, or within
`tolerance`) and 4 on dimensions it declares material (`exact` or `one-of`).
Each material change is the *smallest admissible step*, taken from a
perturbation catalogue fixed in advance (for example, an adjacent minor model
version or the next tool release). Someone other than the envelope author
writes the catalogue, so incompatibility cannot be manufactured with drastic
changes such as swapping in a patched target.

**Trials.** Each cell gets r = 5 trials, plus the 5 control trials. Seeds are
fixed per trial index.

**Outcome per trial.** A trial counts as `recur` only if the finding's frozen
deterministic oracle passes **and** claim-conditioned fidelity
(`prototypes/fidelity.py: assess_fidelity` or its promoted successor) returns
`supported`. It counts as `divergent` if the oracle fails with sufficient
evidence. Otherwise it is `inconclusive`. Infrastructure failures are
recorded as such, never as outcomes.

**Predictor.** `compare_context(source, candidate, frozen_rules).status`,
computed only from recorded context fields, never from outcome events.

**Separation of roles.** The envelope author, the operator, and the analyst
who locks outcomes are three different people. Verdicts are computed only
after outcomes are locked. If the people are not independent, the result must
be labelled same-team.

## 4. Analysis

- **Primary.** The H1 risk difference at trial level, from a mixed logistic
  model `recur ~ verdict + (1 | finding) + (1 | model_family)`, with a
  cluster bootstrap by finding (10,000 resamples) as a cross-check. Primary
  grouping: compatible plus drifted versus incompatible. `unknown` verdicts
  are reported separately and excluded from the primary analysis.
- **Inconclusive trials.** Excluded from the primary estimate. Partial
  identification bounds are also reported, treating every inconclusive trial
  first as recur and then as not recur.
- **H2.** The difference compatible minus control, with a cluster-bootstrap
  95% confidence interval.
- **Baselines**, scored with the same metric:
  - B0: the marginal recurrence rate;
  - B1: model identity equal, yes or no;
  - B2: all dimensions `exact`, the strictest possible envelope.

  An embedding-similarity baseline is optional and needs its own
  authorisation, because it is a model call.
- **Reported metrics:** RD, risk ratio, PPV of "compatible", the recurrence
  rate within "incompatible" (how often the envelope is too strict), balanced
  accuracy against B0, B1 and B2, and the number of excluded and
  infrastructure-failed trials.

## 5. Success and failure criteria

| Outcome | Rule |
|---|---|
| H1 supported ("predictive") | Lower bound of the 95% CI for RD is at least 0.10 |
| H1 refuted ("not usefully predictive") | Upper bound of the 95% CI for RD is below 0.10 |
| H1 inconclusive | Anything else |
| H2 supported | Lower bound of the 95% CI for (compatible - control) is above -0.15 |
| H2 refuted ("compatible over-promises") | Upper bound of the 95% CI for (compatible - control) is below -0.15 |
| H2 inconclusive | Anything else |
| Better than B2 | Balanced accuracy beats B2 with a paired bootstrap CI excluding 0. Reported, not a gate. |

All outcomes are published, including refutations.

## 6. Sample size

Two-proportion approximation at cell level. This is conservative relative to
the trial-level model. Settings: alpha = 0.05 two-sided, power 0.80, and
P(recur | compatible) = 0.70.

| RD | Independent cells per arm | ICC 0.1 | ICC 0.2 | ICC 0.3 |
|---|---:|---:|---:|---:|
| 0.30 | 42 | 72 cells, 18 findings | 101 cells, **26 findings** | 131 cells, 33 findings |
| 0.25 | 61 | 104 cells, 26 findings | 147 cells, 37 findings | 190 cells, 48 findings |

The design effect is 1 + (m - 1) x ICC, with m = 8 cells per finding and 4
cells per arm per finding.

**Planned size:** 26 findings x (8 cells x 5 trials + 5 controls) = **1,170
fresh trials**. This must be scaled by 1 / (1 - f), where f is the
infrastructure failure rate. At the campaign's observed f of about 0.89, the
study is infeasible. Infrastructure must be hardened first. Proceed only if a
pilot shows f <= 0.20, which means 1,463 or fewer trials.

**Pilot (not confirmatory):** 6 findings x 45 trials = 270 trials. It
estimates f, the ICC and the base recurrence rate, but it does **not** look at
the association between verdict and recurrence. Sample size may be revised
once, by a rule fixed in advance, using only the pooled rate and the ICC.

## 7. Exclusions, stopping and deviations

- Infrastructure-failed trials get at most 2 logged retries. A trial that
  still fails is `inconclusive (infrastructure)`.
- A cell with more than 40% infrastructure-failed trials is excluded from the
  primary analysis but reported.
- There is no stopping rule that depends on outcomes.
- The protocol, envelopes, perturbation catalogue, oracles and analysis code
  are frozen by digest before the first perturbed run. Any change is a new
  protocol version that keeps the original and lists every deviation.
- Answer-key and outcome custody stays with the analyst, not the operator.

## 8. Safety and authorisation

- Owned or licensed targets only, such as the AI Goat challenges and other
  owned fixtures. No third-party targets.
- Each provider run needs explicit, current authorisation, with budget caps
  set in advance on calls, tokens, cost and time.
- No credentials are ever handled in chat.
- Raw traces stay private. Only aggregate, redacted results are published.

## 9. What the current paper can claim

> The envelope's compatible/incompatible verdict has not been tested as a
> predictor of outcome recurrence. All retained local data are either
> constructed with the same rules the envelope encodes (circular), hold the
> envelope verdict constant (AgentRewardBench: all eleven pairs `drifted`), or
> contain too few conclusive fresh executions (AI Goat: about six, one
> positive). A preregistered design requiring roughly 1,200 fresh,
> independently operated re-executions is specified for future work.
