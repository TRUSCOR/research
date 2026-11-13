# Topics 04–06 Fresh Falsification Review

Private founder-review record — 2026-07-31

## Review question

What would make the current `.sova`, `.sova-trace`, semantic-reproduction,
evidence-fidelity, and executor conclusions false, unsafe, or materially
overstated?

## Defects found and corrected

1. **Scaffolding had previously been mistaken for research completion.**
   The private roadmap now requires a mechanism, primary prior art, baselines,
   preregistration, experiments, ablations, limitations, reproducibility,
   safety, interoperability, and separate paper/patent decisions.

2. **Exact comparison could hide recorder loss.**
   The public comparator now verifies both traces and returns inconclusive when
   either recorder reports dropped events, uses non-full capture, or lacks a
   selected event family.

3. **Legitimate opaque secret references were rejected by capsule packaging.**
   Packaging now distinguishes strictly shaped `sova-secret:` references from
   actual embedded secret material. Malformed/plaintext references fail before
   a capsule is written.

4. **Provider exceptions could escape orchestration without a finalized
   trace.** The runner now emits a crash outcome and deliberately omits the
   provider exception message, which may contain sensitive target data.

5. **The first uncertainty rule was too optimistic.**
   Worst-cell Wilson coverage was 0.914 and failed. The result remains in the
   record. A disclosed protocol amendment added an exact interval whose
   minimum analytic grid coverage was 0.956; this established method is not
   claimed as novel.

6. **Local CPU, memory, and process-count settings looked like promises.**
   The backend now refuses them before process creation because ordinary host
   execution cannot enforce them portably.

7. **Background process support lacked ownership and cleanup semantics.**
   Handles are now executor-owned, supervised, bounded, terminally collected,
   and cleaned on close.

8. **The integrated semantic evaluator initially treated trace fidelity as a
   report beside the conclusion.** A complete trace missing mandatory
   evidence could therefore retain an `equivalent` result. Fidelity is now
   evaluated first and any mandatory `inconclusive` support state forces the
   semantic decision to `inconclusive`.

9. **A partial prefix with no terminal provider result was initially called
   nonconformant.** Absence is not contradiction. The conformance mechanism
   now returns `inconclusive` unless independent evidence contradicts the
   declared effect.

10. **Reference oracle output was not visibly distinguishable from executor
    output.** Public oracle events now identify producer
    `sova:actor:oracle`. This records provenance but does not establish truth,
    infallibility, or organizational independence.

11. **The prior Inspect AI repository pin had drifted.** The source ledger and
    bounded JSON adapter now pin exact commit
    `1ea01a9e1b3c94db3cdf93ce5583ffebf86e159f`, exact source files, and
    EvalLog version 2. Binary `.eval` interoperability remains explicitly out
    of scope.

12. **One-language independent verification was weaker than the exit wording
    implied.** The Python verifier now optionally checks required-key
    DSSE/Ed25519 signatures, and a separate dependency-free Node.js verifier
    independently parses archives, verifies chains/manifests, and checks the
    same signature binding. Both still remain same-team implementations.

13. **The Inspect adapter had been validated against a synthetic layout rather
    than the pinned official fixture.** The official EvalLog v2 fixture places
    events under `sample.transcript.events`; the original flat assumption would
    have silently imported zero events. Adapter 0.2 now requires the official
    layout, imports all 11 source events, and refuses the flat shape.

14. **Transcript-only Inspect support was still too narrow.** Across thirteen
    official JSON logs, adapter 0.2 accepted 5/13 and typed-refused eight.
    Adapter 0.3 added explicit transcript, legacy-flat-event, and
    no-event-stream handling and produced 280/280 verified events on the
    unchanged corpus. The 5/13 result remains retained.

15. **External experts do not always agree.** Seven of twenty-two
    AgentRewardBench trajectories contained categorical disagreement. The
    paired rule yielded four inconclusive outcomes rather than silently
    converting disagreement into equivalence.

16. **Structural baselines can hide evidence classes.** Harness Evals exact,
    tool-argument, and tool-correctness baselines produced two, three, and five
    false-equivalence decisions on the frozen seven-case corpus because the
    binary matchers do not represent incompatible, inconclusive, and unsafe.

17. **Generic telemetry is not a lossless SOVA trace.** Official OTLP protobuf
    preserved its declared transport fields but could not reconstruct SOVA
    authorization, safety, capture-redaction proof, monotonic ordering, or the
    event hash chain.

18. **Supported Python minor versions might change stable decisions.** Isolated
    runs on CPython 3.11–3.14 produced identical stable integrated and vertical
    decision digests on one host. This falsifier did not trigger, but a second
    machine remains untested for the private mechanism.

## Falsification attempts that passed

- malformed, duplicate-key, invalid-Unicode, traversal, oversized, corrupted,
  truncated, reordered, substituted, signature-confused, and hostile-extension
  artifacts fail visibly;
- migrations refuse unknown required behavior and never invent absent
  historical information;
- exact source manifests and migration provenance remain recoverable;
- redaction placeholders and records must agree;
- secret-shaped values, malformed secret references, and provider failure
  details do not enter normal durable evidence;
- six audience profiles build, execute, verify, and render using one capsule
  core;
- false provider success without SOVA-owned observation is never accepted as
  conformant in either private conformance corpus;
- recomputing a package manifest around a changed segment does not defeat the
  event-chain verifier;
- loss of mandatory evidence changes a supported semantic conclusion to
  inconclusive;
- Python and Node.js independent verifiers agree on canonical digests and
  required-key signature policy and reject the tested chain/key mutants;
- the pinned Inspect JSON adapter omits content by default and reports
  unsupported fields rather than claiming losslessness;
- the thirteen-log Inspect corpus produces 280/280 verified events with every
  import marked lossy and zero known forbidden-content findings; twenty-two
  AgentRewardBench trajectories produce verified action-digest/expert-label
  traces and capsules with excluded goal, reasoning, screen,
  accessibility-tree, URL, chat, and annotator content;
- securesystemslib accepts the valid SOVA DSSE envelope and rejects five
  mutation/key controls; rfc8785.py agrees on all 65 shared-domain canonical
  values; official OTLP protobuf makes mapping losses explicit;
- pinned AgentEvals 0.0.9 strict, unordered, superset, and graph-strict
  matchers run directly on the seven-case integrated corpus; each matches 2/7
  multi-valued labels, exposing the different treatment of context, safety,
  contradictory observations, and missing evidence without mischaracterizing
  AgentEvals;
- same portable intent survives scripted and local mechanics while
  platform-specific output variation is explicit;
- optional Codex access failure is visible and does not weaken mandatory
  offline gates.

## Remaining falsifiers not yet defeated

1. A blind third-party implementation may interpret the private semantic
   contract differently.
2. Real model/provider drift may defeat the current typed predicates or make
   context dimensions insufficient.
3. Human judges may disagree with the constructed ground truth or show poor
   calibration.
4. An external trace converter may silently lose a relationship not exercised
   by the current Inspect/OTLP/STIX/Collector cases.
5. Dictionary, correlation, structure, length, and usage-pattern attacks may
   undermine a proposed disclosure policy.
6. Browser/computer providers may expose side effects that the current
   filesystem/process conformance corpus does not model.
7. A malicious allowlisted executable can escape the semantic restrictions of
   an ordinary host process. `RestrictedLocalExecutor` is not a sandbox.
8. Same-team corpus construction can inflate apparent accuracy.
9. Reviewed patents and papers may not exhaust relevant prior art.
10. A valid signer, recorder, sensor, oracle, or model can still lie.
11. The completed small WebGraphEval-style and calibrated semantic-text
    baselines did not erase the candidate's multi-valued advantage, but direct
    `agrepl` execution or a broader independently labelled corpus may do so.
12. The retrospective two-model WebArena cohort may be unrepresentative and is
    not controlled re-execution.
13. The 50,000-event same-host synthetic envelope may conceal production
    collector, backend, distribution, and random-access failures.

## Gate result

- Public engineering foundation: **PASS**, bounded to experimental 0.1.
- Internal preliminary mechanisms: **PASS-BOUNDED**.
- Stable 1.0: **HOLD**.
- Publication submission: **HOLD**.
- Broad novelty/patent claims: **NO-GO**.
- Narrow private counsel screening: **GO**.
- “Revolutionary,” state-of-the-art, universal, unforgeable, deterministic
  stochastic rerun, hidden-thought capture, or security-sandbox claims:
  **NO-GO**.
