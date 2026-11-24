# VeCI guest portal hardening — source-only, 2026-11-11

## Production evidence

VeCI MT7628AN/WE5927 can enter `mt76` kernel deadlock during radio reload.
On 2026-11-11, two phones and a separate Windows Wi-Fi scan lost the
primary SSID. A manual reload hung with `MCU message 08 timed out`, and
`hostapd` plus `rpcd` entered uninterruptible sleep. After reboot,
the primary SSID and login returned. The root cause of original beacon
disappearance remains under investigation in firmware PR #7.

Guest SSID was configured `disabled=1`, guest uhttpd listener `enabled=0`;
the guest interface was `NO_DEVICE` while disabled, which is expected.
One early boot `bind(): Address not available` was seen before the
runtime service recovered; a clean-boot and active guest UAT are still required.

## Source changes

The sanitized production `/usr/libexec/rpcd/veci.app.guest` source has
been captured in this firmware repository at
`source/veci-guest/veci.app.guest` with conservative changes:

- **Provision action** only stages UCI while guest is disabled.
  It no longer restarts all network services or reloads radio0. Such
  disruptive operations are postponed to the explicit enable action.
- **Repeated disable action** does not reload the primary radio when
  guest was already disabled; active guest still triggers one reload.
- **Rollback** reloads Wi-Fi only when a guest AP had actually been enabled
  before rollback.
- **Status** is active only when uspot, guest radio and guest uhttpd are
  all configured active.

The procedure remains a **source candidate**; no image or hardware UAT is
implied by these tests. Sensitive device-specific configuration is not
included.

## Tests and roll-forward gates

- `sh -n source/veci-guest/veci.app.guest`.
- `python -m unittest discover -s scripts/tests -p test_guest_startup_guard.py -v`:
  six offline mock tests for provision/rollback/repeated disable.
- Before a live guest enable test, deploy only via atomic copy with
  exact source hash, known rollback file, preserved file owner/mode,
  and stable Ethernet administration. No test should intentionally
  reload radio0 until the mt7603 kernel fix has passed hardware UAT.
- Validate admin login, Wi-Fi broadcast, client isolation, LAN firewall,
  DHCP, DNS, captive redirect, and service startup on cold boot.
- Keep guest disabled by default; never silently open the unsecured SSID.

Do not merge this into a release without the exact package integration
and complete device testing.
