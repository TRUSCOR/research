# Post hoc analyses of preprint version 1.2

Version 1.2 is the short version of the .sova preprint. It changes no result of version 1.1 and
uses the version 1.1 artifact in `../pf-v1.1/`. It adds analyses raised in a mock review, each
marked post hoc in the paper and none in a frozen protocol:

- the scoreboard of study S2 weighted to AgentDojo v1.2.2's own goal mix, with Kendall's tau-b;
- agreement between the audit and the benchmark on the published runs;
- sensitivity checks of the comparability test (worst case for unjudged runs, models treated as a
  sample, the models added by extension E1 alone) and of extension E2 (declared rules on the same
  fresh findings, a 20,000-resample check, the non-material changes on fresh findings);
- pooled upper bounds for the upgrade checks.

`posthoc_pf_v1_2.py` computes all of them from the released result files and calls no model;
`pf-posthoc-v1-2-2026-11-17.json` is its output. To recompute, copy the script into
`../pf-v1.1/overlay/private/experiments/` (it imports `analyze_pf_v2.py` and `extend_pf_e2.py`
from there) and run `python posthoc_pf_v1_2.py`. It needs `numpy` and `scipy`.
