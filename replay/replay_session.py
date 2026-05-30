from __future__ import annotations

import argparse
import json
from pathlib import Path

from render_timeline import render_timeline


def load_trace(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a stored session trace as a decision timeline")
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    print(render_timeline(load_trace(args.trace)))


if __name__ == "__main__":
    main()
