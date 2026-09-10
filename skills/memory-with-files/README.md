# Memory With Files

MWF provides durable project-local memory using readable `.mwf` files.
The TypeScript CLI and local stdio MCP server implement deterministic operations;
this Skill is the light trigger and policy adapter.

## Install and connect

Follow the [runtime guide](../../packages/mwf/README.md). Build/install the local
package, then run:

```sh
mwf setup --root /absolute/project --harness codex,pi --git-mode track
```

Setup writes the managed AGENTS bootstrap block, registers the selected Harness,
and verifies an actual MCP bootstrap call. Merely copying this Skill does not
complete project setup. Runtime files and memory remain entirely local.

## Use

At task start/resume call bootstrap, then recall incrementally as scope changes.
Store durable guidance, decisions and verified solutions; use candidates for
ambiguous scope. Update handoff at milestones. Memory never overrides current
user instructions, formal project rules or verified facts.

Read [SKILL.md](SKILL.md) for triggers, [protocol](references/protocol.md) for
schema, and [operations](references/operations.md) for maintenance. Node.js 22.16+
is required. TypeScript is the sole runtime; legacy schema-1 data remains supported
and is verified using fixed compatibility fixtures in the runtime package.

## Existing memory

Python-era schema-1 `.mwf` files remain readable without conversion. Before
writing, stop old Python writers and explicitly adopt the project using the
installed TypeScript runtime:

```sh
mwf setup --root /absolute/project --harness codex --git-mode track
mwf doctor --root /absolute/project
```

Keep the project's existing Git preference: use `--git-mode ignore` if memory
should remain local. Setup refreshes managed rules and client configuration;
it preserves existing records and user content outside managed blocks.
Use `mwf init` instead when only memory initialization/adoption is needed.
For older schemas and recovery details, see the
[runtime migration guide](../../packages/mwf/README.md#migration-and-recovery).

## Validate

```sh
npm test --prefix packages/mwf
node --experimental-strip-types scripts/validate-all.ts --tests
```
