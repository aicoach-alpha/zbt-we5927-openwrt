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
- Device-side package: thin shell/rpcd `veci.quota` contract and bounded, root-only cache. No Python, Node, Docker, external CLI or browser scraping on the router.
- The carrier-specific adapter may run off-router (self-hosted companion service) with appropriate storage and cryptographic tools, accessed only via authenticated HTTPS, with explicit session/OTP consent and no network ingress from the public internet. A portable native MIPS adapter can be investigated later only after binary size, crypto and performance benchmarks.
- Router status endpoint must be read-only; remote updates must reject arbitrary or unsigned payload injection. Secret management remains off device when using companion mode.
- Never conflate modem IMEI with subscriber phone number. Never modify modem identity.

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
