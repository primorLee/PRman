#!/usr/bin/env python3
"""Run PRman's confirmation and workflow safety helper from an installed plugin."""

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

    return prman_main(list(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
