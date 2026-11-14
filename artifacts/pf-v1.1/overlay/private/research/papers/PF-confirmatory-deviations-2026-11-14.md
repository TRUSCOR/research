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

- the Grok 4.20 full pass was stopped at 662 of 949 runs (three were in flight when the stop was
  decided at 659), and eligibility was taken from those
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

## D2, completed (10:47 UTC)

After the first analysis of the reduced design, the author instructed that the whole locked design
be run. The locked 40 xAI findings and halves were reconstructed by the frozen selection rule
(`plan-locked.json`; the first 10 of each half equal the D2 plan exactly, and the eligible set,
351 attacks, is the same). The missing runs (N1 trials 106 to 110 and the third trial of each other
condition for the first 20 findings; the full design for the other 20; the S5 check on Grok 4.7 for
the other 20) were then made with `drive_pf_complete_locked.py`. Because they follow an interim
look at the results, the paper reports both the interim analysis (`*-d2-interim.json`) and the final
one. The Grok 4.20 full pass stays stopped at 662 runs; it served only the xAI selection, which it
had already decided.

**Budget cap for the completion.** `drive_pf_complete_locked.py` capped this results folder at USD
305 so that all Azure runs stayed within the earlier USD 500 budget. Its Grok 4.20 runs cost about
USD 0.065 each, not the USD 0.034 assumed, and the cap stopped it with 26 runs left. The author had
raised the Azure budget to USD 700, so `finish_pf_locked_runs.py` imported the unchanged frozen
script, raised only the cap, and made the remaining runs at about 12:00 UTC.

## E1. Extension (frozen 11:04 UTC, commit `6a90764`)

`PF-extension-addendum-2026-11-14.md` adds three primaries by a fixed rule (at least 40 confirmed
action-goal attacks), a third blind reader, and S6b, before any of their runs. Correction to its
section 1: the count quoted for Grok 4.1 Fast (63) is from its full pass alone; the rule as written
counts its S2 runs too, which gives 65. The rule, not the quoted count, decides the selection, and
the selected model is the same.

**S6 discovery runs under E1.** The frozen S6 script takes the first trial-1 run it finds for each
finding, from the folders in the order given. Keeping Grok 4.20's discovery runs as in the
original S6 needs the full-pass folder before `s2/`. With that order, one of Grok 4.1 Fast's 40
findings (banking `user_task_8`, `injection_task_7`), which was an attack in its S2 run but not in
its full-pass run, is paired with the full-pass run. Only the producers that read the discovery
verdict (naive pairing, AgentTriage with the pairing lift) are affected, in that finding's six cells;
`.sova`'s decision does not read it.

**Shared runs between added primaries (E1).** Some findings of the added primaries are the same
attack instance (for example, both Mistral models had slack `user_task_10`, `injection_task_3`).
Their M1 runs on `gpt-4o` have the same key, and the job list asked for them once per primary, so
the runner made 45 such runs two or three times. The frozen loader keeps one record per key (the
last), so the M1 cells of those findings are identical for the primaries that share them. The
repair of the trace file (below) keeps the same record.

**Trace file repair (E1).** From 11:04 to 12:01 UTC the locked completion and E1 both appended to
`s34/traces.jsonl.gz`. Each trace is its own gzip member, but the lock that serialises writes works
only inside one process, so two members interleaved. After both drivers had ended (19:15 UTC),
`repair_pf_traces.py` decoded every member: 2 were damaged. It kept the 5,916 intact traces, one per
run (the 5,973 episode lines held 5,919 distinct runs, the extra lines being the shared runs above),
and dropped the 3 episode records whose trace was damaged (one each on GPT-4o, Grok 4.20 and Mistral
Medium 3.5). The two drivers then re-ran those 3 runs, one after the other, and a fresh scan found
5,919 traces and no damaged member. `s34/repair-report.json` lists the three runs. The damaged
originals were saved as `*.damaged` but are not published: a leftover copy of the post-run script ran
the repair a second time at 22:34 UTC on the repaired folder, found no damage, and overwrote the saved
copies with the repaired files. That second pass left every episode record and trace unchanged; the
first pass's printed report is in the run log and in `repair-report.json`.

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

## D5. S6b results read back from the runs' own records (2026-11-14, 19:57 and 23:07 UTC)

**What.** The frozen `compare_pf_tasks_ext.py` (E1) ran every S6b task but recorded two of them
wrongly. For T8 it ran `sova rerun` on the four released findings, three runs per model on GPT-4o
and GPT-5.5; every call finished (exit 0) and wrote its runs to `s6b/rerun-*/runs.jsonl` and a
capsule. But the script kept the last line of output that parses as JSON, which for the indented
`--json` output is an inner string such as the returned model name, so `s6b-tasks.json` holds no
counts. For T10 it called `sova matrix` with a spending cap (`--max-usd 4`) but without the
prices the cap needs, and the tool refused to run (exit 2: "--max-usd needs --price-in and
--price-out").

**What was done.** Nothing in the frozen script or its output was changed. `recover_pf_s6b.py`
reads T8 from each `runs.jsonl` (24 runs, no errors) and checks each re-run capsule with
`sova verify` (8 of 8 verified). `run_pf_s6b_t10.py` made the T10 call again at 23:07 UTC with
`--price-in 2.5 --price-out 10` added (GPT-4o's prices, the higher of the two, so the cap is
conservative) and nothing else changed: 24 runs, all four findings classed as stopped, an
estimated USD 0.68. Both are in `s6b-tasks-recovered.json`, which the paper reports. T10's
GPT-4o runs used the provider's default sampling, as the frozen call did, so its baseline
counts differ from T8's, which used temperature 0.

**Why.** The runs are what S6b measures; the faults were in reading and invoking them, not in
the tool or the data.

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
  the three models weighted equally, the interim gap is 12.1 points (8.0 to 16.0), which misses
  the threshold. The paper reports this beside the interim result
  (`results/pf-confirmatory-2026-11-14/posthoc-sensitivity-d2-interim.json`). With the locked
  design completed (all 40 xAI findings), the models carry equal weight by design, and the
  frozen H1 statistic itself missed the threshold (`prediction.json`; the equal-weight check in
  `posthoc-sensitivity.json` gives 12.7, 9.2 to 16.2).

## Frozen files

After the last run, every file in `MANIFEST.sha256` and `MANIFEST-head-to-head.sha256` was
byte-identical to its published digest. The pacing change of D2 was made by the driver at run
time (`rc.PACE = 0.92`), not by editing the frozen runner.

## Run record

The driver log (`results/pf-confirmatory-2026-11-14/driver.log`) records every stage start
and finish, cost so far, and the remaining jobs per deployment. Run windows per study and
model are in the paper's Appendix A.
