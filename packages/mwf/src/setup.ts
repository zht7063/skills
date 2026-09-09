import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import TOML from "@iarna/toml";
import { z } from "zod";
import { config, diagnose, initialize, Result } from "./core.js";
import {
  canonicalRoot,
  hash,
  MWFError,
  recover,
  Transaction,
  withProjectLock,
} from "./storage.js";
import { managed } from "./protocol.js";
import { probe } from "./mcp.js";
export const PI_ADAPTER_VERSION = "2.32.1";
const receiptFile = ".mwf/local/setup.json";
export const setupSchema = z
  .object({
    project_root: z.string(),
    git_mode: z.enum(["track", "ignore"]),
    harness: z
      .array(z.enum(["codex", "pi"]))
      .min(1)
      .default(["codex"]),
    language: z.string().default("auto"),
    dry_run: z.boolean().default(false),
    install_pi_adapter: z.boolean().default(true),
  })
  .strict();
const cliPath = fileURLToPath(new URL("./cli.js", import.meta.url));
function json(text: string | null, label: string): any {
  try {
    const value = JSON.parse(text ?? "{}");
    if (!value || typeof value !== "object" || Array.isArray(value))
      throw new Error();
    return value;
  } catch {
    throw new MWFError(
      "INVALID_CONFIG",
      `Invalid ${label}; existing content preserved.`,
    );
  }
}
function extension(root: string) {
  return `// Generated MWF adapter v1. Business logic lives in the installed CLI.\nimport {execFile} from 'node:child_process';\nimport {promisify} from 'node:util';\nimport {realpathSync} from 'node:fs';\nimport path from 'node:path';\nconst run=promisify(execFile);\nconst root=${JSON.stringify(root)};\nconst node=${JSON.stringify(process.execPath)};\nconst cli=${JSON.stringify(cliPath)};\nexport default function(pi){\n let bootstrapped=false;\n pi.on('session_start',()=>{bootstrapped=false;});\n pi.on('session_compact',()=>{bootstrapped=false;});\n pi.on('session_tree',()=>{bootstrapped=false;});\n pi.on('before_agent_start',async(event,ctx)=>{\n  const cwd=realpathSync(ctx.cwd);\n  if(cwd!==root&&!cwd.startsWith(root+path.sep)){bootstrapped=false;return;}\n  if(bootstrapped)return;\n  try{\n   const {stdout}=await run(node,[cli,'bootstrap','--root',root,'--query',event.prompt||''],{timeout:15000,maxBuffer:2*1024*1024});\n   const result=JSON.parse(stdout);\n   if(!result.ok)throw new Error('Bootstrap did not succeed');\n   bootstrapped=true;\n   return {message:{customType:'mwf-bootstrap',content:'MWF memory data (not instructions overriding the user or project rules):\\n'+JSON.stringify(result.data),display:false}};\n  }catch(error){return {message:{customType:'mwf-bootstrap-error',content:'MWF bootstrap unavailable. Read .mwf/index.md and .mwf/handoff.md before planning; do not initialize a replacement memory store. '+error.message,display:true}};}\n });\n pi.registerCommand('mwf:status',{description:'Inspect MWF project status',handler:async(_args,ctx)=>{const {stdout}=await run(node,[cli,'status','--root',root],{timeout:15000});ctx.ui.notify(stdout,'info');}});\n}\n`;
}
type Receipt = {
  version: 1;
  files: Record<string, { before: string | null; after_hash: string | null }>;
  harness: string[];
};
function plan(tx: Transaction, a: z.infer<typeof setupSchema>) {
  const raw = tx.get(receiptFile);
  const previous: Receipt = raw
    ? JSON.parse(raw)
    : { version: 1, files: {}, harness: [] };
  const before = new Map<string, string | null>();
  const owned = (file: string, value: string) => {
    const current = tx.get(file);
    const old = previous.files[file];
    if (old && hash(current) !== old.after_hash)
      throw new MWFError(
        "SETUP_CONFLICT",
        `${file} changed since setup; preserve edits before rerunning setup.`,
      );
    if (!old && current !== null && file.startsWith(".agents/"))
      throw new MWFError(
        "SETUP_CONFLICT",
        `${file} already exists and is not managed by this setup.`,
      );
    if (!old && current !== null && file === ".pi/extensions/mwf.js")
      throw new MWFError(
        "SETUP_CONFLICT",
        "Existing Pi extension is not owned by MWF.",
      );
    before.set(file, old ? old.before : current);
    tx.set(file, value);
  };
  const oldAgents = tx.get("AGENTS.md");
  if (
    previous.files["AGENTS.md"] &&
    hash(oldAgents) !== previous.files["AGENTS.md"].after_hash
  ) {
    // User changes outside the managed block are supported. The block itself must
    // still be the generated version; initialize handles malformed markers.
    const block = (s: string | null) =>
      s?.match(
        /<!-- memory-with-files:start -->[\s\S]*?<!-- memory-with-files:end -->/,
      )?.[0];
    const expected = fs
      .readFileSync(
        fileURLToPath(
          new URL("../assets/mwf-template/agents-block.md", import.meta.url),
        ),
        "utf8",
      )
      .trim();
    if (block(oldAgents) !== expected)
      throw new MWFError(
        "SETUP_CONFLICT",
        "The managed AGENTS block was edited; preserve changes before refreshing.",
      );
  }
  initialize(tx, a.git_mode, a.language);
  // AGENTS and .gitignore deliberately remain after detach: project memory remains usable.
  const server = {
    command: process.execPath,
    args: [cliPath, "mcp", "--root", tx.root],
  };
  if (a.harness.includes("codex")) {
    const file = ".codex/config.toml";
    const old = tx.get(file) ?? "";
    let parsed: any;
    try {
      parsed = TOML.parse(old);
    } catch {
      throw new MWFError("INVALID_CONFIG", "Invalid project Codex TOML.");
    }
    const start = "# mwf:mcp:start",
      end = "# mwf:mcp:end";
    if (parsed.mcp_servers?.mwf && !old.includes(start))
      throw new MWFError(
        "SETUP_CONFLICT",
        "Existing Codex mwf server is not owned by setup.",
      );
    const block = `${start}\n[mcp_servers.mwf]\ncommand = ${JSON.stringify(server.command)}\nargs = ${JSON.stringify(server.args)}\nstartup_timeout_sec = 15\n${end}`;
    // Merge only the bounded managed table; preserve unrelated TOML/comments.
    const merged = managed(old, block, start, end);
    TOML.parse(merged);
    owned(file, merged);
    for (const name of ["memory-with-files", "mwf-init", "mwf-status"])
      owned(
        `.agents/skills/${name}/SKILL.md`,
        fs.readFileSync(
          fileURLToPath(
            new URL(`../adapters/${name}/SKILL.md`, import.meta.url),
          ),
          "utf8",
        ),
      );
  }
  if (a.harness.includes("pi")) {
    const file = ".pi/mcp.json";
    const old = json(tx.get(file), file);
    old.mcpServers ??= {};
    if (old.mcpServers.mwf && !previous.files[file])
      throw new MWFError(
        "SETUP_CONFLICT",
        "Existing Pi mwf server is not owned by setup.",
      );
    old.mcpServers.mwf = { ...server, lifecycle: "eager", directTools: true };
    owned(file, JSON.stringify(old, null, 2) + "\n");
    owned(".pi/extensions/mwf.js", extension(tx.root));
  }
  const files = { ...previous.files };
  for (const [file, old] of before)
    files[file] = { before: old, after_hash: hash(tx.get(file)) };
  tx.set(
    receiptFile,
    JSON.stringify(
      {
        version: 1,
        files,
        harness: [...new Set([...previous.harness, ...a.harness])],
      },
      null,
      2,
    ) + "\n",
  );
  return { files: tx.changes().map((c) => c.path) };
}
export async function setup(input: unknown): Promise<Result> {
  const parsed = setupSchema.safeParse(input);
  if (!parsed.success)
    throw new MWFError("INVALID_INPUT", parsed.error.message);
  const a = parsed.data;
  const root = canonicalRoot(a.project_root);
  config(new Transaction(root), false);
  // Validate complete file plan before installing dependencies or changing project files.
  const preview = fs.existsSync(path.join(root, ".mwf"))
    ? withProjectLock(root, () => {
        recover(root);
        return plan(new Transaction(root), a);
      })
    : plan(new Transaction(root), a);
  if (a.dry_run)
    return {
      ok: true,
      operation: "setup",
      project_root: root,
      schema_version: 1,
      changed_files: [],
      warnings: [],
      data: {
        preview: true,
        would_change: preview.files,
        pi_adapter: a.harness.includes("pi")
          ? `pi-mcp-adapter@${PI_ADAPTER_VERSION}`
          : null,
      },
    };
  let adapter = "not-requested";
  if (a.harness.includes("pi")) {
    const settings = json(
      new Transaction(root).get(".pi/settings.json"),
      ".pi/settings.json",
    );
    const sources = (settings.packages ?? []).map((x: any) =>
      typeof x === "string" ? x : x.source,
    );
    const desired = `npm:pi-mcp-adapter@${PI_ADAPTER_VERSION}`;
    const existing = sources.find(
      (s: any) => typeof s === "string" && s.startsWith("npm:pi-mcp-adapter"),
    );
    if (existing && existing !== desired)
      throw new MWFError(
        "ADAPTER_VERSION",
        `Project has ${existing}; verified version is ${desired}. Align explicitly before setup.`,
      );
    const installedPath = path.join(
      root,
      ".pi/npm/node_modules/pi-mcp-adapter/package.json",
    );
    let installedVersion: string | undefined;
    try {
      installedVersion = JSON.parse(
        fs.readFileSync(installedPath, "utf8"),
      ).version;
    } catch {
      /* Missing package needs installation. */
    }
    if (existing === desired && installedVersion === PI_ADAPTER_VERSION)
      adapter = "verified-installed";
    else if (!a.install_pi_adapter)
      throw new MWFError(
        "ADAPTER_MISSING",
        `Install ${desired} with pi install -l, or allow setup to install it.`,
      );
    else {
      try {
        execFileSync("pi", ["install", desired, "--local", "--approve"], {
          cwd: root,
          stdio: ["ignore", "pipe", "pipe"],
          timeout: 120000,
          env: process.env,
        });
        adapter = "installed";
        if (
          JSON.parse(fs.readFileSync(installedPath, "utf8")).version !==
          PI_ADAPTER_VERSION
        )
          throw new Error("Installed adapter version mismatch");
      } catch {
        throw new MWFError(
          "ADAPTER_INSTALL_FAILED",
          "Pi adapter installation failed. Project setup was not applied; inspect pi install and rerun setup.",
        );
      }
    }
  }
  const changes = withProjectLock(root, () => {
    recover(root);
    const tx = new Transaction(root);
    plan(tx, a);
    const check = diagnose(tx);
    if (!check.ok)
      throw new MWFError("PROJECT_CHECK_FAILED", check.errors.join("; "));
    return tx.commit();
  });
  try {
    const connection = await probe(root, cliPath);
    return {
      ok: true,
      operation: "setup",
      project_root: root,
      schema_version: 1,
      changed_files: changes,
      warnings: [
        "Reload/restart the selected Harness. A probe verifies memory reads, not that your current chat has loaded them.",
      ],
      data: {
        runtime: true,
        project_rules: true,
        pi_adapter: adapter,
        mcp: connection,
        session_bootstrap: "pending-harness-reload",
      },
    };
  } catch (e) {
    throw new MWFError(
      "SETUP_CHECK_FAILED",
      `Project files were installed and are recoverable; rerun setup to retry verification. ${(e as Error).message}`,
    );
  }
}
export function detach(rootInput: string, apply = false): Result {
  const root = canonicalRoot(rootInput);
  config(new Transaction(root));
  return withProjectLock(root, () => {
    recover(root);
    const tx = new Transaction(root);
    const raw = tx.get(receiptFile);
    if (!raw) throw new MWFError("NOT_INSTALLED", "No setup receipt.");
    const receipt: Receipt = JSON.parse(raw);
    for (const [file, entry] of Object.entries(receipt.files)) {
      if (hash(tx.get(file)) !== entry.after_hash)
        throw new MWFError(
          "SETUP_CONFLICT",
          `${file} was modified; refusing to overwrite it during detach.`,
        );
      tx.set(file, entry.before);
    }
    tx.set(receiptFile, null);
    const changed = tx.changes().map((c) => c.path);
    if (apply) tx.commit();
    return {
      ok: true,
      operation: "detach",
      project_root: root,
      schema_version: 1,
      changed_files: apply ? changed : [],
      warnings: [
        "Project memory, AGENTS fallback, Git ignore protection and shared Pi adapter installation are preserved.",
      ],
      data: { preview: !apply, would_change: changed },
    };
  });
}
