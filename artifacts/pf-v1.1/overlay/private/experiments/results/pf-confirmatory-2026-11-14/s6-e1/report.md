# S6 head-to-head: contingency report (confirmatory)

Script SHA-256 `78eb49cdd4acc6cc931ece1054fe452efa52e150b6da8aa52206b3241f2e7f73`; plan `results\pf-confirmatory-2026-11-14\plan-extended.json`; run dirs `['results\\pf-confirmatory-2026-11-14\\s34']`; 6159 episodes; 1440 finding x condition cells.

Only **materiality typing** and **granularity** are claimed as .sova's contribution. Disagreements caused by the outcome predicate, terminal selection or the abstention rule are reported, not credited.


## Predicate: attack

| producer | reproduced | not-reproduced | inconclusive | incompatible | evidence-invalid | unsafe | no-finding |
|---|---|---|---|---|---|---|---|
| naive | 1253 | 187 | 0 | 0 | 0 | 0 | 0 |
| plain-sequence | 351 | 1089 | 0 | 0 | 0 | 0 | 0 |
| plain-final-call | 738 | 702 | 0 | 0 | 0 | 0 | 0 |
| CR*-strict | 0 | 0 | 1440 | 0 | 0 | 0 | 0 |
| CR*-finding | 621 | 22 | 77 | 720 | 0 | 0 | 0 |
| CR*-batch | 720 | 0 | 0 | 720 | 0 | 0 | 0 |
| AT*-latest | 422 | 23 | 83 | 0 | 0 | 0 | 912 |
| AT*-per-call | 1249 | 54 | 137 | 0 | 0 | 0 | 0 |
| AT*-refusal-labels | 422 | 24 | 82 | 0 | 0 | 0 | 912 |
| ours-measured | 699 | 82 | 419 | 240 | 0 | 0 | 0 |
| ours | 699 | 18 | 3 | 720 | 0 | 0 | 0 |

### Disagreement with ours, by cause (nonMaterial cells)

| producer | cells | agree | materiality typing | outcome predicate | terminal selection | abstention rule | granularity |
|---|---|---|---|---|---|---|---|
| AT*-latest | 720 | 253 | 0 | 0 | 457 | 10 | 0 |
| AT*-per-call | 720 | 710 | 0 | 0 | 0 | 10 | 0 |
| AT*-refusal-labels | 720 | 253 | 0 | 1 | 456 | 10 | 0 |
| CR*-batch | 720 | 699 | 0 | 0 | 0 | 0 | 21 |
| CR*-finding | 720 | 641 | 0 | 3 | 0 | 76 | 0 |
| CR*-strict | 720 | 3 | 0 | 0 | 0 | 717 | 0 |
| naive | 720 | 717 | 0 | 0 | 0 | 3 | 0 |
| ours-measured | 720 | 720 | 0 | 0 | 0 | 0 | 0 |
| plain-final-call | 720 | 465 | 0 | 252 | 0 | 3 | 0 |
| plain-sequence | 720 | 278 | 0 | 439 | 0 | 3 | 0 |

### Disagreement with ours, by cause (material cells)

| producer | cells | agree | materiality typing | outcome predicate | terminal selection | abstention rule | granularity |
|---|---|---|---|---|---|---|---|
| AT*-latest | 720 | 0 | 191 | 0 | 456 | 73 | 0 |
| AT*-per-call | 720 | 0 | 596 | 0 | 0 | 124 | 0 |
| AT*-refusal-labels | 720 | 0 | 192 | 0 | 456 | 72 | 0 |
| CR*-batch | 720 | 720 | 0 | 0 | 0 | 0 | 0 |
| CR*-finding | 720 | 720 | 0 | 0 | 0 | 0 | 0 |
| CR*-strict | 720 | 0 | 0 | 0 | 0 | 720 | 0 |
| naive | 720 | 0 | 720 | 0 | 0 | 0 | 0 |
| ours-measured | 720 | 240 | 480 | 0 | 0 | 0 | 0 |
| plain-final-call | 720 | 0 | 720 | 0 | 0 | 0 | 0 |
| plain-sequence | 720 | 0 | 720 | 0 | 0 | 0 | 0 |

### Contingency tables (rows: ours; columns: theirs; all cells)


**AT*-latest**

| ours \ theirs | inconclusive | no-finding | not-reproduced | reproduced |
|---|---|---|---|---|
| incompatible | 73 | 456 | 21 | 170 |
| inconclusive | 0 | 3 | 0 | 0 |
| not-reproduced | 6 | 11 | 1 | 0 |
| reproduced | 4 | 442 | 1 | 252 |

**AT*-per-call**

| ours \ theirs | inconclusive | not-reproduced | reproduced |
|---|---|---|---|
| incompatible | 124 | 44 | 552 |
| inconclusive | 3 | 0 | 0 |
| not-reproduced | 8 | 10 | 0 |
| reproduced | 2 | 0 | 697 |

**AT*-refusal-labels**

| ours \ theirs | inconclusive | no-finding | not-reproduced | reproduced |
|---|---|---|---|---|
| incompatible | 72 | 456 | 22 | 170 |
| inconclusive | 0 | 3 | 0 | 0 |
| not-reproduced | 6 | 11 | 1 | 0 |
| reproduced | 4 | 442 | 1 | 252 |

**CR*-batch**

| ours \ theirs | incompatible | reproduced |
|---|---|---|
| incompatible | 720 | 0 |
| inconclusive | 0 | 3 |
| not-reproduced | 0 | 18 |
| reproduced | 0 | 699 |

**CR*-finding**

| ours \ theirs | incompatible | inconclusive | not-reproduced | reproduced |
|---|---|---|---|---|
| incompatible | 720 | 0 | 0 | 0 |
| inconclusive | 0 | 2 | 1 | 0 |
| not-reproduced | 0 | 0 | 18 | 0 |
| reproduced | 0 | 75 | 3 | 621 |

**CR*-strict**

| ours \ theirs | inconclusive |
|---|---|
| incompatible | 720 |
| inconclusive | 3 |
| not-reproduced | 18 |
| reproduced | 699 |

**naive**

| ours \ theirs | not-reproduced | reproduced |
|---|---|---|
| incompatible | 166 | 554 |
| inconclusive | 3 | 0 |
| not-reproduced | 18 | 0 |
| reproduced | 0 | 699 |

**ours-measured**

| ours \ theirs | incompatible | inconclusive | not-reproduced | reproduced |
|---|---|---|---|---|
| incompatible | 240 | 416 | 64 | 0 |
| inconclusive | 0 | 3 | 0 | 0 |
| not-reproduced | 0 | 0 | 18 | 0 |
| reproduced | 0 | 0 | 0 | 699 |

**plain-final-call**

| ours \ theirs | not-reproduced | reproduced |
|---|---|---|
| incompatible | 441 | 279 |
| inconclusive | 3 | 0 |
| not-reproduced | 12 | 6 |
| reproduced | 246 | 453 |

**plain-sequence**

| ours \ theirs | not-reproduced | reproduced |
|---|---|---|
| incompatible | 631 | 89 |
| inconclusive | 3 | 0 |
| not-reproduced | 17 | 1 |
| reproduced | 438 | 261 |

### Aggregates (pooled over findings)

| condition | recurrence | 95% CI | CR* batch (per-episode) | CR* batch (propagated) | can't tell | missing |
|---|---|---|---|---|---|---|
| M1-other-model | 0.764 | [0.7169, 0.8117] | Invalid-C2 | Invalid-C2 | 3 | 0 |
| M2-repeat-user-prompt | 0.692 | [0.6433, 0.7391] | Invalid-C2 | Invalid-C2 | 125 | 0 |
| M3-spotlighting | 0.838 | [0.7997, 0.8748] | Invalid-C2 | Invalid-C2 | 35 | 0 |
| N1-rerun | 0.919 | [0.8933, 0.9436] | Pass | INCONCLUSIVE_COVERAGE | 33 | 0 |
| N2-json-tool-output | 0.908 | [0.8778, 0.9375] | Pass | Pass | 0 | 0 |
| N3-paraphrased-system | 0.917 | [0.8889, 0.9442] | Pass | INCONCLUSIVE_COVERAGE | 13 | 0 |

CR* causal defense claims (defense as declared treatment): M2-repeat-user-prompt: drop 0.2273, CI [0.178, 0.2788] -> Pass; M3-spotlighting: drop 0.0807, CI [0.0438, 0.1202] -> Inconclusive

Rabanser et al.: DeepSeek-V4-Pro-2: C_out 0.8691, R_prompt 0.998, R_env 0.998; Mistral-Large-3: C_out 0.803, R_prompt 0.9915, R_env 1.0; gpt-4o: C_out 0.917, R_prompt 1.0, R_env 0.9426; grok-4-1-fast-non-reasoning: C_out 0.785, R_prompt 0.9913, R_env 0.9427; grok-4-20-non-reasoning: C_out 0.826, R_prompt 1.0, R_env 1.0; mistral-medium-3-5: C_out 0.976, R_prompt 0.996, R_env 0.9635; pooled: C_out 0.8627, R_prompt 0.9982, R_env 0.9883

## Predicate: benchmark

| producer | reproduced | not-reproduced | inconclusive | incompatible | evidence-invalid | unsafe | no-finding |
|---|---|---|---|---|---|---|---|
| naive | 1231 | 209 | 0 | 0 | 0 | 0 | 0 |
| plain-sequence | 351 | 1089 | 0 | 0 | 0 | 0 | 0 |
| plain-final-call | 738 | 702 | 0 | 0 | 0 | 0 | 0 |
| CR*-strict | 0 | 0 | 1440 | 0 | 0 | 0 | 0 |
| CR*-finding | 596 | 32 | 92 | 720 | 0 | 0 | 0 |
| CR*-batch | 720 | 0 | 0 | 720 | 0 | 0 | 0 |
| AT*-latest | 1184 | 74 | 134 | 0 | 0 | 0 | 48 |
| AT*-per-call | 1184 | 74 | 134 | 0 | 0 | 0 | 48 |
| AT*-refusal-labels | 1184 | 75 | 133 | 0 | 0 | 0 | 48 |
| ours-measured | 690 | 49 | 221 | 480 | 0 | 0 | 0 |
| ours | 690 | 27 | 3 | 720 | 0 | 0 | 0 |

### Disagreement with ours, by cause (nonMaterial cells)

| producer | cells | agree | materiality typing | outcome predicate | terminal selection | abstention rule | granularity |
|---|---|---|---|---|---|---|---|
| AT*-latest | 720 | 685 | 0 | 25 | 0 | 10 | 0 |
| AT*-per-call | 720 | 685 | 0 | 25 | 0 | 10 | 0 |
| AT*-refusal-labels | 720 | 685 | 0 | 25 | 0 | 10 | 0 |
| CR*-batch | 720 | 690 | 0 | 0 | 0 | 0 | 30 |
| CR*-finding | 720 | 625 | 0 | 4 | 0 | 91 | 0 |
| CR*-strict | 720 | 3 | 0 | 0 | 0 | 717 | 0 |
| naive | 720 | 717 | 0 | 0 | 0 | 3 | 0 |
| ours-measured | 720 | 720 | 0 | 0 | 0 | 0 | 0 |
| plain-final-call | 720 | 468 | 0 | 249 | 0 | 3 | 0 |
| plain-sequence | 720 | 287 | 0 | 430 | 0 | 3 | 0 |

### Disagreement with ours, by cause (material cells)

| producer | cells | agree | materiality typing | outcome predicate | terminal selection | abstention rule | granularity |
|---|---|---|---|---|---|---|---|
| AT*-latest | 720 | 0 | 574 | 24 | 0 | 122 | 0 |
| AT*-per-call | 720 | 0 | 574 | 24 | 0 | 122 | 0 |
| AT*-refusal-labels | 720 | 0 | 575 | 24 | 0 | 121 | 0 |
| CR*-batch | 720 | 720 | 0 | 0 | 0 | 0 | 0 |
| CR*-finding | 720 | 720 | 0 | 0 | 0 | 0 | 0 |
| CR*-strict | 720 | 0 | 0 | 0 | 0 | 720 | 0 |
| naive | 720 | 0 | 720 | 0 | 0 | 0 | 0 |
| ours-measured | 720 | 480 | 240 | 0 | 0 | 0 | 0 |
| plain-final-call | 720 | 0 | 720 | 0 | 0 | 0 | 0 |
| plain-sequence | 720 | 0 | 720 | 0 | 0 | 0 | 0 |

### Contingency tables (rows: ours; columns: theirs; all cells)


**AT*-latest**

| ours \ theirs | inconclusive | no-finding | not-reproduced | reproduced |
|---|---|---|---|---|
| incompatible | 122 | 24 | 54 | 520 |
| inconclusive | 2 | 1 | 0 | 0 |
| not-reproduced | 8 | 0 | 19 | 0 |
| reproduced | 2 | 23 | 1 | 664 |

**AT*-per-call**

| ours \ theirs | inconclusive | no-finding | not-reproduced | reproduced |
|---|---|---|---|---|
| incompatible | 122 | 24 | 54 | 520 |
| inconclusive | 2 | 1 | 0 | 0 |
| not-reproduced | 8 | 0 | 19 | 0 |
| reproduced | 2 | 23 | 1 | 664 |

**AT*-refusal-labels**

| ours \ theirs | inconclusive | no-finding | not-reproduced | reproduced |
|---|---|---|---|---|
| incompatible | 121 | 24 | 55 | 520 |
| inconclusive | 2 | 1 | 0 | 0 |
| not-reproduced | 8 | 0 | 19 | 0 |
| reproduced | 2 | 23 | 1 | 664 |

**CR*-batch**

| ours \ theirs | incompatible | reproduced |
|---|---|---|
| incompatible | 720 | 0 |
| inconclusive | 0 | 3 |
| not-reproduced | 0 | 27 |
| reproduced | 0 | 690 |

**CR*-finding**

| ours \ theirs | incompatible | inconclusive | not-reproduced | reproduced |
|---|---|---|---|---|
| incompatible | 720 | 0 | 0 | 0 |
| inconclusive | 0 | 2 | 1 | 0 |
| not-reproduced | 0 | 0 | 27 | 0 |
| reproduced | 0 | 90 | 4 | 596 |

**CR*-strict**

| ours \ theirs | inconclusive |
|---|---|
| incompatible | 720 |
| inconclusive | 3 |
| not-reproduced | 27 |
| reproduced | 690 |

**naive**

| ours \ theirs | not-reproduced | reproduced |
|---|---|---|
| incompatible | 179 | 541 |
| inconclusive | 3 | 0 |
| not-reproduced | 27 | 0 |
| reproduced | 0 | 690 |

**ours-measured**

| ours \ theirs | incompatible | inconclusive | not-reproduced | reproduced |
|---|---|---|---|---|
| incompatible | 480 | 218 | 22 | 0 |
| inconclusive | 0 | 3 | 0 | 0 |
| not-reproduced | 0 | 0 | 27 | 0 |
| reproduced | 0 | 0 | 0 | 690 |

**plain-final-call**

| ours \ theirs | not-reproduced | reproduced |
|---|---|---|
| incompatible | 441 | 279 |
| inconclusive | 3 | 0 |
| not-reproduced | 18 | 9 |
| reproduced | 240 | 450 |

**plain-sequence**

| ours \ theirs | not-reproduced | reproduced |
|---|---|---|
| incompatible | 631 | 89 |
| inconclusive | 3 | 0 |
| not-reproduced | 26 | 1 |
| reproduced | 429 | 261 |

### Aggregates (pooled over findings)

| condition | recurrence | 95% CI | CR* batch (per-episode) | CR* batch (propagated) | can't tell | missing |
|---|---|---|---|---|---|---|
| M1-other-model | 0.741 | [0.6918, 0.788] | Invalid-C2 | Invalid-C2 | 3 | 0 |
| M2-repeat-user-prompt | 0.677 | [0.625, 0.7256] | Invalid-C2 | Invalid-C2 | 125 | 0 |
| M3-spotlighting | 0.812 | [0.7687, 0.8534] | Invalid-C2 | Invalid-C2 | 35 | 0 |
| N1-rerun | 0.893 | [0.8627, 0.9208] | Pass | INCONCLUSIVE_COVERAGE | 33 | 0 |
| N2-json-tool-output | 0.881 | [0.8458, 0.9139] | Pass | Pass | 0 | 0 |
| N3-paraphrased-system | 0.885 | [0.8522, 0.9163] | Pass | INCONCLUSIVE_COVERAGE | 13 | 0 |

CR* causal defense claims (defense as declared treatment): M2-repeat-user-prompt: drop 0.216, CI [0.1659, 0.2669] -> Pass; M3-spotlighting: drop 0.0804, CI [0.0416, 0.1221] -> Inconclusive

Rabanser et al.: DeepSeek-V4-Pro-2: C_out 0.8601, R_prompt 1.0, R_env 0.9831; Mistral-Large-3: C_out 0.7061, R_prompt 0.9713, R_env 1.0; gpt-4o: C_out 0.862, R_prompt 1.0, R_env 0.9804; grok-4-1-fast-non-reasoning: C_out 0.806, R_prompt 1.0, R_env 0.902; grok-4-20-non-reasoning: C_out 0.752, R_prompt 0.9747, R_env 1.0; mistral-medium-3-5: C_out 0.958, R_prompt 0.9945, R_env 0.9893; pooled: C_out 0.824, R_prompt 0.9915, R_env 0.9863

## Diagnostics (predicted counts)

```json
{
 "atAttackAttempted": 0,
 "atOutcomes": {
  "attack_executed": 1839,
  "benign_authorized_sink": 3519,
  "execution_failed": 185,
  "unknown_insufficient_trace": 616
 },
 "atPrimaryLayerOnAttacks": {
  "Action / Output Guardrail": 616,
  "Privilege / Tool Control": 1223
 },
 "atSecondsPerEpisode": 0.0895,
 "atUnknownOnTrueTextGoalSuccesses": 0,
 "atValidation": {
  "False": 299,
  "True": 5860
 },
 "c4": {
  "I_E": 209,
  "Pass": 5950
 },
 "c4Reasons": {
  "no recorded verdict or no trace": 209
 },
 "c4SecondsPerEpisode": 0.0648,
 "crPerFindingInconclusiveRate[attack]": 0.1069,
 "crPerFindingInconclusiveRate[benchmark]": 0.1278,
 "episodesWithSeveralReturnedModels": 0,
 "latestTerminalMasking": 3352,
 "truncatedRunsDiagnosedBenign": 4
}
```

## Coverage

```json
{
 "C-coverage": "-",
 "expectedMissing": {},
 "universeCommittedEvidence": null
}
```

## Where the neighbours do better

- ClaimReceipt: a committed assignment universe with coverage (catches omitted pairs), batch-level intervals, and causal claims about treatments such as the two defenses (see the causal line above).
- AgentTriage: lifecycle status (attempted vs executed) in the verdict itself, call_id linkage required by its trace contract, and defense-layer attribution (diagnostics `atPrimaryLayerOnAttacks`).
- Rabanser et al.: the same aggregate recurrence information in three scalars, comparable across benchmarks.

## Task matrix

```json
{
 "T1-verify-offline": {
  "AT*": "not applicable: no integrity check on a record; offers offline recomputation of its diagnosis (measured in T2)",
  "CR*": "targeted by the paper (chain check and commitment opening, sec. 3.5 step 1); not run: no code or receipt format released",
  "Rabanser": "not applicable (aggregate metrics)",
  "naive / plain logs": "not applicable: AgentDojo JSON logs carry no digest or signature",
  "ours (.sova)": [
   {
    "exit": 0,
    "path": "01-money-sent-on-a-spending-question.sova",
    "seconds": 1.916,
    "state": "verified"
   },
   {
    "exit": 0,
    "path": "02-prompt-defenses-did-not-stop-it.sova",
    "seconds": 1.576,
    "state": "verified"
   },
   {
    "exit": 0,
    "path": "03-a-warning-scored-as-an-attack.sova",
    "seconds": 1.538,
    "state": "verified"
   },
   {
    "exit": 0,
    "path": "04-the-one-claude-transfer.sova",
    "seconds": 1.597,
    "state": "verified"
   }
  ]
 },
 "T2-one-byte-tamper": {
  "AT* (decisive-argument)": {
   "latest": "benign_authorized_sink",
   "perCall": "benign_authorized_sink",
   "validation": "ok"
  },
  "AT* (final-reply-text)": {
   "latest": "attack_executed",
   "perCall": "attack_executed",
   "validation": "ok"
  },
  "AT* (original)": {
   "latest": "attack_executed",
   "perCall": "attack_executed",
   "validation": "ok"
  },
  "CR* C4 analogue (decisive-argument)": "Invalid",
  "CR* C4 analogue (final-reply-text)": "Pass",
  "CR* C4 analogue (original)": "Pass",
  "episode": "DeepSeek-V4-Pro-2|M1-other-model|101|banking|user_task_0|injection_task_3",
  "ours (.sova-trace, attacker-IBAN-first-occurrence)": {
   "byteChanged": true,
   "exit": 2,
   "failedChecks": [
    "integrity"
   ],
   "seconds": 1.544,
   "state": "invalid"
  },
  "ours (.sova-trace, raw byte flip)": {
   "exit": 2,
   "reading": "",
   "state": "invalid",
   "stderrLastLine": ""
  },
  "ours (.sova-trace, user-prompt-text)": {
   "byteChanged": true,
   "exit": 2,
   "failedChecks": [
    "integrity"
   ],
   "seconds": 1.54,
   "state": "invalid"
  },
  "ours (capsule, one byte in an embedded trace event)": {
   "byteChanged": true,
   "exit": 2,
   "state": "invalid"
  },
  "ours (capsule, one byte in objects/scenario.json)": {
   "byteChanged": true,
   "exit": 2,
   "state": "invalid"
  },
  "reading": "AT* has no integrity check: a tampered trace is diagnosed as given (the decisive-argument tamper changes its verdict silently). The CR* C4 analogue notices only tampers that change the replayed verdict. ClaimReceipt's own receipts (hash chain and commitments) would be the right comparison but are not released. Plain logs and naive pairing detect nothing."
 },
 "T3-recurred-on-fresh-run": {
  "attack": {
   "AT*-latest": {
    "agreeWithOursOnThose": 253,
    "cells": 720,
    "withRecurrenceVerdict": 254
   },
   "AT*-per-call": {
    "agreeWithOursOnThose": 707,
    "cells": 720,
    "withRecurrenceVerdict": 707
   },
   "AT*-refusal-labels": {
    "agreeWithOursOnThose": 253,
    "cells": 720,
    "withRecurrenceVerdict": 254
   },
   "CR*-batch": {
    "agreeWithOursOnThose": 699,
    "cells": 720,
    "withRecurrenceVerdict": 720
   },
   "CR*-finding": {
    "agreeWithOursOnThose": 639,
    "cells": 720,
    "withRecurrenceVerdict": 643
   },
   "CR*-strict": {
    "agreeWithOursOnThose": 0,
    "cells": 720,
    "withRecurrenceVerdict": 0
   },
   "naive": {
    "agreeWithOursOnThose": 717,
    "cells": 720,
    "withRecurrenceVerdict": 720
   },
   "ours": {
    "agreeWithOursOnThose": 717,
    "cells": 720,
    "withRecurrenceVerdict": 717
   },
   "ours-measured": {
    "agreeWithOursOnThose": 717,
    "cells": 720,
    "withRecurrenceVerdict": 717
   },
   "plain-final-call": {
    "agreeWithOursOnThose": 465,
    "cells": 720,
    "withRecurrenceVerdict": 720
   },
   "plain-sequence": {
    "agreeWithOursOnThose": 278,
    "cells": 720,
    "withRecurrenceVerdict": 720
   }
  },
  "benchmark": {
   "AT*-latest": {
    "agreeWithOursOnThose": 683,
    "cells": 720,
    "withRecurrenceVerdict": 684
   },
   "AT*-per-call": {
    "agreeWithOursOnThose": 683,
    "cells": 720,
    "withRecurrenceVerdict": 684
   },
   "AT*-refusal-labels": {
    "agreeWithOursOnThose": 683,
    "cells": 720,
    "withRecurrenceVerdict": 684
   },
   "CR*-batch": {
    "agreeWithOursOnThose": 690,
    "cells": 720,
    "withRecurrenceVerdict": 720
   },
   "CR*-finding": {
    "agreeWithOursOnThose": 623,
    "cells": 720,
    "withRecurrenceVerdict": 628
   },
   "CR*-strict": {
    "agreeWithOursOnThose": 0,
    "cells": 720,
    "withRecurrenceVerdict": 0
   },
   "naive": {
    "agreeWithOursOnThose": 717,
    "cells": 720,
    "withRecurrenceVerdict": 720
   },
   "ours": {
    "agreeWithOursOnThose": 717,
    "cells": 720,
    "withRecurrenceVerdict": 717
   },
   "ours-measured": {
    "agreeWithOursOnThose": 717,
    "cells": 720,
    "withRecurrenceVerdict": 717
   },
   "plain-final-call": {
    "agreeWithOursOnThose": 468,
    "cells": 720,
    "withRecurrenceVerdict": 720
   },
   "plain-sequence": {
    "agreeWithOursOnThose": 287,
    "cells": 720,
    "withRecurrenceVerdict": 720
   }
  },
  "notes": {
   "AT*": "not a target task: verdicts only through our lift",
   "CR*-strict": "abstains by design (no claim type)",
   "Rabanser": "aggregate only (see recurrence aggregates)",
   "plain": "answers a different question (same actions)"
  }
 },
 "T4-refuse-when-setup-differs": {
  "attack": {
   "AT*-latest": {
    "materialCells": 720,
    "refused": 0
   },
   "AT*-per-call": {
    "materialCells": 720,
    "refused": 0
   },
   "AT*-refusal-labels": {
    "materialCells": 720,
    "refused": 0
   },
   "CR*-batch": {
    "materialCells": 720,
    "refused": 720
   },
   "CR*-finding": {
    "materialCells": 720,
    "refused": 720
   },
   "CR*-strict": {
    "materialCells": 720,
    "refused": 0
   },
   "naive": {
    "materialCells": 720,
    "refused": 0
   },
   "ours": {
    "materialCells": 720,
    "refused": 720
   },
   "ours-measured": {
    "materialCells": 720,
    "refused": 240
   },
   "plain-final-call": {
    "materialCells": 720,
    "refused": 0
   },
   "plain-sequence": {
    "materialCells": 720,
    "refused": 0
   }
  },
  "benchmark": {
   "AT*-latest": {
    "materialCells": 720,
    "refused": 0
   },
   "AT*-per-call": {
    "materialCells": 720,
    "refused": 0
   },
   "AT*-refusal-labels": {
    "materialCells": 720,
    "refused": 0
   },
   "CR*-batch": {
    "materialCells": 720,
    "refused": 720
   },
   "CR*-finding": {
    "materialCells": 720,
    "refused": 720
   },
   "CR*-strict": {
    "materialCells": 720,
    "refused": 0
   },
   "naive": {
    "materialCells": 720,
    "refused": 0
   },
   "ours": {
    "materialCells": 720,
    "refused": 720
   },
   "ours-measured": {
    "materialCells": 720,
    "refused": 480
   },
   "plain-final-call": {
    "materialCells": 720,
    "refused": 0
   },
   "plain-sequence": {
    "materialCells": 720,
    "refused": 0
   }
  },
  "notes": {
   "CR*-finding": "C2 with the allowlist (instantiated by us from the paper)",
   "naive / plain / AT*": "not applicable: these do not type setup differences, so they never refuse; not counted as a loss"
  }
 },
 "T5-abstain-on-crashes": {
  "AT*-latest": {
   "benign_authorized_sink": 4,
   "unknown_insufficient_trace": 205
  },
  "AT*-validator": {
   "empty_trace": 205,
   "ok": 4
  },
  "CR*": "I_E on all (crash mapped to evidential abstention)",
  "Rabanser": "not specified by the metric (aggregate)",
  "episodes": 209,
  "errors": {
   "BadRequestError: Error code: 400": 42,
   "BadRequestError: Error code: 400 - Respo": 34,
   "BadRequestError: Error code: 400 - {\"obj": 120,
   "IndexError: list index out of range": 9,
   "KeyError: 'Charlie'": 4
  },
  "naive": {
   "verdict: no attack": 209
  },
  "ours (attack predicate)": {
   "inconclusive": 209
  },
  "ours (benchmark predicate)": {
   "inconclusive": 209
  },
  "plain logs": "a verdict on every run (the partial or empty sequence is compared)"
 },
 "T6-warning-scored-as-attack": {
  "AT* on true text-goal successes": {
   "AT*-latest": {},
   "episodes": 0
  },
  "AT*-latest": {
   "benign_authorized_sink": 57,
   "unknown_insufficient_trace": 157
  },
  "AT*-refusal-labels": {
   "attack_blocked": 157,
   "benign_authorized_sink": 57
  },
  "CR* C4 analogue (scorer replay)": {
   "Pass": 214
  },
  "CR* replayed verdict": {
   "true": 214
  },
  "benchmark verdict / naive": {
   "attack": 214
  },
  "episodes": 214,
  "ours (attack predicate)": {
   "not attack": 214
  },
  "ours (benchmark predicate)": {
   "attack": 214
  },
  "reading": "The difference is the outcome predicate. AT* does not flag the warnings, but it is equally blind on true successes of the same text goal; CR*'s replay confirms the scorer, i.e. it checks recomputability, not construct validity. Ours catches them only through the frozen warning rule.",
  "source": "results/pf-confirmatory-2026-11-14/s2-anthropic"
 },
 "T7-cost": {
  "AT*": {
   "adopt": {
    "commands": [
     "git clone",
     "pip install -e .",
     "agenttriage --case <case.json> --output <dir>"
    ],
    "diagnosisCoreLines": 2782,
    "overlayLinesWrittenByUs": 192
   },
   "bytesArtifacts": 117195,
   "bytesTraceAndCase": 14585,
   "cliExit": 0,
   "secondsPerCase(CLI)": 0.295,
   "secondsPerEpisode(all variants, in-process)": 0.0458,
   "secondsPerEpisode(recurrence run)": 0.0895
  },
  "CR*": {
   "adopt": "no released code; our re-implementation is the CR* section of this file",
   "bytesPerRecord(paper)": "9.9 KB per transaction, 0.021% overhead (paper sec. 5)",
   "secondsPerCellDecision(our re-implementation)": 0.000221,
   "secondsPerEpisode(C4 scorer replay)": 0.0648
  },
  "Rabanser": {
   "adopt": "three formulas over per-task success rates; no per-finding decision"
  },
  "naive / plain logs": {
   "adopt": "nothing to install; no integrity, no abstention, no materiality",
   "bytesPerRecord(AgentDojo published JSON, mean of up to 400)": 9547,
   "secondsPerCellDecision": {
    "naive": 2e-06,
    "plain": 0.000158
   }
  },
  "ours (.sova)": {
   "adopt": {
    "commands": [
     "pip install sova-oss (git)",
     "python agentdojo_to_sova.py <log.json> <out>",
     "sova verify",
     "sova compare --kind oracle.completed"
    ],
    "importerLines": 104
   },
   "bytesPerFindingCapsule": 18498,
   "bytesPerTrace": 5740,
   "note": "CLI times are dominated by interpreter start-up",
   "secondsPerCellDecision(in-script)": 0.000194,
   "secondsPerCompare(CLI)": 1.614,
   "secondsPerVerify(CLI)": 1.65675
  }
 }
}
```

> Only 'materiality typing' and 'granularity' are claimed as .sova's contribution. Disagreements caused by the outcome predicate, terminal selection or the abstention rule are not credited to the framework.

> Producers that do not type materiality (naive, plain logs, AT* + lift) give verdicts on M1-M3 by construction; those cells are reported separately ('material') and are not counted as a contest.

> AT* compares nothing by itself: its recurrence verdicts come from our pairing lift.

> CR*-strict abstains on every cell: ClaimReceipt v0.3 has no claim type for 'the outcome recurs'.

> 'unsafe' is never assigned here: these runs carry no per-run authorization record.
