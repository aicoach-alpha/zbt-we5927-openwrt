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
