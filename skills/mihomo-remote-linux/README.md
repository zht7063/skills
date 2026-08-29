# Remote Linux Mihomo

`mihomo-remote-linux` is a safety-first operating guide for installing,
auditing, updating, repairing, or migrating Mihomo (Clash Meta) on a remote
Linux server over SSH. It covers ordinary loopback proxy ports as well as the
higher-risk system-wide TUN routing workflow.

## When to use it

Use this skill for requests involving Mihomo or Clash Meta on a server:
service setup, proxy ports, `mode: rule` or `mode: global`, systemd operation,
TUN routing, egress checks, version upgrades, recovery, or migration.

It requires SSH access to the target host. System-wide TUN changes additionally
require usable sudo access and an independently reachable recovery path.

## What it provides

- A baseline audit for host prerequisites, existing services, executable paths,
  safe listener/controller metadata, selected policy, and actual egress.
- A checksum-verified, architecture-aware release workflow that preserves a
  working installation until the replacement has validated.
- A normal non-root service pattern using loopback-only HTTP, SOCKS, and Mixed
  proxy ports with `systemd --user`.
- A guarded TUN cutover procedure: on-host backups, scheduled rollback,
  separate service unit, node selection/persistence checks, policy-routing and
  DNS verification, and only then cancellation of the rollback timer.

## Privacy boundary

The user must place their private `config.yaml` directly on the target host.
This skill never creates, uploads, downloads, prints, commits, syncs, or edits
that file, and it never reads subscription URLs, proxy definitions, provider
URLs, controller secrets, or node credentials. It inspects only safe metadata
and reports only the selected policy plus independently measured egress data.

Keep `config.yaml` mode `600` in a private directory, and keep the controller
bound to loopback unless the user explicitly requests a secured remote
controller.

## Traffic-model rule

A proxy listener on port `7890` does not automatically proxy the server.
Proxy-aware applications need explicit proxy settings; routing all ordinary
outbound TCP/UDP traffic requires TUN or transparent routing. Before changing
anything, choose the intended model:

| Need | Model |
| --- | --- |
| Proxy-aware commands only | Local HTTP/SOCKS/Mixed port or shell proxy variables |
| Rule-based direct versus proxy routing | `mode: rule` |
| One selected node for captured traffic | `mode: global` plus selected `GLOBAL` node |
| Default server outbound traffic | TUN with `auto-route` and `CAP_NET_ADMIN` |

## Documentation and validation

Read [SKILL.md](SKILL.md) before applying the skill. The detailed
[operations reference](references/operations.md) covers installation and
maintenance; [service and recovery](references/service-and-recovery.md) is
required before changing systemd or enabling TUN. Run the package integrity
test from the repository root with:

```bash
python3 -m unittest skills/mihomo-remote-linux/tests/test_skill_integrity.py
```
