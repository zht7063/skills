#!/usr/bin/env python3
"""Validate every source skill in this repository, with optional Python tests."""

from __future__ import annotations

import argparse
import sys

from _skill_tools import SkillToolError, discover_skills, run_python_tests, validate_skill


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests", action="store_true", help="run unittest suites found under skill tests/")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        skill_dirs = discover_skills()
    except SkillToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not skill_dirs:
        print("error: no skills found", file=sys.stderr)
        return 1

    failures = 0
    for skill_dir in skill_dirs:
        issues = validate_skill(skill_dir)
        if issues:
            failures += 1
            print(f"FAIL {skill_dir.name}")
            for issue in issues:
                print(f"  - {issue}")
            continue
        print(f"PASS {skill_dir.name}")

        if args.tests:
            result = run_python_tests(skill_dir)
            if result is None:
                print("  tests: none")
            elif result.returncode == 0:
                print("  tests: passed")
            else:
                failures += 1
                print("  tests: failed")
                output = (result.stdout + result.stderr).strip()
                if output:
                    print(output)

    if failures:
        print(f"validation failed: {failures} skill operation(s) failed", file=sys.stderr)
        return 1
    print(f"validated {len(skill_dirs)} skill(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
