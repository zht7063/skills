import { argumentsFor, fail, targetConflict } from "./arguments.ts";
import { installSkill, resolveSource, resolveTarget } from "./skill-tools.ts";
try {
  const { values, positionals } = argumentsFor({
    allowPositionals: true,
    options: {
      agent: { type: "string" },
      "target-dir": { type: "string" },
      mode: { type: "string", default: "link" },
      replace: { type: "boolean" },
      "dry-run": { type: "boolean" },
      help: { type: "boolean", short: "h" },
    },
  });
  if (values.help)
    console.log(
      "Usage: node --experimental-strip-types scripts/install-skill.ts SKILL [--agent codex|pi | --target-dir DIRECTORY] [--mode link|copy] [--replace] [--dry-run]",
    );
  else {
    targetConflict(values);
    if (positionals.length !== 1)
      throw new TypeError("Exactly one skill name or path is required");
    if (values.mode !== "link" && values.mode !== "copy")
      throw new TypeError("--mode must be link or copy");
    const [source, metadata] = resolveSource(positionals[0]);
    const result = installSkill(
      source,
      metadata,
      resolveTarget(values.agent, values["target-dir"]),
      { mode: values.mode, replace: values.replace, dryRun: values["dry-run"] },
    );
    console.log(
      `${result.action}: ${metadata.name}\nsource: ${result.source}\ndestination: ${result.destination}`,
    );
    if (result.backup) console.log(`backup: ${result.backup}`);
  }
} catch (error) {
  fail(error);
}
