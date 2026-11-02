# VeCI Indonesia Edition — operator quota roadmap

**Development proposal, not a shipped firmware or live carrier login.** Keep the existing J9E build immutable; do not insert these changes into an in-flight firmware run.

## Releases and labels

- **VeCI General**: common OpenWrt + VeCI core, existing router and app features; no Indonesia-specific runtime provider/credentials.
- **VeCI Indonesia**: exactly the same pinned OpenWrt and VeCI Core source revision, plus opt-in `veci-telco-indonesia` package. The user-facing and release filenames must contain `general` or `indonesia` explicitly. Provide signed metadata and independent release manifests with the same board, target and exact-ABI signed feed requirements.
- Build them from one source revision into two reproducible profiles; prohibit overwriting the General image or reusing a feed against a different kernel ABI.
- Show edition on Settings/About and download labels. Never rename an image without rebuilding release metadata/checksums/signatures.

## Initial supported provider: XL

- First release **XL prepaid quota READ ONLY**; confirm multi-bucket accounting (main/local/apps), validity date, current remaining/total quota, timestamp and provenance.
- Login requires user-initiated OTP and explicit carrier-session consent. NEVER embed MyXL account API secrets, refresh tokens, MSISDN, OTPs or signing keys in a public firmware image or GitHub.
- The MyXL reverse-engineered endpoints are **unofficial and subject to breakage, rate limits and terms**. Do not bundle undocumented proprietary credentials, reproduce third-party source blindly or implement purchases.
- Show `Sign in to XL` until authenticated; `Unavailable` after expiry/error. Never invent quota, compute authoritative carrier quota from network byte counters, or silently trigger OTP calls.
- Refresh at most every 15 minutes unless requested by the user; cached reads are local. Back off on 429/auth errors; mask phone numbers in logs; never log tokens or raw carrier payloads.
- The quota widget belongs to the VeCI dashboard and Cellular page. The General edition must not display misleading XL-specific data.

## Architecture under WE5927 constraints

- WE5927 OpenWrt 25.12.x is **mipsel_24kc**, low free overlay/RAM; EnQuota's documented precompiled Linux ARM64/AMD64 binaries are incompatible. BITS-XL requires Python/PyCryptodome; do not install the release APK blindly or run pip on router.
- Device-side package: a thin shell/rpcd `veci.quota` contract, bounded root-only cache and future on-device carrier clients. No Python, Node, Docker, browser scraping, developer cloud, or mandatory external services. Current package is only a read-only schema/registry skeleton; it has NO working carrier login or live quota yet.
- **Mandatory public-firmware rule:** carrier adapters execute on each owner's router and contact only authorized operator HTTPS endpoints directly. No hosted companion, NAS, cloud proxy, developer service, or failover to such a service. Share TLS/crypto libraries already in firmware; validate complete login flows and RAM/flash budgets before enabling a provider.
- The status endpoint remains read-only, backed by locally stored sanitized snapshots. A separate authenticated action handles consent-driven OTP, refresh and logout. Root-only (0600) local session storage reduces exposure to other users, but cannot protect against a compromised root account; never claim otherwise. Tokens and personal data must never leave the router except when communicating directly with the chosen operator.
- Never conflate modem IMEI with subscriber phone number. Never modify modem identity.

## Standalone mode — mandatory release gate

1. **No central VeCI backend** in firmware for quota, OTP, authentication, profile, or account tokens. Do not hardcode a private IP, a developer hostname, an analytics host, or a fallback proxy. Publisher-hosted signed firmware artifacts are separate from daily operation and may be checked only through the optional updater.
2. **Direct-to-carrier egress only.** Provider modules have explicit operator endpoint allowlists, verified TLS certificates, normal hostname validation, short network timeouts, strict response-size limits, and no insecure-cert fallback. Unofficial API discovery must be separately reviewed for lawful authorization and stability. Do not embed proprietary credentials or copied third-party API signing secrets in a public build.
3. **Use existing image packages** identified in WE5927 build config: `libmbedtls`, `libustream-mbedtls`, `uclient-fetch`, `ca-bundle`, `ucode`, and `jsonfilter`. This demonstrates reusable tooling but **not** that a working MyXL/other-provider login exists. Evaluate any extra native helpers via reproducible MIPS cross-build size/RAM benchmarks first.
4. **No always-on provider processes.** Only one local quota scheduler and one cache, adapters loaded on demand. Each account's token is separate and removable. Admin reads of the quota status do not trigger OTP or remote traffic. Quota widgets never conflate raw LTE traffic usage with operator quota balances.
5. **Security:** store authorized session secrets only when opted in, with directory 0700 and files 0600. Prevent log, crash dump, ubus API, or browser telemetry leaks. Logout revokes/erases local session; flash storage is not encrypted by default, so physical/root attacks remain out of scope without additional safeguards.
6. **When unavailable, degrade honestly:** unknown/null quota, `not_connected`, `stale` or `unsupported`. Never add a hosted fallback. Firmware must still route traffic and provide all regular administration features with no carrier API access.
7. UAT must verify the router has **zero egress toward developer-owned servers**, no DNS requests to private VeCI infrastructure, and no network bottleneck created by centralized connections. Carrier sessions and number ownership must be validated only against that account's operator.

## Stable quota schema

```json
{
  "schema": 1,
  "provider": "xl",
  "state": "not_connected",
  "total_bytes": null,
  "remaining_bytes": null,
  "used_bytes": null,
  "expires_at": null,
  "fetched_at": null,
  "source": null,
  "buckets": []
}
```

Allowed states: `not_connected`, `otp_required`, `ready`, `stale`, `unauthorized`, `unavailable`. Bytes are nonnegative integers or null, not floating unit strings. Unknown does not equal zero. Each bucket has a stable `id`, `label`, `total_bytes`, `remaining_bytes`, `expires_at`; timestamps UTC ISO 8601. Separate provider names from user-visible service branding.

## Future adapters

Provider registry: `xl`, `axis`, `telkomsel`, `byu`, `indosat`, `tri`, `smartfren`. Show only providers with tested read-only authentication/quota adapters; don't promise working Smartfren from prefix detection alone.

## Evidence and hard gates

1. Device-independent schema and provider plugin tests (bad bytes, partial buckets, expiry, invalid OTP, 429, cache fallback, secrets redaction).
2. XL test account with authorized SMS OTP; verify actual carrier values against MyXL app. Obtain user permission for sending OTP; tokens remain private.
3. Test on approved recoverable WE5927 with overlay/RAM/CPU metrics, live dashboard and no routing interruption.
4. General image must exclude Indonesia package. Verify both editions' signed image, kernel ABI and app feed; rerun J9/J9B/J9D and all Router App/updater UAT.
5. **No production flash** until 5 Router Apps, updater, all UAT and explicit owner approval PASS.

## Reviewed upstream sources

- https://github.com/Banten-IT-Solutions/BITS-XL (MIT; LuCI, Python + PyCryptodome)
- https://github.com/Najihh/EnQuota (TypeScript; published native AMD64/ARM64, multi-provider)
- https://github.com/bitscoid/Ah-Si-Ata (MIT; Python 3.10+, MyXL APIs)

Do not install the instructions from an unrelated OpenWrt version using `opkg` on OpenWrt 25.12 (uses `apk`). Verify release asset existence and ABI first.


## Multi-operator research (October 2026)

Official service brands surveyed: **MyTelkomsel**, **by.U**, optional **MyOrbit/Orbit**, **myIM3**, **bima+** (Tri), **myXL** including XL Prioritas, **AXISNET**, **mySF / MySmartfren**. Business families are *not* equivalent to authentication backends.

| Brand | Parent group | Official quota app | Community evidence | Adapter readiness |
| --- | --- | --- | --- | --- |
| XL | XLSMART | myXL | BITS-XL CLI; EnQuota XLProvider | Research only, no live account test |
| AXIS | XLSMART | AXISNET | EnQuota routes AXIS to XLProvider | Possible sharing; not proven interchangeable |
| Smartfren | XLSMART | mySF | EnQuota prefix detection only (no driver) | No validated API |
| Telkomsel | Telkomsel | MyTelkomsel | EnQuota wraps separate Telbot process | Separate auth, not tested |
| by.U | Telkomsel | by.U | EnQuota relies on pre-existing web/Ruby session token | No proven router-side login |
| IM3 | IOH | myIM3 | EnQuota IM3 requests and OTP references | Needs authorized live test |
| Tri | IOH | bima+ | EnQuota Tri requests and OTP references | Needs authorized live test |
| Orbit (optional) | Telkomsel | MyOrbit / MyTelkomsel | Official router/product companion | Product-specific login; not generic mobile SIM API |

Source-code observations from EnQuota SHA \`8416a90fa00024226412cde220d220f10cc3f697\`:
- \`src/providers/index.ts\` instantiates the **same XLProvider class for XL and AXIS**. This is a reuse hypothesis, not validation that native AXISNET endpoints are identical.
- \`src/providers/indosat.ts\` and \`tri.ts\` have similar request-signing, guest token and OTP patterns, but distinct hosts, payloads and quota parsing. Share a crypto/HTTP library, not the subscriber token or adapter logic.
- \`src/providers/telkomsel.ts\` spawns an external Telbot child process. Do not bundle on WE5927 MIPS without compiled support and hard memory/CPU benchmarks.
- \`src/providers/byu.ts\` describes using an existing web session token rather than a complete self-contained OTP login. Prefer officially supported user authentication if possible. No credential scraping from apps.
- \`src/detector.ts\` recognizes Smartfren number prefixes but explicitly marks them unsupported; it has no Smartfren provider in \`src/providers/index.ts\`.
- Despite the README claim, \`src/session.ts\` serializes sessions with \`JSON.stringify\` to \`~/.enquota/sessions.json\`, and no encryption appears on that storage path. Do not reuse the persistence model for sensitive sessions.
- Community MyXL quota endpoint descriptions differ across codebases. Pin and live-test endpoint/response version rather than hardcode a single unverified quota URL.

**Shared services** (ONE **on-router** implementation regardless of brand): shared OTP consent UI, isolated subscriber session handling, local cache, native TLS-validated HTTP transport, retry/backoff, rate limiting, structured quota formatting, timestamp provenance and privacy-safe logs. Each provider supplies its own authorized login flow, signed requests if necessary, bucket interpretation and operator host allowlist. No cross-provider credential sharing.

**Single lightweight router package:** \`veci-telco-indonesia\` now holds one JSON provider registry at \`/usr/share/veci/telco/providers.json\`, served via authenticated/read-only \`veci.quota providers\`, alongside \`veci.quota status\`. There are **no per-provider daemons or Python/Node dependencies in this skeleton**. Current output is \`not_connected\` (the original XL placeholder); all registry entries are \`not_implemented\`. Neither an actual General/Indonesia dual-firmware release nor a working quota dashboard has been built yet.

**Mandatory execution boundary:** one on-device shared client handles local account/session cache, direct HTTPS with normal CA and hostname validation, bounded requests, backoff, scheduling and sanitized quota responses. Use the existing OpenWrt TLS stack and a small compiled/native MIPS adapter if needed; no Python/Node runtime or additional server. Provider-specific crypto and login are local and opt-in, never routed through developer infrastructure. If a carrier requires undistributable proprietary client secrets or unapproved access, show 'Unsupported' rather than sending credentials to someone else's server.

**Quota accuracy and semantics:** show total/remaining only if the provider reports a verified aggregate or a provably disjoint set of buckets. Some packages overlap or have special restrictions (night, app, local, roaming, FUP). Do not sum overlapping buckets as a misleading grand total. Unknown or unlimited does NOT equal \`0\`. Account for voice, SMS, currency and postpaid billing separately. A normal dashboard read does not request OTP or refresh remote quota. Suggested polling: 15–30 minutes while authenticated and opt-in, exponential backoff on failures, always show \`last_updated\` or \`stale\` rather than silently reusing old data.

**Carrier and brand registry**: \`xl\`, \`axis\`, \`smartfren\`, \`telkomsel\`, \`byu\`, \`im3\`, \`tri\`, and optional \`orbit\`. The three shared family IDs \`xlsmart\`, \`telkomsel\`, \`ioh\` are organizational labels, not universal authentication handlers. A subscriber's phone prefix is merely a hint; confirm the operator during account setup.

**Sources reviewed:**
- https://www.xlsmart.co.id/en/about-xlsmart/news/xlsmart-integrated-unified-network-operation-center-customer-experience-and-service-operation-center
- https://www.telkomsel.com/support/faq/bagaimana-cara-mengecek-jumlah-kuota-dan-sisa-kuota-internet
- https://www.byu.id/id/faq-detail/cara-login-nomor-byu
- https://im3.id/portal/id/psmyim3landing
- https://care.tri.co.id/s/article/Temukan-semua-kebutuhan-digitalmu-dengan-fitur-fitur-menarik-Bima
- https://www.axis.co.id/axisnet
- https://www.smartfren.com/connect-with-us/support/faq/
- https://github.com/Najihh/EnQuota/tree/8416a90fa00024226412cde220d220f10cc3f697/src/providers

**Shipping gates:** REGISTRY_PASS is not LOGIN_PASS, QUOTA_PASS, or IMAGE_RELEASE_PASS. Never flash the live WE5927 on the strength of provider research. J9E general build and hard requirements for Router Apps, signed updater and physical UAT remain independent.
