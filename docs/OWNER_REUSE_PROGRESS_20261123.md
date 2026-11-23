# VeCI — use existing OEM, OpenWrt and VeCI sources

23 November 2026. Source only; no OpenWrt image build or physical router operation.

Integration worktree: /home/andre/projects/zbt-we2825-veci-openwrt/worktrees/parallel-fast-reuse-20261123
Branch: development/we2825-fast-reuse-20261123. Original main is dirty; do not force merge.
OEM hardware reference: /home/andre/projects/veci/vendor-research/WE2825-2SIM_V26.03.04_V26.08.09-OEM-REFERENCE-DO-NOT-FLASH.bin
OpenWrt core: netifd, dnsmasq, firewall4, procd, hostapd/mt76, dropbear, odhcpd.

## Audited 27-module progress
Source verified 14/27 (51.85%); partial 13/27; unported 0; physical UAT 0/27.
Baseline main 4/27, isolated integration progress +10. Not yet on canonical main.

### Source-verified modules
- router_login_and_permissions
- interface_wan_lan
- dhcp_dns_static_leases
- ipv6_ra_dhcpv6
- static_routes_policy
- wifi_ap_2g
- wifi_survey_channel
- wifi_clients_access_control
- lte_apn_pin_puk
- lte_ussd
- system_services_startup
- system_cron_scheduler
- system_time_ntp
- system_access_ssh_https

### Remaining source-partial modules
- firewall_zones_nat
- port_forward_dmz
- lte_rndis_data
- lte_dual_sim_manual
- system_logs_diagnostics
- system_leds_buttons
- system_backup_restore
- system_update_policy
- addon_enable_disable
- firmware_network_watchdog
- firmware_gpio_hardware_watchdog
- firmware_24x7_observability
- guest_wifi_isolation

## Existing-code reuse evidence
- Staging branch reused existing VeCI login, SSH/HTTPS, static routes and prior LTE/SIM/USSD/services/NTP work.
- Existing native host UCI and libubox tested IPv6 RA/DHCPv6, Wi-Fi 2.4 GHz AP/channel/client ACL, cron, WAN/LAN.
- Existing test-owner-dhcp-dns.py exercised native dnsmasq/DHCP UCI, shared lock, negative cases, byte-exact rollback.
- Original implementation preserved: no replacement DNS/modem daemon and no transplant of OEM Linux 4.4 binary into 6.12.
- All source acceptance records are backed by scoped test IDs, source hashes, actual successful method logs and receipt hashes.

## Hard release gate
Build forbidden until all 40 source core verified and source-completion-gate returns build_permitted=true.
Do not interpret source-verified as physical hardware UAT. Do not trigger compilation, signing, sysupgrade or flash.
