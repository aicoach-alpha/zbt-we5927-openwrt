# WE5927 VeCI v2 — OEM factory baseline and release requirements (2026-11-25)

The owner is currently reverting their SOLE ZBT-WE5927-2SIM router to factory firmware for stability. No physical SSH, UCI, modem, SIM, network, firmware write, reboot or automated flashing actions may be undertaken during developer work on andre-nas/GitHub.

## Separate previously observed failure modes

1. Non-procd netifd duplicate, physical recovery: procd PID 1366, extra PID 16862; after guarded SIGTERM to extra instance and one LTE-only down/up, usb0 IPv4/default route were present and external HTTPS direct IP HTTP301 exit0 + DNS HTTPS HTTP200 exit0. One UAT snapshot, not 72h stability.
2. Modem local web HTTP200 at 192.168.7.1 and RNDIS usb0 IPv4/default route did not prove public Internet; the owner later clarified SIM data quota was exhausted and refilled. Follow-up public HTTP 301 and SNI-pinned HTTPS 200 exit0. Never assume DNS, LTE hardware or netifd failed solely based on the quota incident.
3. Router had no timeout binary, so three nslookup tests failed before execution (exit127), not proof of DNS outage.
4. On curl HTTP status 000, backend JSON must use numeric 0, not invalid JSON 000. Simulations cover public success, DNS/endpoint failure, modem local success/public failure, modem and public unavailable, missing usb0.
5. The modem-connected but public-unavailable GUI now recommends checking data quota/operator only as a possibility, not a claimed quota balance API; no watchdog reset or modem power-cycle from a read-only probe.

## Exact release gates (must not bypass)

- 39/39 active modules source-verified with executed test receipts. Permanently retired USSD absent. No false PASS.
- Exactly one procd-managed netifd; recovery blocks duplicate/unowned instances and never auto-kills network processes.
- Four main GUI menus and nested pages, truthful live RX/TX and memory chart, working LTE/SMS/security controls with hardware UAT still required.
- Firmware image compiled from final commit, correct ABI, 53 mapped ROM paths, no LuCI/USSD, flash-partition sizing, correct board and sysupgrade metadata, SHA256, cryptographic signer, embedded trust and invalid-signature rejection.
- IMPORTANT stock/OEM-to-VeCI compatibility: do NOT assume factory firmware accepts OpenWrt sysupgrade image via vendor UI, or has identical trust key, partition map, bootloader, or recovery tools. Verify factory image path and OEM platform with read-only checks after owner approval. If incompatible or unknown, status DO NOT FLASH.
- CI cannot deploy the router. Owner-device sysupgrade -T and trust key verification require specific consent, and do not themselves prove 72-hour stability after flashing. Config backup is not a full MTD/bootloader rescue copy.
- Previous signed build a187353e (5,899,090 B SHA256 940544001b83fc137bc9b8cc79935e3dd2906cfa99d1c9417559c1d87ab47568) predates peer DNS and quota diagnostics revisions, so never relabel or distribute it as the latest fixed firmware.

Stock firmware remains the stable fallback while all final firmware changes are built, verified and signed. Do not claim fully READY FLASH until the exact OEM-to-custom upgrade route has been verified.
