# VeCI LuCI-independent migration contract (WE5927)

## Status (2026-11-12)
**IN PROGRESS / NOT DEPLOYABLE.** Existing VeCI navigation and LTE RPC/UI are not proof of LuCI parity. No production LuCI removal is authorized by this branch. Flashing remains blocked.

## Current facts
- Current project README describes LuCI LTE status and ships `files/www/luci-static/resources/view/we5927_lte.js`, a LuCI menu entry and an RPC ACL.
- `web/v15/veci-general-ui.js` moves existing authenticated SPA navigation; it is not a standalone replacement for network administration.
- `packaging/veci-general-apps/files/usr/libexec/rpcd/veci.apps` still maps WireGuard to `luci-proto-wireguard`. Replace only after a native VeCI WireGuard flow is proven.
- `uhttpd`, `rpcd`, `ubus`, `uci`, JSON filter, firewall and network services are *not* synonymous with LuCI. Keep required services and audit actual dependencies.

## Full functional parity acceptance matrix
Each row requires both a native authenticated VeCI user journey and an automated RPC/config test, plus backup-and-recovery evidence. UI-only mock screens do not count.

| Area | Required native VeCI functions | Gate |
| --- | --- | --- |
| Access | login/logout, ACL roles, CSRF, password/session management, SSH keys, HTTPS/certificates | P0 |
| Status | system/uptime, CPU/RAM/flash, logs, processes, service status, time/NTP | P0 |
| LAN/WAN | interface configure, DHCP static leases, DNS, IPv4/IPv6, VLAN/bridge, routes, diagnostics | P0 |
| Wi-Fi | SSID, encryption, guest isolation, radio settings, connected clients, safe apply/rollback | P0 |
| Security | firewall zones/rules, port forwarding, DMZ, NAT, ban/allow management | P0 |
| Cellular | modem status/AT lock, data, SIM, APN, recovery, quota when supported, SMS inbox/send/sent/drafts | P0 |
| System | backup/restore, factory reset, package inventory, config diff, signed upgrade validation | P0 |
| Services | DDNS, VPN/WireGuard, scheduled tasks, startup services, DNS/DHCP | P1 |
| Addons | signed exact-ABI apps, storage limits, installed/unavailable states, guest portal | P1 |
| OTA | signed release manifest/image, exact board, metadata/size, preflight, recovery, postflight | P1 |

## Hard engineering constraints
1. Build against an identified exact board (MT7628/mt7603, 8 MB NOR, 64 MB RAM), kernel and package ABI. Treat changing upstream kernel versions as separate hardware qualification.
2. Install a native VeCI backend with least-privilege rpcd ACL; never expose generic `uci set`, shell execution or unauthenticated package operations to the browser. Whitelist per-feature methods and validate every field.
3. Implement safe apply for network/radio/firewall with rollback on lost management access. Do not restart radio automatically while the MT7603 MCU D-state failure remains unresolved.
4. Test on a spare/staged firmware and wired Ethernet first. Run `scripts/check-veci-luci-independence.py` on extracted rootfs + package manifest. The script checks absence of LuCI and preservation of core services; **it does not prove feature parity**.
5. Run functional hardware acceptance, SMS modem tests, 72-hour Wi-Fi/LTE observation, verify signed sysupgrade with `sysupgrade -T`, and retain calibration/ART and recovery backups before moving to production.
6. Only then build firmware without LuCI packages/assets. Never run `apk del luci*` on production SquashFS to simulate image savings.
7. Compare image sizes with identical base config, modules and build flags. Report compressed image delta, not installed package sizes.

## Follow-up implementation
Create independent native VeCI RPC methods/pages by row, record evidence and failing cases. Remove `luci-proto-wireguard` dependency only when native WireGuard management supports import, editing, status and safe apply. Do not merge or release this migration solely because the static gate passes.
