# VeCI MT7628 Wi-Fi Guardian: fail-safe mitigation

On 2026-11-11 the WE5927's 2.4 GHz SSID repeatedly vanished from an independent
laptop scan and two phones while `radio0.up=true` and hostapd reported
`ENABLED`. Kernel debugfs `/sys/kernel/debug/ieee80211/phy0/mt76/reset`
recorded `RX PSE busy stuck: 1` since boot. A prior `wifi down/up`
entered `mt76_wmac MCU message 08 timed out` and made hostapd and rpcd
uninterruptibly sleep. Neither an `up` status nor hostapd is evidence that
a beacon is detectable by external devices.

**Mitigation candidate, not a driver fix:** make Guardian observe-only
until PR #7's actual MT7603 driver build passes signed image and hardware
acceptance. The old Guardian could execute `wifi up radio0` autonomously
after repeated missing-AP checks, which is unsafe on this firmware.

- Use bounded local ubus (3-second timeout) for netifd + hostapd health
  instead of issuing `iw` commands which can hang in the kernel.
- Report `beacon_verified=0` honestly in tmpfs state. Keep `wifi=ready`
  for backward compatibility but define it only as AP runtime readiness.
- Observe cumulative MT76 RX PSE reset counts. Warn if the count rises,
  not simply because a previous reset persists.
- Report `manual_recovery_required` instead of automatic radio mutation.
- `auto_recover=0` in effective state regardless of legacy configuration.
  This intentionally trades automatic reconnect for avoiding a known
  kernel/login deadlock. Admin must not misinterpret the old `auto_recover=1`
  UCI value as an effective command.
- No client MACs, SSIDs, passwords or location data are emitted.

This does not fix intermittent beacon stalls; monitor with independent
external clients until a verified driver update is deployed. Never run
this source as an unattended cron job from a Windows laptop. The user's
`VeCI-External-Monitor` scheduled task remains disabled.

**Acceptance:** sh syntax + offline mock tests; compatible runtime ubus
syntax check; exact source/hash staging; atomic on-device install with
rollback copy; no radio reload or network restart; live check/status
and a minimum 24–72h counter and external SSID monitoring.

## Live script cutover verified — 2026-11-11 ~16:15 WIB

The **script-only** Guardian mitigation was deployed to the tested router.
The deployed source matched GitHub blob
`c74fe19acfe4ba3010b4bff59769dc39d89a3628`, and the existing
source hash matched the recorded production baseline before replacement.
Verified backups remain on the office laptop and in router tmpfs.
Staging and shell syntax passed; an atomic replacement followed by a
**Guardian daemon-only restart** succeeded. No radio reload, LTE/modem
reset, router reboot or Windows scheduled task enablement occurred.

Post-check reported
`wifi=ready failures=0 auto_recover=0 beacon_verified=0 rx_pse_resets=1`.
At 16:16, independent Windows SSID scans passed 3/3, local gateway and
public IP pings passed, DNS and HTTPS passed, `hostapd` and `rpcd` remained
running. Both Linux CI 6/6 and Windows Git Bash 6/6 tests passed after a
Windows-path and test-PATH compatibility correction.

**Interpretation:** This stops a known dangerous auto-recovery path; it
does not demonstrate beacon durability or address the root driver failure.
Keep long-term Wi-Fi and 122-minute LTE acceptance separate.
