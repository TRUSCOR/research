# PF confirmatory protocol: deviations and run record

Companion to `PF-confirmatory-protocol-2026-11-14.md` (frozen in github.com/TRUSCOR/research
commit `c7e3fb4`, 2026-11-14 05:57 UTC) and `PF-head-to-head-addendum-2026-11-14.md` (commit
`5a2ad61`, 06:41 UTC). Section 7 of the protocol requires every deviation to be recorded with
its time and reason and reported in the paper. Times are UTC on 2026-11-14. Custody is the
author's own.

## D1. Order of runs (about 06:30)

**What.** S3 and S4 for `DeepSeek-V4-Pro-2` and `gpt-4o` started before the xAI primary was
chosen, while the Grok full passes were still running. GPT-4o's M1 condition, whose
alternative model is the xAI primary, waited for the choice.

**Why.** To save time. The findings of these two models depend only on their own earlier
passes and a per-model seed, not on the xAI choice.

**Check.** The final `analyze_pf_v2.py select` must reproduce the findings and halves already
in use. The driver compared `plan.json` with `plan-run1.json` and logged "findings identical
= True" for both models before running any further job.

## D2. Smaller xAI design and higher pacing (about 07:40)

**What.** The selection rule chose `grok-4-20-non-reasoning` as the xAI primary: 349 confirmed
action-goal attacks in 659 completed full-pass runs, against 63 for
`grok-4-1-fast-non-reasoning` in 949. The remaining 290 runs could not change the choice.
Then:

- the Grok 4.20 full pass was stopped at 659 of 949 runs, and eligibility was taken from those
  runs;
- the xAI primary got the first 10 findings of each locked half (20 instead of 40);
- N1 ran 5 times (trials 101 to 105) instead of 10, and N2, N3, M1, M2 and M3 twice (trials
  101 and 102) instead of three times;
- the pacing limit rose from 70% to 92% of each deployment's token and request limits, for
  all deployments.

DeepSeek and GPT-4o kept the full design. GPT-4o's M1 runs on Grok 4.20 kept trials 101 to
103. The S5 check from Grok 4.20 to Grok 4.7 used the 20 xAI findings with 3 trials each.

**Why.** Grok 4.20 used about 99,000 tokens per episode (7.5 model calls on average), about
two episodes per minute at 70% of its rate limit. The full design would have taken about
eight hours, past the time available.

**Effect.** Wider intervals for the xAI primary. ClaimReceipt's coverage check in S6 reports
the comparison as incomplete for this reason (100 N1 and 20 runs per other condition fewer
than the locked design). No S3 or S4 outcome had been computed when the change was made.

## D3. S6 scope (06:41, in the frozen addendum)

**What.** The protocol listed TRACE among the S6 systems. The S6 addendum, frozen before S6
ran, dropped it.

**Why.** A TRACE record keeps a digest of the tool transcript, not an event stream, so it
gives no recurrence verdict to compare. The paper's Appendix C.3 describes what an import
from TRACE loses.

## D4. Order of S6 and S7

**What.** Section 6 of the protocol ran S7 (blind reading) before S6 (head-to-head). S6 ran
first, at about 08:10, on the complete S3 and S4 data.

**Why.** S6 uses no reader output, its data were complete earlier, and S7 waited for the last
S2 runs, which it samples.

## Not deviations

- Infrastructure failures (HTTP errors, content-filter blocks, malformed tool calls, rate
  limits after retries) are kept as "can't tell" and never removed, as the protocol requires.
- S5 had no Claude Opus 4.5 pair: Opus 4.5 had no confirmed action-goal attack, so the
  protocol's rule selected no finding to check.
- `sova` product fixes made during the day (structured errors for damaged files, distinct
  names for repeated runs, auditing capsules, pinned method and taxonomy digests) changed
  packaging and reporting only. The research audit (`audit_pf.py`) and the analysis
  (`analyze_pf_v2.py`) are the frozen files.

## Corrections and post-hoc analyses (not deviations from the design)

- **Published folder count.** Section 1 of the protocol says the published runs come in 29
  folders. AgentDojo's published `runs/` directory has 28 model folders with
  `important_instructions` runs (two of them, Llama 3.3 70B and Meta-SecAlign 70B, record the
  pipeline name `local`). The audit read all of them; the paper says 28.
- **Several-action goals.** An early note split the 433 executed-but-unscored runs of S1 into
  264 one-step and 169 multi-step goals; that split could not be reproduced. The paper uses an
  explicit list of the ten goals whose text asks for several state-changing actions (Appendix
  B): 307 one-action and 126 several-action runs.
- **banking `user_task_15`.** 21 of the 433 runs are on a task whose older published wording
  names the attacker's account as the landlord's new account in the user's own request, so the
  transfer may be what the user asked for. A blind reader flagged one. The paper reports at
  least 412 attacker actions the benchmark did not count.
- **Equal weighting of the primary models (after review).** The frozen H1 statistic is a mean
  over findings. D2 cut the xAI model, whose gap was smallest, from 40 findings to 20. With
  the three models weighted equally, the gap is 12.1 points (8.0 to 16.0), which misses the
  threshold. The paper reports this beside the frozen result
  (`results/pf-confirmatory-2026-11-14/posthoc-sensitivity.json`).

## Frozen files

After the last run, every file in `MANIFEST.sha256` and `MANIFEST-head-to-head.sha256` was
byte-identical to its published digest. The pacing change of D2 was made by the driver at run
time (`rc.PACE = 0.92`), not by editing the frozen runner.

## Run record

The driver log (`results/pf-confirmatory-2026-11-14/driver.log`) records every stage start
and finish, cost so far, and the remaining jobs per deployment. Run windows per study and
model are in the paper's Appendix A.
