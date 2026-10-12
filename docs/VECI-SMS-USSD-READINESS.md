# VeCI SMS / USSD — read-only device capability phase

Date: 2026-10-12. Status: **development-only source and CI**, **physical UAT not executed**, **production flash NO_GO**.

## Purpose

VeCI General and VeCI Indonesia share one modem communication interface. The WE5927 / W907 path can issue non-mutating 3GPP AT capability tests on demand. This **does NOT implement an SMS inbox, send SMS, operator OTP intercept, or an executable USSD session**. Those require separate design, approval and physical modem UAT.

- RPCD method: `veci.cellular messagingCapabilities`, read ACL only; no writable SMS/USSD RPC names.
- On-demand VeCI Cellular button: **Check modem capabilities**; never called by ordinary dashboard polling.
- Probe helper `veci-modem-capabilities`, BusyBox POSIX shell; no Python, Node, cloud service or per-operator daemon.
- Exactly four allowlisted AT **test** commands: `AT+CMGF=?`, `AT+CPMS=?`, `AT+CNMI=?`, `AT+CUSD=?`.
- Select USB serial interface 1.4 via sysfs, fall back to one configured ttyUSB AT port, explicitly avoid the problematic W907 interface 1.5 / ttyUSB3.
- Serialize **all** queries under `/var/lock/we5927-at.lock`, matching the existing LTE watchdog/IMEI process. Fail immediately when busy; never probe ports iteratively.
- Never return or log raw AT output; return only `supported`, `rejected`, `unknown`, `unavailable`, or `not_tested` for the individual capability. `ERROR` means the modem rejected the command, not definitive hardware incompatibility.
- Capability test success does NOT guarantee network-side USSD availability, authorized SMS forwarding, SIM support, or a working inbox.

## Build pipeline integrity finding

The existing OpenWrt board patch stages a bootstrap `package/we5927-lte`. The canonical maintained LTE source lives in `source/we5927-lte`, and it previously contained a broken, duplicated shell block. The malformed portion was repaired in the development tree (one unique function per operation, complete read-only IMEI helper, one dispatcher). The build staging script `scripts/prepare-veci.sh` now **replaces** the patch's LTE package with the syntax-checked canonical source. CI compares the staged files in both General and Indonesia profiles. Both builds must use the same corrected modem manager and read-only SMS/USSD helper.

## UAT matrix, ALL NOT TESTED on physical router

1. Before any AT request, verify wired recovery access, backup, SIM presence and correct USB interface mapping using read-only sysfs commands.
2. Explicitly click "Check modem capabilities" on an authorized test WE5927; check AT lock contention with watchdog and IMEI read.
3. Test modem absent, non-AT serial device, modem busy, timeout, `ERROR`, incomplete `OK`, and partial split serial responses. No unsafe ttyUSB3 auto-probe.
4. Compare `AT+CMGF=? / CPMS=? / CNMI=? / CUSD=?` responses to manufacturer's capability documentation. Never declare SMS or USSD transaction success on a capability test alone.
5. Benchmark CPU, RSS, overlay use, serial timeout and impact on RNDIS internet; verify no AT raw text, IMEI, MSISDN, ICCID, OTP or messages persist in browser/server logs.
6. Future SMS send/read and USSD execute require separate **explicit administrator action**, ACL write separation, masking/privacy controls, a transaction-aware serial transport and physical UAT. No automatic reading/forwarding of OTP without informed consent.
7. Update firmware only after rebuilt J9/J9B verification, all five Router Apps and updater physical UAT, recovery drills and explicit owner authorization of exact image/device.

## Evidence

- `tests/test_veci_modem_sms_ussd.py`: mocked serial AT protocol responses, lock contention, strict allowlist, ACL and source syntax checks.
- `.github/workflows/veci-modem-diagnostics-ci.yml`: offline regression + staging comparison in both firmware editions.
- `veci/js/pages/cellular.js` in a pinned VeCI Core after its quality CI has passed.

**No router has been contacted, flashed, rebooted or reconfigured during this stage.**
