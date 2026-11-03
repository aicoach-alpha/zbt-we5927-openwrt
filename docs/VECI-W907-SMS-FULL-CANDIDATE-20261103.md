# VeCI W907 Full SMS feature candidate — NOT YET LIVE

Router OpenWrt 25.12.5, firmware d0d4800, currently live read-only Inbox.
User requires Compose/Send, Delete, Sent History and Drafts as full features.

Candidate combines authenticated veci.sms methods:
- Inbox reading on demand (no automatic SMS polling).
- Send after explicit per-message confirmation. Native CMGS worker validates
  one SMS-SUBMIT PDU, waits for prompt, sends Ctrl-Z, verifies modem ACK.
  Unknown outcome is NOT automatically retried.
- Delete only exact matching PDU at selected slot, no bulk deletion.
- Local Drafts up to 10 and Sent records up to 30, private root-only storage.
- Four-part GSM7/UCS2 user-confirmed multipart submission is UI-managed.

The new worker must use W907 USB function 1.4 and the existing exclusive
AT lock without restarting LTE, Wi-Fi or RNDIS.
This is source staging, NOT a production install. Live send/delete tests
require explicit operator-confirmed real hardware UAT.
Storage selection must be verified; do not guess SIM or ME.
Previous removed UI actions were not the desired final scope.
