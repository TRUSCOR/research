# Topic 04-05 research source ledger

Status: internal working record, written before publication; released unchanged in
content with the PF v1.1 artifact (2026-11-13). It is a source ledger, not a novelty or
legal opinion. (Original status line: "PRIVATE WORKING RECORD - DO NOT PUBLISH".)
Owner: Gautam R. Patil
Organization: TRUSCOR Private Limited
Contact: gautam@truscor.org
Last reviewed: 2026-08-01

## Scope and conclusion

This ledger supports the `.sova` capsule and `.sova-trace` design gates. It is
not a legal opinion or an exhaustive freedom-to-operate search.

The reviewed record contains extensive prior art for:

- workflow and program execution recording/replay;
- reproducible machine-learning experiment packages;
- provenance and lineage graphs;
- event-trace interoperability;
- content-addressed packages;
- cryptographic attestations and tamper-evident logs;
- AI/agent observability and evaluation logs.

Accordingly, SOVA must not claim novelty for those broad concepts. The research
question worth testing is narrower: whether a portable, typed AI-behavior
capsule can preserve enough scenario, trace, environment, evidence, evaluation,
and provenance semantics to support safe inspection, controlled re-execution,
and measured semantic reproduction across materially different agent runtimes.

## Primary standards and specifications

| Source | Exact use in SOVA | Limits |
|---|---|---|
| JSON Schema 2020-12, https://json-schema.org/draft/2020-12 | Structural schemas and conformance fixtures | Does not define behavior, integrity, or execution safety |
| RFC 8259, https://www.rfc-editor.org/rfc/rfc8259 | UTF-8 JSON interoperability and strict parsing baseline | Permits implementation differences that SOVA must narrow |
| RFC 8785, https://www.rfc-editor.org/rfc/rfc8785 | Canonical JSON for stable digests and signatures | Numeric and Unicode constraints require hostile-input tests |
| W3C Trace Context, https://www.w3.org/TR/trace-context/ | Cross-system trace and parent identifiers | Correlation is not proof or causal truth |
| OpenTelemetry core semantic conventions 1.43.0, commit `89aae438b3b3b0a8dd33003c9d70592baf7dbd0d`, https://opentelemetry.io/docs/specs/semconv/ | Span/event/resource import and export | The separate GenAI repository is not part of this release |
| OpenTelemetry GenAI repository, commit `434c91dcc34ed038e3048c07720ddfed2c6bddfc`, https://github.com/open-telemetry/semantic-conventions-genai | Exact-commit experimental GenAI mapping | No release tags or stable Schema URL were available at review |
| OpenInference semantic conventions 0.1.30, commit `789d41974c08a9a13147977f28ef4142a07e2106`, PyPI sdist SHA-256 `81fece76e09c83789e35c393b8b30523481eeabf1008745b955631a53e3221d9`; OpenInference instrumentation 0.1.56, commit `a374cbdcec6bf712a005549d15293c57c27cd109`, sdist SHA-256 `c43bea7f1f4460fe13c3c88aff092500cc3397aaffea37188d72246489dcbc9f`; OpenTelemetry SDK 1.44.0, commit `53a5a40c9604583c501bcf13970a635f00e62df4` (Apache-2.0), https://github.com/Arize-ai/openinference | AI model, agent, tool, retriever, embedding, reranker, guardrail, evaluator, prompt, and chain telemetry mappings. The official OITracer emitted one valid-ID LLM span; the six used constants and all eleven 0.1.30 kinds matched. The public importer omitted the emitted input/output by default and reported every loss; explicit preserve mode retained and labelled both sensitive | Telemetry is lossy relative to SOVA evidence requirements; 0.1.30 has no `MEMORY` span kind; the scenario, harness, and interpretation remain same-team rather than an independently operated producer or reviewer |
| MCP specification, https://modelcontextprotocol.io/specification/ | Tool/resource/prompt observations and consent boundaries | Protocol logs do not supply SOVA authorization or truth |
| A2A protocol, https://a2a-protocol.org/latest/ | Agent task/message/artifact interchange mapping | A2A artifacts are not SOVA evidence roots |
| in-toto Attestation Framework 1.2.0 Statement/v1, https://github.com/in-toto/attestation/blob/v1.2.0/spec/v1/statement.md | Digest-bound typed attestations | Attestation does not prove an observation was honest |
| DSSE 1.0.2, https://github.com/secure-systems-lab/dsse/blob/master/protocol.md | Type-bound signature envelope and PAE | `keyid` is a routing hint; trust policy and key provenance remain operator decisions |
| Sigstore bundle, https://docs.sigstore.dev/about/bundle/ | Optional portable verification material | Online transparency is optional, never required for local use |
| OCI image specification descriptors, https://github.com/opencontainers/image-spec/blob/main/descriptor.md | Media type, digest, size, and content-addressed references | OCI distribution is optional, not the native runtime |
| RO-Crate 1.3, https://www.researchobject.org/ro-crate/specification/1.3/index.html | Research object and dataset packaging lessons | Too general to define executable agent scenarios |
| W3C PROV-O, https://www.w3.org/TR/prov-o/ | Provenance vocabulary and export | Native SOVA model remains smaller and execution-aware |
| CycloneDX 1.7, https://cyclonedx.org/specification/overview/ | Component, dependency, service, model, and provenance export | SBOM/ML-BOM is only one capsule view |
| Citation File Format 1.2.0, https://citation-file-format.github.io/ | Publication authorship and citation export | Citation metadata is not artifact identity |
| DataCite Metadata Schema 4.7, https://schema.datacite.org/versions.html | Research-object citation/export mapping | Metadata export is not native behavior semantics |
| CloudEvents 1.0.2, https://github.com/cloudevents/spec/tree/ce@v1.0.2 | Optional event-envelope projection | Envelope metadata is not evidence, ordering, or authorization |
| OASIS STIX 2.1 and Incident Core Extension, https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html and https://github.com/oasis-open/cti-stix-common-objects/tree/main/extension-definition-specifications/incident-core | Explicitly lossy incident-case interchange | STIX does not preserve SOVA's event chain, authorization, replay procedure, redaction history, or DSSE trust policy |
| RFC 3161 and RFC 9162, https://www.rfc-editor.org/rfc/rfc3161.html and https://www.rfc-editor.org/rfc/rfc9162.html | External timestamp and transparency verification model | Time/inclusion does not prove event truth; pinned authorities remain required |
| RFC 9901, https://www.rfc-editor.org/rfc/rfc9901.html | Salted selective-disclosure prior art | Not adopted as the native trace format |
| NIST SP 800-38D and RFC 9180, https://csrc.nist.gov/pubs/sp/800/38/d/final and https://www.rfc-editor.org/rfc/rfc9180.html | AES-GCM and recipient key-wrapping design constraints | Nonce and key lifecycle are critical. The 2026-08-01 same-team attack study measured exact unpadded ciphertext-length leakage, 512/512 distinct nonces, and compromised-key dictionary recovery. Optional authenticated power-of-two length buckets were implemented as ordinary padding hardening, not a novel cryptographic construction; bucket, path, presence, structure, key-compromise, and malicious-recorder risks remain |

## Primary implementation references

| Source | Observation applied |
|---|---|
| Inspect AI eval logs, https://inspect.aisi.org.uk/eval-logs.html; official fixture repository commit `1ea01a9e1b3c94db3cdf93ce5583ffebf86e159f`; Inspect AI package 0.3.251 at `8f92b6ed30bde33a3c40879492ee8e0900cb26c4`, wheel SHA-256 `6f18df2f14dd0646db78eaffe0db6d7735334450fdd4e03ec8f45b42a669b0fe` (MIT) | JSON and optimized `.eval` logs, versioned schema/API, incremental sample access, deduplication, zstd compression, partial-log handling, and replayable run configuration show that rich agent evaluation logs can remain practical. A frozen thirteen-file JSON corpus first falsified adapter 0.2's transcript-only assumption: 5/13 imported and eight typed-refused. Adapter 0.3 handled three layouts and produced 280/280 verified events. The official 0.3.251 reader then parsed ten small pinned `.eval` fixtures. Adapter 0.3 initially accepted 9/10 and typed-refused the v3 condensed-message fixture; adapter 0.4 accepts v3 only after official-reader expansion (`events_data` null) and still fails closed on unexpanded pooled data. The unchanged binary corpus then produced 483/483 verified events from 358 source events and 31 incrementally read samples, with every import declared lossy and zero known forbidden-content probes | The package/fixture commits differ by one day; the official reader, not SOVA, owns binary parsing. These are public test logs in a same-team study, not production adoption or broad Inspect compatibility. Raw fixtures and converted JSON are not redistributed |
| AgentRewardBench, arXiv `2504.08942`, https://agent-reward-bench.github.io; official demo Space commit `271f96552e2e6dd13fe8e3572f0e5264039f6fd0` | Expert annotations cover success, side effects, and looping across real-model web-agent trajectories. The pinned annotation table contained 1,408 rows and four benchmarks. All twenty-two cleaned WebArena demo trajectories—two model families across eleven shared tasks—became 22 verified traces and capsules using only task/model provenance, step count, action verb/digest, and expert categorical labels. Goals, raw reasoning, arguments, screenshots, accessibility trees, URLs, chat messages, and annotator identity were omitted. Paired results were two equivalent, five divergent, and four inconclusive, with expert disagreement in seven trajectories. The Space metadata did not assert a source-data licence, so source bytes are not redistributed; the retrospective same-team SOVA interpretation is not blind calibration or controlled re-execution |
| LangChain AgentEvals 0.0.9, https://github.com/langchain-ai/agentevals (MIT), https://pypi.org/project/agentevals/0.0.9/ | The official deterministic evaluators support strict, unordered, subset, superset, tool-argument, and graph-trajectory comparison without an LLM call. In the post-result seven-case integrated study, strict, unordered, superset, and graph-strict modes each matched 2/7 multi-valued SOVA labels: they accepted equal structure despite incompatible context, unsafe comparison, and contradictory oracle evidence, and called missing-evidence cases divergent rather than inconclusive. This is a direct mature-library baseline on constructed SOVA cases, not proof of superiority on AgentEvals' intended tasks |
| Harness Evals 0.15.0, repository commit `7828ffa93c597c9e66a866a122c62a21e94376e0`, https://github.com/harness/harness-evals (Apache-2.0) | ExactMatch, ToolArgumentMatch, and ToolCorrectness were executed as independently maintained deterministic baselines on the frozen seven-case corpus. They matched 3/7, 2/7, and 2/7 respectively, with two, three, and five false-equivalence decisions; none natively represents incompatible, inconclusive, or unsafe. This is an external implementation over same-team cases, not a state-of-the-art claim |
| securesystemslib 1.4.0, commit `8416c50ec6814762b32db08ab37fd2e495e771a4` (MIT); rfc8785.py 0.1.4, commit `65ecc7d2b065d79a99e7a6a2f9aaa9d689db1c53` (Apache-2.0) | securesystemslib independently accepted the SOVA DSSE envelope and rejected payload/signature mutation, wrong key, key-ID mismatch, and non-canonical substitution. rfc8785.py agreed on 65/65 values in SOVA's shared canonical domain while confirming the deliberate binary-float boundary. These are cross-library compatibility checks, not identity, freshness, truth, non-repudiation, or full-JCS claims |
| OpenTelemetry protobuf 1.44.0, commit `d2d893fefdbabae63762e328688ea1c97c04cb24` (Apache-2.0) | The official protobuf round trip preserved identifiers, parent, links, time, attributes, event count, and an unknown external attribute. Export and import remained explicitly lossy for SOVA ordering, clock, redaction, authorization, safety, attempt, and hash-chain semantics. No collector or hosted backend was used |
| OASIS `cti-python-stix2` 3.0.2, commit `679bfe0befae5c39143cedcdc3cacf97ac31c890` (BSD-3-Clause), wheel SHA-256 `f4814d29ebc332c92694fc8ddc96a4a5bfe2eac08494c0dec219719e7e654eb3` | The official parser accepted one SOVA-derived STIX 2.1 incident bundle. Its explicitly lossy import emitted a seven-event verified trace and preserved custom references to the source trace digest and chain root. This proves one metadata interchange path, not incident truth, full-fidelity conversion, or broad format compatibility |
| OpenTelemetry Collector Contrib v0.157.0, official Windows archive SHA-256 `7b3938e1522ff04261a694a58e7111c5f7cdd19be617c3a77118cffad7abb815`, extracted binary SHA-256 `76146071912cc973553058795b7bb1b0c839991757257dabfce2d99fa89e26be`, https://github.com/open-telemetry/opentelemetry-collector-releases/releases/tag/v0.157.0 | A local-only official Collector accepted eight OTLP/HTTP protobuf spans and wrote eight records with trace IDs, span IDs, and required SOVA projection attributes preserved. No hosted backend, account, credential, or external pipeline network was used; this is one Collector/file-exporter path, not production certification |
| Model2Vec 0.8.2, commit lineage pinned through `minishlab/potion-base-8M` commit `bf8b056651a2c21b8d2565580b8569da283cab23` (MIT), Model2Vec wheel SHA-256 `f0ecfe994316e401dca583fbf6dd22079d308c05717dd36d40bff60f265431cf`, https://github.com/MinishLab/model2vec | CPU semantic-text baseline. Platt calibration on STS Benchmark train labels achieved held-out STS test Brier 0.1267 and ECE10 0.0382; on eleven AgentRewardBench pairs it matched 7/7 conclusive labels but could not represent four inconclusive cases. The out-of-domain, post-result threshold is not independent SOVA calibration |
| STS Benchmark via MTEB commit `96943a16ea6a35129e253c659081cb59daf81b30`, https://huggingface.co/datasets/mteb/stsbenchmark-sts | 8,628 human-labelled sentence pairs supplied train/validation/test calibration splits without test refit | Dataset licence was not asserted in the retrieved metadata; no source sentences are retained or redistributed, and sentence similarity is not agent-behavior validity |
| WebGraphEval, OpenReview `IPpOtWGmdf`, https://openreview.net/forum?id=IPpOtWGmdf | A deterministic two-pass edit-similarity adaptation of its action-graph construction matched 5/7 conclusive AgentRewardBench labels and missed both equivalent pairs | SOVA did not reproduce the paper's LLM canonicalizer or necessity annotations; the study is post-result, same-team, and far below the intended corpus scale |
| OpenInference semantic conventions 0.1.30 and instrumentation 0.1.56 at the commits and PyPI hashes above; OpenTelemetry SDK 1.44.0 (Apache-2.0) | The official OITracer emitted one LLM span with nonzero 32/16-hex identifiers, official service resource identity, and the 0.1.30 span-kind attribute. The six used constants and all eleven 0.1.30 kinds matched. Default SOVA import excluded the emitted input/output, while explicit preservation retained both and labelled them sensitive. This checks a real external library producer in a same-team harness, not an independently operated system, backend, privacy review, or causal validity |
| Astral uv 0.11.3 managed CPython builds, https://docs.astral.sh/uv/guides/install-python/ | Private tests and stable decision slices passed on CPython 3.11.15, 3.12.13, 3.13.12, and 3.14.3 with identical canonical digests on one Windows host. This is cross-version evidence, not independent cross-machine replication |
| MLflow tracing, https://mlflow.org/docs/latest/genai/tracing/ | OTel-compatible agent/model/tool/retriever/memory tracing supports an adapter-first capture strategy |
| PyTorch reproducibility, https://pytorch.org/docs/stable/notes/randomness.html | Exact reproducibility is not generally guaranteed across releases, platforms, or devices; SOVA must separate playback, re-execution, and semantic reproduction |
| TransformerLens, https://transformerlensorg.github.io/TransformerLens/ | Activation capture and interventions belong in an optional interpretability profile, not the portable minimum core |

## Patent prior-art signals

These records were reviewed as prior-art signals. Claims and legal status need
qualified patent counsel before any filing or freedom-to-operate conclusion.

| Publication | Priority / theme | Relevance |
|---|---|---|
| US8032831B2, "Computer-implemented workflow replayer system and method" | 2003-09-30; historical workflow capture and visual replay | Broad workflow recording and replay is old |
| US9170915B1, "Replay to reconstruct program state" | workflow history used to reconstruct application state | Event-history-driven deterministic replay is established |
| US8578340B1, "Recording and replaying computer program execution with recorded execution event breakpoints" | nondeterministic inputs, ordered events, replay | Execution-event recording/replay is established |
| US10802822B2, "System and method for reproducible machine learning" | environment, data, code, hyperparameters, hashes | ML experiment reproducibility packages and fingerprints are established |
| US11829853B2, "Systems and methods for tracking and representing data science model runs" | environment/dependency capture, provenance, reruns | Shareable reproducible model runs are established |
| US10540624B2 / US20180025307A1, "System and method to automate provenance-aware application execution" | provenance graph, inputs/outputs, recorded subsequences | Provenance-aware re-execution is established |
| US11853304B2, "System and method for automated data and workflow lineage gathering" | workflow events and lineage proxy | Automatic lineage capture is established |
| US20170032151A1, "Event log tamper detection" | signatures/hashes tied to event records | Signed tamper-detection records are established |
| US11295031B2, "Event log tamper resistance" | chained/double signatures across records | Tamper-resistant log chaining is established |
| US11368307B1, "Tamper-resistant, multiparty logging and log authenticity verification" | multiparty log integrity and ordering | Authenticity verification for event logs is established |

## Interoperability conclusion

SOVA should use a small native semantic core and versioned adapters:

1. Native SDK capture for loss-minimized SOVA events.
2. OpenTelemetry/OpenInference import for broad adoption.
3. Protocol taps for MCP, A2A, and AG-UI.
4. Importers for common evaluation and tracing logs.
5. Optional research-profile attachments for activations or internal probes.

Imported telemetry must carry an explicit fidelity report. Missing SOVA
authorization, safety, redaction, and evidence fields cannot be invented.

## Research hypotheses to test

H1: A small typed core plus content-addressed optional objects can represent
security, evaluation, interpretability, incident, and research cases without
forcing every producer to emit every field.

H2: SOVA native capture and OTel/OpenInference import can preserve the same
behavioral outcome meaning even when low-level event fidelity differs.

H3: A declared semantic outcome contract can support useful cross-runtime
reproduction rates without claiming deterministic equality.

H4: Different disclosure mechanisms may offer measurable verification utility
at different leakage cost. Keyed HMAC is only a private, context-bound equality
token and is not assumed to be a public selective-disclosure proof.

## 2026-07-30 implementation audit result

- SOVA canonical JSON now uses RFC 8785 UTF-16 member ordering, Unicode scalar
  validation, exact I-JSON integers, and a no-binary-float subset.
- Canonical content digest, exact package digest, and per-object digests are
  separate.
- Attachments use `blobs/sha256/<hex>` and exact-byte deduplication.
- Migration preflight refuses semantic invention, preserves exact source
  manifest bytes in package migration, and reports classification, assumptions,
  preserved unknowns, blockers, source-manifest digest, and source-package
  digest.
- OTel projection derives valid identifiers, preserves SOVA IDs, and uses Span
  Links for additional causal parents.
- An independent Python verifier validates capsules and redacted traces in a
  separate process without importing the SOVA implementation and can
  optionally verify DSSE/Ed25519 with the signing dependency.
- A dependency-free Node.js verifier independently validates canonical
  packages, trace chains, redactions, DSSE/Ed25519, and required-key policy;
  same-artifact content and package digests agree cross-language.
- These are established engineering mechanisms and do not change the HOLD /
  NO-GO novelty decisions.

## Required experiments

- Corpus pressure across at least six profiles and two runtimes.
- Native-vs-import fidelity and loss accounting.
- Package size and parse-time measurements under lite, standard, forensic, and
  interpretability capture profiles.
- Tampering, truncation, event insertion, reordering, attachment substitution,
  zip-bomb, path-traversal, duplicate-key, invalid-Unicode, and signature tests.
- Redaction attacks covering dictionary guessing, correlation, length leakage,
  structure leakage, and secret-shaped environment values.
- Exact playback, controlled re-execution, and semantic reproduction reported
  as three separate outcomes.

## 2026-07-31 corrected-goal prior-art refresh

This refresh was performed before implementing the corrected Topics 04–06
research candidates. Sources were opened at their primary publication,
standards, official project, or patent records. Recent preprints remain
unreviewed prior-art signals and are not treated as independently replicated
results.

| Source | Verified proposition | Consequence for SOVA |
|---|---|---|
| NIST AI 800-2 Initial Public Draft, https://doi.org/10.6028/NIST.AI.800-2.ipd | Reproducible automated evaluation requires model/version, protocol, data, assumptions, transcripts where appropriate, and uncertainty reporting | SOVA must preserve evaluation context and uncertainty; this is not itself novel |
| NIST AI 800-3, https://doi.org/10.6028/NIST.AI.800-3 | Generalized linear mixed models can estimate generalized accuracy and decompose evaluation variance more correctly than naive benchmark summaries | A simple success percentage is not a defensible universal reproduction metric; hierarchical/context variance is a required baseline |
| ReliableEval, DOI `10.18653/v1/2025.findings-emnlp.594` | Meaning-preserving prompt perturbations and repeated stochastic evaluation address prompt sensitivity | SOVA cannot claim novelty for repeated semantic variants or stochastic evaluation broadly |
| Semantic-Eval, DOI `10.18653/v1/2025.acl-long.477` | Graph/NLI-based semantic generation evaluation can correlate with human judgments | Typed outcome contracts must be compared with semantic-text metrics and calibrated judges |
| WebGraphEval, OpenReview `IPpOtWGmdf` | Canonical graph abstraction supports cross-agent trajectory comparison beyond final binary outcomes | Trajectory normalization and graph comparison are direct baselines |
| Deterministic Replay for AI Agent Systems / `agrepl`, arXiv `2607.16200` | Transport interception can replay external interactions in isolation and classify signal/noise divergence | Exact playback and HTTP record/replay are not SOVA novelty; semantic reproduction must be distinguished. A bounded normalized request/outcome interaction comparator matched 3/7 constructed multi-valued labels, but this is only a controlled request-key comparison—not a direct `agrepl` execution or transport-isolation result |
| Shepherd, arXiv `2605.10913` | Typed Git-like agent execution traces can fork and replay past state | Typed traces, branching, and replay are not broad novelty claims |
| Proof of Execution, arXiv `2607.05397` | A contract, causal event stream, replay context, validator invariants, and authority separation can support bounded runtime guarantees | SOVA must not claim novelty for contract-plus-trace validation or authority-plane separation generally |
| No Certificate, No Execution, arXiv `2605.24462` | Certified traces and proposal/certification/execution separation are active research directions | SOVA authorization and permissibility mechanisms require direct comparison |
| PROV-CONSTRAINTS, W3C Recommendation 2013, https://www.w3.org/TR/prov-constraints/ | Provenance validity, normalization, and equivalence are formally defined for PROV instances | Provenance normalization/equivalence are established; SOVA's delta must concern observable AI-behavior conclusions and fidelity |
| PROV-AQ, W3C Note 2013, https://www.w3.org/TR/prov-aq/ | Provenance records are not automatically authoritative or correct | SOVA must separate integrity/provenance from observation truth |
| OpenTelemetry Semantic Conventions 1.43.0, https://opentelemetry.io/docs/specs/semconv/ | Common semantic attributes enable cross-platform telemetry correlation | SOVA should map, version, and report loss rather than replace OTel |
| Sigstore Bundle Format 0.3.2, https://docs.sigstore.dev/about/bundle/ | Bundles carry verification material, signatures, timestamps, and transparency information for offline verification | SOVA should remain compatible and make trust policy explicit; bundle mechanics are established |
| US12287728B1 | Deterministic replay of recorded user/AI-generated interface events with simulated time and queues | Broad interface/session replay claims are blocked |
| US11032065B2 | Salted log hashes can permit verification of a redacted audit-log structure while hiding selected messages/salts | Broad verifiable-redaction and salted-log claims are blocked |
| US11886557B1 | Auditable Merkle trees support selective attribute hiding/disclosure | Broad Merkle selective-disclosure claims are blocked |
| US20110078666A1 | Output-deterministic replay can search for a different execution that exhibits the same output | “Same material output without identical execution” has old direct prior art |

### 2026-08-01 executor-conformance refresh

This pass was performed while expanding the P6 working paper. It used the
official specifications and primary paper records current at review time.

| Source | Verified proposition | Effect on P6 |
|---|---|---|
| MCP specification revision `2025-11-25`, https://modelcontextprotocol.io/specification/2025-11-25 | MCP already standardizes protocol/version negotiation, capability surfaces, tools, resources, tasks, lifecycle, errors, and cancellation behavior | Capability negotiation, protocol adapters, and ordinary executor lifecycle are not P6 novelty |
| WebDriver BiDi Working Draft, 1 June 2026, https://www.w3.org/TR/2026/WD-webdriver-bidi-20260601/ | Browser commands are asynchronous, can complete out of order, and have typed results, errors, events, sessions, and capabilities; WPT supplies an implementation test suite | Browser command normalization and conformance testing are direct baselines; P6 must test semantic effects beyond protocol success |
| OpenTelemetry Semantic Conventions `1.43.0`, https://opentelemetry.io/docs/specs/semconv/ | Common trace/event/resource semantics support cross-runtime correlation; the GenAI conventions are separately versioned/experimental | P6 should map and report telemetry loss, but correlation and common attributes do not prove an effect |
| Deterministic Replay for AI Agent Systems, arXiv `2607.16200` | Transport interception, isolated replay, request-key matching, and noise-aware divergence are implemented and evaluated | Exact transport record/replay and request matching are not P6 contributions |
| Shepherd, arXiv `2605.10913` | A functional meta-agent runtime records typed agent-environment events in a Git-like trace with fork/replay | Typed execution traces, state forks, and replay are not P6 contributions |
| Proof of Execution, arXiv `2607.05397` | Contract, causal event stream, replay context, validator invariants, and separated authority planes can yield bounded runtime guarantees under explicit assumptions | Contract-plus-trace validation and authority separation are blocked as broad novelty claims; P6 must compare and narrow to four-state evidence-bounded executor conformance |
| Execution Lineage, arXiv `2605.06365` | Artifact-producing computations can be represented as a dependency DAG with stable intermediate boundaries and identity-based replay | Execution DAGs and lineage-based replay are not P6 novelty |

The P6 candidate therefore remains the narrower interaction of exact portable
intent, declared side-effect and evidence-role requirements, separately
attributed post-action observations, retry/partial lineage, and a four-state
decision that preserves `inconclusive`. Its internal perfect scores are only
executable-specification evidence. Third-party adapters, browser/computer
actions, a second provider, blinded labels, component ablations, and end-to-end
cost are mandatory before a paper claim.

### Corrected novelty boundary

The following are **not** candidate inventions on the reviewed record:

- a portable archive or manifest;
- typed agent events;
- content addressing, canonical JSON, hash chains, signatures, DSSE, Sigstore,
  transparency material, or Merkle inclusion;
- deterministic fixture playback, interface replay, state forking, transport
  replay, or workflow reconstruction;
- repeated stochastic trials, Wilson/Bayesian intervals, GLMMs, semantic text
  similarity, or LLM judges in isolation;
- provenance normalization/equivalence;
- adapter protocols, capability negotiation, retries, or conformance testing
  in isolation;
- redaction, encryption, commitments, or selective disclosure in isolation.

The research candidates that remain `HOLD` are narrower:

1. a contract that binds typed observable behavior, allowed semantic variation,
   execution-context equivalence, evidence sufficiency, and uncertainty into a
   portable cross-runtime reproduction decision;
2. claim-conditioned evidence-fidelity propagation that makes capture,
   redaction, omission, conversion, and trust losses mechanically alter which
   AI-behavior conclusions remain supportable;
3. executor semantic conformance in which portable intent is judged from
   SOVA-owned post-action evidence while adapter mechanics, substitutions,
   retries, partial observability, and side effects remain explicit.

These are hypotheses, not novelty conclusions. They require implementation,
strong-baseline comparison, ablation, real-system evidence, a fuller patent
search, and qualified counsel before any patent or novelty claim.

## 2026-07-31 second novelty and paper-readiness refresh

This pass specifically searched for behavioral contracts, evaluation
reproducibility records, trajectory comparison, semantic vulnerability
reproduction, and recent patent applications. It further narrows the candidate
claims.

| Source | Verified proposition | Effect on SOVA |
|---|---|---|
| ReproEvalCard, ACL 2026, DOI `10.18653/v1/2026.acl-short.22`, https://aclanthology.org/2026.acl-short.22/ | A lightweight reporting standard already specifies prompts, judges, retrieval snapshots, intermediate traces, randomness controls, and other artifacts needed to reproduce LLM-pipeline evaluations | Packaging evaluation-critical artifacts and calling them a reproducibility record is not enough for novelty; `.sova` must demonstrate machine-executable, evidence-bounded cross-runtime outcome semantics |
| ContractEval, Findings of ACL 2026, DOI `10.18653/v1/2026.findings-acl.2112`, https://aclanthology.org/2026.findings-acl.2112/ | Explicit behavioral contracts and verifier-backed tests are an active evaluation approach | “Use a behavioral contract” is not novel; SOVA's candidate must concern portable observable behavior plus context/evidence degradation and multi-run decisions |
| Phoenix / “Security Is Relative,” arXiv `2604.19012`, https://arxiv.org/abs/2604.19012 | Behavioral-contract synthesis plus a contract judge is proposed for vulnerability detection | Broad security behavioral contracts and contract judging are blocked as novelty claims |
| PoC-Adapt, arXiv `2604.06618`, https://arxiv.org/abs/2604.06618 | Structured pre/post state semantic oracles are used to validate vulnerability reproduction | Broad semantic-oracle vulnerability validation is blocked; SOVA must compare directly before any security-reproduction claim |
| WebGraphEval, OpenReview `IPpOtWGmdf`, https://openreview.net/forum?id=IPpOtWGmdf | Canonical action graphs compare multi-path trajectories across agents | SOVA cannot claim general trajectory normalization/comparison; outcome-contract evaluation must state what graph structure it ignores or preserves |
| AgentHER, arXiv `2603.21357`, https://arxiv.org/abs/2603.21357 | Failed trajectories can be semantically relabeled with multi-judge verification | Trajectory relabeling and multi-judge validation are direct evaluation baselines |
| Causal Agent Replay, arXiv `2606.08275`, https://arxiv.org/abs/2606.08275 | Counterfactual interventions and repeated stochastic run-forward estimate causal effects with intervals | Causal reproduction is a separate, stronger baseline; current Topics 04–06 work must not imply causal attribution |
| CAR-bench, ACL 2026, DOI `10.18653/v1/2026.acl-long.1886`, https://aclanthology.org/2026.acl-long.1886/ | Agent evaluation can explicitly score uncertainty, missing capabilities, dialogue, tool use, and policy adherence | SOVA's incompatible/inconclusive states must be compared with capability- and uncertainty-aware agent benchmarks |
| US20260056752A1, https://patents.google.com/patent/US20260056752A1/en | Saved historical batches may be rerun and semantically compared using an LLM or embeddings to detect drift | Broad cross-version semantic comparison of agent outputs is patent-blocked |
| US20260121859A1, https://patents.google.com/patent/US20260121859A1/en | Evidence packs, deterministic ordering, context identifiers, numeric tolerance, semantic-equivalence rules, lineage, replay, and supported/contradicted classifications are disclosed in an AI-governance setting | Combining evidence packs, context, tolerances, and deterministic semantic rules is dangerous prior art for a broad SOVA claim; any candidate claim needs a narrower AI-behavior trace/fidelity/reproduction interaction and counsel review |
| US20250315683A1, https://patents.google.com/patent/US20250315683A1/en | AI-agent chains of repeatable actions can be saved, triggered, and reused for similar workflows | Repeatable agent workflow/scenario claims are blocked |
| Agent Behavioral Contracts, arXiv `2602.22302`, https://arxiv.org/abs/2602.22302 | Design-by-contract ideas are applied to autonomous-agent behavior specifications and runtime enforcement | Behavioral contracts and runtime enforcement are direct prior art; SOVA's candidate must remain narrowed to evidence-bounded portability, fidelity loss, and multi-run interpretation |

### Updated paper decision

The work is **paper-worthy as a precise research programme and preliminary
mechanism**, not yet publication-ready as an empirical result. A private
manuscript is justified because the combination being tested is narrower than
the individual prior-art components:

1. declared observable outcome predicates;
2. an explicit execution-context equivalence envelope;
3. claim-conditioned evidence sufficiency that can force `inconclusive`;
4. multi-valued reproduction states that do not collapse unsafe,
   incompatible, or invalid evidence into ordinary failure;
5. recomputable repeated-trial estimates with conservative bounds for
   inconclusive trials.

The current synthetic results show that the reference logic implements its own
ground-truth construction. They do not establish real-system generalization,
human-judge validity, adoption, or superiority over full external systems.

## 2026-07-31 external implementation and corpus refresh

The subsequent external-validation pass moved the evidence beyond one-fixture
imports and same-code tests:

- thirteen pinned official Inspect JSON logs were imported after an initial
  5/13 result falsified a transcript-only assumption; the corrected unchanged
  corpus emitted and verified 280/280 events with explicit loss reports;
- twenty-two pinned real-model WebArena trajectories with external expert
  annotations became verified traces and capsules, producing eleven
  multi-valued cross-model comparisons;
- three Harness Evals implementations were run directly on the frozen
  semantic corpus;
- securesystemslib, rfc8785.py, and the official OTLP protobuf implementation
  independently exercised signature, canonicalization, and transport
  boundaries; and
- the stable private decisions repeated identically on CPython 3.11 through
  3.14 on one host.

This changes the paper decision from “synthetic preliminary only” to
**PASS-BOUNDED external empirical evidence, PAPER HOLD**. The mechanism is now
paper-worthy as a private research candidate with concrete external results,
but not submission-ready. Purpose-built blind labels, controlled independent
re-execution, independent privacy/security review, and a broader
interoperability corpus remain necessary. The patent decision remains **HOLD
FOR FOUNDER AND COUNSEL SCREENING**; the external results improve enablement
but do not establish novelty or non-obviousness.
Publication remains `HOLD` pending external-runtime and independent-label
experiments.

### Updated patent decision

A **private invention disclosure is warranted** for counsel screening of the
specific combined mechanism. This is a `GO` to prepare and review a disclosure,
not a conclusion of novelty or patentability and not authorization to file or
publish. Broad file-format, behavioral-contract, evidence-pack, semantic-oracle,
trace, replay, tolerance, statistics, or adapter claims remain `NO-GO`.

## 2026-08-01 graph, semantic, incident, Collector, and scale refresh

This final machine-executable pass closed the previously identified same-team
baseline and infrastructure gaps without changing the external-review gates:

- P4 added a deterministic WebGraphEval-style graph adaptation and a
  Model2Vec semantic-text baseline calibrated on frozen STS Benchmark splits.
  The graph method matched 5/7 conclusive AgentRewardBench labels; the semantic
  method matched 7/7, but both forced all four inconclusive cases to divergent.
  The result therefore supports the value of an evidence-sufficiency state; it
  does not establish superiority, independent calibration, or controlled
  reproduction.
- P5 added an official-parser OASIS STIX 2.1 incident projection, an official
  checksum-verified OpenTelemetry Collector v0.157.0 OTLP/HTTP-to-file path,
  and signed 1,000/10,000/50,000-event synthetic traces. Every scale case passed
  required-key verification, indexed query, payload-minimized disclosure, and
  dependency-free Python/Node digest agreement.
- Two complete P5 runs had identical normalized semantic-invariant digest
  `0c7cd3e0143c589d6faf386f090ef0195e6d5143cbccbe602032b6a6383669e4`.
  Compressed package sizes varied slightly because each run generated fresh
  identifiers and signatures; timings and bytes are not claimed deterministic.
- All downloaded raw AgentRewardBench, STS, model, Collector, and distribution
  inputs were removed after pinned digests and minimized result artifacts were
  retained. The underlying sources can be reacquired; source content is not
  redistributed.

Updated decision: the predeclared graph-or-transport plus calibrated-semantic
baseline gate and the same-team incident/Collector/synthetic-scale gates are
**PASS-BOUNDED**. P4 and P5 remain **HOLD-EXTERNAL** for independently authored
labels or cases, independently operated systems, and privacy/security review.
These results strengthen the papers but do not establish patent novelty or
non-obviousness; counsel screening remains required for every narrow invention
candidate.

## 2026-08-01 publication-process verification

| Source | Verified proposition | Effect on P4-P6 |
|---|---|---|
| arXiv submission guidance, https://info.arxiv.org/help/submit/index.html | arXiv is a moderated public preprint repository; a registered author submits source/PDF, chooses a distribution licence, and may face category or technical moderation | Source packages may be prepared privately, but public posting requires Gautam's account, licence, category, rights, and final-submit decisions; arXiv posting is not peer-reviewed acceptance |
| arXiv endorsement guidance, https://info.arxiv.org/help/endorsement.html | first submission to a category can require community endorsement; endorsement is an access control, not scientific validation | endorsement cannot be fabricated or treated as peer review |
| ResearchGate preprint guidance, https://help.researchgate.net/hc/en-us/articles/14293104044177-Preprints | an author can add a public or private preprint and must have the right to upload it | ResearchGate is a distribution/visibility path after founder/IP clearance, not a peer-review venue |
| ResearchGate DOI guidance, https://help.researchgate.net/hc/en-us/articles/14293044585745-ResearchGate-DOIs | a public preprint can receive a DOI; DOI-bearing items have correction and replacement consequences | DOI creation must wait for an author-approved stable version and must not be represented as peer-reviewed publication |
| ResearchGate copyright guidance, https://help.researchgate.net/copyright/copyright-and-researchgate | upload rights depend on the version, licence, and any publisher agreement | third-party redistribution, future venue policy, and paper licence must be checked before upload |

The machine-complete publication stage now includes three self-contained
private source/PDF review packages and automated citation, result-drift,
private-boundary, and PDF guards. This changes presentation readiness, not the
scientific gate: all three remain `HOLD-EXTERNAL` for the paper-specific
independent evidence recorded in the reviewer packet.
