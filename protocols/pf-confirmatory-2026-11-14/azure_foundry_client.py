"""OpenAI-compatible client for an Azure AI Foundry project, for the PF cross-provider runs.

The endpoint and key are read at run time from a local notes file whose path is given
in the PF_AZURE_NOTES environment variable (or passed explicitly). Neither the key nor
the resource name is printed, logged, or written to any result file; records carry
only the deployment name and the model string the service returns.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


def _read_notes(path: str | os.PathLike | None) -> tuple[str, str]:
    notes = Path(path or os.environ["PF_AZURE_NOTES"]).read_text(encoding="utf-8", errors="replace")
    endpoints = re.findall(r'endpoint\s*=\s*"(https://[^"]+/openai/v1)/?"', notes)
    keys = re.findall(r"(?im)^\s*API key:\s*(\S+)\s*$", notes)
    if not endpoints or not keys:
        raise SystemExit("could not find an /openai/v1 endpoint and an 'API key:' line in the notes file")
    if len(set(endpoints)) != 1 or len(set(keys)) != 1:
        raise SystemExit("the notes file lists more than one endpoint or key; refusing to guess")
    return endpoints[0], keys[0]


def make_client(notes_path: str | os.PathLike | None = None, timeout: float = 240.0):
    import openai

    endpoint, key = _read_notes(notes_path)
    return openai.OpenAI(base_url=endpoint, api_key=key, max_retries=8, timeout=timeout)


def describe(notes_path: str | os.PathLike | None = None) -> dict[str, object]:
    """Non-secret facts about the configuration, safe to print."""
    endpoint, key = _read_notes(notes_path)
    return {"endpointPath": "/openai/v1", "endpointHostKind": endpoint.split("//", 1)[1].split(".", 1)[1].split("/", 1)[0], "keyLength": len(key)}
