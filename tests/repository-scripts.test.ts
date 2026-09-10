import test from "node:test";
import type { TestContext } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import * as tools from "../scripts/skill-tools.ts";
function temp(t: TestContext) {
  const root = fs.realpathSync(
    fs.mkdtempSync(path.join(os.tmpdir(), "skill-tools-")),
  );
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}
function makeSkill(root: string, name = "demo-skill") {
  const skill = path.join(root, "skills", name);
  fs.mkdirSync(skill, { recursive: true });
  fs.writeFileSync(
    path.join(skill, "SKILL.md"),
    `---\nname: ${name}\ndescription: A demo skill for installer tests.\n---\n\n# Demo\n`,
  );
  for (const [dir, file, text] of [
    ["assets", "data.txt", "runtime"],
    ["evals", "cases.json", "[]"],
    ["tests", "demo.test.ts", "// development only"],
    ["__pycache__", "demo.pyc", "cache"],
  ]) {
    fs.mkdirSync(path.join(skill, dir));
    fs.writeFileSync(path.join(skill, dir, file), text);
  }
  return skill;
}
test("target profiles respect environment and explicit directory expansion", (t) => {
  const root = temp(t);
  const oldCodex = process.env.CODEX_HOME;
  process.env.CODEX_HOME = path.join(root, "codex");
  t.after(() => {
    if (oldCodex === undefined) delete process.env.CODEX_HOME;
    else process.env.CODEX_HOME = oldCodex;
  });
  // Environment variables may be absent; restore explicitly for older Node versions.
  const old = process.env.PI_CODING_AGENT_DIR;
  process.env.PI_CODING_AGENT_DIR = path.join(root, "pi");
  t.after(() => {
    if (old === undefined) delete process.env.PI_CODING_AGENT_DIR;
    else process.env.PI_CODING_AGENT_DIR = old;
  });
  assert.equal(
    tools.resolveTarget("codex"),
    path.join(root, "codex", "skills"),
  );
  assert.equal(tools.resolveTarget("pi"), path.join(root, "pi", "skills"));
  assert.equal(
    tools.resolveTarget(undefined, "${PI_CODING_AGENT_DIR}/custom"),
    path.join(root, "pi", "custom"),
  );
});
test("link installation is idempotent, uninstall defaults to preview and preserves source", (t) => {
  const root = temp(t),
    source = makeSkill(root),
    metadata = tools.requireValidSkill(source),
    target = path.join(root, "installed");
  const result = tools.installSkill(source, metadata, target);
  assert.equal(result.action, "installed");
  assert.ok(fs.lstatSync(result.destination).isSymbolicLink());
  assert.equal(
    tools.installSkill(source, metadata, target).action,
    "already-installed",
  );
  assert.equal(
    tools.uninstallSkill(metadata.name, target).action,
    "would-uninstall",
  );
  assert.ok(fs.existsSync(result.destination));
  assert.equal(
    tools.uninstallSkill(metadata.name, target, true).action,
    "uninstalled",
  );
  assert.ok(!tools.exists(result.destination));
  assert.ok(fs.existsSync(source));
});
test("copy excludes evaluations and caches but preserves assets and skill tests", (t) => {
  const root = temp(t),
    source = makeSkill(root),
    metadata = tools.requireValidSkill(source);
  const { destination } = tools.installSkill(
    source,
    metadata,
    path.join(root, "installed"),
    { mode: "copy" },
  );
  assert.ok(fs.existsSync(path.join(destination, "assets/data.txt")));
  assert.ok(fs.existsSync(path.join(destination, "tests/demo.test.ts")));
  assert.ok(!fs.existsSync(path.join(destination, "evals")));
  assert.ok(!fs.existsSync(path.join(destination, "__pycache__")));
  assert.deepEqual(tools.validateSkill(destination), []);
});
test("dry-run never creates target or backup directories", (t) => {
  const root = temp(t),
    source = makeSkill(root),
    target = path.join(root, "missing");
  assert.equal(
    tools.installSkill(source, tools.requireValidSkill(source), target, {
      dryRun: true,
    }).action,
    "would-install",
  );
  assert.ok(!fs.existsSync(target));
  fs.mkdirSync(target);
  fs.mkdirSync(path.join(target, "demo-skill"));
  const preview = tools.installSkill(
    source,
    tools.requireValidSkill(source),
    target,
    { dryRun: true, replace: true },
  );
  assert.equal(preview.action, "would-replace");
  assert.ok(preview.backup);
  assert.ok(!fs.existsSync(path.dirname(preview.backup)));
});
test("occupied destinations refuse by default; replace backs up outside the skills directory", (t) => {
  const root = temp(t),
    source = makeSkill(root),
    metadata = tools.requireValidSkill(source),
    target = path.join(root, "installed");
  fs.mkdirSync(path.join(target, metadata.name), { recursive: true });
  fs.writeFileSync(path.join(target, metadata.name, "sentinel.txt"), "old");
  assert.throws(
    () => tools.installSkill(source, metadata, target),
    /already exists/,
  );
  const result = tools.installSkill(source, metadata, target, {
    replace: true,
  });
  assert.equal(result.action, "replaced");
  assert.ok(result.backup);
  assert.equal(
    fs.readFileSync(path.join(result.backup, "sentinel.txt"), "utf8"),
    "old",
  );
  assert.ok(!result.backup.startsWith(target + path.sep));
});
test("invalid metadata, JSON and local links are reported", (t) => {
  const source = makeSkill(temp(t));
  fs.writeFileSync(
    path.join(source, "SKILL.md"),
    "---\nname: wrong-name\ndescription: |-\n  A multi-line\n  description\n---\n[broken](missing.md)\n",
  );
  fs.writeFileSync(path.join(source, "assets/bad.json"), "{");
  const issues = tools.validateSkill(source);
  assert.ok(issues.some((i) => i.includes("does not match")));
  assert.ok(issues.some((i) => i.includes("invalid JSON")));
  assert.ok(issues.some((i) => i.includes("broken link")));
  assert.equal(
    tools.readSkillMetadata(source).description,
    "A multi-line description",
  );
});
test("uninstall refuses mismatched directories and path traversal", (t) => {
  const root = temp(t),
    source = makeSkill(root);
  fs.writeFileSync(
    path.join(source, "SKILL.md"),
    "---\nname: another-skill\ndescription: Preserve me.\n---\n",
  );
  assert.throws(
    () => tools.uninstallSkill("demo-skill", path.dirname(source), true),
    /does not match/,
  );
  assert.throws(
    () => tools.uninstallSkill("../demo-skill", path.dirname(source), true),
    /invalid skill name/,
  );
  assert.ok(fs.existsSync(source));
});
test("dangling symlinks are occupied, backed up verbatim and unlinked without following targets", (t) => {
  const root = temp(t),
    source = makeSkill(root),
    metadata = tools.requireValidSkill(source),
    target = path.join(root, "installed");
  fs.mkdirSync(target);
  const destination = path.join(target, metadata.name);
  fs.symlinkSync("missing-relative", destination);
  assert.throws(
    () => tools.installSkill(source, metadata, target),
    /already exists/,
  );
  const replacement = tools.installSkill(source, metadata, target, {
    replace: true,
  });
  assert.ok(replacement.backup);
  assert.equal(fs.readlinkSync(replacement.backup), "missing-relative");
  tools.uninstallSkill(metadata.name, target, true);
  fs.symlinkSync("still-missing", destination);
  assert.equal(
    tools.uninstallSkill(metadata.name, target, true).action,
    "uninstalled",
  );
  assert.ok(!tools.exists(destination));
});
test("sources cannot escape repository via symlinks; targets cannot nest in source", (t) => {
  const root = temp(t),
    source = makeSkill(root),
    metadata = tools.requireValidSkill(source);
  assert.throws(
    () => tools.installSkill(source, metadata, path.join(source, "nested")),
    /inside the skill source/,
  );
  assert.throws(
    () => tools.installSkill(source, metadata, path.dirname(source)),
    /source directory itself/,
  );
  const repo = path.join(root, "other");
  fs.mkdirSync(path.join(repo, "skills"), { recursive: true });
  fs.symlinkSync(source, path.join(repo, "skills", "demo-skill"));
  assert.throws(
    () => tools.resolveSource("demo-skill", repo),
    /must be inside/,
  );
  const link = path.join(root, "link");
  fs.symlinkSync(source, link);
  assert.equal(
    tools.resolvePath(path.join(link, "missing", "tail")),
    path.join(source, "missing", "tail"),
  );
});
test("failed final rename restores original destination and removes staging", (t) => {
  const root = temp(t),
    source = makeSkill(root),
    metadata = tools.requireValidSkill(source),
    target = path.join(root, "installed");
  fs.mkdirSync(path.join(target, metadata.name), { recursive: true });
  fs.writeFileSync(path.join(target, metadata.name, "sentinel"), "keep");
  const rename = fs.renameSync;
  t.mock.method(fs, "renameSync", (from: fs.PathLike, to: fs.PathLike) => {
    if (String(from).includes(".install-"))
      throw new Error("injected rename failure");
    return rename(from, to);
  });
  assert.throws(
    () => tools.installSkill(source, metadata, target, { replace: true }),
    /injected rename failure/,
  );
  assert.equal(
    fs.readFileSync(path.join(target, metadata.name, "sentinel"), "utf8"),
    "keep",
  );
  assert.deepEqual(fs.readdirSync(target), [metadata.name]);
});
test("failed staging validation leaves occupied destination untouched", (t) => {
  const root = temp(t),
    source = makeSkill(root),
    metadata = tools.requireValidSkill(source),
    target = path.join(root, "installed");
  fs.mkdirSync(path.join(target, metadata.name), { recursive: true });
  fs.writeFileSync(path.join(target, metadata.name, "sentinel"), "keep");
  // Link is valid in the source but its target is intentionally excluded from copied skills.
  fs.appendFileSync(
    path.join(source, "SKILL.md"),
    "[evaluation](evals/cases.json)\n",
  );
  assert.throws(
    () =>
      tools.installSkill(source, metadata, target, {
        mode: "copy",
        replace: true,
      }),
    /broken link/,
  );
  assert.equal(
    fs.readFileSync(path.join(target, metadata.name, "sentinel"), "utf8"),
    "keep",
  );
  assert.deepEqual(fs.readdirSync(target), [metadata.name]);
});
test("CLI preview/apply, custom paths with spaces, help and unknown argument handling", (t) => {
  const root = temp(t),
    target = path.join(root, "custom skills");
  const run = (script: string, args: string[]) =>
    spawnSync(
      process.execPath,
      [
        "--experimental-strip-types",
        path.join(tools.repositoryRoot, "scripts", script),
        ...args,
      ],
      { encoding: "utf8" },
    );
  const args = ["mihomo-remote-linux", "--target-dir", target];
  assert.equal(run("install-skill.ts", [...args, "--dry-run"]).status, 0);
  assert.ok(!fs.existsSync(target));
  assert.equal(run("install-skill.ts", args).status, 0);
  assert.match(run("uninstall-skill.ts", args).stdout, /would-uninstall/);
  assert.equal(run("uninstall-skill.ts", [...args, "--apply"]).status, 0);
  assert.equal(run("install-skill.ts", ["--help"]).status, 0);
  assert.equal(run("install-skill.ts", ["--nonsense"]).status, 2);
  assert.notEqual(
    run("install-skill.ts", [...args, "--agent", "pi"]).status,
    0,
  );
});

test("path canonicalization resolves symlinks before parent traversal and rejects cycles", (t) => {
  const root = temp(t);
  fs.mkdirSync(path.join(root, "real", "nested"), { recursive: true });
  fs.symlinkSync(path.join(root, "real", "nested"), path.join(root, "alias"));
  assert.equal(
    tools.resolvePath(root + "/alias/../missing"),
    path.join(root, "real", "missing"),
  );
  fs.symlinkSync("cycle-b", path.join(root, "cycle-a"));
  fs.symlinkSync("cycle-a", path.join(root, "cycle-b"));
  assert.throws(
    () => tools.resolvePath(path.join(root, "cycle-a")),
    /Symlink cycle/,
  );
});

test("installer rejects invalid input before writing and runs without repository dependencies", (t) => {
  const root = temp(t);
  // A standalone copy proves the bootstrap script has no dependency on node_modules.
  const standalone = path.join(root, "install-mwf.ts");
  fs.copyFileSync(
    path.join(tools.repositoryRoot, "scripts/install-mwf.ts"),
    standalone,
  );
  const run = (...args: string[]) =>
    spawnSync(
      process.execPath,
      ["--experimental-strip-types", standalone, ...args],
      { cwd: root, encoding: "utf8" },
    );
  assert.equal(run("--help").status, 0);
  assert.match(run("--root", root).stderr, /git-mode/);
  assert.match(
    run("--root", root, "--git-mode", "track", "--harness", "invalid").stderr,
    /Invalid --harness/,
  );
  assert.notEqual(run("--unknown").status, 0);
  assert.deepEqual(fs.readdirSync(root), ["install-mwf.ts"]);
});
