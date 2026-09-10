# Skills Repository

This repository is the source workspace for independently installable agent skills and the repository-level tooling used to build, validate, evaluate, and install them.

## Layout

```text
skills/
  <skill-name>/          One self-contained skill package
packages/mwf/            TypeScript CLI, local MCP and Harness setup
scripts/                 Repository-wide install and validation tools
docs/                    Repository conventions and design notes
```

Skill packages live under `skills/<skill-name>/`. Generated evaluation workspaces, packaged artifacts, and local agent planning state are intentionally excluded from Git.

See [docs/repository-layout.md](docs/repository-layout.md) for the detailed structure and conventions.

## Skills

- [`memory-with-files`](skills/memory-with-files/README.md) — Durable,
  project-scoped agent memory in `.mwf`, including scoped recall, structured
  decisions and incidents, handoffs, safe maintenance, and a local TypeScript CLI/MCP runtime.
- [`mihomo-remote-linux`](skills/mihomo-remote-linux/README.md) — A
  privacy-preserving, recovery-first guide for operating Mihomo on remote Linux
  hosts, from loopback proxy services to guarded system-wide TUN routing.

Repository-level commands under `scripts/` install skills for Codex, Pi Agent,
or a custom target, safely uninstall one exact skill, and validate all source
packages. See [docs/installing-skills.md](docs/installing-skills.md) for command
examples and safety behavior.

Generated review workspaces remain local and ignored.

## MWF local runtime

MWF uses TypeScript as its sole runtime and requires Node.js 22.16+.
Its installation includes deterministic project setup, not just Skill copying.
Build and install the local package, then connect a project:

```bash
npm ci --prefix packages/mwf
npm run build --prefix packages/mwf
npm install -g ./packages/mwf
mwf setup --root /absolute/project --harness codex,pi --git-mode track
```

See [the runtime guide](packages/mwf/README.md) for packaging, migration,
recovery guarantees and verification. The package has not been published to npm.

Existing Python-era schema-1 `.mwf` memory is readable without conversion.
Before new writes, stop old writers and explicitly adopt the project with
`mwf setup`, preserving its `track` or `ignore` Git mode. See
[legacy compatibility and adoption](packages/mwf/README.md#migration-and-recovery).

Local `node_modules/` directories and build outputs are Git-ignored. Commit
`package.json` and `package-lock.json`; restore dependencies with `npm ci`.

## Development

All maintained executable source, repository scripts, tests and the Pi adapter
are TypeScript. Requires Node **22.16+** and npm. Restore both independent
lockfiles before running the full checks:

```sh
npm ci
npm ci --prefix packages/mwf
npm test
npm run format:check
npm run test:package --prefix packages/mwf
```

`npm test` checks types for runtime, tooling and tests, runs repository and skill
tests, validates skills and runs MWF integration tests. Repository commands use
`node --experimental-strip-types scripts/<command>.ts` and need no build step or
third-party loader. The published-package layout continues to use compiled JS;
TS scripts and development dependencies are not shipped. See
[installation commands](docs/installing-skills.md).

The two Python modules under evaluation fixtures represent example user projects;
they are test data and are never executed by the repository toolchain. Historical
review documents preserve their original Python-era descriptions.
