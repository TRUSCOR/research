# External Validation Protocol — Topics 04–06

Private research protocol — not cleared for public release

Version: 0.1  
Date: 2026-07-31  
Owner: Gautam R. Patil, TRUSCOR Private Limited

## Purpose

This protocol defines the evidence that the current same-team deterministic
programme cannot manufacture. It prevents an external-validation hold from
becoming an indefinite or vague excuse.

## Independence rules

- Cases or labels used for the confirmatory set must be frozen by a person who
  did not implement the evaluated mechanism.
- Evaluators receive the declared behavior/evidence contract but not the
  candidate decision for a case.
- Human labels record disagreement before adjudication.
- External adapters/converters may use the public SOVA contract but must not
  import private prototypes.
- Raw per-case results, exclusions, failures, and environment fingerprints are
  retained.
- The same primary outcome and failure rules apply to favorable and
  unfavorable results.

## P4 semantic reproduction

Minimum confirmatory cohort:

- at least 120 independently authored behavior cases across security,
  evaluation, interpretability, debugging, incident, and comparison profiles;
- at least three model/runtime families and two independently operated
  environments;
- repeated trials sufficient to report per-stratum uncertainty;
- exact-trace, final-output, terminal-status, and at least one current
  trajectory/semantic baseline;
- blinded ground-truth or human labels with pre-adjudication agreement;
- version drift, missing dependency, partial evidence, stochastic response,
  incompatible context, unsafe refusal, and evidence-invalid strata.

Report macro-F1, per-class precision/recall, false equivalence, false
divergence, inconclusive rate, calibration when confidence is emitted,
reproduction-rate intervals, coverage, cost, and failures.

## P5 trace fidelity

Minimum confirmatory cohort:

- native SOVA plus OpenTelemetry/OpenInference, Inspect AI, and one additional
  incident/evaluation-log format;
- independently authored claims with required event/content/relationship/trust
  sets;
- full, partial, redacted, encrypted, omitted, corrupted, and migrated traces;
- dictionary, correlation, length, linkage, residual-secret, malformed
  placeholder, signature-policy, parser-differential, archive-resource,
  replay, and equivocation attacks;
- external verifier and privacy reviewer who did not implement the candidate.

Report field/event/relationship/query retention, false support, false
inconclusive, disclosure fraction, verification coverage, package size,
streaming/finalization/query/verification cost, and every external trust
assumption.

## P6 executor conformance

Minimum confirmatory cohort:

- one adapter authored without private SOVA implementation access;
- terminal, browser, and computer action families;
- at least two materially different execution providers;
- honest success, false success, false failure, unsupported action, weaker
  capability, evidence omission, contradictory observation, retry,
  duplicate side effect, timeout, cancellation, crash, partial result, and
  orphan-process cases;
- SOVA-owned observers kept outside the adapters.

Report false conformance, false nonconformance, inconclusive/unsupported rates,
recovery, portability failures, side-effect accounting, and end-to-end
overhead. Compare provider status, exact output, capability-only, and at least
one mature executor/record-replay baseline.

## Stop rules

- Stop and retain the negative result if a candidate fails its predeclared
  threshold.
- Do not tune on the confirmatory set and still call it held out.
- Do not replace unavailable independent labels with a model or SOVA-team
  judgment.
- Do not submit a paper until the relevant confirmatory protocol and
  limitations review pass.
- Do not disclose a held mechanism until Gautam completes the founder/IP
  decision and any chosen counsel review.

