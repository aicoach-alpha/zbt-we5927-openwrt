# VeCI XL Native 0.3.5 — focused production UAT handoff

Date: 15 October 2026

## Status

- **VeCI Core 0.2.2 is physically LIVE and unchanged.** No work on LuCI, LTE modem, SIM, SMS or firmware.
- **XL optional native APK 0.3.5 compiled, signed and released, but is NOT installed on the physical WE5927.**
- Real XL OTP delivery, token issuance, subscriber-profile identity matching and quota retrieval have **NOT** been verified by a real account. Do not claim the feature LIVE from CI alone.
- No CI builds invoke operator APIs, request an OTP or read subscriber SMS.
- No external app Basic credentials, secret keys, tokens, subscriber numbers or OTPs were copied into this repository or the release.

## Exact signed production-test candidate

Release: https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/tag/veci-xl-native-035-894641cb5b22

Signed package: `veci-telco-xl-native-0.3.5-r1.apk`

SHA256: `60b4c3551b2eaabc2483e5a1082a9b4a0491438c50bf09e37034ff22635f2e5a`

Size: 30,173 bytes.

Public P-256 key `veci-xl-035.pem` SHA256: `31394fb9d51991f4e4be74125c296111fae6a829f31cf4ddb8e734a3209a2a5a`.

CI: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38709169191 — SUCCESS.

SDK: OpenWrt 25.12.5 ramips/mt76x8, MIPS32 little-endian, toolchain and mbedTLS source archives SHA-pinned, shared ABI libmbedtls.so.21 / libmbedx509.so.7 / libmbedcrypto.so.16.

The SDK distributed without mbedTLS package-provider metadata, so CI compiled native executables in the SDK and then generated an explicit OpenWrt APK manifest with the existing router runtime dependency `libmbedtls21` and `jsonfilter`. APK content and P-256 signature were checked with apk verify. The package does **not** depend on luci-base or veci-telco-indonesia, and does **not** replace VeCI Core or the quota backend.

## Narrow implemented functionality

1. Native CIAM owner-initiated OTP request/submit, CA/hostname TLS validation, unverified token candidate held in private RAM.
2. Strict pending-profile token staging with 0700/0600 rules and rejection of malformed inputs.
3. Profile-only HTTPS + AES/HMAC, strict number-identity gate; the token session is activated only after account-number matching on the decrypted profile from that pipeline.
4. Quota-only TLS transport, bounded finite DATA parser, and account-session-gated refresh. Writes sanitized canonical local cache only after actual successful TLS/decrypt/parser checks; otherwise no fabricated balance.
5. Local VeCI quota status reader remains unchanged and returns `Not connected` until a valid authenticated cache is written.

## Explicit production-UAT blockers

- Native OTP, profile and quota tools still need a **VeCI-only interactive account-login UI** and a permission-scoped backend RPC interface. Do not expose OTP on insecure browser transport.
- Valid operator application integration credentials/configuration must be provisioned locally through an authorized method, with no hardcoded third-party application secrets. Build tests and reverse-engineered message formats do not establish valid operator credentials or network acceptance.
- Need signed **optional package installer** with exact immutable hash/signature gate, no unrelated package changes, and rollback. Do not run an unattended upgrade of `veci 0.2.2`.
- First real user-owner production UAT should prove OTP request/submit, number/identity match, and a real quota DATA response, not just APK install. Log only status/error codes; do not post OTP, number, tokens, profile JSON or secret keys to GitHub.

**Current decision:** native APK is a real signed build, but **do not ask the owner to run account production testing yet**. Finishing the safe VeCI interaction and local secret provisioning is required first. No broad modem/SMS regression testing is indicated.
