---
name: mihomo-remote-linux
description: Install, audit, update, repair, or migrate Mihomo on a remote Linux server over SSH. Use whenever the task mentions Mihomo, Clash Meta/Mihomo, remote Linux proxy ports, a server proxy, TUN routing, system-wide proxying, `mode: rule`/`mode: global`, or a Mihomo systemd service. Handle the private uploaded `config.yaml` safely: require the user to place it on the target host and never generate, upload, print, commit, sync, or rewrite it.
compatibility: Requires SSH access to the target Linux host; global TUN changes also require passwordless or interactive sudo and a separately reachable recovery path.
---

# Remote Linux Mihomo

Operate Mihomo without exposing subscription URLs, node credentials, or server addresses. This skill is self-contained: read [the operations reference](references/operations.md) before installing, updating, repairing, or migrating; read [the service and recovery reference](references/service-and-recovery.md) before changing systemd or enabling TUN.

## Non-negotiable privacy boundary

- The user manually uploads `config.yaml` to the target server, normally `$HOME/.local/share/mihomo/config.yaml`. Do not create, edit, normalize, upload, download, print, commit, or sync it. The sole exception is a TUN cutover's root-private backup **on that same target host**, which is needed for rollback and must never leave the host.
- Do not read the configuration body, controller secrets, subscription URLs, proxy definitions, or provider URLs. Inspect only safe metadata: permissions, `mihomo -t` output, local listening ports, controller health, selected policy name, TUN state, and egress geolocation.
- Require `chmod 600 "$MIHOMO_DIR/config.yaml"`. Keep the directory private. Never place configuration or backups in the repository.
- A controller must remain loopback-only unless the user explicitly requests a secured remote controller. Never expose `9090` on `0.0.0.0`.
- If the private config is absent, stop before service validation or startup and ask the user to upload it. Installing a binary and data files is allowed, but do not offer to generate a substitute config.

## Decide the traffic model first

State the model before changing anything:

| User need | Correct model | What it does not do |
| --- | --- | --- |
| Proxy-aware commands only | HTTP/SOCKS/Mixed ports or per-shell proxy variables | Does not capture arbitrary server traffic. |
| Rules decide direct versus proxy | `mode: rule` | The `GLOBAL` selector is not the routing decision in this mode. |
| All captured traffic uses one node | `mode: global` plus a selected `GLOBAL` node | Does not capture traffic unless TUN or transparent routing is enabled. |
| Default server outbound TCP/UDP traffic | TUN with `auto-route` and `CAP_NET_ADMIN` | Can disrupt SSH; use the recovery workflow. |

Do not call a server “globally proxied” merely because Mihomo listens on `7890`. No `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` means ordinary shell commands do not use those ports. `redir-port` and `tproxy-port` are not safe substitutes for ordinary non-root deployment.

## Baseline audit

Use targeted, non-secret checks. Confirm:

1. OS, architecture, user, available sudo, and `curl`/`jq`.
2. Current Mihomo process, user/system service state, executable path, private config permissions, listeners, and controller version.
3. Effective safe values from `GET /configs`: mode, HTTP/SOCKS/Mixed ports, loopback binding, `allow-lan`, redir/tproxy state, and `tun.enable`.
4. Selected `GLOBAL` policy and selector/URL-test state from `GET /proxies`; do not emit subscription details beyond the requested selected node.
5. Actual egress with a request explicitly through `7890` if auditing a port proxy, or without proxy environment variables if auditing TUN.

Treat an externally supplied node label as unverified. Verify the exit country from an independent IP-geolocation response rather than trusting its name.

## Standard local-port service

For the normal non-root design:

- Keep HTTP `7890`, SOCKS5 `7891`, and Mixed `7894` loopback-only.
- Prefer `systemd --user` for the long-running process and enable lingering when it must survive logout/reboot.
- Export proxy variables only in the shell or service that needs them. Unset them after short-lived use.
- Before an update, stop the active service, retain the manually uploaded configuration, validate the replacement binary/configuration, then restart the same service type. Never run `nohup` alongside systemd.
- Use the architecture-aware, checksum-verified release workflow in [the operations reference](references/operations.md); do not hard-code a binary architecture or replace a working binary before the download validates.

## Global TUN cutover

Perform this only after the user explicitly asks for default traffic routing and confirms a fixed node choice. Default to an independently verified Singapore node unless the user requests another region.

1. **Preflight.** Confirm `/dev/net/tun`, sudo, a working controller, a validated manually uploaded config with global mode, TUN auto-route, DNS handling, and selection persistence, plus a second SSH session or console path. Check for pre-existing system Mihomo units and do not overwrite an unknown installation.
2. **Backup.** On the target host only, create a timestamped root-private backup of the uploaded config, the active user/system unit, and current enablement state. Create a root-only rollback script that stops the new TUN unit, restores the on-host backup, and restarts the previous unit.
3. **Fail-safe.** Schedule that rollback before the cutover. Prefer a transient `systemd-run --on-active=…` timer when `atd` is not active. Record its exact unit name.
4. **Handoff.** Install a separate, clearly named system unit that runs the existing executable as the normal user with only `CAP_NET_ADMIN`. Disable the old unit before starting the new one to avoid port conflicts. Do not reuse or overwrite an unrelated disabled system unit.
5. **Select then persist.** Choose the requested node through the loopback controller; absent an explicit regional override, choose Singapore. Restart the TUN service and verify the same node remains selected; otherwise the uploaded config lacks persistence and must be manually corrected by the user.
6. **Verify before cancelling rollback.** Validate syntax, service state, the actual TUN interface (its name can be `Meta`, not necessarily `Mihomo`), policy-routing rules, DNS, and a no-proxy-environment egress request. For the default policy, require independently measured `country: SG`; cancel the rollback timer only after it passes.

If SSH breaks, allow the scheduled rollback to run; use console access rather than repeatedly modifying routes blindly.

## Required report

Report only:

- traffic model, active service unit, and whether the former unit is active;
- whether TUN and automatic routing are active;
- selected policy label and independently measured exit country/IP/ASN;
- exact backup directory and rollback command;
- validation commands/results and whether the fail-safe timer was cancelled.

Do not include config content, subscription/provider URLs, node credentials, controller secrets, or full proxy lists.
