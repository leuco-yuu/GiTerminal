#!/usr/bin/env python3
"""Run the local project validation steps used before packaging or release."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> None:
    print("$", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    run([sys.executable, "-m", "compileall", "-q", "src", "tests", "run.py"])
    run([sys.executable, "-m", "pytest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
