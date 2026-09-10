# TypeScript migration — 2026-09-10

All maintained executable source is TypeScript: the MWF runtime, repository
install/uninstall/validation tools, bootstrap installer, build/acceptance scripts,
tests and generated Pi extension source. Runtime dependencies and schema-1 memory
formats are unchanged. Distributed entry points remain compiled JavaScript.

## Entry points and type checks

Repository tools now use `node --experimental-strip-types scripts/<name>.ts`.
The Python and Bash entry points have been removed; update existing shortcuts
using [the installation guide](installing-skills.md). Their options, default
preview behavior, installation destinations and backup/rollback rules remain.

The root private package owns repository development dependencies and strict
checks. `packages/mwf` retains its independent lockfile and distributable package.
`npm test` checks types and runs both suites. Package type checking builds runtime
code first so tests can validate the compiled output on a clean checkout.

Explicit `any` annotations have been replaced by typed arguments, operation/input
correlation and validated unknown boundaries. Test contracts validate operation
outputs before inspecting them. Pi's external acceptance API has a narrow contract
and is also exercised against its real loader.

`src/pi-adapter.ts` is compiled to a self-contained template. Setup inserts only
JSON configuration and retains the `.pi/extensions/mwf.js` ownership path. Tests
cover v1 refresh, idempotency, user-edit conflicts, detach and quoted project paths.

## Verification

| Check | Result |
| --- | --- |
| Clean build and full tests on Node 22.16.0 | 17 repository/skill tests + 25 MWF tests passed |
| Full tests on Node 26.7.0 | Same 42 tests passed |
| Strict type checks and formatting | Passed |
| Source-skill metadata, JSON and Markdown links | Both skills passed |
| Packaged runtime on Node 22.16 and 26.7 | Offline install into an empty cache; empty-PATH CLI/MCP checks passed |
| TS installer using bundled package | Preview, installation, repeat installation, paths with spaces and conflict retention passed |
| TS installer building from source on Node 22.16 | Dependency restore, build, pack, install and real MCP bootstrap passed |
| Pi 0.83.0 with adapter 2.32.1, Node 22.16 and 26.7 | Real loader, MCP tools, first-turn context, deduplication and resume passed |
| Existing legacy fixture contents | Unchanged |

Installation regressions additionally cover dangling symlinks, source escape,
parent traversal, cyclic links, staging validation failures and rollback after
failed final rename. Pi checks isolate their cache in a temporary agent directory.
No model call or user project setup is needed for these acceptance checks.

Two `.py` modules under `skills/memory-with-files/evals/fixtures/` remain as
example-project data; no build, test or runtime command executes them. Historical
review documents retain their dated descriptions. This verification was performed
on macOS; it does not establish Windows support.
