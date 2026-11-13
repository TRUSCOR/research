"""Private CLI for the integrated Topics 04-06 research candidate."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from private.experiments.prototypes.integrated import (
    evaluate_integrated_research,
    migrate_research_capsule,
    render_integrated_report,
    validate_research_extension,
)
from sova.formats import canonical_json_bytes, strict_json_loads
from sova.formats.errors import FormatError


def _json_object(path: Path) -> dict[str, Any]:
    value = strict_json_loads(path.read_bytes())
    if not isinstance(value, dict):
        raise FormatError(
            "SOVA-RESEARCH-CLI-JSON",
            "input document root must be an object",
        )
    return value


def _emit(data: bytes, output: Path | None) -> None:
    if output is None:
        sys.stdout.buffer.write(data)
        if not data.endswith(b"\n"):
            sys.stdout.buffer.write(b"\n")
        return
    output.write_bytes(data)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sova-private-research",
        description="Private, non-released SOVA research bridge.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate")
    validate.add_argument("extension", type=Path)

    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("capsule", type=Path)
    evaluate.add_argument("trace", type=Path)
    evaluate.add_argument("--context", type=Path, required=True)
    evaluate.add_argument("--unsafe", action="store_true")
    evaluate.add_argument("--output", type=Path)

    render = commands.add_parser("render")
    render.add_argument("capsule", type=Path)
    render.add_argument("trace", type=Path)
    render.add_argument("--context", type=Path, required=True)
    render.add_argument("--unsafe", action="store_true")
    render.add_argument("--output", type=Path)

    migrate = commands.add_parser("migrate")
    migrate.add_argument("source", type=Path)
    migrate.add_argument("destination", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            validate_research_extension(_json_object(args.extension))
            _emit(b'{"valid":true}\n', None)
        elif args.command in {"evaluate", "render"}:
            report = evaluate_integrated_research(
                args.capsule,
                args.trace,
                candidate_context=_json_object(args.context),
                safe_to_compare=not args.unsafe,
            )
            if args.command == "evaluate":
                _emit(canonical_json_bytes(report.to_mapping()) + b"\n", args.output)
            else:
                _emit(render_integrated_report(report).encode("utf-8"), args.output)
        elif args.command == "migrate":
            digest = migrate_research_capsule(args.source, args.destination)
            _emit(canonical_json_bytes({"digest": digest}) + b"\n", None)
        else:
            raise AssertionError("unreachable command")
    except (FormatError, OSError, ValueError) as error:
        code = error.issue.code if isinstance(error, FormatError) else type(error).__name__
        sys.stderr.write(f"{code}: {error}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
