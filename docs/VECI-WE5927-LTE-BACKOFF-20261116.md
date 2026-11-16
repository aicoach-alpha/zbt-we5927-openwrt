# VeCI WE5927 LTE watchdog backoff after post-flash outage

Evidence received from physical router on 2026-11-16 (Asia/Jakarta):
- Earlier 192.168.7.186/24 on usb0, default route via 192.168.7.1,
  local gateway ping 2/2 success but public ICMP 0/2.
- Later the SSH tunnel failed Network unreachable from the router.
  Direct modem HTTP port 80 timed out. Public HTTPS request failed with
  Operation not permitted. This does not alone prove radio disconnection.
- During 13:27:56-13:30:55, we5927-lte logged repeated DHCP renew and
  interface recovery about 55 seconds apart.
- /tmp/veci-lte-performance.state reported at_busy_or_unavailable. This is
  not proof that the modem/SIM is defective; serial may be locked or the
  interface may be temporarily absent during USB reconnect.

Code change: preserve existing conservative gateway and radio checks; add
per-process 120-second retry cooldown for automatic DHCP renew and 300-second
cooldown for LTE teardown/restart. When cooldown is active, the daemon does NOT
escalate to CFUN, power cycling or SIM switch on that pass; it allows netifd
and the modem time to recover. No default APN/DNS/router firewall changes,
no new LuCI, and no retired Data Meter/quota code.

Safety: tests are simulated, not a field-proven fix; this change by itself
does not establish stable Internet and must not be blind-flashed until tested.
For immediate isolation on the office laptop, temporarily stop ONLY the
we5927-lte watchdog (/etc/init.d/we5927-lte stop); do not stop network
or usb0. This preserves netifd/DHCP but disables watchdog recovery until
/etc/init.d/we5927-lte start. Record before/after gateway, external HTTPS,
link/route status and watchdog logs.
