import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
const read = (file: string) =>
  fs.readFileSync(new URL("../" + file, import.meta.url), "utf8");
test("skill is self contained", () => {
  const skill = read("SKILL.md");
  assert.ok(!skill.includes("canonical repository note"));
  assert.ok(!skill.includes("tianyubai"));
  for (const file of [
    "references/operations.md",
    "references/service-and-recovery.md",
  ])
    assert.ok(fs.existsSync(new URL("../" + file, import.meta.url)));
});
test("private config boundary allows only on-host TUN backup", () => {
  const skill = read("SKILL.md"),
    recovery = read("references/service-and-recovery.md");
  assert.ok(skill.includes("sole exception"));
  assert.ok(skill.includes("same target host"));
  assert.ok(
    recovery.includes(
      "must never be copied to the local machine or repository",
    ),
  );
});
test("evals cover install, audit, update, TUN and migration", () => {
  const evals: { skill_name: string; evals: { id: string }[] } = JSON.parse(
    read("evals/evals.json"),
  );
  assert.equal(evals.skill_name, "mihomo-remote-linux");
  assert.deepEqual(
    evals.evals.map((item) => item.id).sort(),
    [
      "audit-local-port-proxy",
      "global-tun-cutover",
      "safe-update",
      "install-without-config",
      "migrate-legacy-clash",
    ].sort(),
  );
});
