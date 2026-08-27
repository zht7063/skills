#!/usr/bin/env python3
"""Shared, dependency-free helpers for repository-level skill tooling."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
IGNORED_TOP_LEVEL_DIRS = {"evals"}
IGNORED_DIR_NAMES = {"__pycache__", ".git", ".pytest_cache"}
IGNORED_FILE_NAMES = {".DS_Store"}
IGNORED_FILE_SUFFIXES = {".pyc", ".pyo"}


class SkillToolError(RuntimeError):
    """A user-actionable repository tooling error."""


@dataclass(frozen=True)
class SkillMetadata:
    name: str
    description: str


@dataclass(frozen=True)
class InstallResult:
    action: str
    source: Path
    destination: Path
    backup: Path | None = None


def repository_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _frontmatter_text(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillToolError(f"{skill_md} must start with YAML frontmatter")
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise SkillToolError(f"{skill_md} has unterminated YAML frontmatter") from exc
    return "\n".join(lines[1:end])


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def read_skill_metadata(skill_dir: Path) -> SkillMetadata:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise SkillToolError(f"missing SKILL.md: {skill_dir}")

    frontmatter = _frontmatter_text(skill_md)
    name_match = re.search(r"(?m)^name:\s*(.+?)\s*$", frontmatter)
    if not name_match:
        raise SkillToolError(f"{skill_md} is missing frontmatter field 'name'")
    name = _unquote(name_match.group(1))

    frontmatter_lines = frontmatter.splitlines()
    description_index = next(
        (index for index, line in enumerate(frontmatter_lines) if line.startswith("description:")),
        None,
    )
    if description_index is None:
        raise SkillToolError(f"{skill_md} is missing frontmatter field 'description'")
    description_value = frontmatter_lines[description_index].split(":", 1)[1].strip()
    if description_value in {">", ">-", "|", "|-"}:
        parts: list[str] = []
        for line in frontmatter_lines[description_index + 1 :]:
            if not line.startswith((" ", "\t")):
                break
            parts.append(line.strip())
        description = " ".join(part for part in parts if part)
    else:
        description = _unquote(description_value)

    return SkillMetadata(name=name, description=description)


def validate_skill(skill_dir: Path, expected_name: str | None = None) -> list[str]:
    skill_dir = skill_dir.resolve()
    issues: list[str] = []
    try:
        metadata = read_skill_metadata(skill_dir)
    except (OSError, SkillToolError) as exc:
        return [str(exc)]

    required_name = expected_name or skill_dir.name
    if expected_name is None and not SKILL_NAME_RE.fullmatch(skill_dir.name):
        issues.append(f"directory name is not lowercase hyphen-case: {skill_dir.name}")
    if metadata.name != required_name:
        issues.append(
            f"frontmatter name {metadata.name!r} does not match expected name {required_name!r}"
        )
    if not SKILL_NAME_RE.fullmatch(metadata.name):
        issues.append(f"invalid skill name: {metadata.name!r}")
    if not metadata.description:
        issues.append("description must not be empty")
    if len(metadata.description) > 1024:
        issues.append(f"description exceeds 1024 characters: {len(metadata.description)}")

    for json_file in sorted(skill_dir.rglob("*.json")):
        if any(part in IGNORED_DIR_NAMES for part in json_file.relative_to(skill_dir).parts):
            continue
        try:
            json.loads(json_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            issues.append(f"invalid JSON {json_file.relative_to(skill_dir)}: {exc}")

    for markdown_file in sorted(skill_dir.rglob("*.md")):
        if any(part in IGNORED_DIR_NAMES for part in markdown_file.relative_to(skill_dir).parts):
            continue
        try:
            markdown = markdown_file.read_text(encoding="utf-8")
        except OSError as exc:
            issues.append(f"cannot read {markdown_file.relative_to(skill_dir)}: {exc}")
            continue
        for raw_target in MARKDOWN_LINK_RE.findall(markdown):
            target = raw_target.strip().strip("<>").split("#", 1)[0]
            if not target or "://" in target or target.startswith(("mailto:", "/")):
                continue
            linked = (markdown_file.parent / target).resolve()
            if not linked.exists():
                issues.append(
                    f"broken link in {markdown_file.relative_to(skill_dir)}: {raw_target}"
                )

    return issues


def require_valid_skill(skill_dir: Path, expected_name: str | None = None) -> SkillMetadata:
    issues = validate_skill(skill_dir, expected_name=expected_name)
    if issues:
        formatted = "\n  - ".join(issues)
        raise SkillToolError(f"skill validation failed:\n  - {formatted}")
    return read_skill_metadata(skill_dir)


def resolve_source(skill: str, repo_root: Path | None = None) -> tuple[Path, SkillMetadata]:
    repo_root = (repo_root or repository_root()).resolve()
    skills_root = (repo_root / "skills").resolve()
    requested = Path(skill).expanduser()
    if requested.is_absolute() or requested.exists() or "/" in skill or "\\" in skill:
        source = requested.resolve()
    else:
        if not SKILL_NAME_RE.fullmatch(skill):
            raise SkillToolError(f"invalid skill name: {skill!r}")
        source = (skills_root / skill).resolve()

    try:
        source.relative_to(skills_root)
    except ValueError as exc:
        raise SkillToolError(f"skill source must be inside {skills_root}: {source}") from exc
    if not source.is_dir():
        raise SkillToolError(f"skill source directory does not exist: {source}")
    metadata = require_valid_skill(source)
    return source, metadata


def resolve_target(agent: str | None, target_dir: str | None) -> Path:
    if target_dir:
        expanded = os.path.expandvars(target_dir)
        return Path(expanded).expanduser().resolve()

    profile = agent or "codex"
    if profile == "codex":
        config_root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    elif profile == "pi":
        config_root = Path(
            os.environ.get("PI_CODING_AGENT_DIR", Path.home() / ".pi" / "agent")
        )
    else:
        raise SkillToolError(f"unsupported agent profile: {profile}")
    return config_root.expanduser().resolve() / "skills"


def _destination_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _same_symlink(destination: Path, source: Path) -> bool:
    return destination.is_symlink() and destination.resolve(strict=False) == source.resolve()


def _copy_ignore(source: Path):
    source = source.resolve()

    def ignore(directory: str, names: list[str]) -> set[str]:
        directory_path = Path(directory).resolve()
        relative = directory_path.relative_to(source)
        ignored: set[str] = set()
        for name in names:
            if name in IGNORED_DIR_NAMES or name in IGNORED_FILE_NAMES:
                ignored.add(name)
                continue
            if Path(name).suffix in IGNORED_FILE_SUFFIXES:
                ignored.add(name)
                continue
            if relative == Path(".") and name in IGNORED_TOP_LEVEL_DIRS:
                ignored.add(name)
        return ignored

    return ignore


def _backup_path(target_root: Path, skill_name: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = target_root.parent / ".skill-install-backups" / target_root.name / stamp
    candidate = base / skill_name
    counter = 2
    while _destination_exists(candidate):
        candidate = base / f"{skill_name}-{counter}"
        counter += 1
    return candidate


def install_skill(
    source: Path,
    metadata: SkillMetadata,
    target_root: Path,
    mode: str = "link",
    replace: bool = False,
    dry_run: bool = False,
) -> InstallResult:
    source = source.resolve()
    target_root = target_root.expanduser().resolve()
    destination = target_root / metadata.name

    if destination == source:
        raise SkillToolError("installation destination is the source directory itself")
    if source in target_root.parents:
        raise SkillToolError("installation target cannot be inside the skill source")
    if mode not in {"link", "copy"}:
        raise SkillToolError(f"unsupported install mode: {mode}")

    occupied = _destination_exists(destination)
    if occupied and mode == "link" and _same_symlink(destination, source):
        return InstallResult("already-installed", source, destination)
    if occupied and not replace:
        raise SkillToolError(
            f"destination already exists: {destination}; rerun with --replace to back it up"
        )

    backup = _backup_path(target_root, metadata.name) if occupied else None
    if dry_run:
        return InstallResult("would-replace" if occupied else "would-install", source, destination, backup)

    target_root.mkdir(parents=True, exist_ok=True)
    staging = target_root / f".{metadata.name}.install-{uuid.uuid4().hex}"
    try:
        if mode == "link":
            staging.symlink_to(source, target_is_directory=True)
        else:
            shutil.copytree(source, staging, ignore=_copy_ignore(source))
            require_valid_skill(staging, expected_name=metadata.name)

        if occupied and backup:
            backup.parent.mkdir(parents=True, exist_ok=True)
            destination.rename(backup)
        try:
            staging.rename(destination)
        except Exception:
            if backup and _destination_exists(backup) and not _destination_exists(destination):
                backup.rename(destination)
            raise
    finally:
        if staging.is_symlink():
            staging.unlink()
        elif staging.exists():
            shutil.rmtree(staging)

    return InstallResult("replaced" if occupied else "installed", source, destination, backup)


def uninstall_skill(skill_name: str, target_root: Path, apply: bool = False) -> InstallResult:
    if not SKILL_NAME_RE.fullmatch(skill_name):
        raise SkillToolError(f"invalid skill name: {skill_name!r}")
    target_root = target_root.expanduser().resolve()
    destination = target_root / skill_name
    if not _destination_exists(destination):
        return InstallResult("not-installed", destination, destination)

    if not destination.is_symlink():
        metadata = require_valid_skill(destination)
        if metadata.name != skill_name:
            raise SkillToolError(
                f"refusing to remove destination with mismatched skill name: {metadata.name}"
            )

    if not apply:
        return InstallResult("would-uninstall", destination, destination)
    if destination.is_symlink() or destination.is_file():
        destination.unlink()
    else:
        shutil.rmtree(destination)
    return InstallResult("uninstalled", destination, destination)


def discover_skills(repo_root: Path | None = None) -> list[Path]:
    root = (repo_root or repository_root()).resolve() / "skills"
    if not root.is_dir():
        raise SkillToolError(f"skills directory does not exist: {root}")
    return sorted(path.parent for path in root.glob("*/SKILL.md"))


def run_python_tests(skill_dir: Path) -> subprocess.CompletedProcess[str] | None:
    tests_dir = skill_dir / "tests"
    if not tests_dir.is_dir() or not any(tests_dir.glob("test*.py")):
        return None
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(tests_dir), "-v"],
        cwd=repository_root(),
        capture_output=True,
        text=True,
        check=False,
    )
