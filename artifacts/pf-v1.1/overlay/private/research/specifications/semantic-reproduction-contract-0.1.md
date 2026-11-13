# Experimental Semantic Reproduction Contract 0.1

Private research specification — not a released SOVA feature

## Scope

This object defines how observable evidence from a candidate run is compared
with the material behavior declared by a capsule. It does not compare hidden
model thought, prove causal attribution, or authorize execution.

## Logical object

Until an IP/publication decision is made, a prototype may store this under the
capsule extension key `x-sova-reproduction`. The object is not part of the
public `0.1.0` schema.

```json
{
  "contractVersion": "0.1",
  "predicates": [
    {
      "id": "effect",
      "eventKind": "oracle.completed",
      "operator": "equals",
      "path": ["payload", "label"],
      "expected": "TRIGGERED",
      "required": true
    }
  ],
  "forbiddenEffects": ["network.egress"],
  "contextEnvelope": [
    {"path": ["model", "family"], "mode": "exact", "required": true},
    {"path": ["runtime"], "mode": "one-of", "allowed": ["python", "node"]},
    {"path": ["temperature"], "mode": "tolerance", "tolerance": 0.05},
    {"path": ["host"], "mode": "record"}
  ],
  "evidenceRequirements": ["trace-integrity", "oracle.completed"],
  "judge": {
    "id": "deterministic",
    "version": "0.1",
    "calibration": null,
    "limitations": ["No open-ended semantic judgment."]
  },
  "adjudication": {
    "status": "unresolved",
    "records": [
      {
        "id": "review-1",
        "adjudicatorId": "blind-reviewer-a",
        "kind": "human",
        "label": "equivalent",
        "blinded": true,
        "independentOfImplementation": true,
        "confidenceBasisPoints": 8000,
        "rationaleDigest": "sha256:<64-lowercase-hex>"
      }
    ],
    "limitations": ["Blinding and independence are externally asserted."]
  }
}
```

## Predicate semantics

Operators:

- `exists`: at least one matching observable event exists;
- `absent`: no matching observable event exists;
- `equals`: at least one visible selected value equals `expected`;
- `contains`: at least one visible selected container contains `expected`;
- `count-at-least`: matching event count is at least `minimum`;
- `ordered-before`: the first local sequence of the left kind is before the
  first local sequence of `otherKind`.

Required predicate result:

- no matching event: `fail` for existence/count/value predicates unless the
  event family was unavailable;
- event family unavailable or required value redacted: `unknown`;
- relation contradicted: `fail`;
- relation satisfied: `pass`.

The contract is `divergent` if any required predicate fails, `inconclusive` if
none fail and any are unknown, and otherwise `equivalent`.

## Context semantics

`exact`, `one-of`, and `tolerance` are compatibility-blocking.
`record` reports drift without blocking. `ignore` is explicitly non-material.
Missing required values produce `unknown`; missing optional values produce
recorded drift.

Aggregate precedence:

```text
incompatible > unknown > drifted > compatible
```

## Reproduction-decision precedence

```text
unsafe
evidence-invalid
incompatible
inconclusive from unknown required context
equivalent | divergent | inconclusive from predicates
```

No later step may upgrade an earlier safety, integrity, or compatibility
failure.

## Adjudication and disagreement

Optional adjudication records use pseudonymous adjudicator identifiers and one
of the typed labels `exact`, `equivalent`, `divergent`, `inconclusive`,
`unsafe`, `incompatible`, or `evidence-invalid`. Each record declares whether
it was blinded and independent of the implementation. A rationale can be
retained privately and bound by digest without putting its content in the
capsule.

The bridge reports label counts and `unanimous`, `plurality`, `tie`, or
`not-assessed`. A resolved record must name a selected label, method, and the
existing record IDs it considered. Neither a plurality nor a recorded
resolution silently changes the evidence-derived outcome. SOVA records the
disagreement; it does not manufacture independent review.

## Trial and estimate

Every `TrialRecord` contains:

- stable trial ID;
- one reproduction outcome;
- environment stratum;
- judge identity;
- evidence digest.

The estimate retains counts for all outcomes. It reports:

- success proportion among `equivalent + divergent`;
- Wilson interval as descriptive output;
- two-sided Clopper–Pearson interval;
- partial-identification range:

```text
lower = equivalent / (equivalent + divergent + inconclusive)
upper = (equivalent + inconclusive) /
        (equivalent + divergent + inconclusive)
```

Unsafe, incompatible, and evidence-invalid trials remain reported but do not
enter the Bernoulli denominator.

## Migration

A future schema may translate this exact object through a deterministic
registered migration. An older capsule that lacks predicates, context rules, or
evidence requirements cannot be called losslessly migrated into this contract.
The migrator must either:

1. preserve the source and mark the new semantics unavailable; or
2. refuse the transformation with an information-deficit blocker.

It must not infer intended semantic predicates from free text.

## Conformance vectors

Normative private vectors are the cases in
`private/experiments/test_research_prototypes.py` and the frozen study JSON.
An independent implementation must reproduce classifications and aggregate
values exactly for those vectors.
