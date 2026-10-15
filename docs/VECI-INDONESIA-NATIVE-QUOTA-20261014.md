# VeCI Indonesia Edition — native direct-operator quota, 2026-10-14

## Binding constraints
- Do not use USSD for scheduled quotas: physical XL SIM responded `network_rejected` to *808#.
- Standalone WE5927 router directly contacts operator HTTPS; no NAS, developer cloud or intermediary. No Python, Node, daemon or customer data sent to GitHub.
- Shared engine / registry / normalized cache with separate provider adapters: XL, AXIS, Smartfren, Telkomsel, by.U, Orbit, IM3, Tri. Grouping does not imply shared auth.
- Automatic SMS OTP reading stays disabled because pre-read sender classification on the W907 generic +CMTI indication is not independently verifiable. Only a user-entered OTP for an active, explicitly approved quota account login may be used until a safe attestation mechanism exists. No bank/e-wallet/other OTP.
- Do not infer quota from router traffic, offers, USSD menu text, or simulated operator results.

## External reference verified as community source, NOT proven current operator API
- Public MIT source https://github.com/Banten-IT-Solutions/BITS-XL 
- Candidate direct CIAM host: gede.ciam.xlaxiata.co.id; OTP /realms/xl-ciam/auth/otp, token /realms/xl-ciam/protocol/openid-connect/token.
- Candidate direct quota host: api.myxl.xlaxiata.co.id, quota route api/v8/packages/quota-details, profile api/v8/profile.
- Reference xdata AES-256-CBC, IV: ASCII first 16 chars of hex SHA256(xtime-ms); base64url ciphertext; HMAC-SHA512 signature over quota POST path/time.
- Reference is Python with PyCryptodome, unfit for WE5927. Never embed or publish scraped app credential, key, or device fingerprint. No MITM, SSL verification disable, or anti-bot bypass.
- XL official help confirms login OTP + quota display but does not publish private API contract: https://www.xl.co.id/en/bantuan/digital-services/our-apps/tentang-myxl

## Committed source-only
- source/veci-telco-indonesia/veci-xl-crypto.c: standalone C AES-256-CBC + HMAC-SHA512 via mbedTLS; optional root-only 0600 local secret/token files and stdin payload; no network or app keys embedded.
- source/veci-telco-xl-native/Makefile: optional OpenWrt MIPS package with libmbedtls21 dependency. Not added to existing firmware image.
- scripts/veci-telco-native-preflight-20261014.sh: read-only board/TLS-CA/crypto libraries/free memory and overlay; never touches modem, OTP or network.
- Existing source/veci-telco-indonesia: 8-brand provider registry and authenticated read-only quota cache (not live backend).
- Host CI verifies independent reference AES/PKCS7/base64url and HMAC test vectors, invalid input, oversized payload, and secret-file permission checks.

## Remaining physical go/no-go
1. Run read-only preflight on actual WE5927 from office laptop to confirm CA, TLS client, MIPS crypto availability and overlay space.
2. Cross-build and SHA-pin exact MIPS package; prove size/ABI on router without changing SMS/LTE.
3. Implement HTTPS host allowlist, certificate+hostname verification, bound responses, read-only profile/quota adapter and local-only login session. Keep client secrets outside public source and refuse if operator API flow differs.
4. Owner-approved manual MyXL OTP login, operator-authenticated quota and refresh verified physically, cache updated from authenticated response only.
5. Reversible atomic rollout and UI LIVE confirmation; independent adapters for other brands afterward.

Status: SMS v1.6.0 LIVE. USSD XL network rejected and excluded from automatic quota. Native myXL crypto AND DATA parser physically PASS on WE5927 (owner-provided output 2026-10-14), but no carrier API login/response yet.
## Physical validation — 2026-10-14
- Owner executed `scripts/veci-xl-native-mips-smoke-20261014.sh --verify` on `root@192.168.1.1` via SSH.
- Device printed `VECI_XL_NATIVE_QUOTA_DATA_PARSER=pass`, `VECI_XL_NATIVE_MIPS_SHA256=pass`, `VECI_XL_NATIVE_MIPS_HMAC=pass`, `VECI_XL_NATIVE_MIPS_AES=pass`, `VECI_XL_NATIVE_MIPS_EXECUTABLE=pass`.
- Device printed `VECI_REAL_OPERATOR_LOGIN=not_attempted`, `VECI_OPERATOR_QUOTA=not_verified`, `VECI_MODEM_AND_SMS_UNCHANGED=true`, `VECI_FLASH_WRITES=none`.
- Treat crypto and parser as a closed physical stage. Do not repeat that same test unless the binary changes.

## Next staged major feature — verified operator HTTPS (no authentication yet)
- New `source/veci-telco-indonesia/veci-xl-tls-probe.c` opens one TCP+TLS connection directly to one hardcoded candidate XL host (`api.myxl.xlaxiata.co.id` or `gede.ciam.xlaxiata.co.id`).
- Uses embedded mbedTLS native C, existing device CA bundle, `MBEDTLS_SSL_VERIFY_REQUIRED`, `mbedtls_ssl_set_hostname` and `mbedtls_ssl_get_verify_result`; no certificate bypass, credential, OTP, modem, SMS, or disk writes.
- Sends only `HEAD /`, reads first HTTP status line with bounded memory, never follows redirects. A 4xx response proves only transport identity, not operator API usability.
- Target build workflow: `.github/workflows/veci-xl-tls-mips-release.yml`. Stage as prerelease and perform one physical operator TLS test from `/tmp`, without installation into firmware.
- **Not yet tested on device; not an authenticated quota client.**
- Future quota client MUST keep authorization secrets out of argv, process listings, GitHub, logs, and developer servers; no API implementation may presume a community endpoint is still valid. Implement manual OTP only after account-owner consent and verified operator-compatible login, and authenticate + normalize a real quota response before any cache source can be set to `carrier_authenticated`.

## Hardware checkpoint and implementation update (2026-10-14)
- Owner's physical XL endpoint `HEAD /` over the SHA-pinned direct TLS probe: `VECI_XL_DIRECT_TLS=verified`, HTTP 404, MIPS SHA256 PASS, SMS/modem unchanged, no flash writes. HTTP 404 is normal for a root path without a handler; it is **NOT** carrier quota API success.
- The native `veci-xl-crypto.c` now supports `decrypt <xtime-ms> <root-only-key-file>` via stdin/stdout, with Base64 URL-safe decode, AES-CBC decrypt, PKCS7 rejection, bounded input and secret wiping. It remains an offline primitive; the caller has to authenticate the operator response and handle data privacy.
- New crypto host and MIPS CI **PASS**; SHA-pinned prerelease: `veci-xl-crypto-3bcd7b516148`, 95,496 bytes, SHA256 `6fb5f4ff793e576901f1e53e243be03f811265203d16eb4e9a40bf67bc35ad0b`.
- One new on-router RAM-only test for changed decrypt primitive: `scripts/veci-xl-decrypt-physical-20261014.sh --verify`. This intentionally does not repeat the previously PASS TLS, modem, SMS, HMAC or legacy encryption tests.
- Carrier account login/refresh and a verified authenticated quota HTTP response remain **NOT implemented/not LIVE**. Community candidate protocols are not official public integration contracts. Never copy upstream mobile application client secrets into public firmware; avoid requesting or printing real OTP/token in ChatGPT, shell history or CI logs. Only account-owner-authorized local secrets are acceptable.
- Final production design should directly use operator-verified HTTPS and allow only read-only profile/quota requests, with no purchase/payment side effects and no developer server dependency.

## Physical decrypt result and authenticated-transport candidate — 14 Oct 2026
- Owner's router executed the SHA-pinned decrypt-stage script from /tmp successfully:
  - VECI_XL_NATIVE_DECRYPT=pass
  - VECI_XL_NATIVE_ENCRYPT_DECRYPT_ROUNDTRIP=pass
  - VECI_XL_NATIVE_DECRYPT_QUOTA_PARSER=pass
  - VECI_XL_RELEASE_SHA256=pass
  - VECI_REAL_OPERATOR_LOGIN=not_attempted
  - VECI_OPERATOR_QUOTA=not_verified
  - VECI_MODEM_AND_SMS_UNCHANGED=true
  - VECI_FLASH_WRITES=none
- This CLOSED the earlier native AES decrypt/normalizer on-device stage. Do not re-run it unchanged.
- Implemented independent source/veci-telco-indonesia/veci-xl-quota-http.c native TLS quota-request transport, NOT enabled in the runtime image and NOT an auth client:
  - Fixed XL HTTPS hostname, fixed quota-only POST path, strict certificate+hostname verification and <=65536-byte JSON body.
  - Root-owned /tmp/veci-telco-private (0700), regular files 0600; protected file reads with O_NOFOLLOW and no symlink/hard-link acceptance. Access token, request signature, API key and encrypted request are NOT accepted via CLI args/environment and NOT printed.
  - Missing authorized user session fails before network; no OTP read, USSD, modem commands, purchases, cache mutation or developer intermediary.
  - Only successful 2xx JSON is passed to a local pipe/file; HTTP success alone is not carrier quota authentication. The final verification and cache-write gate must be downstream.
- GitHub release candidate veci-xl-quota-http-d9a5092fc6a4 is CI PASS and MIPS cross-built (545892 bytes; sha256 323cf58613fbd7fe9567e25e650392d147f0b919a5dfd4a9aea6c93387c4ae22). This prerelease has NOT been installed or run on physical router.
- Verified official operator help confirms myXL uses number + OTP and shows account package data; it DOES NOT document a supported third-party API contract. Public SinergiAPI information found lists other categories (SIM Swap, location, carrier billing), not self-care quota inquiry. Never assume community-derived app key or endpoints are operator-approved for redistribution.
- Blocker to genuine LIVE: implement and validate an account-owner-authorized first-party session/login flow, and verify an authenticated XL payload format + units on the SIM before allowing carrier_authenticated cache writes. Do not copy third-party app secrets into public source or present simulated quota as genuine.
- Protect SMS v1.6.0 and LTE; do not deploy unverified auth code into production.

## 2026-10-14 — direct quota pipeline checkpoint

- Physical MIPS native encrypt/decrypt/quota DATA parser and strict XL HTTPS `HEAD /` were reported PASS by owner. These are complete hardware prerequisites, not operator authentication.
- Added `source/veci-telco-indonesia/files/usr/libexec/veci-xl-quota-chain`: read-only standalone on-router pipeline (fixed verified-HTTPS candidate transport -> root-only temporary response envelope -> `jsonfilter` xdata/xtime -> native AES decryption -> native DATA parser).
- No cache writes, no LTE/modem/SMS/USSD changes, no OTP auto-reader, no external companion, no hardcoded app credentials and no request to any operator without existing authorized session material.
- Data returned by this pipeline is `parsed_only`, NOT `carrier_authenticated`; it is not sufficient to show real quota. Raw responses, encrypted/decrypted payloads and related files are kept within a root-owned temporary working directory, removed at exit.
- GitHub workflow `veci-xl-quota-chain-ci.yml` PASS (run 38552090933), with secret-leak and malformed-response regression fixtures.
- Hardened the native quota HTTPS POST body to require a canonical exact xdata/xtime request and matching signature time, rejecting arbitrary side-effect fields. Cross-compile and offline framing regression PASS (run 38552297100).
- Latest SHA-pinned native HTTP staging build: `veci-xl-quota-http-51e0070e6545`, SHA256 `c27cf4c19446ae311c6321df4f35b5d625f6553c800a5a1fe2bc880c5d495282`, binary 546044 bytes. Not installed in production.
- Hardened the existing quota status cache reader: `ready` requires valid finite positive `total_bytes` and `remaining_bytes <= total_bytes` rather than displaying impossible totals. Quota contract CI PASS (run 38552398872).
- Official XL public guidance (updated 2026-09-16) confirms myXL app and *808# are supported quota inquiry paths; it does **not** document a supported external native API client-registration / signing credential / quota response unit contract. Ref: https://www.xl.co.id/blog/cek-paket-internet-xl
- **Active blocker** is an operator-authorized authentication method/client identity and measured authenticated carrier quota response, including validated units. Do not invent a login, copy app credentials from BITS-XL, mark fake cache provenance or claim XL quota LIVE. Next step must be real authorization validation, then authenticated cache commit, then LuCI display and physical UAT.
- Preserve already-live SMS Center v1.6.0 and LTE. Do not require repeat physical hardware tests without changed target binaries or a genuine account authorization milestone.

## 2026-10-15 — compact native runtime release checkpoint
- Physical XL TLS probe, native crypto/decrypt and parser already PASS on 2026-10-14; do not retest identical legacy binaries.
- Cross-built new compact shared-library MIPS runtime against pinned OpenWrt 25.12.5 ramips/mt76x8 toolchain and mbedTLS 3.6.6; dynamic executable ABI requires router-existing libmbedtls.so.21, libmbedx509.so.7, libmbedcrypto.so.16.
- Release: https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/tag/veci-xl-runtime-compact-4773e7ca0628 ; GitHub Actions CI PASS: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38667601981 .
- Verified assets and SHA256: HTTPS dynamic 13992 bytes eae118cb412eb173789837e683f51a43c64e9fb07faf0c02c78e46448d742a7e ; crypto dynamic 8120 bytes 4bb8f2cb62d18aa7da34bf84aba25a2681cc0dc1ef75d5d984dd0fd68b44d931 ; parser dynamic 7688 bytes 756daba7b1db1dbede615cf6154ed1ca767e66f42118aee947b515a9cdee1015 ; shell pipeline 3129 bytes e6fd9ac7aed8f173aecc5884bcbba813f68273cfec38f76205ff0e3dfe67d39f. All four total 32929 bytes before filesystem/package overhead.
- The OpenWrt optional source/veci-telco-xl-native/Makefile now builds all three binaries dynamically and installs a dormant read-only pipeline script; no auto-login/cron or modem/service changes.
- One new physical *dynamic-ABI* verification script: scripts/veci-xl-compact-runtime-physical-20261015.sh --verify; downloads SHA-pinned executables to /tmp and uses only public synthetic fixtures. HTTPS executable is intentionally started with a rejected invalid command to guarantee zero carrier requests, even if an account exists.
- New dynamic runtime has **CI PASS but physical ABI execution NOT YET PROVEN**. Not installed to flash, not enabled in production and no real operator quota fetched.
- Genuine production blocker remains operator-authorized account onboarding and verified actual quota API response/units. No app secret embedded or synthesized carrier quota permitted. Do not treat static SSL/HTTP CI or data-only normalization as account authorization.
