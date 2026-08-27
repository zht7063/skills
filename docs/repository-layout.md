# Repository layout

## Goals

- Keep every skill independently understandable, testable, and installable.
- Keep repository-wide tooling separate from files shipped with a skill.
- Preserve room for future skills without imposing unused directories on each one.
- Keep generated evaluations, packages, and agent-local work out of source control.

## Planned structure

```text
.
├── README.md
├── docs/
│   └── repository-layout.md
├── scripts/
│   ├── install-skill.*        # Future: install one skill into a supported agent
│   ├── install-all.*          # Future: install all selected skills
│   └── validate-all.*         # Future: validate every skill package
└── skills/
    ├── memory-with-files/
    │   ├── SKILL.md
    │   ├── agents/
    │   │   └── openai.yaml
    │   ├── scripts/           # Deterministic initialization and maintenance
    │   ├── references/        # Memory protocol and operation-specific guidance
    │   └── evals/             # Versioned behavioral test prompts
    └── <future-skill>/
```

Only create optional directories when a skill actually needs them. In particular, `assets/` should not be added unless the skill ships files intended to be copied into generated output.

## Skill package conventions

1. Use lowercase, hyphen-separated directory names that match the `name` in `SKILL.md`.
2. Keep the required entry point at `skills/<skill-name>/SKILL.md`.
3. Put deterministic, reusable mechanics in the skill's `scripts/` directory.
4. Put detailed schemas and conditional procedures in `references/`, linked from `SKILL.md` at the point where they become relevant.
5. Put UI metadata and invocation policy in `agents/openai.yaml` when supported.
6. Keep versioned evaluation prompts in `evals/`; keep generated runs in a sibling `<skill-name>-workspace/`, which Git ignores.
7. Do not put repository installation logic inside an individual skill unless that logic is part of the skill's runtime behavior.

## Repository-level tooling

The root `scripts/` directory is reserved for operations across packages, such as installing a selected skill, validating every skill, or packaging release artifacts. These scripts should discover packages beneath `skills/` rather than hard-code a single skill.

No root scripts are created during bootstrap. Their command interface and supported agent installation targets should be designed when the first installation workflow is specified.

## Generated and local state

The repository ignores:

- `.planning/`, which contains agent-local execution plans;
- `skills/*-workspace/`, which contains generated skill evaluation runs;
- `dist/` and `*.skill`, which contain reproducible package outputs;
- common runtime caches and temporary editor files.

Source eval definitions remain tracked inside each skill so behavior can be reproduced.
