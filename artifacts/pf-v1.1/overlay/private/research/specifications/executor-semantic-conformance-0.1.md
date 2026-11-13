# Experimental Executor Semantic Conformance Contract 0.1

Private research specification — not a released SOVA feature

## Inputs

- portable action intent;
- requested side-effect boundary;
- exact negotiated capability;
- provider outcome;
- required evidence roles;
- SOVA-owned post-action observations;
- retry, substitution, cancellation, timeout, and partial-result lineage.

## Output states

- `conformant`: provider constraints and every independent observation pass;
- `nonconformant`: intent, status, effect, evidence, or observation is
  contradicted;
- `inconclusive`: provider status may be successful, but a required independent
  observation is absent;
- `unsupported`: the required portable action is not supported.

## Core invariant

An executor's own `succeeded` flag cannot establish semantic conformance.
At least one observation produced by a SOVA-owned observer must satisfy every
declared observation requirement.

## Capability substitution

No substitution is implicit.

- `absent`: fail before execution;
- `weaker`: incompatible unless the contract explicitly permits it;
- `emulated`: record the emulation and its limitations;
- `different scope`: incompatible unless a new authorization and alignment
  record cover the scope;
- `newer version`: not compatible merely because its number is higher.

## Failure causality

Normalized categories remain distinct:

- target failure;
- executor/provider failure;
- policy denial;
- environment incompatibility;
- evidence failure;
- timeout;
- cancellation;
- crash;
- partial result;
- unsupported semantics.

Retry creates a new attempt linked to the earlier attempt. Every observed side
effect remains counted. A successful retry does not erase a partial or
duplicate effect.

## Reference conformance vectors

The 60-case private corpus is normative for prototype 0.1. The public
`ScriptedExecutor` and `RestrictedLocalExecutor` demonstrate two mechanics, but
release-level research validity requires an independently structured third
adapter and browser/computer action families.
