# VeCI Generic USSD Dialer — 16 October 2026

## Product correction
USSD is an interactive dial service on the active SIM. It is **not** inherently an XL quota API. The previous VeCI XL-only transport was hard-coded to `*808#` and an XL operator check, which made it unsuitable for a generic router USSD feature. Keep the existing XL quota module unchanged and introduce an optional, independent native VeCI dialer.

## New optional package
- `source/veci-ussd-dialer` — `veci-ussd-dialer` APK 0.1.0.
- Frontend `/veci/ussd-dialer.html`: owner sign-in, free-form bounded USSD code, single-click consent, display actual operator replies, manual numeric response, explicit local session closure.
- RPC `veci.dialer`: read-only `status`; write-only `start`, `reply`, `cancel`. Independent ACL; no raw AT endpoint.
- Worker `veci-ussd-dialer`: verifies real physical WE5927/ttyUSB2/Qualcomm 05c6:902e/SIM slot and uses the pre-existing `we5927-at.lock` and shared prior `/tmp/veci-xl-ussd.session` for mutual exclusion.
- Native `veci-ussd-dialer-once`: bounded `AT+CUSD` only, no `ATD` or `AT+CMGS`, waits for both acknowledgement and asynchronous `+CUSD`; supports full dial strings such as `*123#`, `#21#`, `*808*7*3*2*1#`.
- Input characters strictly `0–9`, `*`, `#`; full code begins with `*` or `#`, ends with `#`, max 32 characters; manual menu reply 0–99.
- HTTPS-only enforced in RPC for all write methods, separate user approval for each transaction, no automation, no dial or reply when page loads, no quota cache writes, no third-party account keys or modem/SMS changes.

## Verification boundaries
- PTY host simulation and source checks: PASS https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38837908400.
- Cross-compiled/signed MIPS release workflow `.github/workflows/veci-generic-ussd-signed.yml`: launched separately, result must be verified before claiming signed package.
- **No generic package has been installed on the physical router; operator USSD response remains unverified.**
- Preserve installed VeCI Core 0.2.2, XL Native 0.3.7, LuCI, SMS, LTE, HTTPS-only, and owner backups.
- Any production installation must verify signed APK and target platform, simulate the apk transaction, then check `veci.dialer` registration and a browser-to-RPC authenticated read-only method before dialing. On failure, remove only the optional package.
