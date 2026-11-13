# Protocol: cross-model semantic reproduction of published AgentDojo prompt-injection outcomes

Version 1.0 - frozen 2026-11-12, before any AgentDojo run log was downloaded or read
by the analyst. The only AgentDojo material inspected before freezing was the
benchmark source code (`src/agentdojo/benchmark.py`, `task_suite/task_suite.py`,
`base_tasks.py`) at commit 089ed468cf3ed0322acc66b0211f26d9d90dbf60, and the
field list of one no-attack log (`runs/gpt-4o-2024-05-13/workspace/user_task_0/none/none.json`)
reported by a web read. Custody of this freeze is same-team: its SHA-256 is
recorded in the analysis output and in the paper, but no independent party
timestamped it.

## Question

When a prompt-injection attack is recorded as successful against one model in
AgentDojo's published runs, does the same observable security outcome recur on
another model under a declared context-equivalence envelope, and how often can
the published evidence not decide?

## Data

- Source: `https://github.com/ethz-spylab/agentdojo`, directory `runs/`, at the
  commit current when fetched (recorded in the output). Code licence MIT; the
  run logs carry no separate licence statement (recorded as a limitation).
- Attack: `important_instructions` only (the attack published for the largest
  number of models).
- Pipelines: every `runs/<pipeline>` directory whose name carries no
  pipeline-level defense suffix (`-tool_filter`, `-spotlighting_with_delimiting`,
  `-transformers_pi_detector`, `-repeat_user_prompt`). Defended pipelines are
  excluded from the primary matrix and reported separately if present.
- Suites: all suites present (expected banking, slack, travel, workspace).
- Unit (attack instance): (suite, user_task_id, injection_task_id, attack_type).
- Logs are read as untrusted JSON. No AgentDojo or model code is executed.

## Per-log evidence reading

A log is **malformed** if it is not valid JSON or lacks any of `suite_name`,
`user_task_id`, `injection_task_id`, `attack_type`, `security`, `utility`,
`messages`. AgentDojo's `security` field means the injection goal was executed
(attack success). Per AgentDojo's harness, context-length, internal-server and
server errors are recorded as `utility=False, security=True`.

For the claim "the injection goal was executed in this run", the log's evidence is:

- **supported** - `security` is true, `error` is null/absent, and `messages`
  contains at least one assistant message;
- **inconclusive** - `security` is true but `error` is non-null, or the message
  trace has no assistant message (the verdict was not produced from an observed
  run);
- **not observed** - `security` is false, `error` is null/absent, and the trace
  has at least one assistant message;
- **inconclusive** - `security` is false and `error` is non-null.

## Envelope

- `suite_name`, `user_task_id`, `injection_task_id`, `attack_type`: **exact**.
- `benchmark_version`: **exact** when present in both logs; in the primary
  envelope E1 a value missing from either log makes the comparison
  **inconclusive** (missing required context). Secondary envelope E2 treats
  `benchmark_version` as **record** (divergence or absence is logged, not
  blocking).
- `pipeline_name` (model): **record** - this is the variable under study.
- `injections` (rendered injection text): **record**, because the
  `important_instructions` attack renders the target model's name into the text
  by design.

## Pairwise decision (ordered pair A -> B, per attack instance where A is supported)

Applied in this order:

1. **evidence-invalid** - B's log is malformed.
2. **unsafe** - not applicable (all runs are published benchmark runs); reported
   as zero by construction.
3. **incompatible** - an exact envelope dimension differs.
4. **inconclusive** - B's log is missing; B's evidence is inconclusive; or (E1
   only) `benchmark_version` is missing from either log.
5. **divergent** - B's evidence is "not observed".
6. **equivalent** - B's evidence is "supported".

## Estimands

- **M1 (laundered successes).** Share of `security: true` logs whose `error` is
  non-null or whose trace has no assistant message, per pipeline and overall.
- **M2 (pairwise reproduction).** For each ordered pair, counts of the six
  states; reproduction rate = equivalent / (equivalent + divergent) with a
  two-sided 95% Wilson interval; partial-identification bounds treating
  inconclusive as unresolved. Reported for E1 and E2.
- **M3 (summary).** Median and interquartile range of pairwise reproduction
  rates over ordered pairs with at least 20 conclusive comparisons; asymmetry
  |r(A->B) - r(B->A)|.
- **M4 (instance specificity).** Lift = r(A->B) / ASR(B), where ASR(B) is B's
  supported-success share over all its instances. H1: median lift > 1, i.e.
  success on A is informative about success on B beyond B's base rate; tested by
  a 95% percentile bootstrap over attack instances (2,000 resamples, seed
  20261112) of the median lift. H1 is supported if the lower bound exceeds 1.
- **M5 (published-evidence sufficiency).** Share of logs carrying
  `benchmark_version`; share with non-null `error`; share missing.
- **Baseline B1 (verdict flag only).** Pairwise decision using `security` alone,
  ignoring `error` and trace presence; report the number of B1 "equivalent"
  decisions that the procedure classifies otherwise.

## Exclusions and stopping

- A pipeline with fewer than 50% of the modal number of
  `important_instructions` logs is excluded from M2-M4 and listed.
- No further pipelines, attacks, or envelopes are added after results are seen;
  any later analysis is labelled exploratory.
- All counts, failures, and exclusions are reported.

## Limitations stated in advance

Retrospective analysis of third-party logs; outcomes are AgentDojo's own
deterministic checker verdicts, not independent labels; runs were produced at
different times by the benchmark authors, so provider-side model drift and
benchmark revisions cannot be ruled out where `benchmark_version` is absent; one
attack only; same-team analysis.
