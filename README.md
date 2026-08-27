# Skills Repository

This repository is the source workspace for independently installable agent skills and the repository-level tooling used to build, validate, evaluate, and install them.

## Layout

```text
skills/
  <skill-name>/          One self-contained skill package
scripts/                 Future repository-wide install and validation tools
docs/                    Repository conventions and design notes
```

The first skill will live at `skills/memory-with-files/`. Generated evaluation workspaces, packaged artifacts, and local agent planning state are intentionally excluded from Git.

See [docs/repository-layout.md](docs/repository-layout.md) for the detailed structure and conventions.

## Repository status

The first skill, [`memory-with-files`](skills/memory-with-files/SKILL.md), is implemented and has completed behavioral evaluation. It provides a portable `.mwf` project-memory protocol, managed `AGENTS.md` fallback instructions, and a standard-library CLI for initialization, scoped recall, typed candidate creation, inbox processing, health checks, duplicate detection, preservation-first compaction, migration, and explicit forgetting.

Generated review workspaces remain local and ignored. Repository-wide installation and validation commands can be added under `scripts/` after the first skill package is accepted.
