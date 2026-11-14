# PF confirmatory protocol, extension E1: more primary models, a third blind reader, and the tasks beyond the decision

Version 1, 2026-11-14. Extends `PF-confirmatory-protocol-2026-11-14.md` (SHA-256
`117b77eb1c4814c38aec898383cc95bb1512da1d604a518f3b4859a1de6db0af`) and
`PF-head-to-head-addendum-2026-11-14.md`. Written by AI coding assistants under the author's
direction. Custody is the author's own; this file and the code below are committed to
github.com/TRUSCOR/research before any run of this extension.

## 0. What was already seen, and why this extension exists

When this extension was written, all results of the main protocol were known: the S2 scoreboard,
S3 and S4 on the reduced xAI design of deviation D2, S5, S6 and S7. In S4 the pooled gap met its
threshold, but per model it held only on GPT-4o, and with the three models weighted equally it
did not. A reviewer's criticism of the earlier version, that the prediction test rested on one
primary model, therefore still applies in part: three models with different results are a thin
basis for a pooled claim.

On the author's instruction, the remaining runs of the locked xAI design (40 findings, N1 ten
times, other conditions three times) were started at 10:47 UTC under the main protocol, with the
locked findings reconstructed by its frozen selection rule (`plan-locked.json`; the first 10 of
each half equal the D2 plan exactly). That completion is a continuation after an interim look and
is reported as such. It is not part of this extension.

This extension adds every remaining model that has enough real attacks to be a primary, under a
rule fixed here, and states its hypotheses before any of its runs. The outcomes of S3, S4 and S5 on
the added models do not exist when this file is committed.

## 1. Added primaries (S3, S4, S5)

**Rule.** Every model with at least 40 confirmed action-goal attacks (the text goal excluded) in its
trial-1 baseline runs of S2 (`s2/`) or of a full pass (`s2-grok-full/`), that is not already a
primary, is added. Applying the rule needed only those counts, which S2 had already produced:
`mistral-medium-3-5` 83, `Mistral-Large-3` 81, `grok-4-1-fast-non-reasoning` 63 (from its full
pass). Every other model has at most 10. The three added models make six primaries from four
developers (DeepSeek, OpenAI, xAI, Mistral AI).

**Findings.** For each added model, 40 findings and two halves, drawn exactly as
`analyze_pf_v2.select` draws them: `random.Random(f"20261114:{model}")`, `sample` of 40 from the
sorted eligible set, then a seeded shuffle and halves (`extend_pf_primaries.py select`, written to
`plan-extended.json`, which also holds the locked plan of the first three primaries).

**Design.** As locked for the main primaries: N1 trials 101 to 110; N2, N3, M1, M2, M3 trials 101
to 103. The M1 model for every added primary is `gpt-4o`, the fastest attack-prone deployment from
another developer. S5 adds one pair, `grok-4-1-fast-non-reasoning` to `grok-4.7` (same developer,
newer model), trials 101 to 103 on the candidate. The Mistral models have no successor deployment
and get no S5 pair. Sampling settings, attack text, runner, audit and pacing are those of the main
protocol (pace 0.92, as under D2).

## 2. Hypotheses (confirmatory for this extension)

With the frozen functions of `analyze_pf_v2.py` (`prediction`, `reliability`, `upgrade`) over
`plan-extended.json`, outcome = the audit's attacker action:

- **H1-E1 (primary):** pooled over all six primaries, recurrence under N1 to N3 minus under M1 to M3.
  Supported if the 95% lower bound is at least 0.10 (2,000 bootstrap resamples of findings within
  each primary, seed 20261113). With 40 findings per primary, the pooled mean weights the models
  equally.
- **Per model:** the same gap for each of the six; reported whatever its direction.
- **H1-dim, H2, measured rules on the calibration halves tested on the test halves, and
  leave-one-model-out over six models:** as in the main protocol.
- **Expectation stated in advance:** from the three-model results, we expect the gap to differ
  between models, the pooled lower bound to lie near the threshold, and rules measured on some
  models not to carry over to others.

The main protocol's H1 on its three primaries remains its own primary result and is reported on
the completed locked design.

## 3. Third blind reader (S7b)

`cohere-command-a` (Cohere, a fourth developer and not a primary) labels the same frozen 1,084
items with the same prompt and label set (`extend_pf_primaries.py read`). We report its agreement
with the audit and the benchmark, and pairwise kappa with the two earlier readers. Its labels do not
change any category.

## 4. The tasks beyond the decision (S6b)

The frozen `compare_pf_neighbors.py` is re-run on `plan-extended.json`, unchanged. In addition,
`compare_pf_tasks_ext.py` records, for the paper's three questions, what each system does on the
paper's data:

- T8: re-run a recorded finding on a model and report k of n (`sova rerun`, the four released
  findings, 3 trials each on GPT-4o and GPT-5.5);
- T9: check benchmark verdicts against recorded actions (`sova audit` on every released bundle);
- T10: classify known findings across a model upgrade (`sova matrix`, GPT-4o to GPT-5.5);
- T11: verify a record offline (S6 T1 and T2).

AgentTriage, ClaimReceipt and TRACE are assessed from their released code or papers; a task they
have no component for is recorded as not supported, with the reason. A task another system does
not attempt is reported as a difference in scope, not as a result in favour of `.sova`.

## 5. Budget and order

All Azure spend of the PF studies (12 to 14 November) stays within USD 700: the runner caps this
results folder at its spend when E1 starts plus USD 170. Order: commit this file and its code;
`select`; `run` and `read`; after the locked completion and E1 runs end, the analyses, S6 and S6b,
packaging, and the audit checks. Infrastructure failures stay "can't tell". Any deviation is
recorded in `PF-confirmatory-deviations-2026-11-14.md`.

## 6. Frozen files (SHA-256)

See `MANIFEST-extension.sha256` beside this file.
