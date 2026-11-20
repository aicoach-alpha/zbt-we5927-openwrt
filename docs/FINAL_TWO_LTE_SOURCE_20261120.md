PIN PUK and USSD source-only reuse from original VeCI, 20 November 2026.
Independent branches:
- d3b9cae PIN/PUK provider + UI from old commit aa1b0b8; PTY integration on fake modem passed.
- 377709b USSD provider + UI from old commit 331ebf7; delayed +CUSD PTY, cancel/timeout pass.
- Shared C transport uses byte-exact old revision 331ebf7 that includes prior PIN/PUK mode and USSD. One AT helper; no duplicate modem daemon.
- Existing LTE policy ACL and permissions preserved. This means all 27 have at least source-code presence, not 27/27 source verification.
- Physical hardware tests NOT RUN; owner has one router. Build is forbidden until 40 core source evidence verified.
