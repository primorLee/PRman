#!/usr/bin/env python3
"""Run PRman's deterministic assessment helper from an installed plugin checkout."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    plugin_root = Path(__file__).resolve().parents[3]
    source_root = plugin_root / "src"
    if not (source_root / "prman" / "cli.py").is_file():
        print("PRman source package is missing from the plugin", file=sys.stderr)
        return 2
    sys.path.insert(0, str(source_root))

    from prman.cli import main as prman_main

    arguments = list(sys.argv[1:])
    if arguments and arguments[0] == "candidate-id":
        return prman_main(arguments)
    if "--decision-config" not in arguments:
        arguments = [
            "assess",
            "--decision-config",
            str(plugin_root / "configs" / "decision.json"),
            *arguments,
        ]
    else:
        arguments = ["assess", *arguments]
    return prman_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
