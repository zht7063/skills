# Repository layout

## Goals

- Keep every skill independently understandable, testable, and installable.
- Keep repository-wide tooling separate from files shipped with a skill.
- Preserve room for future skills without imposing unused directories on each one.
- Keep generated evaluations, packages, and agent-local work out of source control.

## Structure

```text
.
├── README.md
├── package.json          # Private repository tooling and verification commands
├── package-lock.json
├── tsconfig.json         # Strict checks for repository tools and skill tests
├── packages/
│   └── mwf/              # Independently installable CLI/MCP runtime
├── docs/
│   └── repository-layout.md
├── scripts/
│   ├── skill-tools.ts         # Shared dependency-free implementation
│   ├── arguments.ts           # Shared CLI parsing/error handling
│   ├── install-mwf.ts         # Bootstrap and connect the MWF runtime
│   ├── install-skill.ts       # Install one skill into a supported agent
│   ├── uninstall-skill.ts     # Preview or remove one installed skill
│   └── validate-all.ts        # Validate every skill package
├── tests/
│   └── repository-scripts.test.ts
└── skills/
    ├── memory-with-files/
    │   ├── SKILL.md
    │   ├── agents/
    │   │   └── openai.yaml
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

The root `scripts/` directory contains operations across packages, such as installing a selected skill and validating every skill. These scripts discover packages beneath `skills/` rather than hard-code a single skill. Installation supports Codex, Pi Agent, and explicit custom target directories; detailed usage is documented in [installing-skills.md](installing-skills.md).

## Generated and local state

The repository ignores:

- `.planning/`, which contains agent-local execution plans;
- `skills/*-workspace/`, which contains generated skill evaluation runs;
- `dist/` and `*.skill`, which contain reproducible package outputs;
- common runtime caches and temporary editor files.

Source eval definitions remain tracked inside each skill so behavior can be reproduced.

## MWF runtime package

`packages/mwf/` contains the standalone TypeScript Core, CLI, stdio MCP server,
project setup/detach operations, templates and thin Harness adapters. Its npm
package is the sole MWF runtime and owns its templates. The skill is a thin
instruction adapter; it does not ship a Python writer or duplicate templates.
Fixed legacy fixtures in `packages/mwf/tests/fixtures/` verify schema-1 data
compatibility without running Python. Repository installation and validation
tools and tests are also TypeScript; Node 22.16+ runs them with `--experimental-strip-types`.
