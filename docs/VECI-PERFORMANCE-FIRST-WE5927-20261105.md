# VeCI Performance-First – WE5927 MT7628AN / W907-EC (2026-11-05)

Goal: minimize LTE outage recovery time and Wi-Fi AP downtime without
unnecessary modem resets, unverified speed claims, interference-triggered
channel changes, or losing important SMS and management features.

Hardware: only integrated 2.4 GHz MT7628 radio. Current operator configuration
(2026-11-03 backup) uses HT20, channel 1, country ID, and WPA2/WPA3 mixed;
do not override this in a generic release or claim 5 GHz capability.

LTE:
- New factory defaults 10-second monitor / three consecutive failures,
  not 30 seconds / six failures (preexisting UCI settings are preserved).
- First stage renews LTE DHCP via netifd ubus. Second stage reinitializes
  ONLY the LTE network interface when upstream and gateway both fail.
- A still-responsive RNDIS gateway is not evidence of a broken modem.
- Escalate to CFUN only on repeated confirmed failures; use one exclusive
  /var/lock/we5927-at.lock across the transaction, avoiding concurrent SMS.
- Require missing link/IP or detached packet service for hard power-cycle
  after repeated failures, limited to one per 900 seconds.
- Automatic SIM failover remains opt-in and gets 1800-second cooldown.
- Never probe W907 USB interface 1.5 (/dev/ttyUSB3). Only 1.4 is verified.
- Service reload preserves an already healthy RNDIS+DHCP session.
- UCI commits are idempotent on an unchanged modem/SIM configuration.

Wi-Fi Guardian:
- 30-second checks, three consecutive failures, 900-second cooldown.
- Single supported radio0, AP admin-enabled only. Station-safe checks
  prevent recovery if clients are present or the driver state is unknown.
- Only re-run wifi up radio0 after a missing AP; NEVER auto change channel,
  SSID, HT20/HT40 width, country, credentials or TX power.
- All runtime monitor state in tmpfs, no flash writes on each sample.

Home UI:
- Read-only performanceStatus RPC with no extra modem probing.
- Show LTE/Wi-Fi state, failure counts and configured intervals.
- No fabricated throughput, latency, percentages or permanent healthy state;
  status expires if monitor stops or timestamps are stale.
- Keep Cellular SMS, network recovery, security and existing user features.

UAT/rollout requirements:
- Preserve router configuration, SMS history, UCI and authorized SSH keys.
- Stage and install file overlay before integrating a signed firmware.
- Do not interrupt an active connection for benchmarking.
- Simulate: single ping loss, dual ping loss with gateway alive, DHCP
  renewal, LTE ifdown/ifup, modem AT busy, radio absent/present, clients
  connected, stale status, watchdog cooldown and 30-minute endurance.
- Physical before/after comparison: packet loss, median/p95 RTT,
  actual measured LTE restoration duration, 2.4GHz Wi-Fi client reconnect
  counts, throughput in both directions, CPU/RAM pressure and 24h uptime.
- Do not declare FULL LIVE or 'fastest' on source tests alone.
