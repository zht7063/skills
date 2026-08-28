# Service and recovery reference

Use this reference only after the user has manually placed a private, validated `config.yaml` on the target server. It contains no configuration content and must never be used to create or rewrite one. A rollback backup is permitted only for a TUN cutover, only in a root-private directory on the same target host, and must never be copied to the local machine or repository.

## Paths and permissions

```bash
MIHOMO_DIR="$HOME/.local/share/mihomo"
chmod 600 "$MIHOMO_DIR/config.yaml"
"$MIHOMO_DIR/mihomo" -t -d "$MIHOMO_DIR"
```

Keep the config directory private. A root-owned TUN rollback backup directory should use mode `700`; its on-host configuration copy should retain mode `600`.

## User-level unit for port-only operation

```ini
[Unit]
Description=Mihomo proxy service

[Service]
Type=simple
WorkingDirectory=%h/.local/share/mihomo
ExecStart=%h/.local/share/mihomo/mihomo -d %h/.local/share/mihomo
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Enable only this unit for ordinary port proxying:

```bash
systemctl --user daemon-reload
systemctl --user enable --now mihomo.service
sudo loginctl enable-linger "$USER"
```

## Capability-scoped system unit for TUN

Create a **new** unit name, such as `mihomo-tun.service`, when the server already has another system Mihomo unit. Do not overwrite an existing unit merely because it is inactive.

```ini
[Unit]
Description=Mihomo global TUN proxy
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=<USER>
Group=<USER>
WorkingDirectory=/home/<USER>/.local/share/mihomo
ExecStart=/home/<USER>/.local/share/mihomo/mihomo -d /home/<USER>/.local/share/mihomo
Restart=on-failure
RestartSec=5
CapabilityBoundingSet=CAP_NET_ADMIN
AmbientCapabilities=CAP_NET_ADMIN
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

Validate and register it before starting it:

```bash
sudo systemd-analyze verify /etc/systemd/system/mihomo-tun.service
sudo systemctl daemon-reload
```

## Fail-safe rollback timer

Before stopping a working service or enabling TUN, create and syntax-check a root-only rollback script. It must restore the timestamped configuration backup, stop/disable the new TUN unit, and reactivate the prior unit.

Schedule it with a bounded delay. `at` is optional; do not assume `atd` is running:

```bash
sudo systemd-run \
  --unit=mihomo-tun-rollback-<timestamp> \
  --on-active=8m \
  --collect \
  /usr/local/sbin/rollback-mihomo-tun-<timestamp>.sh
```

Check the timer is active before cutover:

```bash
sudo systemctl is-active mihomo-tun-rollback-<timestamp>.timer
```

After measured routing, DNS, and egress checks pass, cancel it:

```bash
sudo systemctl stop mihomo-tun-rollback-<timestamp>.timer
```

## TUN verification

Do not rely on the desired node's label. Check runtime state and actual egress:

```bash
sudo systemctl is-active mihomo-tun.service
ip link show Meta
ip rule show
curl -fsS --noproxy '*' --connect-timeout 10 --max-time 20 https://ipinfo.io/json
```

`Meta` is a common TUN device name; do not treat its absence as proof of failure before inspecting the effective routing state. A successful no-proxy-environment request from the desired country is the behavioral check.
