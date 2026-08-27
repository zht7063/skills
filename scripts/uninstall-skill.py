#!/usr/bin/env python3
"""Safely preview or uninstall one skill from an agent skills directory."""

from __future__ import annotations

import argparse
import sys

from _skill_tools import SkillToolError, resolve_target, uninstall_skill


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", help="lowercase hyphenated skill name")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--agent", choices=("codex", "pi"), help="installation profile (default: codex)")
    target.add_argument("--target-dir", help="explicit skills directory; overrides agent profiles")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the uninstall; without this flag the command is a dry run",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        target_root = resolve_target(args.agent, args.target_dir)
        result = uninstall_skill(args.skill, target_root, apply=args.apply)
    except (OSError, SkillToolError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"{result.action}: {args.skill}")
    print(f"destination: {result.destination}")
    if result.action == "would-uninstall":
        print("rerun with --apply to remove this exact destination")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
