#!/usr/bin/env python3
"""Ratchet for strict typing in life_graph/api (audit M11).

life_graph/api passes mypy at the baseline level set in pyproject.toml
([tool.mypy]). Under `mypy --strict` it still has errors -- mostly route
handlers without a return annotation. This script runs `mypy --strict` with
the same config and compares the number of errors in life_graph/api with the
number committed in .github/mypy-api-strict-baseline.txt:

* more errors than the baseline  -> exit 1 (new untyped code; annotate it)
* fewer                          -> exit 0 with a notice to lower the
                                    baseline (run with --update and commit)
* equal                          -> exit 0

So the count can only go down. Errors in life_graph/core count too, though
core is strict already and should have none.

Usage:
    python scripts/mypy_ratchet.py            # check (what CI runs)
    python scripts/mypy_ratchet.py --update   # rewrite the baseline to the current count
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / ".github" / "mypy-api-strict-baseline.txt"
ERROR_LINE = re.compile(r"^(life_graph/(?:api|core)/[^:]+):\d+: error: ")


def read_baseline() -> int:
    for line in BASELINE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return int(line)
    raise SystemExit(f"{BASELINE}: no count found")


def write_baseline(count: int) -> None:
    text = BASELINE.read_text()
    header = [line for line in text.splitlines() if line.startswith("#")]
    BASELINE.write_text("\n".join([*header, str(count)]) + "\n")


def run_strict() -> tuple[int, Counter[str], str]:
    proc = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--no-error-summary"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    # mypy exits 1 for type errors and 2 for a crash or bad config; only the
    # former is a count.
    if proc.returncode not in (0, 1):
        print(out)
        raise SystemExit(f"mypy failed to run (exit {proc.returncode})")
    per_file: Counter[str] = Counter()
    for line in out.splitlines():
        m = ERROR_LINE.match(line)
        if m:
            per_file[m.group(1)] += 1
    return sum(per_file.values()), per_file, out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--update", action="store_true", help="rewrite the baseline")
    args = parser.parse_args()

    count, per_file, out = run_strict()
    baseline = read_baseline()

    if args.update:
        write_baseline(count)
        print(f"baseline {baseline} -> {count}")
        return 0

    print(f"mypy --strict errors in life_graph/api + core: {count} (baseline {baseline})")
    for path, n in per_file.most_common():
        print(f"  {n:4d}  {path}")

    if count > baseline:
        print(out)
        print(
            f"::error::mypy --strict found {count} errors in life_graph/api, "
            f"{count - baseline} more than the committed baseline ({baseline}). "
            "Annotate the new code (the errors are above) rather than raising "
            ".github/mypy-api-strict-baseline.txt."
        )
        return 1
    if count < baseline:
        print(
            f"::notice::{baseline - count} fewer strict errors than the baseline. "
            "Lock the gain in: python scripts/mypy_ratchet.py --update, and commit "
            ".github/mypy-api-strict-baseline.txt."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
