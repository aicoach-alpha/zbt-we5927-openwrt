# XLSMART/XL verified subscriber-quota integration contract

**Project:** VeCI Indonesia (ZBT-WE5927, native C/OpenWrt, local only).
**Checkpoint:** 2026-10-15. **Status:** operator authorization NOT established; this file is the integration gate, not a grant or a claim that quota is LIVE.

## Evidence / non-evidence

- Official XL myXL FAQ confirms subscriber quota display and manual number + OTP login. Source: https://www.xl.co.id/bantuan/digital-services/our-apps/aplikasi-myxl-terbaru-bisa-digunakan-di-android-dan-ios
- Official XL guide confirms subscriber can check via myXL or *808#: https://www.xl.co.id/blog/cek-paket-internet-xl
- The 20 Sep 2025 Telco API Alliance announcement names six solutions (Active Inactive, Mobile Number Verification, SIM Swap, Device Location, Recycle Number, Scam Signal), none a direct subscriber-remaining-quota API. Source: https://www.telkomsel.com/about-us/news/telkomsel-ioh-dan-xlsmart-jalankan-inisatif-bersama-telco-api-alliance-untuk
- XLSMART Business Digital Rewards/Bulk Data mentions *distribution/injection of packages by API*, which is different from a customer-owned SIM's remaining balance: https://www.xlsmart.co.id/bisnis/solutions/digital-rewards-and-bulk-data/
- Absence of an API from these official pages is NOT proof that no partner quota API exists. Supported access terms, registration and endpoint must be independently established. Community projects using internal myXL endpoints do not prove official third-party permission.

## Operator integration information required before enabling account login

1. Written/documented support for **READ-ONLY subscriber quota and package validity** of an end user's own XL SIM, including prepaid/Go Izi/Prioritas distinctions, or a permitted official delegated-account flow.
2. Authorized client registration, provisioning and credential ownership; allowed grant/login method (e.g. interactive OTP or delegated login), consent rules, renewal and revocation. Never embed a mobile app's private shared signing key in public firmware.
3. The exact authenticated HTTPS base URL/endpoint, TLS rules, JSON response schema, documented unit for each DATA bucket, validity timestamps, and explicit distinction between unlimited/special/general/local quota buckets.
4. Limits and acceptable-use terms for frequent refresh, per-SIM concurrency, anti-abuse measures, and whether a local OpenWrt Linux device is an authorized client.
5. Explicit confirmation that checking quota produces no payment, purchase, activation, unsubscribe, or other side effects.

## Runtime go/no-go

- Physical static prereqs already CLOSED: verified XL-host HTTPS identity (HTTP 404 from HEAD / does NOT test quota), compact MIPS loader, SHA256, AES encrypt/decrypt, DATA parser all PASS on WE5927.
- Existing compact release: https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/tag/veci-xl-runtime-compact-24653c5bc779
- Authentication remains unimplemented: no account session ever entered; real carrier quota unverified.
- Any newly issued secret/token stays ONLY on the local router under a restrictive root-owned runtime session; never passed as a CLI argument, shell history, logs, GitHub, ChatGPT, external AI, or developer server.
- No SMS inbox scan or auto-read to locate quota OTP. A +CMTI modem notification reveals only storage slot, not message purpose; selecting a specific OTP from the inbox by blindly reading could consume banking OTP. Manual OTP entry may only be implemented inside a verified official, user-authorized login flow.
- Signed TLS session alone is insufficient: the canonical response must bind to the intended SIM/account, be accepted by a real operator authorization protocol, have a proven unit, and contain positive bounded totals without contradictory expiry.
- Until ALL checks pass, `veci-xl-quota-chain` returns `parsed_only`, and no producer may write `source=carrier_authenticated` to the cache. UI must show a neutral unavailable/auth-required state, never synthetic numbers.
- Only after operator auth and response validation may a strict root-only cache writer + LuCI status be enabled. Deploy in a rollbackable optional package; never modify SMS Center v1.6.0 or LTE services.

## Minimal operator access inquiry (technical scope)

Please confirm whether XLSMART offers an approved, consumer-consented API or official delegated authentication flow that can read a subscriber's *own* XL mobile-data package remaining quota, total quota, and expiry from a small on-premises OpenWrt router. We need read-only scope, supported client registration and consent, official documentation, rate limits, unit/schema details, and whether prepaid/Go Izi/Prioritas accounts are supported. No billing, payment, package provisioning or SMS OTP reading is required.

**Release decision:** RUNTIME_PHYSICAL_PASS; AUTH_NOT_VERIFIED; QUOTA_NOT_VERIFIED; PRODUCTION_QUOTA_NOT_LIVE.
