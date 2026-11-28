# VeCI v2 — functional acceptance matrix for next WE5927-2SIM image

All 39 active modules are represented. Inventory presence and source test references do NOT imply live router acceptance.
Source evidence from a previous commit is stale after current source revisions: only matching-commit native CI receipts may qualify.
No physical testing of the next image has been performed; no signed image or sysupgrade test is being claimed.

| # | Active module | Source tests (scoped) | Known issue IDs | Next-image physical UAT |
|---:|---|---:|---|---|
| 1 | dashboard status | 8 | REL-006, UI-006 | **NOT TESTED** |
| 2 | router login and permissions | 6 | UI-002, REL-005, REL-006 | **NOT TESTED** |
| 3 | interface wan lan | 2 | REL-006 | **NOT TESTED** |
| 4 | dhcp dns static leases | 2 | REL-006 | **NOT TESTED** |
| 5 | ipv6 ra dhcpv6 | 2 | REL-006 | **NOT TESTED** |
| 6 | firewall zones nat | 6 | REL-006 | **NOT TESTED** |
| 7 | port forward dmz | 6 | REL-006 | **NOT TESTED** |
| 8 | static routes policy | 2 | REL-006 | **NOT TESTED** |
| 9 | wifi ap 2g | 5 | WIFI-001, WIFI-002, WIFI-003, WIFI-004, WIFI-005, WIFI-006, WIFI-007, REL-002, REL-006, TOOL-002 | **NOT TESTED** |
| 10 | wifi survey channel | 4 | REL-006 | **NOT TESTED** |
| 11 | wifi clients access control | 4 | REL-006 | **NOT TESTED** |
| 12 | ethernet port status | 3 | REL-006 | **NOT TESTED** |
| 13 | lte rndis data | 8 | WIFI-001, LTE-001, LTE-006, REL-006 | **NOT TESTED** |
| 14 | lte dual sim manual | 7 | LTE-002, LTE-003, LTE-004, LTE-005, REL-006 | **NOT TESTED** |
| 15 | lte apn pin puk | 4 | LTE-002, REL-006 | **NOT TESTED** |
| 16 | sms inbox | 3 | LTE-006, SMS-001, REL-006 | **NOT TESTED** |
| 17 | sms sent and drafts | 3 | SMS-001, REL-006 | **NOT TESTED** |
| 18 | sms send and delete | 7 | SMS-001, REL-006 | **NOT TESTED** |
| 19 | sms multipart pdu | 2 | REL-006 | **NOT TESTED** |
| 20 | sms security and storage | 4 | REL-006 | **NOT TESTED** |
| 21 | system services startup | 3 | UI-001, UI-003, REL-006, UI-004 | **NOT TESTED** |
| 22 | system cron scheduler | 3 | REL-006 | **NOT TESTED** |
| 23 | system logs diagnostics | 6 | REL-006 | **NOT TESTED** |
| 24 | system time ntp | 2 | REL-006 | **NOT TESTED** |
| 25 | system leds buttons | 2 | REL-006 | **NOT TESTED** |
| 26 | system access ssh https | 2 | REL-005, REL-006 | **NOT TESTED** |
| 27 | system backup restore | 5 | REL-006 | **NOT TESTED** |
| 28 | system manual sysupgrade | 7 | REL-001, REL-002, REL-003, REL-006 | **NOT TESTED** |
| 29 | system signed github ota | 5 | REL-003, REL-006 | **NOT TESTED** |
| 30 | system update policy | 6 | REL-006 | **NOT TESTED** |
| 31 | addon signed package manager | 4 | REL-006 | **NOT TESTED** |
| 32 | addon enable disable | 6 | UI-001, UI-003, REL-006, UI-004 | **NOT TESTED** |
| 33 | firmware network watchdog | 7 | WIFI-003, WIFI-007, LTE-001, REL-004, REL-006 | **NOT TESTED** |
| 34 | firmware gpio hardware watchdog | 4 | REL-006 | **NOT TESTED** |
| 35 | firmware 24x7 observability | 7 | REL-004, REL-006 | **NOT TESTED** |
| 36 | guest wifi isolation | 6 | REL-006 | **NOT TESTED** |
| 37 | system ipv6 off by default | 3 | REL-006 | **NOT TESTED** |
| 38 | system ipv6 guarded settings toggle | 3 | REL-006 | **NOT TESTED** |
| 39 | ui four group navigation | 6 | WIFI-006, UI-002, UI-003, REL-001, REL-006, TOOL-001, UI-004, UI-006 | **NOT TESTED** |

## Required next candidate acceptance

- Firmware source gate: all exact source hashes, real CI unittest transcripts, no unresolved source-level safety failures
- ROM gate: every active module present in extracted SquashFS with exact content, including Wi-Fi AP preparation helper
- Signing gate: board/target metadata, trust anchor, ucert signature, sysupgrade -T on physical WE5927, correct partition sizes
- LTE: SIM1/SIM2 selector, CPIN, registration/attach/PDP, usb0 address/default route, DNS and public HTTPS; single-failure rollback without extra power-cycle
- Wi-Fi: secure first boot, WPA2 SSID, beacon from client, authentication, DHCP/DNS/internet, channel, ACL/client controls, MT76 fault logs
- GUI: login/access permissions, actual desktop/mobile browser, every visible form/button, correct RPC destination, no ghost controls, reliable error states
- SMS: real modem send/receive, inbox/sent/drafts/deletion, multipart/PDU, proper locking and no unrelated modem resets
- Networking: LAN switch ports, DHCP, firewall/NAT, port forwards, DNS, IPv6 off, guest isolation and rollback
- System: time/cron, logs, backup/restore, package manager, signed OTA, GPIO watchdog, continuous link monitoring
- Endurance: real 72-hour LTE and Wi-Fi measurement only AFTER approved candidate is safely flashed

**Release policy:** a source-only PASS never authorizes a flash. The owner has one physical router; preserve the currently working connection until independently approved hardware UAT.

### Wi-Fi AP operational snapshot (source development only)
- **Implemented:** primary AP BSSID/interface and cumulative RX/TX from read-only sysfs in the existing Wi-Fi info API and GUI. Station reconciliation remains iw/hostapd-based.
- **Source verification:** pinned UCI/libubox fixture and JS render regression. Source acceptance receipts are refreshed when implementation hashes change.
- **Physical acceptance:** NOT RUN on the new firmware; zero-station observations do not prove driver failure or fix. No production router changes.
