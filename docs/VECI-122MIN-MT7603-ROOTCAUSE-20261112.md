# VeCI 2026-11-12 — 122-minute LTE interruptions, MT7603 hidden SSID and stable speed

**Status: investigative/staged only. No router/firmware changes.** Relates to #12 and draft PRs #7 (MT7603), #8 (LTE), #9 (guest), #10 (Guardian), #11 (external SSID UAT), #14 (minimal UI). No upstream experiment justifies an unconditional production driver tweak.

## Evidence and internet literature
1. OpenWrt RNDIS setup: https://openwrt.org/docs/guide-user/network/wan/wwan/ethernetoverusb_rndis
   - USB interface `usb0`, DHCP via modem and possible double NAT. Check modem LAN subnet does not conflict with router LAN. Do not switch to QMI/MBIM without proving this hardware exposes those interfaces.
2. OpenWrt-devel 2026-10-03 RFC on stale RNDIS host DHCP addresses after cellular reattachment: https://mail-archive.com/openwrt-devel@lists.openwrt.org/msg68438.html
   - Compare host lease vs modem IP *only for direct-PDP-IP modems*. NAT RNDIS devices are explicitly different; do not compare `AT+CGPADDR` blindly on CX07E.
3. Two-hour DHCP lease renewal seen in a separate modem: https://forum.gl-inet.com/t/gl-x3000-rm520n-gl-loses-packet-service-and-re-registers-every-30-33-minutes/69888
   - 7200 seconds = 120 min. Extra ~2 min might be observer/recovery latency, NOT proof of lease expiry. Need timestamps, lease time and release/rebind/route evidence across 3+ cycles.
4. MT7628 SSID disappearance under heavy load and mt7603 beacon/RX PSE fixes: https://lists.openwrt.org/pipermail/openwrt-devel/2023-August/041449.html
5. MT7603 frames buffering stalls and experimental debugfs knob: https://lists.openwrt.org/pipermail/openwrt-devel/2024-April/042864.html . Verify driver exposes `frames_buffering` before any lab trial; no production write to debugfs without baseline and rollback.
6. OpenWrt stable 25.12.6 release: https://github.com/openwrt/openwrt/releases/tag/v25.12.6 . It includes mt76 fixes for other chipsets and security updates. Do not assume it fixes MT7603 specifically. Re-pin PR #7 against the actual 25.12.6 mt76 revision before compiling.
7. OpenWrt software flow offloading: https://openwrt.org/docs/guide-user/perf_and_log/flow_offloading . Software fastpath can reduce CPU forwarding cost, but hardware flow offload MT7628 support is not demonstrated. Do not add advanced SQM or heavy proxies while diagnosing link stalls.

## Prior production evidence (2026-11-11)
- `hostapd=ENABLED` with SSID absent in independent scans; `RX PSE busy stuck`, MCU message 08 timeout after radio reload, uninterruptible D-state for management daemons.
- WAN repetitive ~122-minute public reachability degradation and DHCP lease release/reacquisition in coincident window; diagnosis incomplete.
- PR #7 addresses a **secondary reset deadlock**, not missing beacon root cause; #8 avoids unnecessary DHCP/interface flaps but is source-only.

## Decision table: do NOT reboot on a single remote ping failure

| Signals | Likely class / next action |
| --- | --- |
| USB device lost + kernel USB disconnect | USB transport, power, modem crash, cabling; inspect power and USB errors |
| USB remains + no IPv4/route/local gateway | Lease, RNDIS DHCP stale data or link; bounded renew ONLY after repeated local failures, preserve SMS |
| USB and local gateway healthy + public ICMP fails but HTTPS works | ICMP blocked/remote target; **do not renew, reset modem or flap network** |
| USB/gateway healthy + ICMP and HTTPS fail | PDP/operator, routing, congestion or packet path; AT diagnostics when serialized and proven safe; avoid automatic modem reset |
| External laptop Wi-Fi scan misses SSID + hostapd enabled | Beacon/mt7603 driver stall, check reset counters; **never auto `wifi up`** while D-state risk persists |
| `hostapd` stops but external beacon remains | Control-plane fault; do not treat as radio-down without outside scan |
| Local LAN/LTE OK but UI unresponsive | rpcd/uhttpd/web service; no blanket network restart |

## Wired-only evidence collection without router writes
Prerequisites: laptop on Ethernet of the WE5927, Python 3, Windows OpenSSH, known working SSH private key and a **previously verified** `known_hosts` pinned entry for the router. Do not discover/accept a new host key automatically. Do not run from an unrelated LAN. No credentials or SSH private key are uploaded to GitHub or ChatGPT.

From the project checkout on the **wired laptop**, with PowerShell (provide paths to files already present):
```powershell
python scripts/veci-link-wired-monitor.py --host 192.168.1.1 `
  --key "C:\path\to\existing_key" --known-hosts "C:\path\to\verified_known_hosts" `
  --ssid "YOUR-SSID" --hours 72 --interval 30 --out ".\veci-link-72h.jsonl"
python scripts/veci-link-analyze.py .\veci-link-72h.jsonl --interval 30
```
`--ssid` is optional and **never written**; external scan only on Windows. The monitor pipes a read-only shell snapshot over SSH stdin; no remote files, no AT commands, no Wi-Fi reload, no service restart. It stores only whitelisted scalar counters on the laptop, not SSID names, IPv4 addresses, MACs, APNs, IMSI/IMEI or SMS content. Router `logread` counters are *ring-window estimates* and can wrap, so negative deltas are inconclusive.

Analyze at least three repeated WAN down edges and all independent SSID scans. Verify local reachability, DHCP lease T1/T2/expiry and USB/PDP status using captured timestamps. Public ICMP alone cannot establish a real disconnection. A 72h run is a target, not a guarantee of >99% sample coverage; report actual coverage and collection gaps. If the wired laptop sleeps, UAT is invalid.

## Safe speed optimization sequence
1. Baseline with one LAN Ethernet client, a second wired host if possible, and external client Wi-Fi SSID scans. Identify actual 10/100 link, Wi-Fi HT20 negotiated PHY, modem LTE category/USB mode and current radio band. Never infer measured WAN throughput from a 300 Mbps Wi-Fi PHY claim.
2. Repair MT7603 crash and source/counter evidence before throughput tweaks. Stable baseline: 2.4 GHz visible SSID, HT20, non-overlapping channel 1/6/11 chosen by survey, country code correctly set, WPA2-AES for compatibility where WPA3 transition causes issues; disable unused guest AP until independently validated.
3. A/B test software flow offload in a controlled window only AFTER wireless stability validation; compare wired NAT forwarding, CPU load, latency and packet loss. Never force hardware flow offload on MT7628 or enable SQM unconditionally on single-core 580MHz CPU.
4. Avoid intrusive continuous speed tests over LTE; compare repeated short download/upload and latency at similar locations/conditions and track RSRP/RSRQ/SINR (when modem reliably exposes them) and thermal/power issues. Ethernet 100 Mb/s is a hard PHY limit on wired interfaces; realistic payload throughput is lower. LTE module category, cell and data plan may impose lower limits.
5. Do not change RNDIS transport to QMI/MBIM or flash a newer kernel until confirmed VID:PID, descriptors, interface drivers, exact ABI and lab hardware UAT.
6. Definition of done: 72h >=99% monitor coverage, independent SSID visible across load/rest tests, zero MT7603 MCU deadlocks, 3+ potential 122-minute intervals observed without self-inflicted DHCP flaps, measured WAN outage duration trend and headroom in RAM/CPU, rollback assets intact.
7. **True zero LTE downtime cannot be guaranteed on a single modem/carrier.** If radio network/ISP actually drops, seamless continuity requires redundant independent WAN and tested automatic failover (with its own reconnection limitations). Aim instead for zero *self-inflicted* downtime.
