# MWF — local file memory

A TypeScript CLI and stdio MCP server share one Core. Memory remains readable,
Git-trackable Markdown in each project's `.mwf/`. No network service or model
API is needed for file operations. Node **22.16+** is required. Tested locally
with Node 26.7, Codex CLI 0.153.4 and Pi 0.83.0.

## One-command installation

From a source checkout, with Node **22.16+** and npm installed:

```sh
bash scripts/install-mwf.sh --root "/absolute/project" --harness codex --git-mode track
```

The script builds the current checkout, installs the runtime under
`~/.local/share/mwf`, runs project setup and verifies the MCP connection.
It does not require sudo or change your shell PATH. It prints the absolute CLI
command afterward. Restart/reload the client and trust the project to activate it.
Use `--harness codex,pi` for both clients (Pi must already be installed).
Building and installing the Pi adapter may need network access.

For an existing bundled tarball, skip the build and install the runtime offline:

```sh
bash scripts/install-mwf.sh --package /path/zht7063-mwf-0.1.0.tgz --root "/absolute/project" --harness codex --git-mode track
```

Use `--prefix /custom/runtime` to change the installation directory, `--git-mode
ignore` for local-only memory, and `--dry-run` to print the installation plan
without writes (this does not validate project setup conflicts). The script
requires an explicit existing project and Git mode. Repeating it refreshes the
runtime and reruns idempotent setup. If setup fails, the installed runtime and
completed setup steps remain available for diagnosis and retry. Stop active MWF
sessions before upgrading the runtime. A hosted `curl | bash` distribution is
not yet published; this entry point runs from the checkout.

## Build and install

From the repository root:

```sh
npm ci --prefix packages/mwf
npm test --prefix packages/mwf
npm pack ./packages/mwf --pack-destination /tmp
npm install -g /tmp/zht7063-mwf-0.1.0.tgz
mwf --version
```

This is an unpublished local package. It ships compiled JavaScript, templates
and light adapters; it does not need Python, tsx, ts-node or the source checkout
at runtime. Installation does not use npm postinstall to guess project roots.
The repository lockfile fixes the build inputs; runtime dependencies are bundled into the tarball for reproducible offline installation. Pin releases rather than downloading `latest` on every MCP startup.

## Connect a project

```sh
mwf setup --root /absolute/project --harness codex,pi --git-mode track --dry-run
mwf setup --root /absolute/project --harness codex,pi --git-mode track
```

Choose `ignore` for entirely local memory. Local runtime data is always ignored.
Use `--harness codex` or `--harness pi` for one client. Setup:

1. Validates the project, schema, existing configuration and planned changes.
2. For Pi, installs project-local `pi-mcp-adapter@2.32.1` through `pi install -l`;
   respects `PI_CODING_AGENT_DIR` and refuses an incompatible project pin.
3. Initializes memory and installs the versioned managed `AGENTS.md` block.
4. Writes project `.codex/config.toml` and `.agents/skills/` for Codex, or
   `.pi/mcp.json` plus a small `.pi/extensions/mwf.js` for Pi. Absolute Node and
   CLI paths avoid depending on a GUI's shell PATH.
5. Starts the actual stdio server, lists its tools and calls bootstrap.

Restart/reload the Harness and trust the project through its normal mechanism.
A connection probe does not load memory into an already-running conversation.
Codex follows the project AGENTS bootstrap rule; Pi's first-turn extension
loads bootstrap deterministically via the same CLI Core before its agent loop.
Pi's MCP adapter provides subsequent tool calls. It registers direct tools after
initialization (awaited on its input event); actual Pi names are `mwf_mwf_*`.

`--no-install-pi-adapter` requires the pinned package already installed and
configured project-locally. Installing a dependency may require network; normal
memory operations do not. Pi adapter failure stops setup with a clear error.
Successful dependency installation is retained for retry if a later stage fails.

Global Skill installation alone does **not** connect a project. `mwf init`
initializes project files and rules only; `setup` additionally registers clients.
No operation silently initializes a missing memory store during recall.

## Operations

All CLI operations except MCP/help/version emit JSON. Use `--input JSON` or
`--input-file FILE` for structured arguments; the same schemas power MCP.

```sh
mwf bootstrap --root /project --query 'continue the converter work'
mwf recall --root /project --path reports/a.docx --operation conversion
mwf add --root /project --type preference --title 'Use clear names' \
  --summary 'Use descriptive exported names' --body '## Guidance\nExplain public interfaces.' \
  --component public-api --request-id stable-request-identifier
mwf doctor --root /project
mwf handoff --root /project --goal 'Finish migration' --completed 'Core verified' \
  --next-action 'Verify installed package'
```

For multiline bodies prefer an input JSON file or `--body-file`; a quoted shell
`\n` is not automatically converted into a newline.

| CLI | MCP | Behavior |
|---|---|---|
| init | mwf_init | Explicit Git mode; `dry_run` available |
| status / doctor | mwf_status / mwf_doctor | Connection status / memory health |
| bootstrap / recall | mwf_bootstrap / mwf_recall | Start/resume context / incremental recall |
| add / propose | mwf_add / mwf_propose | Confirmed memory / typed candidate |
| update | mwf_update | Preview/apply correction or candidate promotion |
| handoff | mwf_handoff | Structured milestone/next-action summary |
| process-inbox | mwf_process_inbox | List, preview, disposition or redact |
| duplicates / compact | mwf_duplicates / mwf_compact | Shortlist / confirmed evidence-preserving merge |
| rebuild-index | mwf_rebuild_index | Rebuild derived routing; no Git operations |
| migrate / forget | mwf_migrate / mwf_forget | Backed-up migration / explicit record deletion |

Update, compact, migrate, forget and inbox disposition preview by default. Apply
only a reviewed/authorized action using `--apply`. Semantic equivalence and
material conflicts still require agent/user judgment. Scope arrays are `paths`,
`file_types`, `components`, `tools`, `operations`, `phases`, `keywords`.

A write's `request_id` identifies one logical operation. Retry with the same ID
and identical arguments after response loss; changed input with the same ID fails.
Receipts survive restart. Do not reuse an ID for an intentional new operation.

Run `mwf mcp --root /project` only as a stdio server. It is bound to that exact
canonical project root; another project needs its own configured instance.
Stdout contains only MCP frames; errors and diagnostics use stderr.

## Migration and recovery

File schema stays at 1. Existing Python memory is readable without conversion.
Run explicit `init`/`setup` to adopt a schema-1 legacy project before TS writes. Older schemas require backed-up `migrate --apply` first. The
repository's Python writer refuses projects marked `runtime_owner: mwf-typescript`.
Older copies of that script cannot be controlled: stop old sessions/writers before
adoption. Keep the existing Python tests as compatibility reference.

All new reads/writes take a project lock. A tiny `.mwf/local/runtime.sqlite`
file provides the OS-backed mutex via Node's built-in SQLite; **no memory records
or authoritative state are stored in this database**. Do not delete or replace
this file while processes are running. No timeout-based lock stealing is used.

Each mutation validates its full plan, persists a forward-recovery journal, then
atomically replaces individual files. New calls first recover interrupted work.
Recovery compares old/target hashes and refuses to overwrite a third-party edit.
A conflicting journal remains at `.mwf/local/transaction.json`; inspect it and
restore the intended before/after state before retrying. Do not discard it blindly.
Index data is derived from records. Atomicity across multiple files applies to
cooperating MWF calls, not arbitrary editors observing intermediate changes.

The supported locking environment is a **single machine and local filesystem**.
Independent Git branches/worktrees can still produce conflicting IDs when merged;
`doctor` detects duplicates. No automatic Git synchronization is performed.

Schema migration preserves an MWF-owned backup under `.mwf/local/backups/`.
Forgetting a record or redacting intake also removes those snapshots to avoid
retaining a hidden copy. It does not remove quotations in other records, external
backups, filesystem snapshots or Git history. Credential detection is heuristic;
never store secrets intentionally.

## Detach or upgrade

```sh
mwf detach --root /project           # preview
mwf detach --root /project --apply   # restore setup-owned adapter files
```

Detach refuses changed owned files, preserves memory, its AGENTS fallback and
Git-ignore protection, and leaves a shared Pi adapter installed. Resolve a
reported conflict rather than overwriting user edits. Upgrade the installed
package, then rerun setup to refresh executable paths and generated adapters.
Setup is idempotent and refuses unmanaged configuration collisions.

## Validation

```sh
npm test --prefix packages/mwf
python3 scripts/validate-all.py --tests
```

Tests cover legacy recall equivalence, strict inputs, secret redaction, candidate
promotion, maintenance, concurrent writers, killed-writer recovery, external edits,
symlinks, persistent idempotency, real MCP calls and setup/detach. Optional Pi
acceptance uses the actual installed Pi loader and extension runner without a
model/API call; see `scripts/check-pi.mjs`. Packed installation and Codex smoke
results are recorded in the repository implementation notes.
