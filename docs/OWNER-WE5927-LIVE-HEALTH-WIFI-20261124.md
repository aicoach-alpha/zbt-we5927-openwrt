# ZBT-WE5927 owner field audit and Wi-Fi remedy — 2026-11-24

Evidence is classified: prior on-device user UAT, confirmed bytes in signed ROM, historical source issues, and untested live status. Never promote source-only evidence to hardware PASS.

## Confirmed or previously observed
- Exact flashed signed image OpenWrt 25.12.6 SHA256 d6d1ce265668af052f592458b7397c1986aca8483c78e20c8c68cbc3342a3f74; rootfs examined directly offline using unsquashfs.
- CONFIRMED ROOT CAUSE: shipped etc/uci-defaults/98-we5927-websafe runs wifi config on first boot and deliberately marks every new Wi-Fi radio disabled=1 until a password is set. There was NO secure activation wizard; owner GUI shows AP disabled in configuration.
- PREVIOUS DEVICE PASS: usb0 DHCP 192.168.7.165 via 192.168.7.1, router-bound Internet HTTP and HTTPS 200/DNS; Windows Ethernet address 192.168.1.223 gateway 192.168.1.1, TCP443 to 1.1.1.1 PASS. Laptop also has another Wi-Fi Internet gateway, so not all laptop traffic is proven LTE.
- PREVIOUS FIRMWARE RISK: guardian source records earlier wifi up radio0 causing an MT76 MCU timeout. Guardian stays strictly observe-only. Whether this happens in the CURRENT firmware remains UNKNOWN.
- OWNER UAT FAILED: Wi-Fi AP disabled, SMS Center checking and buttons disabled, GUI poor. USSD permanently retired.
- Owner's current PHY, hostapd, Wi-Fi clients, DHCP over Wi-Fi, firewall policies, kernel errors, root password current status, modem thermal/counter, reboot persistence, and 72-hour stability NOT YET AUDITED ON DEVICE.
- Past UAT SIM1/2 switch rolled back after modem APN programming failure; polarity of GPIO46 not confirmed. Do not toggle SIM or reset LTE.
- Direct access not available: andre-nas gateway to 192.168.1.1 reaches a different network (refused SSH/incompatible HTTPS). Windows connection tool usage exceeded limit; do not assume a repair was run.

## Local, guarded corrective path
- scripts/router/veci-live-router-audit.sh performs read-only sanitized status collection of board/kernel/firmware/flash/CPU/RAM, SSH/HTTPS/clock/NTP, netifd, LTE routing and HTTPS via USB0, LAN/DHCP/firewall, Wi-Fi radio config/PHY/hostapd/kernel driver errors, SMS RPC, trusted key and verification gaps.
- scripts/router/veci-live-wifi-guarded-repair.sh requires exact board, root, 2.4-GHz AP, PHY0, wpad, LAN bridge, intact LTE route, no pending wireless edits, no current MT76 timeout. It saves protected verified wireless backup, uses WPA2 with random strong credential if needed, changes ONLY wireless UCI; runs bounded per-radio wifi up. Independent 75-second rollback restores config if hostapd does not confirm readiness. It never flashes/reboots/restarts the whole network/touches LTE/SIM.
- scripts/router/VeCI-WE5927-Audit-and-Repair-WiFi.ps1 runs locally on the wired Windows device. Requires known SSH fingerprint and SHA-256-pinned source; captures sanitized before/after reports and prevents Wi-Fi passwords from being written into reports. AuditOnly supported.
- CAUTION: none of these scripts was run on the physical router in this session. Source checks, wrong-device refusals and shell syntax are NOT hardware acceptance.

## Prevent recurrence in next firmware
1. Keep security default of no open AP, BUT ship an intuitive secure WPA2/WPA3 Wi-Fi first-use wizard for SSID/password, safe radio start, automatic rollback and accessible status. Never leave users permanently stuck with disabled AP.
2. Physical UAT must prove actual AP beacon, client joining, DHCP, DNS/TCP HTTPS via LTE, wired reachability preserved, and Wi-Fi kernel stable; not a status boolean or simulation.
3. Never reset LTE, switch SIM GPIO, restart full networking, flash or reboot to enable Wi-Fi. Keep original configs backed up, refuse unknown PHY/driver error.
4. Source CI must regress the first-boot disabled security rule, guarded remediation and audit correctness; release remains fail-closed without real hardware proof. Router only has 2.4-GHz Wi-Fi.
5. SMS and previously reported SIM/APN errors remain separate release-blocking issues. Signing/trust, sysupgrade -T, and real 72-hour stability remain mandatory before final release.

## Owner physical audit evidence 2026-11-24 03:33:45 UTC

Owner ran pinned PowerShell on Windows machine wired to ZBT WE5927. Read-only audit completed through AUDIT_END=OK; PowerShell aborted before Wi-Fi repair because native SSH stderr was emitted as terminating NativeCommandError under global ErrorActionPreference=Stop. This is a Windows wrapper bug, not an observed router kernel crash. Branch update captures both native SSH streams under scoped Continue, restores preference, gates on SSH exit code and completion sentinel, and preserves diagnostics in sanitized report.

Read-only factual on-device snapshot (owner report: E:/Documents/VeCI-Router-Audits):
- board zbtlink,zbt-we5927, OpenWrt 25.12.6 kernel 6.12.112, uptime 4040s, CPU load 0.07/0.04/0.01, MemAvailable 15164 KiB, overlay 1804 KiB. This hardware has tight resource headroom.
- LAN 192.168.1.1/24, br-lan yes, DHCP running, masquerade enabled, LTE usb0 IPv4/default route present and USB0-bound HTTPS HTTP 200. Do not alter established LTE/LAN path.
- wireless config present, radio0 band=2g, primary AP default_radio0 disabled=1, encryption=none, no PSK, network=lan; phy0 present, mt7603e loaded, wpad installed, hostapd/wpad process present, no WLAN kernel netdev found by original audit scanner. network.wireless returned up=true. None of these establish AP readiness. No MCU timeout signatures observed so far this boot.
- veci.sms ubus object registered, veci_sms.main.enabled=0. This is a source-backed status of SMS config; physical SMS send/receive remains unproven, do not auto-enable or send.
- SSH and uhttpd running, firmware trust anchor present; NTP service unknown, clock accurate UTC. Root password audit returned empty due BusyBox awk portability; owner previously successfully changed password. Updated audit will return yes/no/unknown.
- historical SIM selector audit key was wrong and updated to we5927_lte.main.sim.
- timeout executable absent on owner router in earlier terminal. Signed firmware BusyBox binary has timeout applet string; guarded repair now tests busybox --list for timeout and invokes it only if available. Check on hardware before enabling radio.

No Wi-Fi repair execution or post-repair results exist yet. Do not claim hardware PASS. The next live execution must pin SHA256 to approved code, preserve original router state on failed preflight, and report full diagnostic reasons.
