#!/usr/bin/env python3
"""Install one repository skill into Codex, Pi Agent, or a custom directory."""

from __future__ import annotations

import argparse
import sys

from _skill_tools import SkillToolError, install_skill, resolve_source, resolve_target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", help="skill name or path beneath this repository's skills/")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--agent", choices=("codex", "pi"), help="installation profile (default: codex)")
    target.add_argument("--target-dir", help="explicit skills directory; overrides agent profiles")
    parser.add_argument(
        "--mode", choices=("link", "copy"), default="link", help="installation mode (default: link)"
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="replace an occupied destination after moving it to a timestamped backup",
    )
    parser.add_argument("--dry-run", action="store_true", help="show the resolved operation without writing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        source, metadata = resolve_source(args.skill)
        target_root = resolve_target(args.agent, args.target_dir)
        result = install_skill(
            source,
            metadata,
            target_root,
            mode=args.mode,
            replace=args.replace,
            dry_run=args.dry_run,
        )
    except (OSError, SkillToolError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"{result.action}: {metadata.name}")
    print(f"source: {result.source}")
    print(f"destination: {result.destination}")
    if result.backup:
        print(f"backup: {result.backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
