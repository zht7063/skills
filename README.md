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

## Skills

- [`memory-with-files`](skills/memory-with-files/README.md) — Durable,
  project-scoped agent memory in `.mwf`, including scoped recall, structured
  decisions and incidents, handoffs, safe maintenance, and a standard-library
  CLI.
- [`mihomo-remote-linux`](skills/mihomo-remote-linux/README.md) — A
  privacy-preserving, recovery-first guide for operating Mihomo on remote Linux
  hosts, from loopback proxy services to guarded system-wide TUN routing.

Repository-level commands under `scripts/` install skills for Codex, Pi Agent,
or a custom target, safely uninstall one exact skill, and validate all source
packages. See [docs/installing-skills.md](docs/installing-skills.md) for command
examples and safety behavior.

Generated review workspaces remain local and ignored.
