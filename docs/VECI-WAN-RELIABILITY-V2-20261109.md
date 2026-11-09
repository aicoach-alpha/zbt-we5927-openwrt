# VeCI WAN Reliability V2 — gateway-first and non-disruptive diagnosis

## Evidence
From user-supplied 72h sample archive (Nov 5–9, 2026):
- 863/864 persisted five-minute samples, 99.9% coverage.
- 60 out of 4,315 one-minute dual-target ICMP checks failed; 29
  failure clusters with approximately 122-minute recurring cadence.
- LTE gateway check 100%, Wi-Fi AP status 100%, zero observed reboots.
- No individual five-minute window with all five checks failed.
- Only 11/12 small HTTPS downloads succeeded (512 KiB), so ICMP
  failures are NOT yet proven user-visible broadband downtime.
- Wi-Fi RSSI is contaminated by -1 sentinel when no clients are attached.

## Root-cause risk confirmed in code
Old LTE watchdog attempted netifd DHCP lease renewal before checking
whether RNDIS IPv4 gateway was responding. This could disturb an
otherwise healthy LTE DHCP session for ICMP-only failures. The
122-minute cadence origin is NOT confirmed by prior aggregate logs.

## Fix
- Gateway first. With a responding LTE gateway, never renew DHCP,
  bounce LTE, issue AT+CFUN, power-cycle modem, or switch SIM based on
  ICMP-only failures.
- When repeated dual-target ICMP failure occurs, send one bounded
  5-second CA-verified IPv4 HTTPS diagnostic probe (cooldown 90s),
  classifying ICMP-failed/HTTPS-ok vs both-failed.
- Write bounded event CSV, root-only under the existing protected
  /overlay/veci-reliability directory; skip when overlay free <300KiB.
  No identifying SIM, GPS, credentials, APN, or client MAC data.
- Missing gateway/local IPv4 -> existing guarded DHCP renew, then
  guarded interface recovery as previously. Existing hard reset
  15-minute cooldown and SIM failover opt-in remain unchanged.
- Service start with healthy LTE never drives modem power GPIO or
  SIM GPIO, minimizing daemon-only restart risks.
- Exclude wifi RSSI sentinel (no associated client) from 24/72h
  report; retain prior CSV schema for continuity.
- Report new diagnostic event counts without rewriting prior samples.

## Rollout and verification
Versioned three-file overlay install (LTE monitor, logger, new
reference docs only in GitHub). Backup original monitor/logger files
to OFFICE LAPTOP and verify hashes. Stage in /tmp, atomic replace.
Armed rollback failsafe. Restart only the LTE watchdog *daemon* using
procd (not LTE network, modem, firewall or Wi-Fi). Logger daemon
script updated but not restarted; report subcommand loads new file
without service restart. Keep existing IPv4-only, SMS, Wi-Fi guardian,
APN, DHCP config, and historical CSV logs intact.

Check via:
- /usr/sbin/we5927-lte status-fast (existing LTE RPC)
- /usr/sbin/veci-reliability report 24
- /usr/sbin/veci-reliability report 72
- /overlay/veci-reliability/wan-health-YYYYMMDD.csv

New accuracy must be assessed over a fresh 24–72 hour window. Prior
evidence does not prove the 122min cadence was fixed.
