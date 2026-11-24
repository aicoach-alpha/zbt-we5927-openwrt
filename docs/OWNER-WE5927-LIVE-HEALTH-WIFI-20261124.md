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

## Owner latest read-only triage attempt: SSH TCP/22 timeout on Nov 24 2026

The user successfully downloaded immutable read-only Wi-Fi triage source to Windows (4533 bytes), SHA-256 e202255199c00ebe5b2d85a8be21c113ff5a86a5c08a281a5327a81e3f518a8a. Subsequent SSH to 192.168.1.1 TCP port 22 timed out, so read-only triage NEVER EXECUTED on router. No Wi-Fi or LTE configuration changed by this attempt. Post-rollback router state remains unverified. Previous malformed inline shell command produced ubus publish errors but does not prove main netifd or SSH daemon failure. Next action: gather Windows Ethernet state, route, ping and gateway TCP 22/443 before changing anything. No reboot, reflash or radio reset.

## User Windows LAN reachability recheck 24 November 2026 ~12:15 WIB

After read-only SSH transport timeout, the user tested Windows Ethernet directly. Get-NetAdapter reports Ethernet UP 100 Mbps; IPv4 192.168.1.223 on 192.168.1.0/24, local on-link route (next hop 0.0.0.0). Router 192.168.1.1 replied to 3/3 pings with sub-1ms to 1ms latency; Get-NetNeighbor shows F8-5E-3C-A0-B9-08 in transient Probe state; both TCP 443 HTTPS and TCP 22 SSH show Test-NetConnection TcpTestSucceeded=True from Ethernet. Thus the LAN IP path, ICMP and port 22/443 reachability work now. Prior ssh timeout should be classified intermittent/unresolved, not a lasting router/SSH failure; TCP acceptance does not prove login or shell readiness. No config change involved. Next: rerun only the already SHA-verified 4533-byte read-only Wi-Fi/hostapd/MT76 diagnostic via SSH stdin; do not rerun guarded activation/reboot/flash. Capture actual live router output before drawing new conclusions.

## 2026-11-24 05:22:48 UTC: field triage finds netifd multi-PID and LTE not proven

Owner exact-board read-only diagnostics ran to TRIAGE_END=OK with SSH_EXIT=0. Firmware OpenWrt 25.12.6 kernel 6.12.112 uptime 10583s. Radio0.up=true but AP_DISABLED=1, AP_ENCRYPTION=none, AP_KEY_PRESENT=no, no primary interface and no WLAN under sysfs, only hostapd global + hostapd-auth, primary hostapd BSS missing. Compatible with a disabled AP after prior successful UCI rollback, not proof MT76 driver cannot start. mt76 firmware init done, no MCU timeout in supplied filtered log excerpt.

NEW SYSTEM ISSUE: pidof netifd reports THREE PIDs, versus one in prior audit. Original diagnostic did not capture PID/parent/exe; do not kill anything. Recent log has repeated ubus network.interface notify_proto Permission denied while starting udhcpc for both LTE usb0 and WAN eth0.2. Possibilities include process collision, UBus ownership conflict, timing race, or another defect. OpenWrt official issues #18807 and #23266 report similar errors mainly during teardown action=0, whereas this router has action=1; NOT confirmed the same bug. Do not treat a default route as proof of Internet.

Default route usb0 and LAN br-lan present, but the bound HTTPS test returned NOT_VERIFIED; exit reason was not captured by prior script. LTE Internet is UNKNOWN, not proven unavailable. Three PIDs may represent duplicate daemons, transient processes or another process identity; inspect /proc/PID/status fields and executable before action.

Source adds scripts/router/veci-netifd-lte-readonly-20261124.sh: exact-board read-only PID/PPid/state/exe, network ubus registrations, LTE ubus status, udhcpc count, count-only notify_proto Permission denied logs (does not disclose DHCP client IDs), bounded LTE-bound HTTP by numeric IP and HTTPS by hostname, with curl exit and HTTP codes. Both curl tests explicitly use usb0 and never mutate network state. Safety regression tests forbid kill/restart/reload/UCI edits. This script HAS NOT yet run on physical router.

Policy: no kill/restart netifd, global network reload, modem reset, Wi-Fi activation, GPIO changes, or flash while network management health is unknown. Keep Wi-Fi first-boot disabled by design, netifd ownership, DHCP errors and cellular egress as separate next-build gates.

## Repeated SSH timeout after verified download — 2026-11-24 owner field output

Owner successfully downloaded immutable 4037-byte netifd/LTE read-only triage script from pinned GitHub commit and verified SHA-256 0eb716c46f91b446bfecbda357db612c19c390e80b22458d9c14ada7319a2e2f. The attempt to SSH to router 192.168.1.1 on port 22 failed at TCP connection with timeout and SSH_EXIT=255. Consequently the diagnostic script DID NOT RUN and no new router-side state was observed. This is the second intermittent SSH timeout after previous successful Ethernet-onlink IPv4 192.168.1.223, ICMP 3/3 and TCP22/443 port reachability and later authenticated SSH run. Do not infer whether Ethernet or HTTPS is presently functioning; assess them contemporaneously. Do not kill netifd, reset router or flash on only unit. Next action: read-only Windows-side time-bounded, timestamped comparison of Ethernet link, local route, ICMP, TCP22 and TCP443 to distinguish path failure vs SSH-specific outage; then decide next physical UAT step. No automatic retries of Wi-Fi activation.

## 2026-11-24 13:45 WIB: three Windows-side connectivity snapshots recover

Owner executed three consecutive Windows PowerShell read-only network snapshots at 13:45:26, 13:45:31, 13:45:36 local Jakarta time. Ethernet interface remained UP at 100 Mbps, Windows IPv4 192.168.1.223; each snapshot reported ICMP Ping=True, TCP22=OPEN, TCP443=OPEN to WE5927 router 192.168.1.1. This demonstrates LAN reachability and TCP listeners at those three instants; it does not independently verify successful SSH authentication/command execution or ongoing LTE Internet availability. Previous authenticated read-only SSH session succeeded before two intermittent port-22 connection timeouts. Do not treat current port OPEN as permanent SSH stability proof. User can first check a single SSH authenticated harmless echo, then run the already downloaded SHA-pinned netifd/LTE read-only triage once if the shell login succeeds. Never repeat Wi-Fi enable, reboot, kill netifd or flash while root cause remains unverified.

## Another SSH timeout during conditional login, owner next update (24 November 2026)

User verified locally cached 4037-byte netifd LTE read-only diagnostic SHA-256, then SSH_LOGIN_OK preflight to root@192.168.1.1 TCP22 with ConnectTimeout=8 timed out BEFORE authentication. Subsequent pipeline of the same read-only script also timed out, AUDIT_SSH_EXIT=255. Therefore the diagnostic was NOT executed and there are NO new physical router observations. Even with a PowerShell throw, running subsequent interactively pasted lines separately does not halt a later user command; future handoffs should provide one cohesive guarded block, no retry when handshake fails.

Key causal hypothesis updated using an independently inspected OpenWrt netifd ubus.c source: earlier assistant-generated inline Windows SSH diagnostic command suffered shell quoting of grep -Ei expressions with pipes, accidentally RUNNING the executable netifd in a pipeline. Output then showed Failed to publish object network, network.device and network.interface. Later physical read-only snapshot reported THREE netifd PIDs (the prior pre-fault count was one). This is consistent with inadvertently launched extra netifd instances colliding on the UBus registry, and is a potentially assistant-induced problem. Nevertheless it is NOT PROVEN the three PIDs are independent persistent daemons or that this is the cause of later SSH timeout or DHCP permission denied; process identity and procd canonical PID must be verified. OpenWrt reported similar notify_proto action=1 errors in official issue #18105, so do not overstate a single root cause.

Next safe diagnostic should correlate Ethernet IP/link, ICMP, TCP22 and TCP443 IN THE SAME TIME WINDOW as connection failure, locally on Windows (no new router executable). If SSH becomes authenticated, collect canonical procd network instance PID through ubus service list (read-only) and /proc statuses, compare to all netifd PIDs, and collect LTE egress exit codes. Never kill network daemons based merely on PID count, do not trigger reboot/network reload/WiFi up on owner's only router. Prior code's login throw does not prevent separately pasted command blocks; future instructions must prevent this misunderstanding.

## Owner 2026-11-24 13:56:31–13:56:57 WIB Windows 8-probe router availability

User tested Windows 192.168.1.223 to physical WE5927 192.168.1.1 eight sequential time-stamped samples over approximately 26 seconds: every sample Ping=True, TCP22=OPEN, TCP443=OPEN and HTTPS GET / HTTP 200 with curl -k. So router local LAN path, local TCP22 and HTTPS listener/web-server responses were functional throughout this sampled interval. It does NOT prove SSH authentication or application-level SSH handshake, no LTE-bound Internet was tested, and old three netifd PIDs / failed notify_proto remain unresolved. Prior SSH connection timeouts were observed at other moments and may be intermittent, or there may be a client-SSH-specific problem; avoid claiming persistent TCP reachability failure. Next targeted local diagnostic: a single TCP22 SSH identification banner read with short timeout and SSH verbose client logging, correlated to the same clock sample, then only-if-success run already pinned SHA256 netifd/LTE read-only script. No additional router changes.
