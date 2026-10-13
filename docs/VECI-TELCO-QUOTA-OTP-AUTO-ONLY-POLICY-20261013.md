# Decision: automatic SMS OTP handling is EXCLUSIVELY for telecom quota-app login

Date: 2026-10-13. User requirement: **Only OTP used to log into official mobile-operator applications for checking data quota may be automatically read on the router. ALL OTHER OTP MUST NOT BE AUTOMATICALLY READ.**

## Scope is exact, not a generic SMS OTP reader

- **Allow**: one SMS OTP that is strictly part of an active, user-authorized, official mobile operator **data-quota check login**. Providers pre-enumerated in development: XL, AXIS, Telkomsel, by.U, Indosat, Tri and Smartfren. Adding other Indonesian carriers requires a separate verified integration; do not infer the sender from a commercial-looking name.
- **Deny**: bank/credit card, payment, e-wallet, email, social media, shopping, enterprise login, government, recovery/2FA of other accounts, purchases/transactions, even if delivered through a telecom SIM; any phone number not tied to the active quota login; OTP for other purposes inside a telco application (payment or account changes).
- **Deny**: operator SMS outside an active quota-login attempt, expired login, SIM/provider mismatch, unmatched/changed session or modem generation, unapproved provider integration or independently unverified sender/candidate.
- OTP must never be relayed to user NAS or a centralized companion server. If supported under operator rules, use only for the corresponding *official operator login flow* on the router. Never print, log, archive, cache, forward to cloud LLMs, store in browser history or generic diagnostic RPCs. Explicit opt-in to quota sync is required.

## Critical protocol constraint — no blind classification

The W907 modem's standards-based `+CMTI: <mem>,<index>` SMS notification **only tells the slot**, not the sender, category or contents. 3GPP TS 27.005 section 3.4.1:
https://itecspec.com/3gpp/27.005/s/3.4.1

Trying `AT+CMGR` on every new SMS to distinguish a carrier OTP from a bank OTP WOULD ALREADY BE AUTOMATICALLY READING THE BANK OTP. This violates the user's requirement. Even `AT+CMGL` for routine index scanning can touch all SMS and alter unread flags. Direct `+CMT` unsolicited routing sends the PDU for all messages; it is NOT an acceptable workaround because it would also expose non-operator OTP.

An SMS sender ID/phone number is potentially spoofable; mere presence on an allowlist must never be considered proof of an official operator OTP. A secure, independently provider-attested **pre-read classification channel** would be required before auto `CMGR` could be approved. None is known/proven on this physical W907/OpenWrt installation. **Consequently, automatic SMS OTP reading remains DISABLED/NO-GO until such a channel is proven.**

If the operator exposes an authorized OTP-free quota API/login mechanism, prefer that path instead. Otherwise ask the owner to manually retrieve and enter the operator OTP for quota checking, without automatically opening any unrelated SMS. Do not claim this is full automation.

## Source-only policy implementation

`source/we5927-lte/src/veci-telco-quota-otp-policy.[ch]` implements a small fail-closed, single-candidate C gate, disconnected from firmware. It requires:

1. Exactly `VECI_TELCO_PURPOSE_QUOTA_APP_LOGIN`, recognized provider ID, official login flow independently verified, user-authorized quota sync, SIM/operator match, approved provider integration, bound quota-login transaction and modem generation, finite <=120 second monotonic TTL.
2. **Before reading any SMS**, caller must supply independently attested carrier candidate identity and binding to the specific active operator login challenge. These MUST originate from a trusted provider/transport bridge, not an arbitrary browser boolean, SMS sender string or decoded SMS body.
3. It allows exactly one candidate slot and consumes the attempt whether accepted or rejected; no scan of other inbox slots. Wrong provider, wrong purpose, stale session/generation, expired or unverified candidate always deny. Success does not read or decode messages, and no production caller supplies those trusted inputs yet.
4. Current root exec plugin cannot inherently bind a browser-supplied identity to the authenticated rpcd session, as documented in `docs/VECI-SMS-READSLOT-AUTHORIZATION-ADR-20261013.md`. Do not wire this gate to the existing general SMS metadata RPC.

## Testing

- 20 host-only tests include seven enumerated providers, **bank/e-wallet/email/other automatic OTP deny**, bare `+CMTI` deny, spoofable sender not sufficient, no quota login deny, mismatched SIM/provider, expired window, replay, hotplug generation, no modem side effects.
- **460/460 offline PASS** https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38343103424, including `INERT_BUILD_GUARD_PASS`; source-only policy is not linked into firmware.

## Release state

- SMS Storage and explicitly clicked SMS Inbox metadata v1.3.1: **LIVE/PASS** on user's real WE5927.
- **Automatic telco quota-login OTP**: **NOT LIVE; blocked for now by lack of trustworthy pre-read classification and validated operator login integration**.
- Automatic reading of all other OTP: **DENIED BY POLICY; MUST REMAIN DISABLED**.
- Actual SMS content/OTP generic view and XL USSD remain NOT LIVE. No physical router changes, no new daemons, no silent polling or auto-login performed.
