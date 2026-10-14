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
