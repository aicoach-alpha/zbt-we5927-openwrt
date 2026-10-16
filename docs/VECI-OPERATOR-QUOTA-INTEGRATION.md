# VeCI operator quota integration (public firmware)

Status: engineering contract; no operator integration is verified LIVE as of 2026-10-16. Router UAT on the office-connected WE5927 confirmed removal of VeCI USSD (`VECI_USSD_RECONCILE=pass`).

## Scope
The interface is **VeCI**, never LuCI. Target: ZBT WE5927 with 8 MB NOR and limited RAM. Do not change LTE control, modem commands, SMS, LuCI, network configuration, or production deployment to implement this contract. USSD support is retired and must not be reintroduced.

## Important distinction
- Operator quota: authoritative remaining entitlement from the mobile operator, with units, bucket, and expiry.
- Local usage meter: bytes passing through the router; cannot be presented as remaining operator quota.
- A failed or unauthenticated provider lookup must return `unavailable` or `authentication_required`, never a fabricated zero or inferred remaining balance.

## Existing packages
The older `veci-telco-indonesia-0.2.1` package and the optional `veci-data-meter-0.1.0` are separate. The latter's installation was observed failing with `rpc_not_registered`; do not treat its local usage as an operator quota source.

## Adapter contract
An operator adapter should expose these actions through the VeCI backend (not through browser-to-operator requests):
1. `capabilities`: supported authentication and quota features, actual support level (implemented / unverified / unsupported).
2. `start_auth`: user-initiated request, once, using a provider-supported method; never silently send multiple OTPs.
3. `complete_auth`: user-submitted verification code or official consent result; do not log it.
4. `refresh_auth`: refresh only with a valid user-owned session and documented provider behavior.
5. `quota`: retrieve a signed-in user's authoritative package balances.
6. `logout`: revoke/delete stored session data where feasible.

Normalize a successful answer to:
```json
{
  "operator": "xl",
  "source": "operator",
  "state": "ok",
  "fetched_at": "2026-10-16T00:00:00Z",
  "buckets": [
    {
      "label": "Internet utama",
      "remaining_bytes": 1073741824,
      "total_bytes": 2147483648,
      "expires_at": "2026-10-31T16:59:59Z"
    }
  ]
}
```
This is a **schema example only**; amounts and dates above are fictional test values, not a subscriber's quota.

Other states: `not_supported`, `authentication_required`, `pending_otp`, `rate_limited`, `stale`, `unavailable`. No quota number should be emitted for non-`ok` states. Never describe an emulator, mock, or successful package install as proof that real operator quota was read.

## Privacy and distribution
- Store any user credentials or refresh tokens only on that user's own device with root-only permissions and atomic writes, excluding backup/export and logs; no secrets in frontend JavaScript or GitHub.
- Use TLS verification when making requests to operator services. Do not disable certificate checks.
- Never reuse a fixed API secret, IMEI, or token scraped from an old third-party mobile-app build.
- Do not claim private mobile app endpoints are official, stable, or licensed. Verify current endpoints and permission/terms before enabling by default in public builds.
- Bound OTP retries, refresh intervals, timeouts, memory, file size, and cached data age. Explicitly expose error and expired states.
- Operator credentials belong to each subscriber; no mandatory developer-run bridge, custom HTTPS relay, or central user account.

## References inspected
- https://github.com/hillz2/sidompul_api/blob/main/sidompul.sh — historical email OTP, token refresh, package-check sequence; app version / embedded Basic credential makes it unsuitable for copying directly.
- https://github.com/rizredvlo7zer0/Dor-Xl-Termux/blob/master/dor.php — older pre-login OTP workflow; historical only.

## Evidence needed before a LIVE claim
1. Verify provider's currently valid user-authorized access mechanism, without bundled secrets.
2. Implement the adapter, root-only session store, normalized response, and native VeCI screen.
3. Test authentication, expired token, invalid OTP, rate limit, offline mode, non-XL SIM and simultaneous sessions.
4. On the office-connected router, prove actual operator-sourced balances and any available expiry against the user's own operator app; never manufacture an unavailable expiry or total.
5. Confirm unchanged LTE/SMS/core behavior, USSD remains absent, memory/flash headroom, and clean rollback.

Do not deploy to the router via andre-nas. The router is reachable from the office laptop only.


## Physical router UAT: USSD retirement, 2026-10-16
- User-supplied terminal output confirmed `VECI_USSD_RECONCILE=pass`.
- `veci.ussd` RPC absent; `veci-ussd-dialer` APK absent; its RPC executable absent; USSD VeCI page absent.
- `veci.sms`, `veci.quota`, and `veci.xl` RPCs present and executables present.
- Removal/reconcile scripts reported modem unchanged; LTE connectivity after removal was not separately exercised during this acceptance check.
- Prior script initially reported `sms_lost` immediately after restarting rpcd. Later registration confirmed SMS recovered. The source removal script now waits for rpcd registration before checking.
- Do not restore USSD from older package releases or re-enable any `veci.ussd` UI actions. Legacy history is retained in Git only for audit.

## EnQuota applicability (source inspected, 2026-10-16)
- Upstream `Najihh/EnQuota` provides login / OTP / quota methods via provider APIs, **not USSD**.
- Its XL `getQuota()` implementation commonly maps operator response values to `QuotaItem.remainingFormatted` and `validUntil` but does not populate `totalBytes` or `remainingBytes`. The router must not mislabel formatted-only values as independently verified, complete numeric quota records.
- Existing `source/veci-quota/enquota-adapter.js` intentionally fails closed where verified numeric quota and valid expiry are missing; these tests use sample data, not a LIVE XL result.
- The native XL CIAM binary still requires locally provisioned operator app configuration. As of UAT, `basic_auth`, `user_agent`, `fingerprint`, `device_id`, and `ax_api_sig_key` were absent; there is no authenticated XL session.
- Do not copy EnQuota application secrets into the public image. Prioritize a permitted subscriber-authenticated mechanism before attempting OTP login or claiming quota is LIVE.
