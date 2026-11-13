# Experimental Evidence Sufficiency and Fidelity Envelope 0.1

Private research specification — not a released SOVA feature

## Purpose

This envelope determines whether retained trace evidence can support one
declared conclusion. It is downstream of trace integrity and upstream of a
finding, comparison, or reproduction-rate statement.

## Requirement

Each requirement has:

- stable ID;
- event kind;
- minimum count;
- whether full content is required;
- whether redacted content is tolerated;
- mandatory or optional status;
- optional required causal-parent kind.

## Requirement states

Precedence:

```text
invalid
omitted
missing
redacted
unverified
present
```

Definitions:

- `invalid`: structural or integrity verification failed;
- `omitted`: capture policy excluded the family and no event exists;
- `missing`: insufficient event count or required causal relationship absent;
- `redacted`: required full content was transformed or omitted;
- `unverified`: a declared signer-trust requirement did not verify;
- `present`: all declared observable requirements are present.

## Claim support

- Any non-tolerated mandatory degradation yields `inconclusive`.
- A tolerated redaction or degraded optional requirement yields `weakened`.
- Only all-present mandatory requirements and no weakening yield `supported`.

Monotonicity requirement:

> Replacing any required input with a strictly weaker fidelity state must not
> increase claim support.

Integrity and signature validity do not establish observation truth.

## Trace completeness dimensions

An implementation must report separately:

- object/package integrity;
- event-chain continuity;
- recorder-declared dropped count;
- sensor coverage;
- source emission availability;
- semantic sufficiency for this claim;
- signer-trust policy outcome.

## Disclosure closure

Given claim seed events, the planner computes the transitive in-trace parent
closure. A disclosure bundle may reveal the closure and retain commitments to
other ordered events.

The prototype commitment is:

```text
SHA-256(
  "sova-disclosure-commitment/0.1" || 0x00 ||
  32-byte nonce ||
  canonical-event-bytes
)
```

The root binds signed sequence integers and ordered commitment digests. A
revealed event includes its nonce. A hidden event does not.

The root is useful only if authenticated by a trusted source. It does not prove
hidden plaintext, recorder completeness, or event truth. This construction is
an experiment, not a novel cryptographic claim or production privacy scheme.

## Conversion rule

Every importer/exporter must map each source-required field and relationship to
`preserved`, `approximated`, `omitted`, or `unrepresentable`. A conversion must
re-evaluate dependent claim support; it cannot copy a source `supported` label
when the destination loses mandatory evidence.

## Conformance

The private vectors in the 120-case fidelity corpus and disclosure mutation
suite are normative for prototype 0.1. Real release requires independent
implementation and external-format vectors.

