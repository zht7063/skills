import { parseArgs } from "node:util";
import type { ParseArgsConfig } from "node:util";
export function argumentsFor<T extends ParseArgsConfig>(config: T) {
  return parseArgs(config);
}
export function fail(error: unknown): void {
  console.error(
    `error: ${error instanceof Error ? error.message : String(error)}`,
  );
  process.exitCode = error instanceof TypeError ? 2 : 1;
}
export function targetConflict(values: {
  agent?: string;
  "target-dir"?: string;
}): void {
  if (values.agent !== undefined && values["target-dir"] !== undefined)
    throw new TypeError("--agent and --target-dir are mutually exclusive");
  if (values.agent !== undefined && !["codex", "pi"].includes(values.agent))
    throw new TypeError("--agent must be codex or pi");
}
