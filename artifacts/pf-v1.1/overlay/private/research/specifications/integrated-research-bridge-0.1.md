# Private integrated research bridge 0.1

Status: research prototype specification, released with the PF v1.1 artifact
(2026-11-13); not a public SOVA contract or novelty claim. (Original status
line: "implemented private candidate".)

## Purpose

This bridge tests whether the three surviving Topics 04–06 research hypotheses
can operate as one reproducible system rather than as disconnected algorithms:

1. a `.sova` capsule carries versioned semantic, fidelity, and executor
   contracts in the opaque `x-truscor-research` extension;
2. an authorized public runner executes portable intent through either the
   scripted or restricted-local executor;
3. the public recorder creates a structurally verified `.sova-trace`;
4. the private bridge derives semantic-reproduction, claim-conditioned
   evidence-fidelity, and evidence-based executor-conformance results from that
   same verified trace;
5. every result binds the exact capsule and trace digests and renders without
   executing capsule content.

## Contract and validation

The current version is `0.1.0`. The normative private schema is
`research-extension-0.1.schema.json`; the implementation also performs bounded
manual validation so malformed input produces stable `FormatError` codes.
Unknown root fields are rejected. Experimental third-party material may be
retained only below the explicit `extensions` object.

The contract records:

- observable outcome predicates and required context dimensions;
- a named, versioned judge plus calibration/uncertainty limitations;
- optional typed human/model/rule adjudication records, including blinded and
  implementation-independent flags, confidence, rationale digests, explicit
  disagreement, and a resolution that must cite existing records;
- per-claim evidence requirements, capture requirements, causal parent
  requirements, and redaction allowances;
- portable executor intent, permitted terminal states, side-effect class,
  evidence roles, SOVA-owned observations, and trusted observer identifiers.

No field represents hidden model thoughts or chain-of-thought.

## Trace interpretation

The bridge verifies package descriptors and the event hash chain before
evaluation. A complete trace with a captured-but-absent event can support an
absence or failure conclusion. A partial, crashed, or recovered prefix cannot
turn an unobserved required event into a definite absence; it becomes unknown.
Reported provider success is insufficient for executor conformance unless the
contracted SOVA-owned observer event is present and satisfies the observation.

An observer identifier is a provenance label, not proof of independence,
truth, calibration, or trustworthy instrumentation. A cryptographically valid
trace can still contain false observations from a compromised recorder,
sensor, oracle, or signer.

Adjudication records never silently override the evidence-derived semantic
decision. The report exposes whether labels are unanimous, plural, tied, or
absent and whether the records claim blinding or implementation independence.
Those flags are assertions requiring external verification; they are not
created or certified by SOVA.

## Migration

The only registered migration is `0.0.1 -> 0.1.0`. It:

- deterministically maps `semantic`, `claims`, and `executorContracts` into the
  three current contract sections;
- preserves unknown legacy root fields under
  `extensions.x-legacy-unknown`;
- appends a machine-readable migration record;
- retains every capsule object byte and content descriptor while repackaging;
- refuses missing required legacy information, unsupported versions,
  in-place conversion, and destination overwrite.

This is forward preservation, not a claim of universal losslessness or
bidirectional conversion.

## Operations

`private/experiments/research_cli.py` exposes private-only `validate`,
`evaluate`, `render`, and `migrate` operations. Evaluation and rendering are
inert. Re-execution remains a separate public operation requiring fresh
authorization.

## Known limitations and falsification conditions

- same-team synthetic labels do not establish external or real-model validity;
- current contracts evaluate deterministic observable predicates, not semantic
  meaning inferred from hidden state;
- a trusted-observer allow-list is operator policy, not remote attestation;
- offline verification cannot detect byte-identical replay or valid-signer
  equivocation without trusted external freshness state;
- a candidate is falsified if it accepts provider self-report without required
  SOVA observations, treats partial absence as definite, hides evidence loss,
  or changes a source object during migration.
