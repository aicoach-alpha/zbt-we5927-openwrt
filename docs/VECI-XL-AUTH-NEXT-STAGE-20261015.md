# VeCI XL operator account integration — narrow next-stage checkpoint

Date: 2026-10-15  
Core LIVE: **VeCI 0.2.2** (do not reinstall or replace).  
Authenticated XL quota: **NOT CONNECTED / NOT IMPLEMENTED**.

## Official operator evidence
- XL's [official myXL page](https://www.xl.co.id/id/myxl) provides subscriber login and actual remaining-quota checks.
- [XL official help](https://www.xl.co.id/bantuan/digital-services/our-apps/aplikasi-myxl-terbaru-bisa-digunakan-di-android-dan-ios) documents number+OTP account login, including XL GO email OTP, but does NOT document a public third-party API contract for operator-authenticated remaining-quota readings.
- [Official XL quota advice](https://www.xl.co.id/blog/cek-kuota-xl-paling-mudah-ada-yang-baru-lewat-dial-number) documents myXL and *808#. The WE5927 XL USSD previously returned `network_rejected`. Do not automatically dial *808# or mark unverified text as quota.
- Public CAMARA Subscription Status relates to service activation/suspension; it is not evidence of an XL remaining-data quota API. No app-derived client identity or private mobile-app credential may be redistributed.

## Source-only VeCI integration work
- `scripts/veci-xl-account-guidance/myxl-guidance.js`: narrowly staged VeCI-only official-account handoff. Opens only `https://www.xl.co.id/id/myxl` in a separate tab with `noopener noreferrer` and no referrer, and explicitly warns the user that opening official myXL does not connect an account to the router.
- No SMS inspection, OTP requests, phone number input, cookies, embedded browser, session scraping, dynamic host discovery, or operator HTTP traffic. No LuCI page is added.
- The module is **not linked into production VeCI 0.2.2**. Do not modify its installed SHA-pinned panel or existing signed APK based solely on a guidance feature.
- `scripts/veci-xl-account-guidance/myxl-guidance.test.mjs`: focused behavior and no-credential/no-network checks only.
- [Focused GitHub CI PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38695285596). [VeCI-only policy gate PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38695285403).
- No broad firmware UAT or router command requested. No claim of authenticated carrier quota LIVE.

## Blocking prerequisite to genuine automatic quota
A permitted operator-issued integration method, credential and verified read-only self-care quota response (including subscription identity and units) must be available. An existing compact native TLS/crypto/parser pipeline is only a dormant candidate, not a proven operator-authorized client. Only upon real operator authorization may the local root-owned cache be fed with `source=carrier_authenticated`.

Until that prerequisite is met, continue to display `Not connected`, never fabricating data from interface counters, marketing offers, community-derived undocumented endpoints, or synthetic parser tests.

Scope preference: **VeCI native UI only; never develop new LuCI UI.** Development and physical commands must originate from the authorized office laptop, never andre-nas. Avoid repeating previously closed broad physical tests.
