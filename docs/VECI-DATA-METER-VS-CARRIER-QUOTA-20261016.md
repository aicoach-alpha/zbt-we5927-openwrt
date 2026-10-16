# VeCI router data meter — interim capability, not carrier quota

**Scope:** WE5927 OpenWrt 25.12.5; native VeCI add-on `veci-data-meter` 0.1.0. No LuCI or Core changes.

This is deliberately separate from `veci.quota.status` and `veci.xl`, which remain authoritative only when a genuine operator login yields a verified payload. The existing XL 0.3.7 integration cannot access the carrier because it lacks authorized API registration/client credentials; this module does NOT circumvent it.

- `veci.meter.status` reports hardware RNDIS `usb0` traffic RX/TX byte counters since the current boot.
- Optional `setBaseline`: user enters a remaining data quota read from a trusted source (e.g. myXL) in decimal MB. A 0600 baseline is saved only on this explicit action; read-only status does not write to flash.
- Estimated remainder = max(0, owner-entered balance minus interface RX+TX increments since the baseline).
- Interface reset, boot ID change, counter rollback, or baseline older than 31 days invalidate the estimate.
- Data usage may differ from billable carrier volume (rounding, overhead, rollover, other sessions, router resets). This number is **NOT carrier authenticated** or an operator balance; do not populate `carrier_authenticated` or inject estimated data into `veci.quota` cache.
- UI is standalone `/veci/data-meter.html`, administrator-authenticated over the router's existing HTTPS, and labels estimates explicitly. No OTP/SMS/USSD or account secret is collected.
- Other mobile operators may be supported by publishing provider-specific trusted read-only balance adapters; no operator's private mobile app keys may be baked into a public image.

**Status:** source implementation. Release and physical router UAT not yet confirmed. Official myXL documents its app for genuine balances, but does not currently document a public quota API supported for router OEMs: https://www.xl.co.id/id/myxl ; https://www.xl.co.id/blog/cek-kuota-xl-paling-mudah-ada-yang-baru-lewat-dial-number

**Carrier balance LIVE gate:** operator-authorized client registration + supported user-consent flow + authenticated identity and quota units + real on-device response; not satisfied as of 2026-10-16.
