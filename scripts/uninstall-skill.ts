import { argumentsFor, fail, targetConflict } from "./arguments.ts";
import { resolveTarget, uninstallSkill } from "./skill-tools.ts";
try {
  const { values, positionals } = argumentsFor({
    allowPositionals: true,
    options: {
      agent: { type: "string" },
      "target-dir": { type: "string" },
      apply: { type: "boolean" },
      help: { type: "boolean", short: "h" },
    },
  });
  if (values.help)
    console.log(
      "Usage: node --experimental-strip-types scripts/uninstall-skill.ts SKILL [--agent codex|pi | --target-dir DIRECTORY] [--apply]\nWithout --apply, only preview removal of this exact destination.",
    );
  else {
    targetConflict(values);
    if (positionals.length !== 1)
      throw new TypeError("Exactly one skill name is required");
    const result = uninstallSkill(
      positionals[0],
      resolveTarget(values.agent, values["target-dir"]),
      values.apply,
    );
    console.log(
      `${result.action}: ${positionals[0]}\ndestination: ${result.destination}`,
    );
    if (result.action === "would-uninstall")
      console.log("rerun with --apply to remove this exact destination");
  }
} catch (error) {
  fail(error);
}
