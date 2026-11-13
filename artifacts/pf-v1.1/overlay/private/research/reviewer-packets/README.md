# SOVA Topics 04–06 Independent Review Packets

Private handoff material — do not publish or send before founder/IP review

Owner and corresponding author: Gautam R. Patil, TRUSCOR Private Limited  
Contact: gautam@truscor.org

## What this packet can and cannot establish

The accompanying offline tool validates record shapes, freezes content
digests, separates blinded P4 cases from labels, and computes deterministic
metrics after label release. It cannot verify a person's identity,
independence, competence, consent, confidentiality, or truthfulness. Those are
human governance facts and must be documented separately.

Copy the matching single-record examples from `templates/` when authoring
JSONL inputs or reviewer outputs. They contain synthetic placeholders only and
must not be mistaken for completed cases or evidence.

An external library, model, subagent, second parser, or SOVA-team member is not
an independent reviewer.

As of 2026-08-01, the SOVA team has completed the bounded graph/calibrated-
semantic baselines for P4 and the incident-format, official-Collector, privacy-
attack, and synthetic 50,000-event scale studies for P5. Reviewers should be
given those retained results after founder/IP clearance and asked to challenge,
repeat, and extend them. They must not be told that those same-team results are
expected truth or asked merely to endorse them.

## P4 — blind semantic-reproduction cohort

The independent case author runs:

```text
python -m private.experiments.external_review_kit prepare-p4 authored.jsonl frozen-p4
```

They retain `p4-sealed-labels.jsonl` and send only:

- `p4-blinded-cases.jsonl`;
- `p4-cohort-manifest.json`.

The SOVA team freezes one prediction per case with `caseId`, `outcome`,
`evidenceDigest`, and optional `confidenceBasisPoints`. The SHA-256 prediction
digest is returned to the case author. Only then does the case author release
the exact sealed-label file whose digest is already in the manifest.

Scoring is performed with:

```text
python -m private.experiments.external_review_kit score-p4 \
  p4-cohort-manifest.json p4-blinded-cases.jsonl predictions.jsonl \
  p4-sealed-labels.jsonl p4-score.json
```

The confirmatory cohort requires at least 120 independently authored cases,
all six SOVA profiles, all seven declared failure/drift strata, multiple
model/runtime families, and two independently operated environments. The
software enforces the case count, profiles, strata, exact case set, digests,
and label-release boundary. Environment operation and independent authorship
remain externally audited assertions.

## P5 — privacy, integrity, and interoperability review

Before handoff, the SOVA team freezes the complete hostile and interoperability
case matrix:

```text
python -m private.experiments.external_review_kit prepare-p5 authored.jsonl frozen-p5
```

The reviewer returns one finding for every frozen case. The finding must retain
adverse dispositions rather than converting limitations or trust dependencies
into passes. Validate and summarize the returned record with:

```text
python -m private.experiments.external_review_kit score-p5 \
  frozen-p5/p5-review-manifest.json frozen-p5/p5-review-cases.jsonl \
  findings.jsonl p5-score.json
```

The reviewer receives only the release-candidate public trace specification,
schemas, dependency-free verifier instructions, a hostile corpus, and the
claim matrix. They should attempt at minimum:

- dictionary recovery and compromised-key analysis;
- within/across-context correlation and linkage;
- ciphertext length and trace-structure inference;
- malformed placeholder and residual-secret cases;
- corruption, truncation, reorder, substitution, parser differential, and
  archive-resource attacks;
- signer equivocation and replay as explicitly offline-undetectable controls;
- Inspect, OpenTelemetry/OpenInference, and one additional external-log
  conversion with per-claim loss accounting;
- verifier disagreement and policy confusion.

The reviewer must distinguish an implementation defect, specification defect,
unsupported claim, privacy limitation, usability failure, and external-trust
requirement. A valid signature or hash chain is never treated as truth,
freshness, signer honesty, or non-repudiation.

## P6 — external executor adapter

The adapter author receives only the public executor contract and conformance
input/output schema. They must not receive private prototype code or expected
decisions. The adapter must exercise terminal, browser, and computer families
across at least two materially different providers and retain unsupported,
false-success, false-failure, omission, contradiction, retry, duplicate-effect,
timeout, cancellation, crash, partial-result, and orphan-process cases.

Provider self-report is not sufficient evidence. SOVA-owned observers remain
outside the adapter. Ordinary host-process restriction must not be called a
security sandbox.

The case custodian freezes at least 90 cases, including at least 30 per action
family, two provider identifiers, and every required failure stratum:

```text
python -m private.experiments.external_review_kit prepare-p6 authored.jsonl frozen-p6
```

The adapter author receives `p6-blinded-cases.jsonl`, not the labels. After the
adapter runs, SOVA freezes decisions plus evidence and adapter-run digests. The
custodian releases the sealed labels only after receiving that prediction
digest. Scoring also requires a signed-or-otherwise-authenticated human
declaration that the adapter was independently implemented and that private
SOVA implementation code was not received:

```text
python -m private.experiments.external_review_kit score-p6 \
  frozen-p6/p6-cohort-manifest.json frozen-p6/p6-blinded-cases.jsonl \
  predictions.jsonl frozen-p6/p6-sealed-labels.jsonl \
  adapter-declaration.json p6-score.json
```

The tool validates only artifact shapes, digests, case coverage, and the
presence of assertions. It cannot authenticate the person, prove independence,
or prove that the providers were materially different.

## Human records Gautam must retain

- reviewer name and affiliation, kept private if requested;
- competence basis and conflict-of-interest statement;
- exact packet digest and review dates;
- confidentiality and data-handling agreement;
- pre-adjudication labels and disagreements;
- raw findings, including unfavorable results;
- any compensation, consent, ethics, or institutional-review determination;
- permission before naming or acknowledging the reviewer publicly.

These packets are preparation for external validation. They do not authorize
contact, submission, publication, public disclosure, patent filing, or use of
any person's name.
