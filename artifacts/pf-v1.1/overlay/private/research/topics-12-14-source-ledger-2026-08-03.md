# Topics 12-14 verified source ledger

Private research record - not cleared for publication or filing

Date: 2026-08-03
Owner and proposed paper author: Gautam R. Patil
Affiliation: TRUSCOR Private Limited

## Method and limits

This is a scoped technical prior-art screen, not a legal patent search or a
freedom-to-operate opinion. Sources were checked at the linked primary paper,
standard, official repository, patent publication, or patent-office guidance.
Search-result snippets were not treated as proof of novelty. A qualified patent
professional must repeat and expand the search by claims, classifications,
families, citations, prosecution history, and non-English literature before a
filing decision.

## Topic 12 - semantic reproduction and replay

| Source | Verified contribution | Constraint on SOVA claims |
|---|---|---|
| AgentRR, arXiv:2505.17716, https://arxiv.org/abs/2505.17716 | Records agent interactions, abstracts them into reusable experience, and replays experience under checks | Agent record/replay, experience abstraction, and replay-time checking are not broad novelty |
| Deterministic Replay for AI Agent Systems, arXiv:2607.16200, https://arxiv.org/abs/2607.16200 | Intercepts external interactions, isolates replay, matches requests, and reports deterministic replay fidelity | Exact transport capture/replay and request-key matching are not SOVA novelty |
| WebGraphEval, arXiv:2510.19205, https://arxiv.org/abs/2510.19205 | Canonicalizes web-agent trajectories into weighted action graphs for cross-agent structural evaluation | Graph-based semantic trajectory comparison is an explicit baseline |
| AgentRewardBench, arXiv:2504.08942, https://arxiv.org/abs/2504.08942 | Evaluates automatic judges over expert-labelled web-agent trajectories | SOVA must compare judge decisions with independent labels and disagreements |
| ReproEvalCard, ACL 2026, https://aclanthology.org/2026.acl-short.22/ | Specifies reproducibility-critical information for LLM evaluation pipelines | Reproducibility metadata and evaluation cards are not novelty |
| Inspect AI logs, https://inspect.aisi.org.uk/eval-logs.html | Provides versioned evaluation logs, events, scoring, retries, conversion, and viewers | Log inspection, replay configuration, and evaluation-log portability are established baselines |
| W3C PROV Constraints, https://www.w3.org/TR/prov-constraints/ | Defines provenance validity, normalization, and equivalence rules | Provenance graphs and canonical provenance equivalence are not novelty |
| US12287728B1, https://patents.google.com/patent/US12287728B1/en | Deterministically replays recorded user and generated application events using simulated time and an event queue | Broad recorded-event replay and deterministic UI/session replay claims are blocked |
| US9170915B1, https://patents.google.com/patent/US9170915B1/en | Reconstructs workflow state from history and replayed decisions | Workflow-history replay and state reconstruction are blocked broadly |
| US20210064512A1, https://patents.google.com/patent/US20210064512A1/en | Selectively traces program state and replays execution using captured nondeterministic state | Program trace replay and logical-equivalence replay are crowded |
| US20260105394A1, https://patents.google.com/patent/US20260105394A1/en | Captures AI-agent observability data for audit, replay, and diagnostics | AI-agent logs used for replay and diagnostics are not novelty |

Topic 12 claim effect: no claim over a portable trace, replay, semantic
similarity, provenance, repeated trials, or uncertainty interval by itself.
The researchable delta is the ordered coupling of an observable-outcome
contract, explicit context-equivalence envelope, evidence-sufficiency gate,
multi-valued result, and recomputable repeated-trial record. Patentability of
that combination is unknown.

## Topic 13 - executor conformance and capability routing

| Source | Verified contribution | Constraint on SOVA claims |
|---|---|---|
| MCP specification revision 2025-11-25, https://modelcontextprotocol.io/specification/2025-11-25 | Standardizes protocol negotiation, lifecycle, capabilities, tools, errors, and cancellation | Protocol adapters, capability discovery, tool mapping, and ordinary error normalization are not novelty |
| MCP tool-result rules, https://modelcontextprotocol.io/specification/2025-06-18/server/tools | Separates JSON-RPC errors from tool execution errors and uses `isError` in tool results | Transport success versus tool failure is an explicit protocol baseline |
| WebDriver BiDi Working Draft, https://www.w3.org/TR/2026/WD-webdriver-bidi-20260601/ | Defines asynchronous browser commands, results, errors, events, sessions, and capabilities | Browser command conformance and session lifecycle are not novelty |
| OpenTelemetry Semantic Conventions, https://opentelemetry.io/docs/specs/semconv/ | Defines cross-system spans, events, resources, and GenAI mappings | Cross-runtime correlation and semantic telemetry mapping are not novelty |
| Microsoft Playwright MCP, https://github.com/microsoft/playwright-mcp | Provides structured accessibility-tree browser automation and isolated or persistent profiles; explicitly says it is not a security boundary | Browser MCP execution, accessibility snapshots, and isolated profiles are engineering dependencies, not inventions |
| CursorTouch Windows-MCP, https://github.com/CursorTouch/Windows-MCP | Provides Windows UI automation with MCP transports and security controls | Windows MCP execution and accessibility/UI mapping are not novelty |
| US11722324B2, https://patents.google.com/patent/US11722324B2/en | Hashes RPA scripts, runtimes, and logs and records accountable execution in a ledger | Cryptographically accountable automation execution is crowded |
| EP3112965A1, https://patents.google.com/patent/EP3112965A1/en | Uses pre/post screenshots and expected screenshots to verify an RPA action | Post-action visual observation and scene-change verification are blocked broadly |
| US20170039063A1, https://patents.google.com/patent/US20170039063A1/en | Generates idempotent workflows around distributed side effects | Idempotency and retry protection are established |
| US20190155649A1, https://patents.google.com/patent/US20190155649A1/en | Executes guarded idempotent workflow actions with persisted execution records | Guarded retry, progress journals, and workflow recovery are established |
| US7421709B2, https://patents.google.com/patent/US7421709B2/en | Provides a universal adapter framework across heterogeneous systems | Generic adapter frameworks and normalized interfaces are blocked broadly |

Topic 13 claim effect: no broad claim over adapters, capability negotiation,
fallback, retries, post-action screenshots, evidence hashes, or four-state
status vocabularies. The researchable delta is an exact portable-intent and
capability contract whose success is bounded by evidence roles, complete
side-effect lineage, and separately attributed observations outside the
provider report. Patentability is unknown and the present public broker is an
engineering implementation, not proof of that complete research claim.

## Topic 14 - trigger-space search

| Source | Verified contribution | Constraint on SOVA claims |
|---|---|---|
| Sleeper Agents, arXiv:2401.05566, https://arxiv.org/abs/2401.05566 | Demonstrates LLM backdoor behavior activated by deployment context and persistence through safety training | Conditional and sleeper behavior in LLMs is established |
| Watch Out for Your Agents, arXiv:2402.11208, https://arxiv.org/abs/2402.11208 | Studies backdoors in planning, tool observations, intermediate reasoning, and final outcomes of agents | Agent-stage and tool-observation trigger locations are established |
| Stateful Agent Backdoor, arXiv:2605.06158, https://arxiv.org/abs/2605.06158 | Models cross-session persistent agent backdoors as a Mealy machine | Stateful and cross-session trigger behavior is established |
| GPTFuzzer, arXiv:2309.10253, https://arxiv.org/abs/2309.10253 | Uses seed selection, LLM mutation, and a judge for automated jailbreak fuzzing | Prompt seed mutation and evolutionary jailbreak search are not novelty |
| FuzzLLM, arXiv:2309.05274, https://arxiv.org/abs/2309.05274 | Combines jailbreak templates, constraints, and prohibited questions for fuzzing | Template/constraint combination search is established |
| PAIR, arXiv:2310.08419, https://arxiv.org/abs/2310.08419 | Iteratively refines black-box jailbreak prompts with an attacker model | Black-box adaptive prompt refinement is established |
| TAP, arXiv:2312.02119, https://arxiv.org/abs/2312.02119 | Searches a pruned attack tree with attacker and evaluator models | Tree search and pruning for jailbreak discovery are established |
| AgentDojo, NeurIPS 2024, https://papers.nips.cc/paper_files/paper/2024/file/97091a5177d8dc64b1da8bf3e1f6fb54-Paper-Datasets_and_Benchmarks_Track.pdf | Provides dynamic tool-using environments, utility tasks, and prompt-injection test cases | Dynamic agent-security benchmarking is a strong baseline |
| InjecAgent, ACL Findings 2024, https://aclanthology.org/2024.findings-acl.624/ | Benchmarks indirect prompt injection across tool-integrated agents | Tool-integrated indirect-prompt search is established |
| Agent Security Bench, ICLR 2025, https://github.com/agiresearch/asb | Formalizes attacks and defenses across agents, tools, memory, and scenarios | Broad agent-attack taxonomy and benchmark coverage are established |
| ToolEmu, ICLR 2024, https://proceedings.iclr.cc/paper_files/paper/2024/file/7274ed909a312d4d869cc328ad1c5f04-Paper-Conference.pdf | Uses an LM-emulated sandbox and adversarial emulator to identify risky agent behavior | Emulated adverse environments and evaluator-driven risk discovery are established |
| NIST SP 800-142, https://doi.org/10.6028/NIST.SP.800-142 | Uses t-way combinatorial testing because faults often arise from small parameter interactions, including sequence-covering arrays | Factor interaction coverage and sequence combinations are established |
| Error Locating Arrays, https://doi.org/10.1137/080730706 | Locates faulty parameter interactions using covering arrays and adaptive tests | Adaptive faulty-interaction localization is established |
| Adaptive faulty-interaction algorithm, https://doi.org/10.1587/transfun.2021EAP1071 | Adaptively locates faulty interactions in combinatorial tests | Factor-lattice and adaptive localization claims require strong narrowing |
| AFLNet retrospective, arXiv:2412.20324, https://arxiv.org/abs/2412.20324 | Uses message sequences, protocol states, and state/code coverage for stateful protocol fuzzing | Stateful sequence growth and state-coverage guidance are established |
| FOX, arXiv:2406.04517, https://arxiv.org/abs/2406.04517 | Uses fine-grained branch distance and online stochastic control to guide mutations | Near-miss/branch-distance optimization is established |
| Delta Debugging, https://www.st.cs.uni-saarland.de/papers/tse2002/ | Minimizes a failure-inducing input and isolates failure-inducing differences | Trigger reduction/minimization is established |
| US12476993B1, https://patents.google.com/patent/US12476993B1/en | Describes LLM jailbreak mutation with genetic algorithms, mutation rates, evolutionary scoring, grammar rules, helper LLMs, and fuzzers | Broad automated LLM jailbreak mutation/search patent claims are heavily blocked |
| CN119884311A, https://patents.google.com/patent/CN119884311A/en | Generates expandable jailbreak attacks by contextual and role-based rewriting | Context/template rewriting for jailbreak expansion is crowded |
| US11550914B2, https://patents.google.com/patent/US11550914B2/en | Optimizes universal patterns to detect backdoors in neural networks | Optimized trigger-pattern detection is established |
| US11132444B2, https://patents.google.com/patent/US11132444B2/en | Uses gradients to identify backdoor-trigger patterns | Model-gradient trigger reconstruction is established |
| US20240012742A1, https://patents.google.com/patent/US20240012742A1/en | Uses executed and dormant coverage to guide fuzzing instrumentation | Coverage-guided and dormant-coverage scheduling is established |

Topic 14 claim effect: the public SOVA evolutionary search is correctly labelled
as a baseline. Typed dimensions, mutation, near-miss scores, sequence growth,
coverage guidance, genetic selection, minimization, and search budgets are not
individually patentable contributions on this record. A narrower private
hypothesis may combine evidence-derived factor attribution, adaptive interaction
order, multi-valued oracle states, and portable minimized reproduction artifacts,
but error-locating arrays, directed fuzzing, and delta debugging make obviousness
a serious risk. Do not disclose or file without comparative results and counsel.

## Patent-office and publication controls

| Authority | Verified rule or guidance | SOVA consequence |
|---|---|---|
| IP India CRI Guidelines 2025, https://ipindia.gov.in/resource/patents-resources-guidelines | Current official computer-related-invention examination guidance is available; eligibility and technical effect require case-specific analysis | Indian eligibility must be reviewed by Indian counsel; labels such as "AI" or "technical" do not create eligibility |
| WIPO patent FAQ, https://www.wipo.int/en/web/patents/faq_patents | Public disclosure before filing can become prior art and can destroy rights in many jurisdictions; defensive publication is an alternative | No P1 or P4 preprint before the patent/trade-secret decision |
| USPTO provisional guidance, https://www.uspto.gov/patents/basics/apply/provisional-application | A provisional is unexamined, needs an enabling written description, and normally has a non-extendable 12-month pendency | A provisional is not a patent or a completed legal outcome |
| USPTO AI inventorship guidance, https://www.uspto.gov/subscription-center/2025/revised-inventorship-guidance-ai-assisted-inventions | Only natural persons can be named inventors; ordinary inventorship law applies to AI-assisted work | No AI system is an inventor; Gautam's actual human conception must be documented claim by claim |

## Current decisions

- P4 / Topic 12 paper: GO for private revision; HOLD for preprint or submission.
- Topic 12 patent candidate: HOLD for counsel screening; broad replay claims NO-GO.
- P6 / Topic 13 paper: GO for private revision; HOLD for preprint or submission.
- Topic 13 patent candidate: HOLD only for the narrow observation-bounded
  combination; broad adapter/retry/conformance claims NO-GO.
- P1 / Topic 14 paper: GO for private working paper and benchmark protocol;
  HOLD for preprint until the IP choice and real-system study are complete.
- Topic 14 patent candidate: broad evolutionary/corpus-conditioned search
  NO-GO on the currently public baseline; narrow evidence-guided interaction
  search HOLD pending results, inventor evidence, and counsel.

