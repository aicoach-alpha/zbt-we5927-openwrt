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


## Native serial transport hardening for eventual SMS/USSD

Development has hardened `source/we5927-lte/src/we5927-at.c` without enabling message transactions. It now:

- Recognizes complete terminal `OK`, `ERROR`, `NO CARRIER`, `+CMS ERROR` and `+CME ERROR` **across arbitrarily fragmented serial reads**, rather than searching each read fragment separately.
- Enforces an 8 KiB maximum response and 1024-byte maximum logical line, bounds the timeout to 100–30,000 ms, handles short UART writes, and rejects AT commands containing embedded control characters or line breaks.
- Uses 64-bit monotonic milliseconds for reliable timeouts even after many weeks of uptime on 32-bit MIPS.
- Reuses the original shared nonblocking AT lock from the LTE manager; it introduces no daemon, Python/Node runtime, or remote endpoint.
- Adds `tests/test_we5927_at_transport.py`: 11 native host-C/PTTY regressions covering split OK/error, incomplete OK, false terminal substring, long responses, timeout, invalid commands, legacy LTE status and simulated carrier errors. CI now executes these beside nine mocked diagnostics tests.

**Critical protocol distinction:** a generic one-shot AT transaction is still **not** sufficient for SMS inbox/send or interactive USSD. Text-mode SMS content may itself contain a line `OK`, and network-initiated USSD `+CUSD` responses may arrive asynchronously *after* command acknowledgement. Before enabling those operations, implement a session-aware parser (prefer SMS PDU for framing), unsolicited-response handling, strict message privacy/OTP consent and a separate privileged ubus write ACL. Never expose raw modem transcripts to the ordinary dashboard. Physical UAT must verify exact USB interface, APDU capability, message character set/encoding, operator-side USSD availability and race-free coordination with status polling.


## Inert PDU-mode SMS / deferred USSD framing (follow-up development)

The development branch includes a NEW **host-tested, inactive** parser,
source/we5927-lte/src/veci-at-framing.c, gated by
tests/test_veci_at_framing.py. This is not built into any existing router
image or exposed through ubus. A passing test here must **not** be presented
as SMS inbox/send or live USSD support.

- Incremental AT-line parser with 1024-byte line / 8192-byte response bounds,
  explicit EOF handling and failure-closed malformed frames.
- SMS PDU-mode +CMGL, +CMGR, +CMT, +CDS recognize one matching hex PDU,
  validate SMSC octet length and the declared TPDU octet length. Text mode is
  intentionally rejected because SMS body text such as "OK" is ambiguous.
- +CMTI is only a notice; it never exposes, retrieves or stores an SMS.
- +CUSD mode is classified as an **asynchronous** indication. A preceding
  bare AT OK is only acknowledgement, not a finished USSD result.
  Interactive mode 1 requires later explicit user input; it never autoresponds.
- Session expiry must be driven by a future caller using a monotonic deadline.
  The helper marks expired state as failed, never automatically retries.
- The parser does no modem I/O, no network I/O, no logging, no storage, no
  credential access and has no background process.

**Next integration safety gates (not implemented):** one process must hold
/var/lock/we5927-at.lock continuously from command dispatch through the
final asynchronous notification or deadline, including all SMS prompt/PDU
phases. A command-by-command flock is insufficient for interactive USSD and
AT+CMGS transactions. The modem transport must route unsolicited events
without treating them as the command terminal, disable logging of any raw
message/PDU, enforce a small bounded operation queue, and never execute
SMS/USSD on page load. Add privileged ubus write ACLs and explicit
per-action UI consent only after mock integration and physical capability UAT.
Keep current read-only messagingCapabilities as the only exposed RPC method
until all of those gates pass.

**Release gate remains NO_GO**: source-only serial improvements are not proof of SMS/USSD support on a physical W907 modem, and the current live kernel/image has not been altered.

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
