# VeCI operator quota integration (public firmware)

Status: engineering contract; no operator integration is verified LIVE as of 2026-10-16.

## Scope
The interface is **VeCI**, never LuCI. Target: ZBT WE5927 with 8 MB NOR and limited RAM. Do not change LTE control, modem commands, SMS, USSD, LuCI, network configuration, or production deployment to implement this contract.

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
4. On the office-connected router, prove an actual operator-sourced balance and expiry against the user's own operator app.
5. Confirm unchanged LTE/SMS/USSD/core behavior, memory/flash headroom, and clean rollback.

Do not deploy to the router via andre-nas. The router is reachable from the office laptop only.
