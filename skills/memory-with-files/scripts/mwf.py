#!/usr/bin/env python3
"""Deterministic helpers for the memory-with-files project protocol."""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import functools
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
SCOPE_KEYS = (
    "paths",
    "file_types",
    "components",
    "tools",
    "operations",
    "phases",
    "keywords",
)
CORE_FILES = ("config.json", "protocol.md", "index.md", "handoff.md", "inbox.md")
RECORD_DIRS = ("preferences", "decisions", "incidents", "tasks", "knowledge", "candidates")
ALL_DIRS = RECORD_DIRS + ("archive", "local")
TYPE_INFO = {
    "preference": {"prefix": "PREF", "directory": "preferences", "default": "stable", "statuses": {"candidate", "stable", "deprecated"}},
    "decision": {"prefix": "DEC", "directory": "decisions", "default": "accepted", "statuses": {"candidate", "proposed", "accepted", "superseded"}},
    "incident": {"prefix": "INC", "directory": "incidents", "default": "open", "statuses": {"candidate", "open", "resolved", "obsolete"}},
    "task": {"prefix": "TASK", "directory": "tasks", "default": "active", "statuses": {"candidate", "planned", "active", "blocked", "completed"}},
    "knowledge": {"prefix": "KNOW", "directory": "knowledge", "default": "stable", "statuses": {"candidate", "stable", "deprecated"}},
}
INACTIVE_STATUSES = {"deprecated", "superseded", "obsolete", "completed"}
INACTIVE_STATUS_BY_TYPE = {
    "preference": "deprecated",
    "decision": "superseded",
    "incident": "obsolete",
    "task": "completed",
    "knowledge": "deprecated",
}
AGENTS_START = "<!-- memory-with-files:start -->"
AGENTS_END = "<!-- memory-with-files:end -->"
GITIGNORE_START = "# memory-with-files:start"
GITIGNORE_END = "# memory-with-files:end"
PROTOCOL_START = "<!-- memory-with-files:protocol:start -->"
PROTOCOL_END = "<!-- memory-with-files:protocol:end -->"
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:sk|rk)-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:password|passwd|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*\S{8,}", re.I),
)


class MWFError(RuntimeError):
    pass


@dataclass
class Record:
    path: Path
    metadata: dict[str, Any]
    title: str
    body: str

    @property
    def scope(self) -> dict[str, list[str]]:
        raw = self.metadata.get("scope", {})
        return {key: list(raw.get(key, [])) for key in SCOPE_KEYS}

    @property
    def active(self) -> bool:
        return self.metadata.get("status") not in INACTIVE_STATUSES


def today() -> str:
    return dt.date.today().isoformat()


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def run_git_root(start: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return Path(result.stdout.strip()).resolve()


def discover_root(start: Path, explicit: str | None = None) -> Path:
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not root.is_dir():
            raise MWFError(f"Project root does not exist or is not a directory: {root}")
        return root

    start = start.resolve()
    git_root = run_git_root(start)
    if git_root:
        return git_root

    agents_roots = [parent for parent in (start, *start.parents) if (parent / "AGENTS.md").is_file()]
    if agents_roots:
        return agents_roots[-1]

    mwf_roots = [parent for parent in (start, *start.parents) if (parent / ".mwf").is_dir()]
    if mwf_roots:
        return mwf_roots[-1]

    raise MWFError("Could not infer a project root. Pass --root explicitly.")


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def template_dir() -> Path:
    return skill_root() / "assets" / "mwf-template"


def replace_tokens(text: str, git_mode: str, language: str) -> str:
    return text.replace("__DATE__", today()).replace("__GIT_MODE__", git_mode).replace("__LANGUAGE__", language)


def write_if_missing(destination: Path, source: Path, git_mode: str, language: str) -> bool:
    if destination.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(replace_tokens(source.read_text(encoding="utf-8"), git_mode, language), encoding="utf-8")
    return True


def replace_managed_block(path: Path, block: str, start_marker: str, end_marker: str) -> bool:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    start = old.find(start_marker)
    end = old.find(end_marker)
    if (start == -1) != (end == -1):
        raise MWFError(f"Managed block is malformed in {path}; repair it before retrying.")
    normalized = block.strip() + "\n"
    if start != -1:
        end += len(end_marker)
        new = old[:start] + normalized.rstrip("\n") + old[end:]
        if old.endswith("\n") and not new.endswith("\n"):
            new += "\n"
    else:
        prefix = old.rstrip()
        new = (prefix + "\n\n" if prefix else "") + normalized
    if new == old:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def load_config(root: Path) -> dict[str, Any]:
    path = root / ".mwf" / "config.json"
    if not path.is_file():
        raise MWFError(f"Missing {path}. Initialize or migrate the project memory first.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MWFError(f"Invalid config.json: {exc}") from exc
    if not isinstance(data, dict):
        raise MWFError("config.json must contain a JSON object.")
    return data


def initialize(root: Path, git_mode: str, language: str) -> list[str]:
    mwf = root / ".mwf"
    mwf.mkdir(parents=True, exist_ok=True)
    changes: list[str] = []

    for directory in ALL_DIRS:
        path = mwf / directory
        if not path.exists():
            path.mkdir(parents=True)
            changes.append(str(path.relative_to(root)) + "/")

    templates = template_dir()
    for name in CORE_FILES:
        if write_if_missing(mwf / name, templates / name, git_mode, language):
            changes.append(str((mwf / name).relative_to(root)))

    protocol_path = mwf / "protocol.md"
    protocol_template = replace_tokens((templates / "protocol.md").read_text(encoding="utf-8"), git_mode, language)
    protocol_text = protocol_path.read_text(encoding="utf-8")
    if PROTOCOL_START in protocol_text or PROTOCOL_END in protocol_text:
        if replace_managed_block(protocol_path, protocol_template, PROTOCOL_START, PROTOCOL_END):
            if ".mwf/protocol.md" not in changes:
                changes.append(".mwf/protocol.md")
    elif protocol_text.startswith("# Project memory protocol\n"):
        protocol_path.write_text(protocol_template.strip() + "\n", encoding="utf-8")
        if ".mwf/protocol.md" not in changes:
            changes.append(".mwf/protocol.md")
    else:
        if replace_managed_block(protocol_path, protocol_template, PROTOCOL_START, PROTOCOL_END):
            if ".mwf/protocol.md" not in changes:
                changes.append(".mwf/protocol.md")

    config_path = mwf / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    version = int(config.get("schema_version", 0))
    if version > SCHEMA_VERSION:
        raise MWFError(f"Memory schema {version} is newer than supported schema {SCHEMA_VERSION}.")
    config.update(
        {
            "schema_version": SCHEMA_VERSION,
            "updated_at": today(),
            "language": language,
            "git_mode": git_mode,
            "record_format": "markdown-frontmatter",
            "local_directory": ".mwf/local",
            "hooks_required": False,
        }
    )
    if not config.get("initialized_at") or config.get("initialized_at") == "__DATE__":
        config["initialized_at"] = today()
    rendered_config = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    if config_path.read_text(encoding="utf-8") != rendered_config:
        config_path.write_text(rendered_config, encoding="utf-8")
        if str(config_path.relative_to(root)) not in changes:
            changes.append(str(config_path.relative_to(root)))

    agents_block = (templates / "agents-block.md").read_text(encoding="utf-8")
    if replace_managed_block(root / "AGENTS.md", agents_block, AGENTS_START, AGENTS_END):
        changes.append("AGENTS.md")

    ignore_pattern = ".mwf/" if git_mode == "ignore" else ".mwf/local/"
    ignore_block = f"{GITIGNORE_START}\n{ignore_pattern}\n{GITIGNORE_END}\n"
    if replace_managed_block(root / ".gitignore", ignore_block, GITIGNORE_START, GITIGNORE_END):
        changes.append(".gitignore")

    rebuild_index(root)
    if ".mwf/index.md" not in changes:
        changes.append(".mwf/index.md")
    return changes


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value[0] in '[{"' or value in {"true", "false", "null"} or re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


def parse_record(path: Path) -> Record:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise MWFError(f"Missing frontmatter start in {path}")
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise MWFError(f"Missing frontmatter end in {path}") from exc

    metadata: dict[str, Any] = {}
    scope: dict[str, list[str]] = {}
    in_scope = False
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw == "scope:":
            in_scope = True
            continue
        if in_scope and raw.startswith("  "):
            key, separator, value = raw.strip().partition(":")
            if not separator:
                raise MWFError(f"Malformed scope entry in {path}: {raw}")
            parsed = parse_scalar(value)
            if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
                raise MWFError(f"Scope {key} must be an inline JSON string array in {path}")
            scope[key] = parsed
            continue
        in_scope = False
        key, separator, value = raw.partition(":")
        if not separator:
            raise MWFError(f"Malformed frontmatter entry in {path}: {raw}")
        metadata[key.strip()] = parse_scalar(value)
    metadata["scope"] = scope

    body_lines = lines[end + 1 :]
    title = next((line[2:].strip() for line in body_lines if line.startswith("# ")), path.stem)
    return Record(path=path, metadata=metadata, title=title, body="\n".join(body_lines).strip())


def record_paths(root: Path) -> Iterable[Path]:
    mwf = root / ".mwf"
    for directory in RECORD_DIRS:
        target = mwf / directory
        if target.is_dir():
            yield from sorted(target.rglob("*.md"))


def records(root: Path, tolerate_errors: bool = False) -> list[Record]:
    result: list[Record] = []
    for path in record_paths(root):
        try:
            result.append(parse_record(path))
        except (OSError, MWFError):
            if not tolerate_errors:
                raise
    return result


def json_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:48]


def next_record_id(root: Path, record_type: str) -> str:
    prefix = TYPE_INFO[record_type]["prefix"]
    day = today().replace("-", "")
    pattern = re.compile(rf"^{prefix}-{day}-(\d{{3}})$")
    used = []
    for path in record_paths(root):
        try:
            record_id = str(parse_record(path).metadata.get("id", ""))
        except MWFError:
            continue
        match = pattern.match(record_id)
        if match:
            used.append(int(match.group(1)))
    return f"{prefix}-{day}-{max(used, default=0) + 1:03d}"


def find_secrets(text: str) -> list[str]:
    return [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]


def normalized_text(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold(), flags=re.UNICODE))


def record_fingerprint(record: Record) -> str:
    scope = " ".join(
        f"{key}:{'|'.join(sorted(value.casefold() for value in record.scope[key]))}"
        for key in SCOPE_KEYS
    )
    return normalized_text(f"{record.metadata.get('type', '')} {record.metadata.get('summary', '')} {scope}")


def section_map(body: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = "body"
    sections[current] = []
    for line in body.splitlines():
        match = re.match(r"^##+\s+(.+?)\s*$", line)
        if match:
            current = match.group(1).strip().casefold()
            sections.setdefault(current, [])
        else:
            sections[current].append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items() if "\n".join(lines).strip()}


def incident_boundaries(record: Record) -> dict[str, str]:
    if record.metadata.get("type") != "incident":
        return {}
    sections = section_map(record.body)
    result: dict[str, str] = {}
    for heading, text in sections.items():
        if any(term in heading for term in ("applicability", "applies", "limits", "valid when")):
            result.setdefault("applicability", text)
        if any(term in heading for term in ("invalid", "does not apply", "failure condition", "obsolete when")):
            result.setdefault("invalid_when", text)
    return result


def candidate_body(summary: str) -> str:
    return (
        "## Candidate guidance\n\n"
        f"{summary}\n\n"
        "## Confirmation needed\n\n"
        "Confirm whether this is durable, its intended scope, and any exceptions before promotion."
    )


def render_record(record_id: str, record_type: str, status: str, title: str, summary: str, scope: dict[str, list[str]], body: str) -> str:
    lines = [
        "---",
        f"id: {record_id}",
        f"type: {record_type}",
        f"status: {status}",
        f"created: {today()}",
        f"updated: {today()}",
        f"summary: {json_string(summary)}",
        "scope:",
    ]
    lines.extend(f"  {key}: {json.dumps(scope[key], ensure_ascii=False)}" for key in SCOPE_KEYS)
    lines.extend(["---", "", f"# {title}", "", body.strip(), ""])
    return "\n".join(lines)


def add_record(root: Path, args: argparse.Namespace) -> Path:
    info = TYPE_INFO[args.type]
    status = args.status or info["default"]
    if status not in info["statuses"]:
        raise MWFError(f"Invalid status {status!r} for {args.type}; choose from {sorted(info['statuses'])}.")
    scope = {
        "paths": args.path or [],
        "file_types": args.file_type or [],
        "components": args.component or [],
        "tools": args.tool or [],
        "operations": args.operation or [],
        "phases": args.phase or [],
        "keywords": args.keyword or [],
    }
    directory = "candidates" if status == "candidate" else info["directory"]
    slug = slugify(args.title)
    if args.body is not None and args.body_file is not None:
        raise MWFError("Pass only one of --body or --body-file.")
    if args.body_file is not None:
        body = Path(args.body_file).expanduser().read_text(encoding="utf-8")
    elif args.body is not None:
        body = args.body
    elif status == "candidate":
        body = candidate_body(args.summary)
    else:
        raise MWFError("Non-candidate records require --body or --body-file so durable memory is not created incomplete.")
    if find_secrets("\n".join((args.title, args.summary, body))):
        raise MWFError("Potential sensitive content detected. Redact it before creating a shared memory record.")
    destination: Path | None = None
    for _ in range(1000):
        record_id = next_record_id(root, args.type)
        filename = record_id.lower() + (f"-{slug}" if slug else "") + ".md"
        candidate = root / ".mwf" / directory / filename
        try:
            with candidate.open("x", encoding="utf-8") as handle:
                handle.write(render_record(record_id, args.type, status, args.title, args.summary, scope, body))
        except FileExistsError:
            continue
        destination = candidate
        break
    if destination is None:
        raise MWFError("Could not allocate a unique record ID after repeated concurrent attempts.")
    rebuild_index(root)
    return destination


def pending_inbox_count(root: Path) -> int:
    path = root / ".mwf" / "inbox.md"
    if not path.is_file():
        return 0
    text = path.read_text(encoding="utf-8")
    pending = text.partition("## Pending")[2].partition("## Processed")[0]
    return sum(1 for line in pending.splitlines() if re.match(r"^\s*- \[ \]\s+\S", line))


def pending_inbox_items(root: Path) -> list[dict[str, Any]]:
    path = root / ".mwf" / "inbox.md"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    in_pending = False
    items: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines):
        if line.strip() == "## Pending":
            in_pending = True
            continue
        if in_pending and line.startswith("## "):
            break
        match = re.match(r"^\s*- \[ \]\s+(.+?)\s*$", line)
        if in_pending and match:
            text = match.group(1)
            items.append(
                {
                    "index": len(items) + 1,
                    "line_number": line_number,
                    "text": text,
                    "sensitive": bool(find_secrets(text)),
                }
            )
    return items


def process_inbox_item(
    root: Path,
    item_index: int,
    outcome: str,
    record_id: str | None,
    redact: bool,
    apply: bool,
) -> str:
    if not outcome.strip():
        raise MWFError("Inbox processing requires a concise --outcome.")
    if find_secrets(outcome):
        raise MWFError("The inbox outcome appears to contain sensitive content; redact it first.")
    if record_id and not any(str(record.metadata.get("id")) == record_id for record in records(root)):
        raise MWFError(f"Cannot link inbox disposition to unknown current record ID {record_id}.")
    items = pending_inbox_items(root)
    if item_index < 1 or item_index > len(items):
        raise MWFError(f"Pending inbox item {item_index} does not exist; choose 1..{len(items)}.")
    item = items[item_index - 1]
    sensitive = bool(item["sensitive"])
    if sensitive and not redact:
        raise MWFError("The selected item contains credential-like content; re-run with --redact so it is not preserved.")
    reference = f" [{record_id}]" if record_id else ""
    preserved = "[sensitive input redacted]" if redact else str(item["text"])
    processed_line = f"- {today()} — {preserved} → {outcome.strip()}{reference}"
    if not apply:
        return f"Would process inbox item {item_index} as: {processed_line}. Re-run with --apply."

    path = root / ".mwf" / "inbox.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[int(item["line_number"])]
    try:
        processed_heading = lines.index("## Processed")
    except ValueError as exc:
        raise MWFError("inbox.md is missing the '## Processed' heading.") from exc
    insert_at = processed_heading + 1
    while insert_at < len(lines) and not lines[insert_at].strip():
        insert_at += 1
    if insert_at < len(lines) and lines[insert_at].strip() == "No processed items yet.":
        del lines[insert_at]
    lines.insert(insert_at, processed_line)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    rebuild_index(root)
    return f"Processed inbox item {item_index} and rebuilt the index."


def duplicate_candidates(root: Path, threshold: float = 0.55) -> list[dict[str, Any]]:
    active = [record for record in records(root) if record.active and record.metadata.get("status") != "candidate"]
    matches: list[dict[str, Any]] = []
    for left_index, left in enumerate(active):
        left_tokens = token_set(f"{left.title} {left.metadata.get('summary', '')}")
        for right in active[left_index + 1 :]:
            if left.metadata.get("type") != right.metadata.get("type"):
                continue
            right_tokens = token_set(f"{right.title} {right.metadata.get('summary', '')}")
            union = left_tokens | right_tokens
            similarity = len(left_tokens & right_tokens) / len(union) if union else 0.0
            exact = record_fingerprint(left) == record_fingerprint(right)
            shared_routes = []
            for key in ("paths", "file_types", "components", "tools", "operations", "keywords"):
                overlap = sorted(set(value.casefold() for value in left.scope[key]) & set(value.casefold() for value in right.scope[key]))
                if overlap:
                    shared_routes.append(f"{key}=" + ",".join(overlap))
            paraphrased_route_match = len(shared_routes) >= 3 and len(left_tokens & right_tokens) >= 2
            if exact or (similarity >= threshold and shared_routes) or paraphrased_route_match:
                matches.append(
                    {
                        "left_id": left.metadata.get("id"),
                        "right_id": right.metadata.get("id"),
                        "type": left.metadata.get("type"),
                        "similarity": round(similarity, 4),
                        "exact_fingerprint": exact,
                        "shared_routes": shared_routes,
                    }
                )
    return matches


def render_existing_record(
    record: Record,
    *,
    status: str | None = None,
    summary: str | None = None,
    scope: dict[str, list[str]] | None = None,
    body: str | None = None,
) -> str:
    metadata = record.metadata
    resolved_scope = scope or record.scope
    lines = [
        "---",
        f"id: {metadata['id']}",
        f"type: {metadata['type']}",
        f"status: {status or metadata['status']}",
        f"created: {metadata['created']}",
        f"updated: {today()}",
        f"summary: {json_string(summary if summary is not None else str(metadata['summary']))}",
        "scope:",
    ]
    lines.extend(f"  {key}: {json.dumps(resolved_scope[key], ensure_ascii=False)}" for key in SCOPE_KEYS)
    known = {"id", "type", "status", "created", "updated", "summary", "scope"}
    for key in sorted(set(metadata) - known):
        lines.append(f"{key}: {json.dumps(metadata[key], ensure_ascii=False)}")
    lines.extend(["---", "", body.strip() if body is not None else record.body.strip(), ""])
    return "\n".join(lines)


def strip_primary_heading(body: str) -> str:
    lines = body.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def compact_duplicate(root: Path, canonical_id: str, duplicate_id: str, apply: bool) -> str:
    by_id = {str(record.metadata.get("id")): record for record in records(root)}
    canonical = by_id.get(canonical_id)
    duplicate = by_id.get(duplicate_id)
    if canonical is None or duplicate is None:
        raise MWFError("Both --canonical and --duplicate must identify current records.")
    if canonical_id == duplicate_id:
        raise MWFError("Canonical and duplicate IDs must be different.")
    if canonical.metadata.get("type") != duplicate.metadata.get("type"):
        raise MWFError("Only records of the same type can be compacted together.")
    if not canonical.active or not duplicate.active:
        raise MWFError("Compact only active records; inactive history already belongs in archive/.")
    if canonical.metadata.get("status") == "candidate" or duplicate.metadata.get("status") == "candidate":
        raise MWFError("Do not compact unresolved candidates; resolve their intended scope first.")
    if not apply:
        return (
            f"Would merge unique scope and evidence from {duplicate_id} into {canonical_id}, "
            f"archive {duplicate_id}, and rebuild the index. Re-run with --apply after confirming they are duplicates."
        )

    merged_scope = {
        key: sorted(dict.fromkeys([*canonical.scope[key], *duplicate.scope[key]]), key=str.casefold)
        for key in SCOPE_KEYS
    }
    canonical_body = canonical.body.strip()
    duplicate_detail = strip_primary_heading(duplicate.body)
    if duplicate_detail and normalized_text(duplicate_detail) not in normalized_text(canonical_body):
        canonical_body += f"\n\n## Merged evidence from {duplicate_id}\n\n{duplicate_detail}"
    canonical.path.write_text(
        render_existing_record(canonical, scope=merged_scope, body=canonical_body),
        encoding="utf-8",
    )

    inactive_status = INACTIVE_STATUS_BY_TYPE[str(duplicate.metadata["type"])]
    archive_body = (
        f"# Archived duplicate of {canonical_id}\n\n"
        f"This record was merged into `{canonical_id}` on {today()}. Its unique scope and evidence were preserved in the canonical record."
    )
    archive_path = root / ".mwf" / "archive" / duplicate.path.name
    if archive_path.exists():
        archive_path = archive_path.with_name(f"{archive_path.stem}-{timestamp()}{archive_path.suffix}")
    archive_path.write_text(
        render_existing_record(duplicate, status=inactive_status, body=archive_body),
        encoding="utf-8",
    )
    duplicate.path.unlink()
    rebuild_index(root)
    return f"Merged {duplicate_id} into {canonical_id}, archived the duplicate, and rebuilt the index."


def scope_hint(record: Record) -> str:
    hints: list[str] = []
    for key in SCOPE_KEYS:
        values = record.scope[key]
        if values:
            hints.append(f"{key}=" + ", ".join(values[:2]))
    return "; ".join(hints) if hints else "global"


def escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def rebuild_index(root: Path) -> Path:
    config = load_config(root)
    parsed = records(root)
    active = [record for record in parsed if record.active and record.metadata.get("status") != "candidate"]
    candidates = [record for record in parsed if record.metadata.get("status") == "candidate"]
    global_records = [record for record in active if not any(record.scope[key] for key in SCOPE_KEYS)]
    routed_records = [record for record in active if any(record.scope[key] for key in SCOPE_KEYS)]

    lines = [
        "# Memory index",
        "",
        f"Generated: {today()}  ",
        f"Schema version: {config.get('schema_version', 'unknown')}",
        "",
        "Read this file and `handoff.md` before loading detailed records.",
        "",
        "## Global active memory",
        "",
    ]
    if global_records:
        for record in sorted(global_records, key=lambda item: str(item.metadata.get("id", ""))):
            rel = record.path.relative_to(root / ".mwf").as_posix()
            lines.append(f"- **{record.metadata['id']}** ({record.metadata['type']}, {record.metadata['status']}): {record.metadata['summary']} — `{rel}`")
    else:
        lines.append("No records yet.")

    lines.extend(
        [
            "",
            "## Routed active memory",
            "",
            "| ID | Type | Status | Summary | Scope | Path |",
            "|---|---|---|---|---|---|",
        ]
    )
    for record in sorted(routed_records, key=lambda item: str(item.metadata.get("id", ""))):
        rel = record.path.relative_to(root / ".mwf").as_posix()
        values = (
            record.metadata.get("id", ""),
            record.metadata.get("type", ""),
            record.metadata.get("status", ""),
            record.metadata.get("summary", ""),
            scope_hint(record),
            f"`{rel}`",
        )
        lines.append("| " + " | ".join(escape_table(value) for value in values) + " |")

    lines.extend(["", "## Pending candidates", ""])
    if candidates:
        for record in sorted(candidates, key=lambda item: str(item.metadata.get("id", ""))):
            rel = record.path.relative_to(root / ".mwf").as_posix()
            lines.append(f"- **{record.metadata['id']}**: {record.metadata['summary']} — `{rel}`")
    else:
        lines.append("No candidates pending.")

    lines.extend(
        [
            "",
            "## Pending review",
            "",
            f"- Candidates: {len(candidates)}",
            f"- Inbox items: {pending_inbox_count(root)}",
            "",
        ]
    )
    destination = root / ".mwf" / "index.md"
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination


def token_set(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"\w+", text, flags=re.UNICODE) if len(token) > 1}


def contains_value(value: str, haystack: str) -> bool:
    return value.lower() in haystack.lower()


def recall_score(record: Record, args: argparse.Namespace) -> tuple[int, list[str]]:
    query = args.query or ""
    haystack = " ".join(
        [query, args.path or "", *(args.component or []), *(args.tool or []), *(args.operation or []), *(args.phase or []), *(args.file_type or [])]
    )
    score = 0
    reasons: list[str] = []
    scope = record.scope

    if not any(scope[key] for key in SCOPE_KEYS):
        score += 5
        reasons.append("global")

    if args.path:
        normalized = args.path.replace("\\", "/")
        for pattern in scope["paths"]:
            if fnmatch.fnmatch(normalized, pattern) or normalized == pattern.rstrip("/"):
                score += 100
                reasons.append(f"path:{pattern}")
                break

    for key, provided, weight in (
        ("components", args.component or [], 80),
        ("tools", args.tool or [], 80),
        ("operations", args.operation or [], 50),
        ("phases", args.phase or [], 50),
    ):
        matched = next((value for value in scope[key] if any(contains_value(value, item) or contains_value(item, value) for item in provided) or contains_value(value, query)), None)
        if matched:
            score += weight
            reasons.append(f"{key}:{matched}")

    matched_keywords = [value for value in scope["keywords"] if contains_value(value, haystack)]
    if matched_keywords:
        score += 15 * min(3, len(matched_keywords))
        reasons.extend(f"keyword:{value}" for value in matched_keywords[:3])

    file_match = False
    file_inputs = list(args.file_type or [])
    if args.path:
        file_inputs.append(Path(args.path).suffix)
        file_inputs.append(Path(args.path).name)
    for pattern in scope["file_types"]:
        if any(fnmatch.fnmatch(value, pattern) or value == pattern for value in file_inputs if value):
            file_match = True
            break
    if file_match and (matched_keywords or any(reason.startswith("operations:") for reason in reasons)):
        score += 20
        reasons.append("file_type")

    overlap = token_set(query) & token_set(f"{record.title} {record.metadata.get('summary', '')}")
    if overlap:
        score += min(10, len(overlap) * 2)
        reasons.append("summary:" + ",".join(sorted(overlap)[:4]))

    return score, reasons


def recall(root: Path, args: argparse.Namespace) -> list[dict[str, Any]]:
    matches = []
    for record in records(root):
        if not record.active:
            continue
        score, reasons = recall_score(record, args)
        if score <= 0:
            continue
        match = {
            "score": score,
            "id": record.metadata.get("id"),
            "type": record.metadata.get("type"),
            "status": record.metadata.get("status"),
            "summary": record.metadata.get("summary"),
            "path": str(record.path.relative_to(root)),
            "reasons": reasons,
        }
        boundaries = incident_boundaries(record)
        if boundaries:
            match["incident_boundaries"] = boundaries
        matches.append(match)
    return sorted(matches, key=lambda item: (-item["score"], str(item["id"])))[: args.limit]


def valid_date(value: Any) -> bool:
    try:
        dt.date.fromisoformat(str(value))
        return True
    except ValueError:
        return False


def doctor(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    mwf = root / ".mwf"
    if not mwf.is_dir():
        return ([f"Missing {mwf}"], warnings)

    for name in CORE_FILES:
        if not (mwf / name).is_file():
            errors.append(f"Missing core file: .mwf/{name}")
    for directory in ALL_DIRS:
        if not (mwf / directory).is_dir():
            errors.append(f"Missing directory: .mwf/{directory}/")

    try:
        config = load_config(root)
        version = int(config.get("schema_version", 0))
        if version != SCHEMA_VERSION:
            errors.append(f"Schema version is {version}; expected {SCHEMA_VERSION}.")
        if config.get("git_mode") not in {"track", "ignore"}:
            errors.append("config.json git_mode must be 'track' or 'ignore'.")
    except (MWFError, TypeError, ValueError) as exc:
        errors.append(str(exc))
        config = {}

    seen: dict[str, Path] = {}
    parsed_records: list[Record] = []
    for path in record_paths(root):
        rel = path.relative_to(root)
        try:
            record = parse_record(path)
        except (OSError, MWFError) as exc:
            errors.append(f"{rel}: {exc}")
            continue
        parsed_records.append(record)
        metadata = record.metadata
        missing = [field for field in ("id", "type", "status", "created", "updated", "summary", "scope") if field not in metadata]
        if missing:
            errors.append(f"{rel}: missing fields {', '.join(missing)}")
            continue
        record_type = str(metadata["type"])
        if record_type not in TYPE_INFO:
            errors.append(f"{rel}: unknown type {record_type!r}")
            continue
        info = TYPE_INFO[record_type]
        record_id = str(metadata["id"])
        if not re.fullmatch(rf"{info['prefix']}-\d{{8}}-\d{{3}}", record_id):
            errors.append(f"{rel}: ID {record_id!r} does not match type {record_type}")
        if record_id in seen:
            errors.append(f"Duplicate ID {record_id}: {seen[record_id].relative_to(root)} and {rel}")
        seen[record_id] = path
        if metadata["status"] not in info["statuses"]:
            errors.append(f"{rel}: invalid status {metadata['status']!r} for {record_type}")
        if path.parent.name == "candidates" and metadata["status"] != "candidate":
            errors.append(f"{rel}: records in candidates/ must have status candidate")
        for field in ("created", "updated"):
            if not valid_date(metadata[field]):
                errors.append(f"{rel}: invalid {field} date {metadata[field]!r}")
        if not str(metadata["summary"]).strip():
            errors.append(f"{rel}: summary is empty")
        scope = metadata.get("scope", {})
        for key in SCOPE_KEYS:
            if key not in scope or not isinstance(scope[key], list) or not all(isinstance(item, str) for item in scope[key]):
                errors.append(f"{rel}: scope.{key} must be a string array")
        if find_secrets(path.read_text(encoding="utf-8")):
            errors.append(f"{rel}: potential sensitive content detected")
        if record_type == "incident" and metadata.get("status") == "resolved":
            boundaries = incident_boundaries(record)
            if not boundaries.get("applicability"):
                warnings.append(f"{rel}: resolved incident should state an explicit Applicability section")
            if not boundaries.get("invalid_when"):
                warnings.append(f"{rel}: resolved incident should state an explicit Invalid when section")

    record_files = {path.resolve() for path in record_paths(root)}
    for path in sorted(mwf.rglob("*")):
        if not path.is_file() or path.resolve() in record_files:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if find_secrets(text):
            errors.append(f"{path.relative_to(root)}: potential sensitive content detected")

    try:
        duplicate_matches = duplicate_candidates(root, threshold=0.8)
    except (OSError, MWFError):
        duplicate_matches = []
    for duplicate in duplicate_matches:
        kind = "exact" if duplicate["exact_fingerprint"] else "likely"
        warnings.append(
            f"Possible {kind} duplicate records: {duplicate['left_id']} and {duplicate['right_id']} "
            f"(similarity {duplicate['similarity']:.2f})"
        )

    agents_text = (root / "AGENTS.md").read_text(encoding="utf-8") if (root / "AGENTS.md").is_file() else ""
    if AGENTS_START not in agents_text or AGENTS_END not in agents_text:
        errors.append("AGENTS.md is missing the managed memory-with-files block.")

    ignore_text = (root / ".gitignore").read_text(encoding="utf-8") if (root / ".gitignore").is_file() else ""
    expected_ignore = ".mwf/" if config.get("git_mode") == "ignore" else ".mwf/local/"
    if expected_ignore not in ignore_text:
        errors.append(f".gitignore does not protect {expected_ignore}")

    index_path = mwf / "index.md"
    if index_path.is_file():
        indexed = set(re.findall(r"`((?:preferences|decisions|incidents|tasks|knowledge|candidates)/[^`]+\.md)`", index_path.read_text(encoding="utf-8")))
        expected = {
            record.path.relative_to(mwf).as_posix()
            for record in parsed_records
            if record.active
        }
        for missing in sorted(expected - indexed):
            errors.append(f"Active record missing from index: {missing}")
        for stale in sorted(indexed - expected):
            errors.append(f"Index references inactive or missing record: {stale}")

    protocol_text = (mwf / "protocol.md").read_text(encoding="utf-8") if (mwf / "protocol.md").is_file() else ""
    if PROTOCOL_START not in protocol_text or PROTOCOL_END not in protocol_text:
        warnings.append(".mwf/protocol.md lacks the managed protocol markers; re-run init to refresh the fallback contract.")

    pending = pending_inbox_count(root)
    if pending:
        warnings.append(f"Inbox contains {pending} pending item(s).")
    candidates = sum(1 for record in parsed_records if record.metadata.get("status") == "candidate")
    if candidates:
        warnings.append(f"There are {candidates} candidate record(s) awaiting confirmation.")
    return errors, warnings


def migrate(root: Path, apply: bool, git_mode: str | None, language: str) -> str:
    config_path = root / ".mwf" / "config.json"
    if config_path.is_file():
        try:
            version = int(json.loads(config_path.read_text(encoding="utf-8")).get("schema_version", 0))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise MWFError(f"Cannot determine current schema: {exc}") from exc
    elif (root / ".mwf").is_dir():
        version = 0
    else:
        raise MWFError("No .mwf directory exists; use init instead of migrate.")

    if version > SCHEMA_VERSION:
        raise MWFError(f"Refusing to downgrade newer schema {version} to {SCHEMA_VERSION}.")
    if version == SCHEMA_VERSION:
        return f"Schema {SCHEMA_VERSION} is already current."
    if not apply:
        return f"Migration required: schema {version} -> {SCHEMA_VERSION}. Re-run with --apply and an explicit --git-mode."
    if git_mode not in {"track", "ignore"}:
        raise MWFError("Migration apply requires --git-mode track or --git-mode ignore.")

    backup = root / f".mwf-backup-{timestamp()}"
    shutil.copytree(root / ".mwf", backup)
    initialize(root, git_mode, language)
    return f"Migrated schema {version} -> {SCHEMA_VERSION}. Backup: {backup}"


def forget(root: Path, record_id: str, apply: bool) -> str:
    matches = []
    for record in records(root):
        if record.metadata.get("id") == record_id:
            matches.append(record.path)
    if not matches:
        raise MWFError(f"No current record has ID {record_id}.")
    if len(matches) > 1:
        raise MWFError(f"ID {record_id} is duplicated; run doctor and resolve the duplicate before deletion.")
    target = matches[0]
    if not apply:
        return f"Would permanently delete {target.relative_to(root)}. Re-run with --apply after explicit user authorization."
    target.unlink()
    rebuild_index(root)
    return f"Deleted {target.relative_to(root)} and rebuilt the index."


def add_root_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", help="Project root. Otherwise infer Git root or highest AGENTS.md.")


def add_record_arguments(parser: argparse.ArgumentParser, *, include_status: bool) -> None:
    add_root_argument(parser)
    parser.add_argument("--type", required=True, choices=tuple(TYPE_INFO))
    if include_status:
        parser.add_argument("--status")
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--body")
    parser.add_argument("--body-file")
    parser.add_argument("--path", action="append")
    parser.add_argument("--file-type", action="append")
    parser.add_argument("--component", action="append")
    parser.add_argument("--tool", action="append")
    parser.add_argument("--operation", action="append")
    parser.add_argument("--phase", action="append")
    parser.add_argument("--keyword", action="append")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a project-local .mwf memory filesystem.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize .mwf and install the managed AGENTS.md block.")
    add_root_argument(init_parser)
    init_parser.add_argument("--git-mode", required=True, choices=("track", "ignore"))
    init_parser.add_argument("--language", default="auto")

    recall_parser = subparsers.add_parser("recall", help="Rank active records relevant to the current task.")
    add_root_argument(recall_parser)
    recall_parser.add_argument("--query", default="")
    recall_parser.add_argument("--path")
    recall_parser.add_argument("--file-type", action="append")
    recall_parser.add_argument("--component", action="append")
    recall_parser.add_argument("--tool", action="append")
    recall_parser.add_argument("--operation", action="append")
    recall_parser.add_argument("--phase", action="append")
    recall_parser.add_argument("--limit", type=int, default=10)
    recall_parser.add_argument("--json", action="store_true")

    add_parser = subparsers.add_parser("add", help="Create a structured memory record and rebuild the index.")
    add_record_arguments(add_parser, include_status=True)

    propose_parser = subparsers.add_parser(
        "propose",
        help="Create a correctly typed candidate record without inventing a candidate record type.",
    )
    add_record_arguments(propose_parser, include_status=False)

    inbox_parser = subparsers.add_parser(
        "process-inbox",
        help="List or safely disposition one pending inbox item; semantic classification remains agent work.",
    )
    add_root_argument(inbox_parser)
    inbox_parser.add_argument("--item", type=int, help="One-based pending item number. Omit to list pending items.")
    inbox_parser.add_argument("--outcome", default="")
    inbox_parser.add_argument("--record-id")
    inbox_parser.add_argument("--redact", action="store_true")
    inbox_parser.add_argument("--apply", action="store_true")
    inbox_parser.add_argument("--json", action="store_true")

    duplicates_parser = subparsers.add_parser(
        "duplicates",
        help="Report likely duplicate active records without resolving semantic conflicts.",
    )
    add_root_argument(duplicates_parser)
    duplicates_parser.add_argument("--threshold", type=float, default=0.55)
    duplicates_parser.add_argument("--json", action="store_true")

    compact_parser = subparsers.add_parser(
        "compact",
        help="Merge a confirmed duplicate into a canonical record and archive it; dry-run by default.",
    )
    add_root_argument(compact_parser)
    compact_parser.add_argument("--canonical", required=True)
    compact_parser.add_argument("--duplicate", required=True)
    compact_parser.add_argument("--apply", action="store_true")

    index_parser = subparsers.add_parser("rebuild-index", help="Rebuild derived routing data from current records.")
    add_root_argument(index_parser)

    doctor_parser = subparsers.add_parser("doctor", help="Validate .mwf structure, records, index, and safety invariants.")
    add_root_argument(doctor_parser)
    doctor_parser.add_argument("--json", action="store_true")

    migrate_parser = subparsers.add_parser("migrate", help="Inspect or apply a recoverable schema migration.")
    add_root_argument(migrate_parser)
    migrate_parser.add_argument("--apply", action="store_true")
    migrate_parser.add_argument("--git-mode", choices=("track", "ignore"))
    migrate_parser.add_argument("--language", default="auto")

    forget_parser = subparsers.add_parser("forget", help="Permanently delete one explicitly authorized record.")
    add_root_argument(forget_parser)
    forget_parser.add_argument("--id", required=True)
    forget_parser.add_argument("--apply", action="store_true")
    return parser


def command_root(args: argparse.Namespace) -> Path:
    return discover_root(Path.cwd(), args.root)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = command_root(args)
        if args.command == "init":
            changes = initialize(root, args.git_mode, args.language)
            print("Initialized memory-with-files at", root)
            for change in changes:
                print("-", change)
        elif args.command == "recall":
            load_config(root)
            matches = recall(root, args)
            if args.json:
                print(json.dumps(matches, ensure_ascii=False, indent=2))
            elif not matches:
                print("No relevant active memory found.")
            else:
                for match in matches:
                    reasons = ", ".join(match["reasons"])
                    print(f"{match['score']:>3}  {match['id']}  {match['path']}\n     {match['summary']}\n     {reasons}")
                    boundaries = match.get("incident_boundaries", {})
                    for name, value in boundaries.items():
                        print(f"     {name}: {value}")
        elif args.command in {"add", "propose"}:
            load_config(root)
            if args.command == "propose":
                args.status = "candidate"
            destination = add_record(root, args)
            print("Created", destination.relative_to(root))
        elif args.command == "process-inbox":
            load_config(root)
            if args.item is None:
                items = pending_inbox_items(root)
                if args.json:
                    safe_items = [
                        {**item, "text": "[sensitive pending item]" if item["sensitive"] else item["text"]}
                        for item in items
                    ]
                    print(json.dumps(safe_items, ensure_ascii=False, indent=2))
                elif not items:
                    print("No pending inbox items.")
                else:
                    for item in items:
                        text = "[sensitive pending item; use --redact]" if item["sensitive"] else item["text"]
                        print(f"{item['index']}: {text}")
            else:
                print(process_inbox_item(root, args.item, args.outcome, args.record_id, args.redact, args.apply))
        elif args.command == "duplicates":
            load_config(root)
            matches = duplicate_candidates(root, args.threshold)
            if args.json:
                print(json.dumps(matches, ensure_ascii=False, indent=2))
            elif not matches:
                print("No likely duplicate active records found.")
            else:
                for match in matches:
                    routes = ", ".join(match["shared_routes"])
                    print(
                        f"{match['left_id']} <-> {match['right_id']}  "
                        f"similarity={match['similarity']:.2f}  {routes}"
                    )
        elif args.command == "compact":
            load_config(root)
            print(compact_duplicate(root, args.canonical, args.duplicate, args.apply))
        elif args.command == "rebuild-index":
            print("Rebuilt", rebuild_index(root).relative_to(root))
        elif args.command == "doctor":
            errors, warnings = doctor(root)
            if args.json:
                print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
            else:
                for error in errors:
                    print("ERROR:", error)
                for warning in warnings:
                    print("WARNING:", warning)
                if not errors and not warnings:
                    print("OK: .mwf is healthy.")
            return 1 if errors else 0
        elif args.command == "migrate":
            print(migrate(root, args.apply, args.git_mode, args.language))
        elif args.command == "forget":
            print(forget(root, args.id, args.apply))
        return 0
    except (MWFError, OSError) as exc:
        print(f"mwf: {exc}", file=sys.stderr)
        return 2


def _guard_legacy_writer(function):
    """Prevent this old writer from bypassing the TypeScript transaction lock."""
    @functools.wraps(function)
    def guarded(root, *args, **kwargs):
        config_path = Path(root) / ".mwf" / "config.json"
        if config_path.is_file():
            try:
                owner = json.loads(config_path.read_text(encoding="utf-8")).get("runtime_owner")
            except (OSError, json.JSONDecodeError):
                raise MWFError("Cannot verify memory ownership; use mwf doctor before writing.")
            if owner == "mwf-typescript":
                raise MWFError("This project uses the TypeScript MWF runtime. Use the mwf CLI or MCP tools; the legacy Python writer is disabled.")
        return function(root, *args, **kwargs)
    return guarded


for _writer_name in ("initialize", "add_record", "process_inbox_item", "compact_duplicate", "rebuild_index", "migrate", "forget"):
    globals()[_writer_name] = _guard_legacy_writer(globals()[_writer_name])


if __name__ == "__main__":
    raise SystemExit(main())
