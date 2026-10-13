# VeCI / WE5927 SMS Center — feature parity and releases (13 Oct 2026)

The owner physically verified SMS v1.5.1 UI: SMS feature ON, Open Inbox
successfully displays five actual XL operator SMS, including sender and
GSM7 message text. This is **real Inbox read LIVE**, not a simulated success.

## Incremental releases

- **v1.5.2 UI-only READY**: parse original 3GPP SMSC timestamp (SCTS)
  with signed quarter-hour timezone; display local received date/time;
  read/unread status; sort newest-first; reassemble 8-/16-bit UDH
  multipart segments only when complete, same sender/reference/count and
  within 48 hours. Do not invent missing timestamps. SHA-pinned rollback.
- **v1.5.3 READY for owner physical install, NOT YET LIVE**:
  identify selected SMS memory through `AT+CPMS?` (`SM` SIM, `ME`
  modem, `MT` combined/ambiguous); show it in Inbox. Support one-at-a-
  time deletion only in a *known selected* SM/ME storage, with a single
  explicit permanent-deletion confirmation. The admin WRITE-only
  `veci.sms.deleteMessage` handler requires persistent SMS feature ON,
  decimal slot 0..65535, expected memory, and exact PDU of the displayed
  message. Under the existing shared modem lock the worker validates
  physical USB identity, verifies current `AT+CPMS?` memory and PDU
  mode, re-reads `AT+CMGR=<slot>` and compares the full PDU to the
  expected one, then sends `AT+CMGD=<slot>,0` for only that message.
  A deleted multipart message invokes separately for each segment;
  there is **no bulk delete**. Anonymous access is denied. Modem
  is untouched during installation. The current user-selected SMS
  ON/OFF setting is preserved.
- **not yet implemented**: selecting/temporarily switching SMS memory
  between `SM` and `ME` with state restoration and UAT; deleting in
  ambiguous `MT`; reply/send SMS, Sent folder, delivery reports,
  drafts, search/filter and export. Do not present these as LIVE.

## Outgoing SMS transport gate

The existing `we5927-at` CLI is explicitly a single printable
`AT...\r` command and waits for terminal `OK`; it **cannot** carry a
two-stage `AT+CMGS` prompt, PDU plus Ctrl-Z transaction. Do not hack a
transmit feature using shell-embedded control characters or switch to text
mode without a robust transport. Implement one bounded modem transaction
worker using the same modem lock; validate recipient, GSM7/UCS2 encoding,
multipart and exact send confirmation; require one click (not repeated
overconfirmation); never log SMS/OTP or number; do not retry an uncertain
send automatically. Test the transport on a synthetic PTY first, then
release after targeted UAT without affecting LTE.

## Execution cadence

Feature implementation -> focused test -> SHA-pinned reversible deployment
-> physical LIVE functional check -> next feature. Do not claim the new
delete route LIVE from source or CI alone. Do not read real OTP/message
contents in logs or user-visible diagnostics.
