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

### 2026-10-15 compact runtime physical gate release verification
- GitHub Actions run 38668000318 PASS for syntax, forbidden live operations and SHA-256 checks against three public MIPS release assets.
- Physical stage script `scripts/veci-xl-compact-runtime-physical-20261015.sh` loads all three dynamic executables from RAM, checks their pinned hashes, executes synthetic AES encrypt/decrypt and quota parser, and calls HTTP binary with a deliberately invalid command (only checks linker/ABI; no carrier HTTP).
- Hardware physical dynamic ABI status PENDING until user supplies one router result. Successful source CI or MIPS cross-build alone does not establish live physical compatibility.
- Next operator integration cannot truthfully become LIVE without authorized account session and a real XL quota response with validated units; do not infer from synthetic test data or static API candidates.

## 2026-10-15 — focused hardening and compact release
- Native HTTP quota transport now rejects non-JSON Content-Type, duplicate or missing valid JSON media-type, unframed HTTP bodies and conflicting Content-Length/Transfer-Encoding, to prevent silent truncation and HTML/error payload masquerading as quota responses.
- Offline tests include valid JSON with charset plus missing/non-JSON type, no body framing, and mixed framing rejection. CI runs 38669531578 (native HTTP), 38669531583 (dynamic MIPS runtime) PASS on the hardened HTTP source.
- Staged read-only quota chain now refuses to contact the operator unless the locally provisioned decryption key is exactly 32 bytes, held inside the owner-only (0700) session directory as owner-only (0600) regular file. Test run 38669609314 PASS, including proof that weak permissions/invalid length prevent network calls.
- Combined compact release contains ALL improvements: `veci-xl-runtime-compact-24653c5bc779`, GitHub Actions run 38669639452 PASS. Native sizes: HTTP 13992 bytes, crypto 8120 bytes, parser 7688 bytes, shell chain 3620 bytes. SHA256 HTTP 64c140562ddbc4fd1bb35597ef3a69022e392227a7a89d04ca1bea0c5ca4401b; crypto 4bb8f2cb62d18aa7da34bf84aba25a2681cc0dc1ef75d5d984dd0fd68b44d931; parser 756daba7b1db1dbede615cf6154ed1ca767e66f42118aee947b515a9cdee1015.
- Physical one-shot script updated to this exact release: `scripts/veci-xl-compact-runtime-physical-20261015.sh --verify`; SHA-pinned transport binaries loaded only into /tmp. It deliberately invokes HTTP with invalid command to test dynamic loader without ANY carrier network request. The shell script is NOT an installer and touches no firmware/SMS/modem.
- Legacy AES, HTTPS identity and parser physical PASS results remain closed. New compact MIPS executable runtime compatibility on router remains UNVERIFIED until device evidence. No operator-authenticated login or quota result exists, no credentials should be passed through ChatGPT.

## 2026-10-15 — Compact MIPS physical UAT CLOSED/PASS

Owner ran SHA-pinned scripts/veci-xl-compact-runtime-physical-20261015.sh --verify via SSH on the ZBT-WE5927 (root@192.168.1.1). Device reported:
```text
VECI_XL_COMPACT_RUNTIME_MIPS_ABI=pass
VECI_XL_COMPACT_RUNTIME_SHA256=pass
VECI_XL_COMPACT_CRYPTO_ROUNDTRIP=pass
VECI_XL_COMPACT_QUOTA_PARSER=pass
VECI_XL_COMPACT_HTTP_LOADER=pass
VECI_REAL_OPERATOR_LOGIN=not_attempted
VECI_OPERATOR_QUOTA=not_verified
VECI_MODEM_AND_SMS_UNCHANGED=true
VECI_FLASH_WRITES=none
```

**Closed:** compact runtime native MIPS binary physical ABI and synthetic AES+DATA parser UAT PASS. CI also PASS (compact runtime build run 38669639452 and on-device one-shot script integrity gate run 38669737201). Prior sections of this doc reporting physical gate pending are historic; this checkpoint supersedes them. Do not re-run unchanged MIPS/crypto/parser/TLS/loader checks.
**Not LIVE:** new compact runtime was only downloaded into volatile /tmp, not installed to flash. XL account login not attempted, real quota not verified. Network access and runtime authenticity alone do NOT establish supported XL subscriber-quota API access or correct units.

## Next actual integration blocker: operator-approved authentication and quota

- As of Oct 15 2026, publicly verifiable XL help describes manual number+OTP login using myXL and checking actual quota via myXL or *808#, but no validated third-party consumer selfcare quota API onboarding agreement/client credential procedure was established.
- Public XLSMART business bulk-data and CAMARA APIs are distinct product categories, not evidence of a subscriber selfcare quota-read grant.
- Obtain a supported operator integration/delegated access method before issuing authenticated quota requests. Do not redistribute reverse-engineered app secrets or embed other parties' signing keys. Never request the owner's OTP in ChatGPT.
- VeCI auto SMS-OTP reading must remain disabled. A modem CMTI slot notice is insufficient to distinguish an XL OTP from banking OTP; reading SMS blindly violates the existing safety policy.
- After authorization is verified, implement a single local authenticated session and a real operator DATA response validation including units, expiry, per-SIM binding and no side-effects. Only then permit a trusted producer to mark root-only cache source=carrier_authenticated, and deploy to LuCI.
- Preserve live SMS v1.6.0, modem LTE, OpenWrt and any existing dashboard configuration. No new unnecessary tests without changing relevant code/binaries.

## 2026-10-15 — LuCI read-only quota status 0.2.0 and profile isolation
- User-supplied physical compact MIPS PASS remains closed. No repeated AES/TLS/MIPS test necessary. Neither official account login nor carrier quota is LIVE.
- Introduced optional Indonesia-edition LuCI view at `source/veci-telco-indonesia/files/www/luci-static/resources/view/veci/quota.js` and menu `admin/network/veci_indonesia_quota`, gated by the existing strictly READ-ONLY `veci-quota` ACL; the view does not accept OTP, store tokens, or call modem/SMS. Refresh button re-reads only local cache RPC (`veci.quota status`) and local provider registry.
- State rules: show numeric quota only when schema=1, provider=xl, state=ready, source=carrier_authenticated, total positive and finite, remaining finite and in [0,total]. Otherwise show no quota number, no synthetic data, and a clear not_connected/stale/unavailable status. Last verification timestamp never displayed for unverified data. Other provider names explicitly label integrations unavailable.
- The view includes an external official myXL help link (not an embedded login, token proxy or credential collector), and does not promise that authentication works on OpenWrt.
- Package `veci-telco-indonesia` version 0.2.0 installs the LuCI page/menu alongside the previously read-only `veci.quota` provider/cache/registry. It does not start a new service or change modem, SMS Center or existing UCI settings.
- `scripts/prepare-veci.sh` now stages the optional `veci-telco-xl-native` build recipe **only for Indonesia**, so it is actually buildable from the prepared OpenWrt source workspace. Both General and Indonesia selectors explicitly keep `CONFIG_PACKAGE_veci-telco-xl-native` disabled by default; the existing Indonesia read-only UI remains selected for Indonesia only. General source workspace cannot carry either Indonesia package.
- LuCI offline behavioral tests (`tests/test_veci_indonesia_quota_ui.cjs`) simulate valid carrier quota, synthetic parsed-only data, wrong source/provider, impossible totals, stale data, not connected status and RPC failure. UI shows no numbers for unverified cases. GitHub Actions `VeCI Indonesia optional quota contract` PASS run 38670747773. More recent runs should be checked after version bump.
- **Release state:** source committed to GitHub feature branch PR #4; tested in CI with offline LuCI VM and source-build staging. No flash deployment/physical page UAT, real operator session, or carrier-authenticated quota response. Remain honest about that distinction.

## 2026-10-15 — Quota LuCI packaged, physical target routing corrected

- Owner confirmed ZBT-WE5927 is accessible from the **office Windows laptop**, NOT from `andre-nas`. NEVER assume that IP `192.168.1.1` on `andre-nas` refers to VeCI; SentinelX confirmed that route serves a ZTE F660 login page and rejects TCP/22. No router deployment through `andre-nas`.
- Desktop Commander lists the office device as online, but its connector reports this month's usage limit reached. Do not retry or reconnect until the service quota recovers. Production router remains unchanged.
- GitHub Actions run 38671500097 successfully built an actual OpenWrt 25.12.5 ramips/mt76x8 SDK `.apk` file for the read-only Indonesia LuCI quota page. The pinned source commit is `5dfbb0318e6f5881e88a3e6f3dc00ae36a36eab2`.
- Immutable prerelease: https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/tag/veci-indonesia-quota-apk-5dfbb0318e6f ; asset `veci-telco-indonesia-0.2.0-r1.apk`, 5528 bytes, sha256 `7669331c810b7ab35b133b3f1229c50569a3dee4844c029a4279d8f8dab94ab2`.
- `.apk` has not been installed; package-manager trust/signing and rootfs/LuCI UAT must be validated at the actual router through authorized office-laptop connectivity. Treat a successful SDK package build as build-PASS, not deployment-PASS.
- An unsigned or independently signed APK should never be installed by bypassing signature policy on a production router just to mark the work LIVE. Coordinate with a trusted firmware/package feed, preserve configs and rollback. Do not restart LTE modem or SMS v1.6.0.
- Login/account authentication remains unimplemented and operator quota has not been verified. This package is status-view only and will display `not_connected` until a genuinely authorized carrier data source exists.


## 2026-10-15 — Standalone quota UI package build

- Package v0.2.1 now depends on rpcd, luci-base and jsonfilter rather than requiring VeCI core. This supports optional installation on existing compatible OpenWrt installations.
- Native OpenWrt 25.12.5 SDK produced `veci-telco-indonesia-0.2.1-r1.apk` (5567 bytes, sha256 `7ebb290ff5973c52a970f2e78b784254dcbafc3e5256633affaad9644685f8b4`). Release: `veci-indonesia-quota-apk-fb9630bdc1cd`.
- APK payload and dependency metadata inspection PASS in GitHub Actions run 38672198210. Read-only staging preflight CI PASS in run 38672382680.
- `scripts/veci-indonesia-quota-apk-preflight-20261015.sh --verify` checks board, OS, disk, exact hash, and uses a non-mutating package-manager simulation. It does not install anything or use a signature-bypass flag.
- Production router access is via the office laptop only; do not target the similarly addressed ZTE device visible from andre-nas. Physical package trust and deployment have not been proven.
- Real XL account login and carrier quota still not verified. Do not label this UI-only package as quota LIVE.

## 2026-10-15 — On-device APK trust gate blocked; scoped signed candidate prepared

The office-laptop SSH physical run of `scripts/veci-indonesia-quota-apk-preflight-20261015.sh --verify` returned:
```text
VECI_INDONESIA_APK_BOARD=pass
VECI_INDONESIA_APK_OPENWRT_VERSION=pass
VECI_INDONESIA_APK_OVERLAY_SPACE=pass
VECI_INDONESIA_APK_SHA256=pass
VECI_INDONESIA_APK_TRUST_AND_DEPENDENCIES=blocked
VECI_INDONESIA_APK_REASON=signature_or_dependency_not_verified
VECI_INDONESIA_APK_INSTALLED=false
```

That first physical error is **ambiguous** between trust and dependency solving; no raw package-manager stderr was exposed, so do not claim a definitive cause. OpenWrt APKv3 normally rejects unsigned SDK-built third-party package installations unless a trusted signature is provided. Never bypass this gate with `apk add --allow-untrusted` on a production router.

Fix prepared: SHA-pinned original v0.2.1 APK was signed in CI with a short-lived P-256 release-only key. Signed candidate release `veci-indonesia-quota-signed-a0b5b97ff9a2`: https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/tag/veci-indonesia-quota-signed-a0b5b97ff9a2

- Signed APK 5683 bytes, sha256 `da72b09afefcd2bdf99bc501d86bd8e485f6a7156b8ccdaae189449a3b0ce34f`.
- Public key PEM 178 bytes, sha256 `4d1bae271c4cca9b46ac10404d887c246637795f5b89d271fa38672efe9bdbfa`.
- CI `apk verify` with that key PASS; without it FAIL (the expected behavior), run 38673239329. Private signing key never published; released candidate uses ephemeral signing key and is NOT a persistent signing identity for future upgrades.
- Added physical read-only `scripts/veci-indonesia-quota-signed-apk-preflight-20261015.sh --verify`. It obtains only those exact SHA-pinned assets into `/tmp`, copies existing trusted *public* system keys to a local tmp directory, verifies the signed package with `apk --keys-dir /tmp/... verify`, and uses `apk --keys-dir /tmp/... --simulate add` to validate dependencies without changing device keys, package DB, firmware, SIM or SMS.
- Physical preflight code/asset CI PASS run 38673494322. **No physical execution yet of new signed artifact**, no trusted key permanently enrolled, no APK installed. Do not repeat old compact runtime tests.
- If signature verification PASS but dependency simulation BLOCKED, report that exact blocker; do not try `--allow-untrusted`, `apk upgrade`, overwrite keys or sysupgrade.
- After signed preflight PASS on the actual office-attached WE5927, only then undertake narrowly scoped installation with pre-change backup and specific rollback, preserving existing SMS Center v1.6.0 and LTE services.
- XL login remains not attempted and real operator quota not verified; this milestone addresses only the LuCI status page distribution.

## 2026-10-15 — Signed APK on-device trust gate CLOSED/PASS

Owner ran the SHA-pinned signed-APK preflight from the **office laptop SSH session** on the ZBT-WE5927 router. Actual router output:
```text
VECI_SIGNED_APK_SHA256=pass
VECI_SIGNED_APK_SIGNATURE=pass
VECI_SIGNED_APK_DEPENDENCY_SIMULATION=pass
VECI_SIGNED_APK_PREFLIGHT=pass
VECI_SIGNED_APK_INSTALLED=false
VECI_MODEM_AND_SMS_UNCHANGED=true
VECI_FLASH_WRITES=none
VECI_XL_ACCOUNT_LOGIN=not_attempted
VECI_OPERATOR_QUOTA=not_verified
```

Signing trust, exact artifact integrity and dependency solver pass with a temporary, root-only public-key directory. **Close this preflight: do not repeat it without changed APK or install logic.** No persistent signing key enrollment has occurred.

Scoped installer prepared in `scripts/veci-indonesia-quota-apk-deploy-20261015.sh` with explicit `--install`, `--status`, `--rollback`: only 6 new quota-specific files, refuses existing files or installed package, SHA-pinned signed APK, one-time trusted public key, local-only dependency solver, volatile backup of /etc/config and installed package inventory, automatic package removal on installation/UAT failure, optional one-time rpcd restart if plugin not auto-discovered. Does not change LTE, modem, SMS, firmware image or UCI network settings. Package installation DOES intentionally write to OpenWrt overlay and package database.

**Do not confuse candidate installer with LIVE deployment.** Installer is unexecuted on physical router; GitHub Actions deployment script static/CLI verification must PASS before issuing the on-device command. The private signing key was one-time, so future updates need a deliberately stable signing key/identity and an approved package feed. The status page cannot show verified XL quota until an operator-authorized integration exists.

## 2026-10-15 — Actual signed APK install failed RPC UAT and automatically rolled back

Owner executed the previously staged signed installer on the office-laptop-connected WE5927. Physical output:
```text
VECI_QUOTA_SIGNATURE=pass
VECI_QUOTA_DEPENDENCIES=pass
VECI_QUOTA_VOLATILE_BACKUP=pass
VECI_QUOTA_DEPLOY=blocked
VECI_QUOTA_REASON=quota_rpc_missing
VECI_QUOTA_AUTO_ROLLBACK=pass
```

The actual install DID reach the overlay package transaction, but failed to make the `veci.quota` ubus endpoint available immediately after `/etc/init.d/rpcd restart`. Automatic APK removal/restart reported PASS. No LIVE claim and no verified real XL quota. Note: rollback output is not an independent read-after-rollback audit of all affected files; treat this as script-reported rollback rather than proven full configuration restoration.

The OpenWrt rpcd executable-plugin mechanism registers method objects at service startup from `/usr/libexec/rpcd/<name>`, using its `list` response. The original installer made one immediate ubus request after restart, which may have hit an asynchronous startup race. Actual reason is NOT yet proven; it could be delayed registration, malformed script output, missing plugin executable or other runtime issue.

Remediation in script only, signed v0.2.1 APK UNCHANGED: check installed executable and its direct `list` and `call status`, then allow bounded 12 one-second ubus retries after rpcd restart; on failure report whether the object was not registered or the method call failed, and auto rollback again. The script refuses file collisions and leaves all non-quota services untouched. CI installation/rollback safety gate PASS run 38677442971.

The next single physical transaction is running the updated SHA-pinned installer from office PowerShell; only report LuCI UI installed once on-device `VECI_QUOTA_PACKAGE_INSTALL=pass`, `VECI_QUOTA_RPC=pass`, and `VECI_QUOTA_PROVIDER_REGISTRY=pass` are observed. No operator authentication is implemented. Do not repeat closed AES/SDK/PKG signature tests except for changed artifacts.

## 2026-10-15 — Signed quota UI v0.2.1 physical installation & RPC UAT PASS

Owner retried the corrected, commit-pinned installer via SSH from the **office Windows laptop** to the actual ZBT-WE5927. Full physical stdout:
```text
VECI_QUOTA_SIGNATURE=pass
VECI_QUOTA_DEPENDENCIES=pass
VECI_QUOTA_VOLATILE_BACKUP=pass
VECI_QUOTA_RPC_EXECUTABLE=pass
VECI_QUOTA_PACKAGE_INSTALL=pass
VECI_QUOTA_RPC=pass
VECI_QUOTA_PROVIDER_REGISTRY=pass
VECI_QUOTA_LOCAL_STATE=not_connected
VECI_QUOTA_ROLLBACK_COMMAND_AVAILABLE=true
VECI_XL_ACCOUNT_LOGIN=not_attempted
VECI_OPERATOR_QUOTA=not_verified
VECI_MODEM_AND_SMS_UNCHANGED=true
```

**Deployment milestone CLOSED/PASS**: APK `veci-telco-indonesia-0.2.1-r1.apk` installed to router overlay, signed package verified, executable rpcd plugin recognized, `ubus veci.quota status` and provider registry function, with state `not_connected` (correct fail-closed behavior). `rpcd` retry/direct-plugin-contract correction fixed the observed previous install blocker. Script reports LTE/SMS unchanged; additional independent modem/SMS regression not conducted in this transaction.

**Remaining verification distinct from installation:** LuCI web navigation/rendering through authenticated browser, persistence after a normal reboot (do not reboot just to close the gate), and eventual approved actual XL operator account/remaining-quota integration. No credentials or OTP were supplied. Authentication NOT LIVE, operator balance NOT verified. Optional application package installation LIVE is NOT equivalent to operator quota LIVE.

**Release discipline:** preserve physical PASS, do not reinstall or run signed preflights again unless the package changes. Owner should keep a recovery path because rollback is available through existing installer `--rollback`; future upgrades require a stable operator-controlled APK signing key rather than this one-time ephemeral CI signing key. GitHub feature PR #4 remains open pending broader release gates.

## 2026-10-15 — Native VeCI-only Cellular UI signed upgrade ready, not yet physically deployed

- Product directive: no further LuCI frontend development. Operator quota belongs in VeCI > Cellular; LuCI remains only historical expert administration.
- Firmware integration pinned native VeCI source `9bdc072884ffaa32539d221217f1d48e81bb076b` with real `cellular-quota-panel` and read-only `veci.quota status`, preserving existing SMS/USSD/SIM UI. Previous core source for rollback is `f19603b6172854dfeca3861826017d8f1aa1268c`.
- Signed matching APKv3 release `veci-native-quota-core-pair-9cbf71fcb12f` successfully built using official SHA-verified OpenWrt 25.12.5 RAMIPS mt76x8 SDK: https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/tag/veci-native-quota-core-pair-9cbf71fcb12f
- Native UI update `veci-0.2.1-r1.apk` 52686 bytes SHA256 `fe19f1f1c7c433512cf9c51778877b988a51bdc3b6ef7ab5eebad66eed317b19`. Rollback `veci-0.2.0-r1.apk` 52098 bytes SHA256 `5822cd96a04bf4a856d1d0abe3ec2065811f712808ca3eaa223ddec933effbcf`. Same ephemeral release key `veci-core.pem` SHA256 `7c62736c912bed2e08dabb89dfaa05e7ed9a362672a902d119cc7ced4c1f5432`.
- Standalone guarded upgrade/rollback script `scripts/veci-native-cellular-quota-core-deploy-20261015.sh`. It **refuses to overwrite unknown source**: installed base `veci` version 0.2.0-r1 and SHA256 of `/www/veci/js/pages/cellular.js` must be `e569794565fd2d59d4badeae9bcc086ab931b1200cafec5f4b247954f29485b4`, and helper must match `fb3e078c2e65a39c3d0e852f5364f2fd433cbfd547df21b480b1cfd514104a9d`. Expected post-update Cellular SHA256 `2f043f5e45c0839de3caba0f7ee832e1ba30adae7549afe17014d7e96ef9b818`.
- Only package `veci` is changed, with signed ephemeral trust, offline solver and package transaction, volatile config/page backup, unrelated package inventory guard, backend RPC liveness guard, and signed old APK rollback. It does NOT replace the existing signed `veci-telco-indonesia` backend, develop LuCI, or touch SMS/LTE/modem/APN. VeCI core post-install may restart `rpcd` and `uhttpd` briefly.
- Native-only deployment security CI PASS run 38680706731 and paired APK build PASS run 38680366911. Device **UI core upgrade not yet executed**, so `VeCI Cellular UI LIVE` must not be asserted until office-laptop router UAT and VeCI browser view have PASSed. This is a distinct milestone from the already-LIVE `veci.quota` backend.
- Desktop Commander office-laptop remote execution is limited by the connector's monthly quota. Router operations must be conducted through authorized office-laptop SSH; NEVER use andre-nas `192.168.1.1` (different ZTE router).
