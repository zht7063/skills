#!/usr/bin/env bash
# Install a bundled local MWF runtime and connect one explicitly selected project.
set -euo pipefail
usage() {
  cat <<'HELP'
Usage: bash scripts/install-mwf.sh --root PROJECT --git-mode track|ignore [options]
  --harness codex|pi|codex,pi   Clients to configure (default: codex)
  --prefix DIRECTORY          Runtime location (default: ~/.local/share/mwf)
  --package FILE.tgz          Install a prebuilt bundle; otherwise build this checkout
  --no-install-pi-adapter      Require the pinned Pi adapter already installed
  --dry-run                   Print the installation plan without writing files
  --help                      Show this help
Requires Node >=22.16 and npm; Pi must be installed when selected.
HELP
}
fail() { echo "MWF installer: $*" >&2; exit 1; }
project=''; git_mode=''; harness=codex; prefix="${HOME}/.local/share/mwf"; bundle=''; dry_run=false
adapter_args=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --root|--git-mode|--harness|--prefix|--package)
      [ "$#" -ge 2 ] && [ -n "$2" ] || fail "Missing value for $1"
      case "$1" in
        --root) project=$2;; --git-mode) git_mode=$2;; --harness) harness=$2;;
        --prefix) prefix=$2;; --package) bundle=$2;;
      esac
      shift 2;;
    --no-install-pi-adapter) adapter_args=(--no-install-pi-adapter); shift;;
    --dry-run) dry_run=true; shift;;
    --help|-h) usage; exit 0;;
    *) fail "Unknown argument: $1";;
  esac
done
[ -n "$project" ] && [ -d "$project" ] || fail '--root must name an existing project directory'
case "$git_mode" in track|ignore) ;; *) fail '--git-mode must be track or ignore';; esac
case "$harness" in codex|pi|codex,pi|pi,codex) ;; *) fail 'Invalid --harness';; esac
command -v node >/dev/null || fail 'Install Node >=22.16 and npm first'
command -v npm >/dev/null || fail 'Install npm first'
node_bin=$(node -p 'process.execPath')
"$node_bin" -e 'const [a,b]=process.versions.node.split(".").map(Number);if(a<22||(a===22&&b<16))process.exit(1)' || fail 'Node >=22.16 is required'
case "$harness" in *pi*) command -v pi >/dev/null || fail 'Install Pi before selecting the pi harness';; esac
project=$(cd "$project" && pwd -P)
prefix=$("$node_bin" -e 'console.log(require("node:path").resolve(process.argv[1]))' "$prefix")
if [ -n "$bundle" ]; then
  [ -f "$bundle" ] || fail "Package not found: $bundle"
  bundle=$("$node_bin" -e 'console.log(require("node:fs").realpathSync(process.argv[1]))' "$bundle")
fi
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
if [ -z "$bundle" ]; then
  [ -f "$repo/packages/mwf/package.json" ] || fail 'Run from a source checkout or supply --package FILE.tgz'
fi
printf 'Project: %s\nRuntime: %s\nClients: %s\nGit mode: %s\n' "$project" "$prefix" "$harness" "$git_mode"
if "$dry_run"; then
  printf 'Would install %s, then run MWF setup (including MCP probe). No files changed.\n' "${bundle:-a fresh build of this checkout}"
  exit 0
fi
scratch=$(mktemp -d "${TMPDIR:-/tmp}/mwf-install.XXXXXXXX")
trap 'rm -rf "$scratch"' EXIT
if [ -z "$bundle" ]; then
  npm ci --prefix "$repo/packages/mwf" --cache "$scratch/cache" --no-audit --no-fund
  npm run build --prefix "$repo/packages/mwf"
  (cd "$repo/packages/mwf" && npm pack --ignore-scripts --json --pack-destination "$scratch" --cache "$scratch/cache") > "$scratch/pack.json"
  filename=$("$node_bin" -e 'const p=require(process.argv[1]);console.log((Array.isArray(p)?p[0]:Object.values(p)[0]).filename)' "$scratch/pack.json")
  bundle="$scratch/$filename"
fi
# Bundled dependencies permit offline installation without running package scripts.
npm install --prefix "$prefix" --ignore-scripts --offline --no-audit --no-fund --cache "$scratch/cache" "$bundle"
cli="$prefix/node_modules/@zht7063/mwf/dist/cli.js"
[ -f "$cli" ] || fail 'Bundle did not install @zht7063/mwf'
"$node_bin" "$cli" --version
if ! "$node_bin" "$cli" setup --root "$project" --harness "$harness" --git-mode "$git_mode" ${adapter_args[@]+"${adapter_args[@]}"}; then
  fail 'Setup failed. The runtime and any completed setup steps are retained; resolve the reported issue and rerun this command.'
fi
printf '\nInstalled. Restart/reload the selected client and trust the project.\nCLI: '
printf '%q ' "$node_bin" "$cli"
printf '\n'
