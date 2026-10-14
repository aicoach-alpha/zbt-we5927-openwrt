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

Status: SMS v1.6.0 LIVE. USSD XL network rejected and excluded from automatic quota. Native myXL cryptography HOST CI only, no carrier API login/response yet.