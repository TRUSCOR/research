# PF extension E2: per-model measured envelopes, tested on fresh findings

Version 1, 2026-11-14. Extends `PF-confirmatory-protocol-2026-11-14.md` and extension E1
(`PF-extension-addendum-2026-11-14.md`). Written by AI coding assistants under the author's
direction. Custody is the author's own; this file and its code are committed to
github.com/TRUSCOR/research before any run of E2.

## 0. What was already seen, and why E2 exists

When E2 was written, the main protocol's S4 result on its three primaries with the locked design
complete was known: the declared envelope missed its pre-set test (gap 12.8 points, 95% interval
9.2 to 16.3). Per model it held on GPT-4o only, and rules measured on some models did not carry over
to others. E1's six-model S4 runs were still in progress, and their outcome was not known.

The paper's reading of these results is that comparability rules must be measured on the model at
hand. E2 tests that recommendation prospectively, on findings that have never been run under any
change. It does not change, replace, or re-analyse any earlier test; the main protocol's result
stands as reported.

## 1. Fresh findings

For each of the six primaries of E1 (`plan-extended.json`), 20 findings are drawn from the model's
confirmed action-goal attacks (text goal excluded) in any trial-1 baseline run we hold
(`pf-cross-provider-2026-11-13/`, `s2/`, `s2-grok-full/`), excluding its 40 S3/S4 findings and, for
DeepSeek V4 Pro, the 60 findings of the earlier addendum. Sampling: `random.Random(f"20261114:{model}:E2")`,
`sample` of 20 from the sorted pool (`extend_pf_e2.py select`, written to `plan-e2.json`).

## 2. Runs

Each fresh finding runs under N1 (unchanged), N2, N3, M1, M2 and M3, trials 201 to 203, with the
runner, attack, audit, sampling settings and M1 models of the main protocol and E1. Runs go to their
own folder (`e2/`), so no other process writes to it. The two Mistral models start only after E1's
runs on their deployments have ended.

## 3. Measured envelopes

For each model, from its 40 S3/S4 findings and all their runs, the measured rule of the main
protocol is applied to that model alone: for each change, the drop in recurrence from N1 with a 95%
bootstrap interval over findings (2,000 resamples, seed 20261113); material if the lower bound is
at least 0.10, non-material if the upper bound is below 0.10, otherwise undetermined. No E2 run
enters the envelopes.

## 4. Hypotheses (confirmatory for E2)

Outcome: the audit's attacker action. Recurrence per finding and condition is the mean over judged
runs; pooled values are means over findings; intervals use 2,000 bootstrap resamples of findings
within each model (seed 20261113).

- **H-E2 (primary):** on the fresh findings, pooled over the models whose measured envelope calls at
  least one change material, recurrence under N1 and the changes measured non-material, minus
  recurrence under the changes measured material. Supported if the 95% lower bound is at least
  0.10. Undetermined changes are left out of both sides.
- **H-E2-declared (replication):** the declared envelope (N1 to N3 against M1 to M3) on the same
  fresh findings, same criterion.
- Per model, both gaps, reported whatever their direction.

## 5. Budget

All Azure spend of the PF studies stays within USD 700: the E2 runner caps this results folder at
its spend when E2 starts plus USD 110.

## 6. Frozen files

See `MANIFEST-e2.sha256` beside this file.
