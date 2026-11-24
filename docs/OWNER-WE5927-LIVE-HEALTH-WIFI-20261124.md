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


## Owner physical audit 2026-11-24 03:40:29 UTC and correction of unsafe assumptions

Owner's second verified Windows run: uptime 4443 seconds; free RAM 15004 KiB; free overlay 1804 KiB; root password YES; LTE HTTPS bound USB0 PASS HTTP 200; LAN/DHCP/NAT intact. Primary AP disabled=1, encryption=none, no PSK. phy0 and mt7603e present, network.wireless up=true, but no AP netdev observed. SMS RPC registered, SMS configuration disabled. Wi-Fi is NOT hardware PASS.

Read-only audit reached AUDIT_END=OK then SSH exit=127 with shell 'CR not found'. A reproducer shows a carriage-return-only line after a POSIX script produces exit 127, whereas a literal exit with prior status placed BEFORE that terminal CR preserves success. PowerShell stdin transport now appends that explicit POSIX exit statement, retaining real nonzero results and success-token checks.

Owner hardware reports WIFI_TIMEOUT_HELPER=unavailable. No standalone timeout command or supported BusyBox timeout applet is available in the runtime. Previous guarded repair would safely abort before touching settings. Revised repair uses built-in bounded RPC timeout: ubus -S -t 12 call network.wireless up, targeting radio0 only.

Crucial new source finding from the signed ROM /sbin/wifi itself: wifi up radio0 triggers ubus call network reload, which may perturb functioning LTE/LAN. The prior repair script assumption of radio-only behavior was INCORRECT. That call is now removed. Targeted network.wireless up may legitimately do nothing if radio0 is already reported up. If AP BSS/hostapd cannot be proven, restore original wireless UCI and report failure; do not force radio down or reset. The original backup is retained, and rollback includes UCI revert plus file verification.

This is a source-level safety correction, NOT executed on the physical router. Historical owner evidence includes MT76 MCU timeouts after radio down/up, so kernel deadlock cannot be excluded or made safe by a user-space watchdog. Do not claim physical Wi-Fi PASS until beacon/client-DHCP/DNS/HTTPS is observed. No new firmware image was flashed.

Next build permanent regression: no wifi up calling full network reload, no unbounded Wi-Fi action, no unsafely enabled open SSID, no fabricated AP-ready from phy0/ubus; add secured first-use AP wizard and real hardware tests.

## Physical Wi-Fi UAT follow-up, 24 November 2026 03:50 UTC: missing od

Owner ran SHA256-pinned a65fe54 Windows workflow on their only physical WE5927. Pre-audit complete: firmware OpenWrt 25.12.6/kernel 6.12.112, uptime 5022 seconds, 15340 KiB RAM available and 1804 KiB flash overlay free; LAN/USB0 default route, DHCP, NAT, SSH, HTTPS are up; USB0-bound HTTPS 200 PASS. Wi-Fi radio is 2g with phy0/mt7603e and wpad available; default_radio0.disabled=1, encryption NONE, no WPA2 key; radio0.up=true does NOT prove AP netdev exists. SMS RPC object registered, SMS UCI disabled; no MCU timeout detected.

Wi-Fi repair did begin and created a verified original-wireless backup at /root/veci-router-uat/wireless-before-20261124T035014Z.uci. WPA2 key generation failed because od is not installed on this firmware: /bin/sh: od: not found, WIFI_REPAIR_STOP=key_generation_failed. The script printed WIFI_UCI_ROLLBACK=PASS. The script stopped BEFORE UCI wireless commit, radio-targeted ubus call or driver activation; no flashed image, reset, network reload or modem operation. Never present this run as Wi-Fi activation success.

Corrective next-build requirement: A secure first-use AP wizard and router recovery script MUST NOT rely on tools absent from the actual shipped ROM. Remove od/hexdump/base64/openssl prerequisites for password generation. New code uses /proc/sys/kernel/random/uuid, a CSPRNG-generated UUIDv4, strips hyphens with already-observed tr, checks exactly 32 hex characters and version4 pattern. A UUIDv4 carries 122 bits of randomness, sufficient for a 32-character ASCII WPA2 passphrase. Fail closed when kernel random UUID is not readable or malformed. A new regression test runs the exact shell branch without UCI mutations, validates success across five invocations, and never prints keys. Validate the actual physical kernel path before claiming AP PASS.

No extra software is installed into the 1804 KiB overlay, no changes made to the functioning LTE path. Driver/hostapd AP startup and external client beacon/WPA2/DHCP/Internet still NOT VERIFIED.

## Owner fourth field attempt 2026-11-24 03:55 UTC: AP failed readiness after bounded radio-only ubus

Physical signed firmware OpenWrt 25.12.6, kernel 6.12.112; uptime 5315s, RAM available 15148 KiB, flash overlay available 1824 KiB, firmware MTD size 0x007a0000. LTE HTTPS via usb0 HTTP 200; SSH/HTTPS/LAN/DHCP/NAT remain up at audit start. Wi-Fi primary AP disabled=1, security none, no key; PHY0 and mt7603e present; radio0 reports up=true while WLAN interface count=0. No prior MT76 timeout observed in this boot's filtered diagnostic.

The audited recovery attempt created wireless backup /root/veci-router-uat/wireless-before-20261124T035505Z.uci, generated a WPA2 key using kernel UUID, committed UCI wireless, issued only bounded ubus network.wireless up for radio0 with no network reload; its hostapd/AP verification did not pass, reporting WIFI_REPAIR_STOP=hostapd_ap_not_enabled_rollback. UCI rollback returned WIFI_UCI_ROLLBACK=PASS. This means original wireless UCI settings were restored; it does NOT prove a physical beacon appeared or that kernel runtime was perfectly untouched. No post-audit was run because wrapper stopped on failure, so post-attempt LTE path and live radio health are not independently confirmed yet. Do not assert Wi-Fi UAT PASS.

Technical assessment: netifd's radio0 up method can leave preexisting radio state unchanged when radio0 already reports up, and may not reload newly committed wireless configuration. OpenWrt's /sbin/wifi up does trigger a broad ubus network reload, which may perturb the working LTE path; refrain from running that on owner's only router. Earlier 2026-11-17 UAT on another installed version observed radio0 up with missing phy0-ap0 interface/hostapd BSS, showing this is a recurring class of defect, not proof of the exact present root cause.

Next action: obtain a READ-ONLY snapshot of ubus radio0 status, hostapd.* registrations, sysfs WLAN interfaces, netifd/hostapd and mt76 logs, LAN/LTE gateway. Distinguish (1) missing UCI apply/reload, (2) netifd radio teardown, (3) hostapd config/ACL failures, (4) persistent MT76 driver problems, and (5) diagnostic selector false negatives. No repeated Wi-Fi up, no driver reset, no LTE network reload, no new flash until evidence identifies a controlled fix.

Next firmware gates: secure first-use AP config wizard; per-radio application without broad network reload; fail-closed detection of radio reports up with no primary interface; logs that expose exact failure phase without SSID/password leakage; physical client beacon association+WPA2+DHCP+DNS+HTTPS, plus MT7603 durability. Record UCI rollback separately from runtime recovery and verify WAN availability after any attempted change.

## Owner read-only command UAT 2026-11-24 ~10:55 WIB: PowerShell/SSH quoting fault

Owner executed an inline SSH remote command with nested double quotes and grep expressions separated by pipes. Output shows network.wireless status true; ubus lists only global hostapd and hostapd-auth objects (no hostapd.phy0-ap0 registered), and /sys/class/net lists only br-lan, eth0, eth0.1, eth0.2, lo, usb0 (no WLAN BSS). This independently confirms primary WLAN BSS is absent AT TIME OF READ; it does not establish driver malfunction versus AP disabled due to deliberate UCI rollback. The web UI earlier correctly reports AP disabled. A per-radio up call had failed its AP readiness gate and UCI rollback restored the disabled AP.

The command's quoted grep regex alternations were mangled by Windows PowerShell/OpenSSH inline quoting. Shell consequently attempted to run words such as netifd, mt76, timeout, radio0, setup, teardown, psk, password, key as separate commands; 'Failed to publish object network/network.device/network.interface' likely came from an accidental invocation of an extra netifd instance colliding with the existing network ubus objects, NOT evidence netifd's primary daemon is broken. The diagnostic did not produce a reliable post-rollback LTE HTTPS result. Do not cite those text lines as hostapd/driver errors.

Permanent prevention: never send complex shell regex with quoted pipes in a Windows ssh inline command; deliver a SHA256-pinned read-only .sh over SSH stdin, append literal POSIX exit status before PowerShell native stdin trailing CR, keep single-shell quotes under the shell script, and check SSH exit + TRIAGE_END=OK. The new script scripts/router/veci-live-wifi-readonly-triage.sh checks exact board; reads radio UCI disabled flags without revealing the key; reads bounded ubus radio and hostapd states, sysfs interface names, filtered privacy-safe netifd/hostapd/mt76 diagnostics, process counts, and HTTPS over usb0 after rollback. It MUST NOT change radio, network, LTE, modem, or firewall and must distinguish missing AP BSS from a driver error. Source unit tests cover read-only commands, wrong-device refusal and syntax. No new physical data read by the developer; hardware triage is PENDING owner local run.

Release requirement: add the shell-transport quoting regression, no automatic netifd invocation, display 'radio up but no AP BSS' as a diagnosable state, no fake Wi-Fi PASS, and keep WAN uptime proof separate.
