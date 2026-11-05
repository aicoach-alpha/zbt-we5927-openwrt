# VeCI Reliability Logger — ZBT WE5927, W907-EC

## Goal and collection
Persist non-PII reliability data for at least 72 hours. This logger is
not a router speed optimizer and proves no world record.

Every 60 seconds collect: LTE IP/gateway and two outbound cellular ICMP
targets, Wi-Fi radio0 AP presence, WAN and Wi-Fi interface RX/TX counters,
Wi-Fi station count and signal/link rate, router uptime, available RAM,
1-minute load and existing LTE/Wi-Fi recovery monitor stages.
No MAC, SSID, SIM identity, phone number, SMS or password is logged.

Every five minutes: flush one aggregated CSV row to persistent overlay.
A six-hour optional low-volume active download uses only 512 KiB of test
payload (about 2 MiB/day, ~6 MiB over 72 hours). HTTPS validation applies.
No upload test. This limited probe measures neither maximum WAN capacity
nor maximum Wi-Fi throughput.

Files: /overlay/veci-reliability/samples-YYYYMMDD.csv,
probe-YYYYMMDD.csv, summary-YYYYMMDD.txt and latest-72h-evaluation.txt.
The directory is root-only (0700), survives reboot, rotates old day logs
after seven days, and stops persistent writes below 250 KiB free overlay.
Minute samples buffered in RAM may be lost on an abrupt reboot.
Procd starts logger on boot. Clock must synchronize for sampling.

## How to inspect
veci-reliability status
veci-reliability report 24
veci-reliability report 72
ls -lh /overlay/veci-reliability/

An eligible 72-hour assessment requires full timespan and at least
90 percent of 864 expected five-minute windows. Insufficient duration or
coverage is NOT a pass. Real classification should examine packet loss,
RTT, measured outage events, reboot frequency, RAM pressure and peak
actual traffic. For claims of fastest Wi-Fi, add an independent Wi-Fi
client throughput benchmark and a comparable baseline/other router.

The logger does not switch SIM, reset modem, restart network/Wi-Fi,
send/delete SMS, modify channel or credentials, or run an unbounded
speed test. Installer is additive, rollback preserves collected logs.
