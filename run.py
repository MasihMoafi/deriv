#!/usr/bin/env python3
"""Run the replayable ticket evaluation pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.workflow import run_pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tickets", default="tickets.json", type=Path)
    parser.add_argument("--labels", default="labels.json", type=Path)
    parser.add_argument("--output-dir", default=".", type=Path)
    parser.add_argument(
        "--provider",
        choices=("auto", "openrouter", "local"),
        default=None,
        help="Use OpenRouter, local fallback, or automatic configuration selection.",
    )
    args = parser.parse_args()
    result = run_pipeline(args.tickets, args.labels, args.output_dir, args.provider)
    print(" -> ".join(result["stages"]))
    print(f"provider={result['provider']} model={result['model']}")
    print(f"artifacts written to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
