# `.mwf` protocol

## Purpose

`.mwf` is a project-local, agent-neutral memory filesystem. It preserves only information likely to change a later agent's decisions: durable user rules, project constraints, decisions, reusable solutions, open blockers, and a concise handoff.

The protocol does not rely on chat transcripts or lifecycle hooks. A managed project `AGENTS.md` block bootstraps the protocol on every compatible agent session.

## Directory structure

```text
.mwf/
├── config.json
├── protocol.md
├── index.md
├── handoff.md
├── inbox.md
├── preferences/
├── decisions/
├── incidents/
├── tasks/
├── knowledge/
├── candidates/
├── archive/
└── local/
```

| Path | Meaning |
|---|---|
| `config.json` | Schema version, Git mode, language, and initialization metadata. |
| `protocol.md` | Small project-local fallback contract for agents that do not load this skill. |
| `index.md` | Generated routing summary; read at task start. |
| `handoff.md` | Current stage, completed work, blockers, and next action; read at task start. |
| `inbox.md` | User-editable intake. Agents classify pending items into managed records. |
| `preferences/` | Durable user preferences and project-specific behavioral rules. |
| `decisions/` | Accepted or proposed technical and product decisions. |
| `incidents/` | Open problems, failed approaches, root causes, and verified resolutions. |
| `tasks/` | Durable planned, active, blocked, or completed project work worth handing off. |
| `knowledge/` | Terminology, environment facts, command recipes, dependencies, and reusable project knowledge. |
| `candidates/` | Ambiguous steering awaiting user confirmation. |
| `archive/` | Compressed historical detail and inactive records. |
| `local/` | Private local memory that is always excluded from Git. |

## Authority

Apply this order when two sources disagree:

1. Current user instruction.
2. Formal project instructions and documentation.
3. Current code and verified runtime facts.
4. Confirmed active memory.
5. Historical or inactive memory.

A lower source never silently overrides a higher one. Ask the user when the conflict is material or the intended scope cannot be inferred safely. After resolution, update the memory so the ambiguity does not recur.

## Record schema

Store one durable record per Markdown file. Use YAML frontmatter with inline JSON arrays so the files remain readable without a YAML library:

```markdown
---
id: PREF-20260827-001
type: preference
status: stable
created: 2026-08-27
updated: 2026-08-27
summary: Keep the auxiliary GT module out of formal documentation.
scope:
  paths: ["experiments/gt/**"]
  file_types: []
  components: ["GT test module"]
  tools: []
  operations: ["documentation", "repository exploration"]
  phases: []
  keywords: ["ground truth", "GT evaluation"]
---

# Do not document the auxiliary GT module

## Context

The module is enabled for the experiment but is an auxiliary implementation detail.

## Guidance

Do not add it to formal project documentation unless the user explicitly requests it.

## Rationale and limits

This applies when documenting or mapping the experiment. It does not require disabling the module.
```

Required fields are `id`, `type`, `status`, `created`, `updated`, `summary`, and every scope list. Dates use `YYYY-MM-DD` in the project's local timezone.

Use these prefixes and status lifecycles:

| Type | Prefix | Lifecycle |
|---|---|---|
| Preference or rule | `PREF` | `candidate → stable → deprecated` |
| Decision | `DEC` | `proposed → accepted → superseded` |
| Incident or reusable solution | `INC` | `open → resolved → obsolete` |
| Durable task, risk, or debt | `TASK` | `planned → active → blocked → completed` |
| Project knowledge or recipe | `KNOW` | `stable → deprecated` |

Candidate records live in `candidates/` regardless of their eventual type. Keep IDs stable when moving or updating a record.

### Type-specific content

Preferences explain the rule, context, reason, scope, and exceptions.

Decisions explain the problem, selected option, alternatives, rationale, consequences, and replacement conditions.

Incidents explain:

- the problem and environment;
- why each attempted approach was reasonable;
- the observed failure and root cause;
- the final solution, if known;
- why the final solution works and how it was validated;
- positive applicability: where the successful approach is appropriate and where a failed approach remains acceptable;
- invalidation conditions: when the workaround should no longer be trusted or used.

Use explicit `## Applicability` and `## Invalid when` sections for resolved incidents. The doctor warns when either boundary is missing. This is not formatting for its own sake: retrieval must not turn “Pandoc failed on embedded objects” into “never use Pandoc for any document.”

Tasks explain the current objective, state, blockers, affected area, and next action.

Knowledge records explain the fact or recipe, evidence or verification method, and conditions under which it may become stale.

## Scope and recall

Scope is a retrieval route, not an authorization rule. Use these dimensions:

- `paths`: project-relative paths or glob patterns;
- `file_types`: suffixes or glob forms such as `*.pdf`;
- `components`: module, service, feature, or domain names;
- `tools`: commands, libraries, services, or applications;
- `operations`: actions such as conversion, testing, deployment, or documentation;
- `phases`: project stages such as prototype, migration, or release;
- `keywords`: aliases and semantic hints.

Recall rules:

1. An exact path, component, or tool match loads the record directly.
2. A broad file-type match requires a matching operation or keyword.
3. A keyword-only match first exposes the index summary; load the record only when relevance is clear.
4. Multiple independent matches raise priority.
5. Empty scope means project-global. Read its index summary at every task start, and load the full record only when needed.

Read `index.md` and `handoff.md` before detailed records. Never read the entire tree just because it exists.

When a recalled record is an incident, read its complete body before acting or writing a handoff. Preserve all of these when relevant:

1. the failed approach and its observed failure;
2. the successful approach and verification evidence;
3. where the workaround applies;
4. where the failed approach remains valid;
5. the conditions that invalidate the workaround.

## Write and confirmation rules

Write clear durable rules, accepted decisions, verified solutions, important blockers, and checkpoint handoffs without interrupting the user for every file change. Mention material memory updates in the task summary.

Use a candidate when wording lacks durable or scoped intent. Confirm candidates at the earliest of:

- completion of the current small task;
- preparation for handoff;
- before the candidate affects implementation;
- discovery of a conflict with active memory or formal rules.

An interrupted session leaves the candidate unchanged for the next session.

A candidate is always a status on a concrete type. For example, ambiguous tool guidance is commonly `type: preference` with `status: candidate`; `type: candidate` and `status: pending` are invalid.

Do not persist instructions explicitly limited to the current attempt, session, active coordination window, or temporary phase. Examples include skipping a full test once, deferring mobile work for the current phase, or avoiding a file while another agent is editing it.

## Inbox

Users place manual memory input in `inbox.md`. Preserve their wording until it is processed.

For each pending item:

1. Determine whether it is durable, temporary, ambiguous, sensitive, conflicting, or duplicate.
2. Reject and redact sensitive content.
3. Create or update the appropriate managed record, or create a candidate.
4. Move the checklist item to `Processed`, keep a concise original summary, and link the resulting record ID or state why it was not stored.

Do not erase unprocessed user input or silently reinterpret material ambiguity.

## Index

`index.md` is derived data. It contains:

- schema version and generation date;
- current global rules;
- routing rows for active shared records with ID, type, status, summary, scope hints, and relative path;
- pending candidate and inbox counts;
- no private content from `local/`.

Rebuild it after adding, moving, changing status, archiving, or deleting records.

## Handoff

`handoff.md` is a concise handoff, not an audit log. Keep these sections current:

- current goal and stage;
- completed since the previous handoff;
- decisions that affect the next session;
- blockers and open questions;
- next action;
- relevant record IDs.

Do not copy commit history, full test output, or line-level changes. Summarize important file changes by purpose and affected area.

## Git and private memory

Default to tracking shared `.mwf` content. Ask during first initialization whether the user instead wants the entire memory tree ignored, and record the answer in `config.json`.

Always ignore `.mwf/local/`. Never route local records into the shared index. Shared records must be safe for the repository's intended audience.

## Security

Never store secrets, credentials, cookies, tokens, private keys, complete authentication material, exploitable internal credentials, or unrelated personal information. Redact logs and environment values when exact content is unnecessary.

If sensitive content is found, remove it from the current `.mwf` tree immediately. Warn that a committed value may remain in Git history. Rewriting history requires separate explicit authorization.

## Compaction and archival

Compact based on retrieval quality, redundancy, and staleness rather than a fixed line threshold.

- Never remove an active fact merely to shorten a file.
- Merge duplicates into one active conclusion.
- Keep a one-line supersession summary and link when useful.
- Move detailed inactive history to `archive/`.
- Preserve IDs and replacement relationships.
- Validate and rebuild the index afterward.

## Concurrency and merging

Prefer Git's normal merge workflow. When concurrent sessions create semantically duplicate records:

1. Preserve both until their meaning and scope are compared.
2. Choose one canonical ID or create a new merged record.
3. Redirect or supersede the duplicates.
4. Merge unique rationale, limitations, and validation evidence.
5. Rebuild the index and run the doctor.

Never resolve a material semantic conflict by choosing the newest timestamp alone.

## Conservative fallback without the skill

The project-local protocol keeps recall available when the full skill is not loaded, but fallback behavior should be deliberately narrower than full maintenance.

- Do not create an alternative memory directory or replace `.mwf`.
- Do not invent types, statuses, lifecycle transitions, or schema fields.
- Route ambiguous user input into `inbox.md`; do not hand-build a candidate unless the project-local schema is fully understood.
- Safe writes are limited to concise handoff updates and unambiguous edits to an existing schema-conforming record.
- Preserve conflicts, suspected duplicates, and unknown structures unchanged. Ask the user or defer them to a session with the skill.
- Do not perform migration, compaction, hard deletion, or schema repair without the skill's deterministic operations.
- Do not claim the tree is structurally healthy unless the official doctor has run.
