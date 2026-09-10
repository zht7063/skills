/** Dependency-free repository installation and validation. */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { randomUUID } from "node:crypto";
import { spawnSync } from "node:child_process";

export const repositoryRoot = fileURLToPath(new URL("../", import.meta.url));
const namePattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const ignoredDirs = new Set([
  "__pycache__",
  ".git",
  ".pytest_cache",
  "node_modules",
]);
export class SkillToolError extends Error {}
export interface SkillMetadata {
  name: string;
  description: string;
}
export interface InstallResult {
  action: string;
  source: string;
  destination: string;
  backup?: string;
}
export function exists(file: string): boolean {
  try {
    fs.lstatSync(file);
    return true;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw error;
  }
}
/** Like Path.resolve(strict=False): resolve existing symlinks and missing tails. */
export function resolvePath(file: string, seen = new Set<string>()): string {
  const absolute = path.isAbsolute(file)
    ? file
    : process.cwd() + path.sep + file;
  const { root } = path.parse(absolute);
  let resolved = root;
  for (const part of absolute
    .slice(root.length)
    .split(path.sep)
    .filter(Boolean)) {
    if (part === ".") continue;
    if (part === "..") {
      resolved = path.dirname(resolved);
      continue;
    }
    resolved = path.join(resolved, part);
    if (exists(resolved) && fs.lstatSync(resolved).isSymbolicLink()) {
      if (seen.has(resolved))
        throw new SkillToolError(`Symlink cycle: ${resolved}`);
      const next = new Set(seen).add(resolved);
      const target = fs.readlinkSync(resolved);
      resolved = resolvePath(
        path.isAbsolute(target)
          ? target
          : path.dirname(resolved) + path.sep + target,
        next,
      );
    }
  }
  return resolved;
}
function expandUser(value: string): string {
  return value === "~"
    ? os.homedir()
    : value.startsWith("~/")
      ? path.join(os.homedir(), value.slice(2))
      : value;
}
export function readSkillMetadata(skill: string): SkillMetadata {
  const file = path.join(skill, "SKILL.md");
  if (!fs.existsSync(file) || !fs.statSync(file).isFile())
    throw new SkillToolError(`missing SKILL.md: ${skill}`);
  const lines = fs.readFileSync(file, "utf8").split(/\r?\n/);
  if (lines[0]?.trim() !== "---")
    throw new SkillToolError(`${file} must start with YAML frontmatter`);
  const end = lines.findIndex((line, i) => i > 0 && line.trim() === "---");
  if (end < 0)
    throw new SkillToolError(`${file} has unterminated YAML frontmatter`);
  const head = lines.slice(1, end);
  const unquote = (s: string) => s.trim().replace(/^(['"])(.*)\1$/, "$2");
  const name = head.join("\n").match(/^name:\s*(.+?)\s*$/m)?.[1];
  if (!name)
    throw new SkillToolError(`${file} is missing frontmatter field 'name'`);
  const i = head.findIndex((line) => line.startsWith("description:"));
  if (i < 0)
    throw new SkillToolError(
      `${file} is missing frontmatter field 'description'`,
    );
  let description = head[i].slice("description:".length).trim();
  if ([">", ">-", "|", "|-"].includes(description)) {
    const parts: string[] = [];
    for (const line of head.slice(i + 1)) {
      if (!/^[ \t]/.test(line)) break;
      if (line.trim()) parts.push(line.trim());
    }
    description = parts.join(" ");
  } else description = unquote(description);
  return { name: unquote(name), description };
}
function filesBelow(dir: string): string[] {
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .sort((a, b) => a.name.localeCompare(b.name))
    .flatMap((entry) => {
      const file = path.join(dir, entry.name);
      if (entry.isDirectory())
        return ignoredDirs.has(entry.name) ? [] : filesBelow(file);
      return [file];
    });
}
export function validateSkill(
  directory: string,
  expectedName?: string,
): string[] {
  const skill = resolvePath(directory);
  const issues: string[] = [];
  let metadata: SkillMetadata;
  try {
    metadata = readSkillMetadata(skill);
  } catch (error) {
    return [String((error as Error).message)];
  }
  const required = expectedName ?? path.basename(skill);
  if (expectedName === undefined && !namePattern.test(path.basename(skill)))
    issues.push(
      `directory name is not lowercase hyphen-case: ${path.basename(skill)}`,
    );
  if (metadata.name !== required)
    issues.push(
      `frontmatter name '${metadata.name}' does not match expected name '${required}'`,
    );
  if (!namePattern.test(metadata.name))
    issues.push(`invalid skill name: ${metadata.name}`);
  if (!metadata.description) issues.push("description must not be empty");
  if ([...metadata.description].length > 1024)
    issues.push(
      `description exceeds 1024 characters: ${[...metadata.description].length}`,
    );
  for (const file of filesBelow(skill)) {
    if (file.endsWith(".json")) {
      try {
        JSON.parse(fs.readFileSync(file, "utf8"));
      } catch (error) {
        issues.push(
          `invalid JSON ${path.relative(skill, file)}: ${(error as Error).message}`,
        );
      }
    }
    if (file.endsWith(".md")) {
      let markdown: string;
      try {
        markdown = fs.readFileSync(file, "utf8");
      } catch (error) {
        issues.push(
          `cannot read ${path.relative(skill, file)}: ${(error as Error).message}`,
        );
        continue;
      }
      for (const match of markdown.matchAll(/(?<!!)\[[^\]]+\]\(([^)]+)\)/g)) {
        const target = match[1].trim().replace(/^<|>$/g, "").split("#", 1)[0];
        if (
          !target ||
          target.includes("://") ||
          target.startsWith("mailto:") ||
          target.startsWith("/")
        )
          continue;
        if (!fs.existsSync(path.resolve(path.dirname(file), target)))
          issues.push(
            `broken link in ${path.relative(skill, file)}: ${match[1]}`,
          );
      }
    }
  }
  return issues;
}
export function requireValidSkill(
  skill: string,
  expectedName?: string,
): SkillMetadata {
  const issues = validateSkill(skill, expectedName);
  if (issues.length)
    throw new SkillToolError(
      `skill validation failed:\n  - ${issues.join("\n  - ")}`,
    );
  return readSkillMetadata(skill);
}
const isWithin = (root: string, file: string) => {
  const relative = path.relative(root, file);
  return (
    relative === "" ||
    (!relative.startsWith(`..${path.sep}`) &&
      relative !== ".." &&
      !path.isAbsolute(relative))
  );
};
export function resolveSource(
  skill: string,
  repo = repositoryRoot,
): [string, SkillMetadata] {
  const root = resolvePath(path.join(repo, "skills"));
  const requested = expandUser(skill);
  let source: string;
  if (
    path.isAbsolute(requested) ||
    fs.existsSync(requested) ||
    /[/\\]/.test(skill)
  )
    source = resolvePath(requested);
  else {
    if (!namePattern.test(skill))
      throw new SkillToolError(`invalid skill name: ${skill}`);
    source = resolvePath(path.join(root, skill));
  }
  if (!isWithin(root, source))
    throw new SkillToolError(`skill source must be inside ${root}: ${source}`);
  if (!fs.existsSync(source) || !fs.statSync(source).isDirectory())
    throw new SkillToolError(
      `skill source directory does not exist: ${source}`,
    );
  return [source, requireValidSkill(source)];
}
export function resolveTarget(agent?: string, targetDir?: string): string {
  if (targetDir)
    return resolvePath(
      expandUser(
        targetDir.replace(
          /\$(\w+)|\$\{([^}]+)\}/g,
          (match, plain: string, braced: string) =>
            process.env[plain ?? braced] ?? match,
        ),
      ),
    );
  const profile = agent ?? "codex";
  let root: string;
  if (profile === "codex")
    root = process.env.CODEX_HOME ?? path.join(os.homedir(), ".codex");
  else if (profile === "pi")
    root =
      process.env.PI_CODING_AGENT_DIR ??
      path.join(os.homedir(), ".pi", "agent");
  else throw new SkillToolError(`unsupported agent profile: ${profile}`);
  return path.join(resolvePath(expandUser(root)), "skills");
}
function backupPath(root: string, name: string): string {
  const stamp = new Date()
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\.\d{3}Z$/, "Z");
  const base = path.join(
    path.dirname(root),
    ".skill-install-backups",
    path.basename(root),
    stamp,
  );
  let candidate = path.join(base, name);
  for (let counter = 2; exists(candidate); counter++)
    candidate = path.join(base, `${name}-${counter}`);
  return candidate;
}
export interface InstallOptions {
  mode?: "link" | "copy";
  replace?: boolean;
  dryRun?: boolean;
}
export function installSkill(
  sourceInput: string,
  metadata: SkillMetadata,
  targetInput: string,
  options: InstallOptions = {},
): InstallResult {
  const source = resolvePath(sourceInput),
    target = resolvePath(expandUser(targetInput));
  const destination = path.join(target, metadata.name);
  const mode = options.mode ?? "link";
  if (destination === source)
    throw new SkillToolError(
      "installation destination is the source directory itself",
    );
  if (isWithin(source, target))
    throw new SkillToolError(
      "installation target cannot be inside the skill source",
    );
  if (!["link", "copy"].includes(mode))
    throw new SkillToolError(`unsupported install mode: ${mode}`);
  const occupied = exists(destination);
  if (
    occupied &&
    mode === "link" &&
    fs.lstatSync(destination).isSymbolicLink() &&
    resolvePath(destination) === source
  )
    return { action: "already-installed", source, destination };
  if (occupied && !options.replace)
    throw new SkillToolError(
      `destination already exists: ${destination}; rerun with --replace to back it up`,
    );
  const backup = occupied ? backupPath(target, metadata.name) : undefined;
  if (options.dryRun)
    return {
      action: occupied ? "would-replace" : "would-install",
      source,
      destination,
      backup,
    };
  fs.mkdirSync(target, { recursive: true });
  const staging = path.join(
    target,
    `.${metadata.name}.install-${randomUUID()}`,
  );
  try {
    if (mode === "link") fs.symlinkSync(source, staging, "dir");
    else {
      fs.cpSync(source, staging, {
        recursive: true,
        dereference: true,
        filter: (file) => {
          const relative = path.relative(source, file);
          if (!relative) return true;
          const name = path.basename(file);
          return (
            !ignoredDirs.has(name) &&
            name !== ".DS_Store" &&
            !/\.py[co]$/.test(name) &&
            relative !== "evals"
          );
        },
      });
      requireValidSkill(staging, metadata.name);
    }
    if (backup) {
      fs.mkdirSync(path.dirname(backup), { recursive: true });
      fs.renameSync(destination, backup);
    }
    try {
      fs.renameSync(staging, destination);
    } catch (error) {
      if (backup && exists(backup) && !exists(destination))
        fs.renameSync(backup, destination);
      throw error;
    }
  } finally {
    if (exists(staging)) fs.rmSync(staging, { recursive: true, force: true });
  }
  return {
    action: occupied ? "replaced" : "installed",
    source,
    destination,
    backup,
  };
}
export function uninstallSkill(
  name: string,
  targetInput: string,
  apply = false,
): InstallResult {
  if (!namePattern.test(name))
    throw new SkillToolError(`invalid skill name: ${name}`);
  const destination = path.join(resolvePath(expandUser(targetInput)), name);
  if (!exists(destination))
    return { action: "not-installed", source: destination, destination };
  if (!fs.lstatSync(destination).isSymbolicLink())
    requireValidSkill(destination, name);
  if (!apply)
    return { action: "would-uninstall", source: destination, destination };
  fs.rmSync(destination, { recursive: true });
  return { action: "uninstalled", source: destination, destination };
}
export function discoverSkills(repo = repositoryRoot): string[] {
  const root = path.join(repo, "skills");
  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory())
    throw new SkillToolError(`skills directory does not exist: ${root}`);
  return fs
    .readdirSync(root)
    .sort()
    .map((name) => path.join(root, name))
    .filter((dir) => fs.existsSync(path.join(dir, "SKILL.md")));
}
export function runSkillTests(skill: string) {
  const dir = path.join(skill, "tests");
  const files = fs.existsSync(dir)
    ? fs
        .readdirSync(dir)
        .filter((file) => file.endsWith(".test.ts"))
        .sort()
        .map((file) => path.join(dir, file))
    : [];
  if (!files.length) return null;
  return spawnSync(
    process.execPath,
    ["--experimental-strip-types", "--test", ...files],
    { cwd: repositoryRoot, encoding: "utf8" },
  );
}
