# GitHub operator app research — myXL, AXISNET, Telkomsel, IM3, Tri

**Date:** 2026-10-16  
**Objective:** Publicly distributable VeCI native router firmware for WE5927, with genuine authenticated operator **remaining quota** separated from local traffic meter and manual quota estimates. Do not modify LuCI, VeCI Core, LTE, or working SMS. Stop USSD work as requested.

## Primary finding: BITS-XL

Repository: https://github.com/Banten-IT-Solutions/BITS-XL (MIT for repository code, not a license to use XL's private services or mobile-app credentials).

Observed in `bitsxl/root/usr/bin/bitsxl` and README:
- LuCI OpenWrt application powered by Python 3, `pycryptodome`, rpcd ACL, and UCI.
- myXL login starts by sending an SMS OTP through XL CIAM, then exchanges OTP for account-scoped tokens.
- Account identity/profile is resolved through `api/v8/profile`.
- Read-only quota is requested through `api/v8/packages/quota-details`.
- Account refresh-token handling, a token cache, and failed-auth recovery are implemented.
- Cryptographic request processing includes AES-CBC, HMAC signing and client-identification fields.
- Scope includes purchasing and payment; VeCI quota module must **not** inherit those operations.
- A bundled UCI configuration includes application authentication material. Those embedded values are NOT authorized credentials for publication in independent router firmware. Do not include or echo values into logs.

**What can be reused architecturally:** read-only data shape, OTP state machine, profile matching, retry only after authorized refresh, strict quota normalization, cache expiry and error states, permission separation. Implement VeCI-native using already-built mbedTLS code, not LuCI/Python or imported app secrets.

**Blocker:** no documented, authorized public myXL API/client registration for third-party firmware was found in the reviewed repository. The presence of a private endpoint or working GitHub example does not grant permission to reuse its credentials.

## Other relevant repositories

| GitHub repository | Observed capability | VeCI suitability |
| --- | --- | --- |
| https://github.com/Banday-Wrt/myxl-cli | myXL quota endpoint in `my_package.py`, OTP/session helpers, requires externally supplied API key | Illustrates account flow; API key dependency prevents universal firmware use |
| https://github.com/rizkirmdhnnn/myxllite | Old OpenWrt-style XL FUP/quota display; repository description says API probably dead | Historical only, not reliable backend |
| https://github.com/ipkzone/axisnet | AXISNET login/token CLI; README requires license key and restricts concurrent logins | User-facing authentication concept; not a free native dependency |
| https://github.com/0xtbug/telbot | Go client for Telkomsel OTP login, session caching, quota/profile; also supports payments | Good reference for provider adapters with user consent; exclude payment/auto-buy |
| https://github.com/ipkzone/myIM3 | Community myIM3 API exploration | Research candidate only; endpoint, authentication, license must be independently verified |
| https://github.com/scripthon/bima-tri-api | Tri OTP login and account profile REST wrapper | Research candidate; no demonstrated operator quota correctness |
| https://github.com/rozy97/myxl-backend | Node/MongoDB clone backend, synthetic app database | NOT a genuine XL operator balance API |

## Existing VeCI implementation gap

- XL Native 0.3.7 has optional `veci.xl` OTP/profile/normalizer/HTTPS transport; physical status shows `operator_configured=false`, `quota_status=not_authenticated`.
- `veci.quota.status` accepts only authentic, recent cache `source=carrier_authenticated`, never unverified fake balances.
- `veci-data-meter` separately measures `usb0` and optional manually anchored estimate; must **never** render as the carrier balance.
- Do not use USSD or SMS for outbound quota verification; SMS remains working independently.
- The WE5927 overlay has limited free flash; adding Python and pycryptodome from BITS-XL is not a suitable required dependency.

## Proposed publisher-safe integration contract

1. Provider adapter has capability `read_quota`, `request_otp`, `submit_otp`, `refresh_session`, `disconnect`; no purchase, store, payment, or unrelated subscriber control.
2. Application credentials are provisioned only through a documented, authorized provider or user-consent mechanism — never copied from embedded mobile app keys.
3. Mandatory profile/MSISDN identity verification before read_quota. No logging of OTP, access/refresh tokens, mobile number, or operator response bodies.
4. Cryptographically authenticated transport; fail closed on missing or expired credentials, absent quota buckets/units, identity mismatch and HTTP errors.
5. Read-only normalized quota data includes operator, last verified time, total/remaining, per-bucket expiration, and provenance. Never substitute router RX/TX for operator remaining quota.
6. Small native/OpenWrt-compatible implementation, opt-in manual quota refresh, bounded rate, per-user credential isolation, no cloud relay imposed by VeCI.
7. Real carrier UAT is mandatory to claim auto quota LIVE. **Not achieved yet**.

## Verifiability

Research examined repository files and advertised behavior, **not** live account login or real operator endpoint responses. No OTP was sent and no operator credentials were captured. No guarantee that undocumented endpoints remain working in production.

References:
- https://github.com/Banten-IT-Solutions/BITS-XL/blob/main/README.md
- https://github.com/Banten-IT-Solutions/BITS-XL/blob/main/bitsxl/root/usr/bin/bitsxl
- https://github.com/Banday-Wrt/myxl-cli/blob/main/my_package.py
- https://github.com/0xtbug/telbot/blob/main/README.md
