# Operations reference

Use this reference for installation, ordinary port-proxy operation, repair, migration, and updates. It deliberately contains no `config.yaml` template: the user must manually place their private, validated file on the target host before it is tested or used.

## Preconditions and architecture

Use a private directory such as `$HOME/.local/share/mihomo`. Check the operating system, CPU architecture, available sudo, and required tools before downloading:

```bash
uname -s
uname -m
lscpu | grep 'x86-64-v3' || true
command -v curl jq gzip sha256sum
```

For x86-64, use the `amd64-v3` asset only when the CPU supports it; otherwise select the matching `amd64-compatible` release asset. Select the matching ARM asset for ARM hosts. Do not guess an asset name or use a pre-release when the user requests stable Mihomo.

## Install or update the executable and GeoIP data

Fetch the latest stable release from the official Mihomo GitHub API. Preserve the manual config untouched. Stop an active managed service first; download to temporary filenames, verify the digest when GitHub supplies one, then atomically replace only the executable and `country.mmdb` after validation.

```bash
set -euo pipefail
MIHOMO_DIR="$HOME/.local/share/mihomo"
mkdir -p "$MIHOMO_DIR"
cd "$MIHOMO_DIR"

release_json="$(curl -fsSL https://api.github.com/repos/MetaCubeX/mihomo/releases/latest)"
# Choose the exact asset after detecting the host architecture; this example is only for x86-64-v3.
asset_url="$(jq -r '.assets[] | select(.name | test("^mihomo-linux-amd64-v3-v[0-9]+\\.[0-9]+\\.[0-9]+\\.gz$")) | .browser_download_url' <<<"$release_json")"
expected_digest="$(jq -r '.assets[] | select(.name | test("^mihomo-linux-amd64-v3-v[0-9]+\\.[0-9]+\\.[0-9]+\\.gz$")) | .digest // empty' <<<"$release_json")"
test -n "$asset_url" && test "$asset_url" != null
curl -fL --retry 3 -o mihomo.new.gz "$asset_url"
if [ -n "$expected_digest" ]; then
  printf '%s  %s\n' "${expected_digest#sha256:}" mihomo.new.gz | sha256sum -c -
else
  echo 'No API digest: verify the release checksum manually before continuing.' >&2
  exit 1
fi
gzip -dc mihomo.new.gz > mihomo.new
chmod 0755 mihomo.new
./mihomo.new -v

curl -fL --retry 3 -o country.mmdb.new \
  https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country.mmdb
curl -fL --retry 3 -o country.mmdb.sha256sum \
  https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country.mmdb.sha256sum
awk '{print $1 "  country.mmdb.new"}' country.mmdb.sha256sum | sha256sum -c -
mv mihomo.new mihomo
mv country.mmdb.new country.mmdb
rm -f mihomo.new.gz country.mmdb.sha256sum
```

The `amd64-v3` selection in the example is conditional. Adapt both jq patterns to the detected asset rather than running it unchanged on an unsupported host. If GitHub has no digest, pause for a human checksum verification instead of installing an unverified binary.

## Private configuration and port-only operation

After the user has placed the config, restrict permissions and test it without reading or displaying its body:

```bash
MIHOMO_DIR="$HOME/.local/share/mihomo"
chmod 700 "$MIHOMO_DIR"
chmod 600 "$MIHOMO_DIR/config.yaml"
"$MIHOMO_DIR/mihomo" -t -d "$MIHOMO_DIR"
```

For a normal non-root deployment, expect loopback HTTP `7890`, SOCKS `7891`, and Mixed `7894`. `redir-port` and `tproxy-port` commonly fail without network privileges and do not make ordinary shell traffic proxied. A temporary foreground process is useful for diagnosis; use `systemd --user` for persistence and do not leave a `nohup` process running beside it.

Use a proxy explicitly for a port-proxy test, then clear temporary environment variables:

```bash
curl -fsSI -x http://127.0.0.1:7890 --connect-timeout 15 https://www.google.com
export http_proxy=http://127.0.0.1:7890 https_proxy=http://127.0.0.1:7890
export all_proxy=socks5://127.0.0.1:7891
# Run only the command that needs the proxy.
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
```

## Safe audit and repair order

1. Inspect processes, `systemctl --user` and system-unit state, executable path, permissions, listeners, and controller health without reading the config body.
2. Use the loopback controller only when it is configured and authenticated. Report safe values from `/configs`, selected policy label, and TUN state; never print proxy lists, controller secrets, or provider URLs.
3. Diagnose `address already in use` by finding the owning process and retain one deliberate service owner. Diagnose `operation not permitted` by checking for `redir-port`/`tproxy-port` or missing TUN capability.
4. For an update, preserve the current service type, validate the new binary and private config, then start that same service type. If validation fails, restore the prior binary; do not touch the config.

## Migration rules

When migrating from an older Clash installation, inventory its service ownership and ports before stopping it. Install Mihomo under its own private directory and keep the old service disabled-but-recoverable until the new port-only validation passes. Do not copy a legacy config yourself; ask the user to place a compatible config manually. Never run both services on the same proxy ports.
