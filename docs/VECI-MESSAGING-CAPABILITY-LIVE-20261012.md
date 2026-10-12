# VeCI WE5927 — Capability Diagnostics LIVE / PASS

Date: 12 October 2026 (Asia/Jakarta). Owner-executed deployment and
read-only modem capability UAT using **office Windows laptop** SSH to
**WE5927 at 192.168.1.1**. This is a direct transcript supplied by the
operator, not a CI-run hardware test. Do not confuse private IP
192.168.1.1 with the unrelated ZTE device reachable from andre-nas.

## Scope of this PASS

**LIVE/PASS: explicitly invoked modem messaging *capability checks only*.**
**NOT LIVE: SMS inbox, SMS send/delete, actual USSD sessions, XL quota.**

Pre-deployment installed veci.cellular UBUS methods: status,
reconnect, switchSim(String). No messagingCapabilities endpoint, helper
missing, ACL old. Physical router identity from prior read-only evidence:
zbtlink,zbt-we5927, OpenWrt 25.12.5/kernel 6.12.94, USB VID:PID
05c6:902e, verified AT interface ttyUSB2 USB 1.4; never probe ttyUSB3.

Operator ran pinned overlay installer from commit
737fe54ac91377dfeb65c00b4d450046f043b1ce:
- Download 7623-byte scripts/veci-live-capability-hotfix.sh to /tmp.
- Shell syntax check succeeded.
- Install returned LIVE_RPC_REGISTRATION_PASS.
- Install returned NO_AT_COMMAND_SENT_BY_INSTALLER.
- Persistent rollback directory:
  /root/veci-capability-hotfix-rollback.
- After bounded rpcd restart, confirmed the method list:
  status: {}; messagingCapabilities: {}; reconnect: {};
  switchSim: {sim:String}.
- /overlay 2.1M total, 352K used, 1.7M available (17% used).
  No firmware flashing or reboot was performed.

Operator explicitly invoked:
    ubus call veci.cellular messagingCapabilities

Observed response:
    {"ok":true,"state":"probed","source":"read_only_at_test",
     "sms_mode":"supported","sms_storage":"supported",
     "sms_notifications":"supported","ussd":"supported"}

These indicators mean the modem accepted four 3GPP AT **test**
commands: AT+CMGF=?, AT+CPMS=?, AT+CNMI=?, AT+CUSD=?.
They DO NOT prove any inbox retrieval, ability to send SMS,
USSD network-session execution, operator data balance, or SMS privacy.

## Gates, follow-up

- LIVE PASS applies only to the capability RPC and supporting minimal
  overlay hotfix (not the whole SMS/USSD draft PR).
- Maintain the known-working installed helper at its immutable pin
  until a separate next-phase package is tested; do not blindly overwrite
  the RPC or change SIM/LTE/network config.
- Incremental future SMS storage **counts** may use AT+CPMS? on
  explicit user request with the shared modem session lock; do not
  return SMS text, sender numbers, OTP, or raw AT bytes.
- SMS inbox/PDU decoding, UI permissions, USSD interactive state,
  carrier quota parsing, and real modem UAT remain NOT_TESTED.
- Full image release, updater recovery, power-cycle, and complete
  physical hardware UAT remain NO_GO.
- Existing rollback directory must not be overwritten by any subsequent
  hotfix. To restore original files, use the previously downloaded
  installer with the rollback subcommand from an authorized router SSH.

Evidence designation: **OPERATOR-OBSERVED PHYSICAL UAT**, specifically
the command and response above; no automatic unapproved modem activity.
