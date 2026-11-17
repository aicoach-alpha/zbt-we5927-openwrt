# VeCI v2 settings: IPv6 default OFF and four menu groups

Source: rebuild/veci-v2-we5927-2sim-20261117
Board: ZBT-WE5927-DSIM / WE2825-2SIM (custom MT7628AN DTS).

## Four top-level menu groups
1. Beranda: LTE, AP health, overall resources.
2. Koneksi: dual-SIM LTE, Wi-Fi, LAN/WAN, DHCP, attached clients.
3. SMS Center: messages and the existing serialized AT/PDU provider.
4. Pengaturan: IPv6, nested addon manager, future firmware/backup/security.

Advanced controls and optional features belong inside subpanels, not an
ever-expanding main menu. Preview shows only currently implemented actions;
full LuCI and vendor feature parity remain pending release gates.

## IPv6: OFF on first boot, ON by explicit choice in Settings
- The new board-specific package ships a UCI setting disabled.
- A one-time default script runs before normal network setup and disables
  LAN IPv6 prefix delegation, WAN/LTE IPv6, WAN6, LAN RA, LAN DHCPv6 and NDP.
- A boot service starts at S16, after the OpenWrt sysctl step and before
  the S20 network step, and configures the IPv6 kernel sysctl on all/default.
- Settings shows saved IPv6 preference and the live kernel IPv6 state
  separately. It does not claim actual IPv6 Internet connectivity.
- A request to change IPv6 requires authenticated privileged RPC access,
  explicit confirmation, an exact router board check, and existing UCI
  LAN/DHCP sections. It makes private backups and rolls back on errors.
- Saving only changes persistent UCI network/DHCP/IPv6 preferences.
  No automatic wifi reload, ifdown, modem power-cycle, reboot or
  network reload is performed. The choice applies at the next user
  scheduled reboot.
- Enabling IPv6 does not create guaranteed IPv6 Internet access on a
  modem that may provide only IPv4 via RNDIS. Carrier and modem upstream
  IPv6 must be verified separately.
- A planned reboot causes network interruption on this single-slot router.
  No zero-downtime firmware upgrade is claimed.

## Verification
- Source code and shell/JS syntax tests verify defaults, status, ACL,
  explicit confirmation, absence of automatic network commands and
  four-menu composition.
- Physical startup IPv6 behavior, IPv6 WAN negotiation, radio/LTE stability,
  all-port LAN compatibility and 72-hour UAT are not yet verified.
- This new code is a development candidate: DO NOT FLASH current router.
