# Installing skills from this repository

Repository-level commands live under `scripts/`. They discover source packages
under `skills/` and never place installation logic inside a distributable
skill.

Commands require Node 22.16+ and run directly from TypeScript without installing
build dependencies. The former `python3 scripts/*.py` and Bash MWF installer
entry points have been replaced by the TS commands below; flags and installation
semantics are preserved. Update local shortcuts to the new invocation.

## MWF: install the runtime and connect the project

For Memory With Files, use [the MWF runtime guide](../packages/mwf/README.md). From the repository root, install and connect in one command (Node 22.16+ and npm required):

```sh
node --experimental-strip-types scripts/install-mwf.ts --root "/absolute/project" --harness codex --git-mode track
```

Add `--dry-run` to preview without writes; choose `--harness codex,pi` to include an already-installed Pi client. `--package /path/mwf.tgz` uses a bundled runtime instead of building the checkout.

`mwf setup --root /absolute/project --harness codex,pi --git-mode track` installs
project bootstrap rules and Harness configuration, then verifies the connection.
The generic Skill installer below installs only the light instruction adapter;
it does not install the MWF executable, MCP connection or project bootstrap.

## Install one skill

The default target is Codex and the default mode is a symbolic link:

```bash
node --experimental-strip-types scripts/install-skill.ts memory-with-files
```

This keeps the repository source authoritative: edits made here are visible to
new agent sessions without another copy step.

Install for Pi Agent:

```bash
node --experimental-strip-types scripts/install-skill.ts memory-with-files --agent pi
```

The Pi profile respects `PI_CODING_AGENT_DIR` and defaults to
`~/.pi/agent/skills`. The Codex profile respects `CODEX_HOME` and defaults to
`~/.codex/skills`.

Install a filtered standalone copy or use an explicit destination:

```bash
node --experimental-strip-types scripts/install-skill.ts memory-with-files --mode copy
node --experimental-strip-types scripts/install-skill.ts memory-with-files --target-dir /path/to/skills
```

Copy mode excludes root-level `evals/`, caches, bytecode, and local platform
metadata. Versioned test source is retained, matching the repository's `.skill`
packaging boundary. Use `--dry-run` to inspect resolved paths without writing.

## Updating and collisions

Installation refuses to overwrite an occupied destination. An existing link
to the same source is treated as already installed. To replace another copy or
link, use:

```bash
node --experimental-strip-types scripts/install-skill.ts memory-with-files --replace
```

The previous destination is moved to a timestamped backup beneath
`.skill-install-backups/` outside the active skills directory before the new
installation becomes visible.

## Uninstall

Uninstall is a dry run unless `--apply` is supplied:

```bash
node --experimental-strip-types scripts/uninstall-skill.ts memory-with-files
node --experimental-strip-types scripts/uninstall-skill.ts memory-with-files --apply
node --experimental-strip-types scripts/uninstall-skill.ts memory-with-files --agent pi --apply
```

The command resolves one exact skill name and refuses to recursively operate
on a broad target.

## Validate repository skills

Run structural, metadata, JSON, and local Markdown-link checks for every skill:

```bash
node --experimental-strip-types scripts/validate-all.ts
```

Also run TypeScript test suites found in individual skills:

```bash
node --experimental-strip-types scripts/validate-all.ts --tests
```
