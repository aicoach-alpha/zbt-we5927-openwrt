# WE5927 Wi-Fi BSS missing after initial startup

## Verified observations (office unit, 2026-11-17)
- OpenWrt radio0 reports up=true in network.wireless status.
- wpad service says running; /usr/sbin/hostapd global process exists.
- ubus does NOT expose hostapd.phy0-ap0; phy0-ap0 does not exist in ip link.
- File /var/run/hostapd-phy0.conf exists, but existence does not establish
  successful AP activation. Never print this file in logs; it may hold PSK.
- dmesg shows the AP entering/leaving br-lan several times, with last removal
  around 1139 seconds of uptime. No specific mt76 MCU timeout in supplied
  excerpt; cannot conclude kernel driver crash from these lines alone.
- Original LTE lease remained stable after 2026-11-16 17:08 and renewed every
  six hours thereafter. Historic LTE DHCP-flap logs predate the earlier
  duplicate-netifd correction and are not fresh evidence of LTE failure.

## Reason for a source change
The observe-only Guardian previously reset failures at each threshold and
logged "AP runtime unavailable" every approx 90 seconds while the BSS was
missing. Repeated warnings can fill the router's small in-memory syslog and
hide the original hostapd/radio0 setup failure. A real failure persists in the
status state; the warning now logs once for each continuous outage and re-arms
only after the AP returns or Wi-Fi becomes intentionally disabled.

The provider also now recognizes manual_recovery_required and
driver_reset_observed, which were previously filtered out of the read-only
status payload. Home shows an explicit error instead of hiding the stage.

## Recovery policy
Observe only; no automatic Wi-Fi reload, radio power-cycle, kernel module
rebind, APN change, LTE reset or flash action. Before an approved recovery,
capture: hostapd global service, radio0 state, filtered hostapd/netifd logs
around initial AP teardown, relevant UCI options excluding credentials, and
external AP beacon visibility. The exact root cause and 72-hour radio UAT are
still open. The current installed build is unchanged.
