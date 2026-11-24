# Source reuse: 27 modules WE2825-2SIM (20 Nov 2026)

Use firmware OEM, pinned OpenWrt and existing VeCI source. Do not rebuild old driver binaries on new kernel. Do not start image compilation until all source modules pass.

Provenance:
- OEM image: /home/andre/projects/veci/vendor-research/WE2825-2SIM_V26.03.04_V26.08.09-OEM-REFERENCE-DO-NOT-FLASH.bin
- OEM extracted rootfs: /home/andre/projects/veci/vendor-research/WE2825-2SIM-OEM-rootfs
- OpenWrt source pin 64900e756efa667774214f9c6b17c113222e01f7, kernel 6.12.112, MT7628AN 2.4 GHz ONLY.
- Original VeCI and local source: source/veci-core, source/we5927-lte, rebuild/veci-v2/packages.
- Source commit references point to already-written commits; reuse/merge and test instead of generating replacements.

| Module | Reuse OEM reference | Native OpenWrt building block | Reuse existing VeCI implementation | Remaining gap |
|---|---|---|---|---|
| router_login_and_permissions | OEM rpcd + uhttpd | rpcd/ubus sessions | v2 app.js login/ACL | permission/security runtime |
| interface_wan_lan | OEM Network WAN/LAN | netifd, UCI | c9ca523 imported veci2-interfaces | network runtime/rollback |
| dhcp_dns_static_leases | OEM dhcp config | dnsmasq | current veci2-dns + veci2-static-leases | full pool/lease integration |
| ipv6_ra_dhcpv6 | OEM IPv6 disabled | odhcp6c + odhcpd | veci-v2-ipv6 | IPv6 RA/DHCPv6 proof |
| firewall_zones_nat | OEM firewall config | firewall4/nftables | veci2-firewall + old 097f8b1 | zones/NAT runtime |
| port_forward_dmz | OEM DMZ menu | firewall4 redirect | veci2-firewall + 0d44277 | live forward negative tests |
| static_routes_policy | OEM static route menu | netifd route/rule | 806cf55 imported veci2-routes | runtime/reboot |
| wifi_ap_2g | OEM mt7628.dat | MT7603/mt76, hostapd | veci2-wifi + guardian | WPA2-AES beacon/client |
| wifi_survey_channel | OEM site survey | iw/mac80211 | veci2-wifi, v1 VeCI wifi.js | scan + channel verification |
| wifi_clients_access_control | OEM wireless ACL | hostapd/iwinfo | v1 VeCI wifi.js/devices.js | client allow/deny |
| lte_rndis_data | OEM anywifi/start_4g_entry.sh | rndis_host, netifd | we5927-lte daemon | real modem boot/recovery |
| lte_dual_sim_manual | OEM netcard GPIO46 | gpiolib | veci2-sim-manual + we5927-lte | slot mapping hardware |
| lte_apn_pin_puk | OEM cellular menu | USB serial | veci2-lte-policy + aa1b0b8 | PIN/PUK hardened integration |
| lte_ussd | OEM Qualcomm AT | USB serial driver | 331ebf7 and a79fac0 | USSD lock and response |
| system_services_startup | OEM init.d | OpenWrt procd | v1 VeCI serviceAction | whitelist/boot testing |
| system_cron_scheduler | OEM cron | busybox crond | a66f7ec veci2-cron | scheduler runtime tests |
| system_logs_diagnostics | OEM log/diagnostics | logd, ping | veci2-system-admin/status | bounded live tests |
| system_time_ntp | OEM sysntpd | OpenWrt sysntpd | veci2-system-admin | NTP sync testing |
| system_leds_buttons | OEM gpio_switch | kmod-leds-gpio/hotplug | veci2-system-admin | real GPIO/LED mapping |
| system_access_ssh_https | OEM dropbear/uhttpd | dropbear/uhttpd | d983ee3 imported veci2-access | secure actual access |
| system_backup_restore | OEM backup GUI | sysupgrade -b/-r | 636710d backup export | restore test |
| system_update_policy | OEM sysupgrade | fwtool/usign/ucert | veci2-verify-image | full trust/update policy |
| addon_enable_disable | OEM optional services | APK/procd | veci2-apk + 1984f18 | startup/disable test |
| firmware_network_watchdog | OEM anyos_netwatchdog | procd/netifd | we5927-lte + 077d88d | no disruptive restart |
| firmware_gpio_hardware_watchdog | OEM watchsystem_of_dog.sh | Linux watchdog | 461870a GPIO37 status | physical watchdog |
| firmware_24x7_observability | OEM watchsystem_of_dog.sh | logd/procd | veci2-status + system-admin | 72h telemetry |
| guest_wifi_isolation | OEM guest SSID2 off | hostapd/firewall4 | source/veci-app-guest | guest isolated hardware |

Current source reuse incorporated WITHOUT rewriting original scripts:
- WAN/LAN: commit c9ca523 provider/ACL/browser/UI and original test
- IPv4 routes: commit 806cf55 provider/ACL/browser/UI and original test
- SSH and HTTPS: commit d983ee3 provider/ACL/browser/UI and original test

The current source tests cannot substitute for live BusyBox+UCI RPC integration or one-router physical UAT. No module promoted to full PASS by this mapping and no firmware was built.
