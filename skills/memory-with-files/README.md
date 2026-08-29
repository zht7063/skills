# Memory With Files

`memory-with-files` gives an agent durable, project-local memory that survives
sessions without relying on conversation history or lifecycle hooks. It stores
concise, retrievable records in a `.mwf/` directory and uses a managed
`AGENTS.md` block to ensure later sessions load the relevant context.

## When to use it

Use this skill when a project needs to retain decisions, user preferences,
incidents, blockers, workarounds, or handoff context across sessions. It also
covers initializing a new memory store and maintaining an existing one:
recalling records, processing the inbox, resolving duplicates or conflicts,
validating data, compacting history, migrating schema versions, and explicitly
forgetting information.

It is not intended for temporary instructions, routine progress updates, or
one-off failures with no likely future value.

## What it provides

- A portable `.mwf` filesystem protocol with structured memory records,
  generated index, handoff summary, candidate records, and user inbox.
- A standard-library command-line tool for initialization, scoped recall,
  record and candidate creation, inbox processing, diagnostics, duplicate
  detection, compaction, migration, and explicit forgetting.
- Clear authority rules: current user instructions and project facts override
  remembered information, while material conflicts are surfaced for a decision.
- Preservation-first maintenance so active facts remain accessible while stale
  or duplicate detail is archived rather than casually erased.

## Quick start

Install the skill from the repository root, then initialize it in the target
project with an explicit Git-tracking choice:

```bash
python3 scripts/install-skill.py memory-with-files
python3 skills/memory-with-files/scripts/mwf.py init --help
```

Once initialized, agents beginning or resuming work read `.mwf/index.md` and
`.mwf/handoff.md`, then recall only records relevant to the task rather than
loading the entire memory tree.

## Privacy and safety

Never store credentials, tokens, authentication material, or unrelated
personal data in `.mwf`. Shared project memory is Git-trackable by default;
the local-only area is always ignored. Removing sensitive content from the
current tree does not remove a prior Git-history copy, so history rewriting
requires separate, explicit authorization.

## Documentation and validation

The complete contract is in [SKILL.md](SKILL.md). Consult the
[protocol reference](references/protocol.md) for the record format and recall
rules, and the [operations reference](references/operations.md) for lifecycle
procedures. Validate the repository package from its root with:

```bash
python3 scripts/validate-all.py --tests
```
