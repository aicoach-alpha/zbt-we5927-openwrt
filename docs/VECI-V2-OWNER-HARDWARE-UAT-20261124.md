# VeCI v2 · Owner field UAT and binding decisions · 2026-11-24

**Source of truth:** User's one physical ZBT-WE5927/WE2825-2SIM router with signed OpenWrt 25.12.6 VeCI v2. Hardware receipts override source-only test assertions. Neither this document nor source changes imply deployment to that live router.

## PASS evidence (physical)
- Signed image boot, LAN, router SSH, RNDIS USB0 DHCP 192.168.7.165/24 and gateway 192.168.7.1: PASS.
- Modem HTTP management reachable at gateway; modem reports XL LTE, PDP Connected and APN internet. Do not persist modem IMEI/ICCID or UI passwords from screenshot.
- Router bound USB0: public HTTP 301 exit 0, HTTPS 200 exit 0, DNS resolved: PASS.
- Windows Ethernet 192.168.1.223 / gateway 192.168.1.1, TCP 443 to 1.1.1.1 TRUE on Ethernet: PASS. Laptop simultaneously has another Wi-Fi gateway, so this does not certify all traffic through LTE.
- Actual Wi-Fi AP and 72-hour stability: NOT TESTED.

## Blocking owner product decisions, non-negotiable in subsequent builds
1. USSD = **OWNER HARDWARE UAT FAILED, PERMANENTLY RETIRED**. Delete production UI, JavaScript, rpcd handler, ACL grants, native USSD AT mode, build package artifact, active required-module and acceptance contract. Do not add back via reuse or third-party template. Keep this historical note to prevent resurrection.
2. SMS Center = **FAILED OWNER GUI UAT**. Screenshot shows indefinite checking and disabled controls; hardware send/receive/inbox/drafts not validated. Preserve SMS functionality as a requirement, but do not report success until runtime ubus, rpcd ACL, modem AT lock and hardware cases pass. Show precise failure state; never auto-send or resend.
3. GUI = **REJECTED BY OWNER**. Exactly four principal menus: Beranda, Koneksi, SMS Center, Pengaturan. Each includes intuitive secondary navigation. Provide clean responsive layout, readable metrics, charts from live kernel counters (no simulated values), and hide technical controls in advanced. Draw broad usability inspiration from GL.iNet, ASUS, Ubiquiti, MikroTik but do not copy their marks or proprietary assets.
4. Internet health must distinguish physical modem link, claimed PDP connection, on-router bound TCP/TLS/DNS verification, and wired/Wi-Fi client verification. Do not mark end-to-end online from DHCP IP alone.
5. Preserve stable router state. No flashing, modem reset, raw GPIO write, unproven APN edit, or repeated SIM switch during design/code work.

## Unresolved issues and engineering interpretation
- AT+CPIN? returned CME ERROR: SIM not inserted, but modem UI claims PDP Connected and AT+CGDCONT? shows CID1 internet. Contradiction: investigate AT versus modem UI status, no unsupported claim that SIM is physically absent.
- Owner confirms physical card in SIM1; software configured SIM1, gpio46 logical value=1 and active_low=1. DTS declares GPIO_ACTIVE_LOW; vendor baseline had default selector=1. Physical slot-to-level mapping has NOT been proven. Do not silently invert GPIO.
- GUI SIM2 always rolled back to SIM1. Router log confirms modem power cycle after GPIO=0, then 'Modem APN configuration failed', then selector restored GPIO=1. Source conflates APN programming failure with SIM switch failure. Fix error handling separately, retain rollback safety.
- SMS Center source tests do not certify real modem SMS operations. Ship no fake PASS.

## Acceptance criteria for new firmware
- USSD absent in image rootfs, Web UI, RPC ACL, native AT command and build requirements; intentional retired record retained.
- Correct hardware SMS functionality including status, read inbox, drafts, sent, single confirm-to-send and delivery-uncertain handling; prove on device, do not silently send SMS.
- Four main menus and working submenus, responsive accessible forms. Real internet status and byte-counter traffic chart, zero invented throughput.
- Wi-Fi beacon client + actual DNS/TCP internet path proven, LAN NAT proven, 72h stability from real owner flashed hardware.
- Signed build metadata, sysupgrade -T, exact-board checks, rollback evidence, CI regression gates. No release or PASS claim before evidence.

## Build accounting
The earlier contract contained 40 required core modules including USSD. Owner explicitly removed USSD: new active count 39, one intentionally retired. A future report must state '39 active + 1 retired', never '40/40 PASS' with the retired feature.
