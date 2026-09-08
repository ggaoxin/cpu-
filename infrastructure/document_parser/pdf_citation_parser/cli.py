from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import ParseConfig
from .parser import CitationParser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract citation-bearing sentences from academic PDFs")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="JSON output path; stdout when omitted")
    parser.add_argument("--strict-refs", action="store_true", help="drop numeric candidates absent from the detected reference list")
    parser.add_argument("--context", type=int, default=0, metavar="CHARS", help="include surrounding context characters")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ParseConfig(
        strict_reference_validation=args.strict_refs,
        sentence_context_chars=max(0, args.context),
    )
    result = CitationParser(config).parse(args.pdf)
    payload = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
