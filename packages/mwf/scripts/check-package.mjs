import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
const packageRoot = fileURLToPath(new URL("../", import.meta.url));
const base = fs.realpathSync(
  fs.mkdtempSync(path.join(os.tmpdir(), "mwf-packed-")),
);
const packed = JSON.parse(
  execFileSync(
    "npm",
    ["pack", "--ignore-scripts", "--json", "--pack-destination", base],
    { cwd: packageRoot, encoding: "utf8" },
  ),
);
const tgz = path.join(
  base,
  (Array.isArray(packed) ? packed[0] : Object.values(packed)[0]).filename,
);
execFileSync(
  "npm",
  [
    "install",
    "--prefix",
    path.join(base, "installed"),
    "--ignore-scripts",
    "--offline",
    "--cache",
    path.join(base, "empty-cache"),
    tgz,
  ],
  { encoding: "utf8" },
);
const installed = path.join(base, "installed/node_modules/@zht7063/mwf");
assert.equal(fs.existsSync(path.join(installed, "src")), false);
const project = path.join(base, "project");
fs.mkdirSync(project);
const invoke = (...args) =>
  JSON.parse(
    execFileSync(
      process.execPath,
      [path.join(installed, "dist/cli.js"), ...args],
      { cwd: project, env: { ...process.env, PATH: "" }, encoding: "utf8" },
    ),
  );
const setup = invoke(
  "setup",
  "--root",
  project,
  "--harness",
  "codex",
  "--git-mode",
  "track",
);
assert.equal(setup.data.mcp.bootstrap_verified, true);
invoke(
  "add",
  "--root",
  project,
  "--type",
  "preference",
  "--title",
  "Package acceptance marker",
  "--summary",
  "Release packages must pass the crimson-moon-731 check.",
  "--body",
  "## Policy\nRun the installed package acceptance check before release.",
);
assert.equal(invoke("doctor", "--root", project).ok, true);
assert.match(
  JSON.stringify(invoke("bootstrap", "--root", project)),
  /crimson-moon-731/,
);
console.log(
  JSON.stringify(
    {
      ok: true,
      package: tgz,
      project,
      installed,
      tests: [
        "packed files only",
        "empty PATH",
        "no Python",
        "actual stdio handshake",
        "bootstrap",
        "write/read/doctor",
      ],
    },
    null,
    2,
  ),
);
