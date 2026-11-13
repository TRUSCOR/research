from __future__ import annotations

from pathlib import Path

from private.experiments.run_p5_incident_collector_scale import (
    EXTERNAL_EVENT_SCALE,
    _digest,
    _safe_trace,
)
from sova.trace import TraceReader


def test_external_event_scale_is_derived_from_retained_external_results() -> None:
    assert EXTERNAL_EVENT_SCALE == 879


def test_digest_is_typed_sha256() -> None:
    assert _digest(b"owl") == (
        "sha256:10f7127b980b0b06ef157749f8a02cca1c606d22642729dcb2d24dbbf2bf30df"
    )


def test_safe_source_trace_is_signed_and_required_key_verified(tmp_path: Path) -> None:
    trace, key_id = _safe_trace(tmp_path / "source.sova-trace")
    report = TraceReader(trace).verify(required_key_id=key_id)
    assert report.event_count == 8
    assert report.signature_valid is True
    assert report.trust_policy == "required-key"
