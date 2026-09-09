# Operations

Use `mwf --help` for exact command syntax. Use the installed TypeScript CLI and always pass `--root`. Node.js 22.16+ is required; no Python MWF runtime is shipped.

## Initialize

1. Detect the root: Git root first, otherwise the highest applicable `AGENTS.md`. If neither exists, obtain an explicit root from the user.
2. Use an already stated Git preference; otherwise ask whether shared `.mwf` content should be `track`ed or `ignore`d by Git. Do not infer the answer on first initialization.
3. Run:

   ```bash
   mwf init --root /path/to/project --git-mode track
   ```

4. The command creates missing `.mwf` files, creates record directories, installs or refreshes the managed `AGENTS.md` block, and updates the managed `.gitignore` block.
5. Existing records are not overwritten. Re-running initialization is idempotent.
6. Run `doctor` and report created or changed files.

Use `mwf setup` for complete Harness registration plus project initialization and verification. `mwf init` only installs project memory and its managed `AGENTS.md` block. Neither should run on every session start; use bootstrap then.

## Recall

At task start, read `.mwf/index.md` and `.mwf/handoff.md`. Derive only the keys that matter to the task.

Examples:

```bash
mwf recall --root /path/to/project --query "document the GT experiment"
mwf recall --root /path/to/project --path experiments/gt/runner.py --operation documentation
mwf recall --root /path/to/project --file-type .pdf --tool pandoc --operation conversion
```

Treat the result as a shortlist. Read the returned records before acting; do not interpret a low-confidence keyword match as a rule.

For incidents, do not stop at the summary. Read the complete record and carry its `Applicability` and `Invalid when` boundaries into the working plan or handoff when they affect the next action. State both a scoped prohibition and any known safe use of the previously failed approach.

## Add or update a record

Use `add` for a new record when the type, status, title, summary, and scope are known. The command allocates a stable ID and rebuilds the index.

```bash
mwf add \
  --root /path/to/project \
  --type incident \
  --status resolved \
  --title "Convert the legacy report without Pandoc" \
  --summary "Use LibreOffice headless because Pandoc loses embedded objects." \
  --tool pandoc --tool libreoffice \
  --operation conversion --file-type .docx \
  --body-file /path/to/prepared-incident-body.md
```

Non-candidate records require `--body` or `--body-file`; this prevents an accepted durable record from being created with missing evidence or limits. For updates, use `mwf update --root /path/to/project --id ID` with the revised fields; preview first and use `--apply` to commit. The runtime preserves identity and rebuilds routing.

Do not use `add` when the user statement is ambiguous. Create a correctly typed candidate with:

```bash
mwf propose \
  --root /path/to/project \
  --type preference \
  --title "Clarify Pandoc usage" \
  --summary "The durable scope of the user's Pandoc guidance is unclear." \
  --tool pandoc --operation conversion
```

The candidate is stored in `candidates/` with its concrete type and `status: candidate`.

## Process the inbox

1. List only the `Pending` section without echoing credential-like content:

   ```bash
   mwf process-inbox --root /path/to/project
   ```

2. Classify each item using the protocol.
3. Create or update records. Sensitive items are redacted and not persisted elsewhere.
4. Move processed entries deterministically. The command is dry-run by default:

   ```bash
   mwf process-inbox \
     --root /path/to/project --item 1 \
     --outcome "Created a scoped preference candidate" \
     --record-id PREF-20260827-003 --apply
   ```

   For sensitive input, add `--redact`; the original value is not copied into `Processed`.
5. Rebuild the index and update the pending count.

If a pending item is materially ambiguous, create a candidate and ask at the next appropriate checkpoint.

## Update the handoff

Update the handoff when the goal changes, a deliverable finishes, a significant decision or blocker appears, or the current work is preparing to stop.

Keep it short. State what the next session must know and do, not everything the current session did. Preserve unresolved candidates and inbox items in the relevant sections or record references.

## Validate and repair

Run:

```bash
mwf doctor --root /path/to/project
```

The doctor reports missing core files, malformed frontmatter, invalid IDs or statuses, duplicate IDs, likely duplicate records, stale index entries, broken record paths, missing Git-ignore protection for `local/`, unprocessed inbox items, resolved incidents without explicit applicability boundaries, and credential-like content anywhere in the current `.mwf` tree, including inbox, handoff, local, and archive files.

Safe derived-data repairs may be applied with:

```bash
mwf rebuild-index --root /path/to/project
```

Do not automatically rewrite an ambiguous record or select a winner in a semantic conflict.

## Compact and archive

Compaction is semantic work, not a line-count operation.

1. Run the doctor and inspect inactive, duplicated, or weakly routed records. Use `mwf duplicates --root /path/to/project` to obtain a non-destructive shortlist.
2. Compare scope, rationale, evidence, and replacement conditions.
3. Merge duplicate active conclusions without losing unique limits or validation evidence.
4. After confirming two records are semantic duplicates, preview and apply a preservation-first merge:

   ```bash
   mwf compact --root /path/to/project \
     --canonical INC-20260827-001 --duplicate INC-20260827-002
   mwf compact --root /path/to/project \
     --canonical INC-20260827-001 --duplicate INC-20260827-002 --apply
   ```

   The command unions scope, appends unique evidence to the canonical record, and moves a redirect stub to `archive/`.
5. Rebuild the index and run the doctor again.

Ask the user before resolving a conflict that changes an active rule or accepted decision.

## Migrate

Migration must be recoverable. Existing schema-1 memory is readable directly; explicitly run `mwf init` or `mwf setup` with a Git mode before new writes. Stop any externally installed old writers before adoption.

1. Run `migrate` without `--apply` to inspect the current schema and proposed action.
2. If migration is needed, run with `--apply`; supply `--git-mode track` or `ignore`; the command saves a recoverable backup under `.mwf/local/backups/` before changing files.
3. Preserve unknown files and user-authored inbox content.
4. Run the doctor and review the diff.

Never downgrade a newer unknown schema.

## Forget or remove memory

- For ordinary obsolescence, change status and archive the record.
- For an explicit user request to forget, delete the matching current records, remove their index routes, and rebuild the index.
- For sensitive data, remove it immediately from the current tree and warn about possible Git history copies.
- Do not rewrite Git history or remove unrelated records without explicit authorization.

When the requested target is ambiguous, show the matching IDs and ask which ones to remove.
