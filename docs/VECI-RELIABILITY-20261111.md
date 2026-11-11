# WE5927 reliability follow-up — 2026-11-11

## Proven incidents (production, board WE5927/MT7628AN)

- Wi-Fi SSID disappeared from two phones and an independent laptop scanner while
  `radio0.up=true` and `hostapd.status=ENABLED`. A one-shot radio restart
  stalled with `mt76_wmac: MCU message 08 timed out`; `hostapd`, `rpcd`
  and `iw` were stuck in `D` state. One standard reboot restored
  Wi-Fi broadcast and login. A subsequent independent scan found the SSID.
- LTE public ICMP and HTTPS checks degraded repeatedly around 122 minutes
  apart. The gateway remained reachable in several events, so that alone
  does **not** prove loss of local RNDIS, DHCP or LTE registration.
  In another incident, LTE DHCP was released and reacquired multiple times.
  Do not claim that radio or operator alone caused all outages.
- Guest portal could not bind to 10.20.0.1 while its guest SSID was disabled
  and the guest logical interface had no device. Production now has
  `uhttpd.veci_guest.enabled=0` when guest is disabled; full enable/disable
  UAT still remains outstanding.

## Scope of this source change

Production `/usr/sbin/we5927-lte` had **1,032 lines** while the two
firmware source copies in the repository each had **826 lines**. The live
script already contained conservative gateway/HTTPS and PDP diagnostics
absent from the checked-in version. Reconcile both source copies with the
redacted/live-sanitized script before the next image build.

Additional source-only guard for periodic LTE recovery:

1. Do not fall back to `ifup lte` when `ubus ... renew` fails: it may
   release an otherwise working DHCP lease.
2. After a successful renew, allow up to five bounded 2-second local
   gateway checks instead of escalating solely because public ICMP
   is still inaccessible.
3. Recheck local gateway after a short grace period immediately before
   any `ifdown lte` teardown. Preserve Wi-Fi, SIM and modem GPIO state.

These changes reduce **self-inflicted connection flaps**. They do not prove
the underlying 122-minute upstream issue has disappeared, and do not modify
the device in this source-only PR.

## Wi-Fi driver is a separate kernel change

See [PR #7](https://github.com/aicoach-alpha/zbt-we5927-openwrt/pull/7)
and [openwrt/mt76 #1166](https://github.com/openwrt/mt76/pull/1166).
The source-level recovery-deadlock patch applies to the pinned mt76 revision,
but is **not yet built, flashed or hardware-UAT approved**. It does not
itself identify the initial cause of stalled beacons.

## Acceptance before production release

- `sh -n` on both LTE shell files and `cmp` to prove byte-for-byte copies.
- `python -m unittest discover -s scripts/tests -p test_lte_recovery_guard.py -v`.
  Offline test cases: renew request fails without `ifup`; local gateway
  returns during retry; gateway stays absent; conditional teardown only
  after gateway loss persists.
- For a live deployment: preserve signed 25.12.5 image, radio/ART
  calibration, kernel ABI, and verified rollback path; back up the router.
- Check 24+ hours of independent LTE/WAN logs including the former
  122-minute boundary, tracking gateway loss separately from public
  reachability and DHCP renew/release counts.
- Require two phones plus an independent Wi-Fi scanner to continue seeing
  the SSID; validate session login, LTE, SMS, and guest-disabled boot.
  Test guest portal activation separately, with guest LAN isolation.
- Do not publish router configuration archives, SIM identifiers,
  Wi-Fi passwords, or private device telemetry.

**State:** source candidate only. No kernel image built or flashed.
## Verified production LTE daemon cutover — 2026-11-11 15:56 WIB

The **script-only** PR #8 LTE watchdog was deployed on the tested WE5927
via pinned SSH host key and an exact matching GitHub blob
`9b8c9ad5d7792dac19e1a4dab28cec4678383fac` from commit
`cbec5a852f7e74f990e14051366a66967764719b`.
Preflight confirmed local RNDIS carrier, gateway and two public IPs.
Original file hash was verified and old bytes backed up on the office
laptop and router RAM. The file was installed atomically; only
`/etc/init.d/we5927-lte restart` ran. No router reboot, modem reset,
Wi-Fi reload, SIM switching or APN changes. Post-check PASS: LTE route,
gateway and public ping, watchdog `stage=healthy`, and active process.
This is a **point-in-time successful deployment**, not 122-minute cycle UAT.

**Important build regression hazard:** the historical
`source/openwrt-zbt-we5927-current.patch` still embeds the 826-line
legacy `we5927-lte` payload. Applying that older board patch and building
immediately would undo this live fix. After applying the board patch and
before image build, `sh scripts/reconcile-we5927-lte-build-tree.sh <openwrt-source-root>`
**must** run. It checks both repository copies, stages the latest script
into the OpenWrt package tree and verifies byte-for-byte parity. CI tests
this failure mode with a fake legacy package, plus invalid-path rejection.
Never flash an image whose package manifest/source audit lacks this step.
