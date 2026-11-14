# VeCI ZBT-WE5927 full-native release contract

Status: **DEVELOPMENT ONLY; NO NEW FIRMWARE APPROVED**. No source work below is
proof of installation on the physical router. Last audited binary: commit
`4fa427d886d6fa273a8b10355309e46a452c9139`, OpenWrt 25.12.5,
5,898,530 bytes; the stock /www/index.html still redirected to LuCI.

## User-facing acceptance (read against actual image, not only source)

| Requested capability | RC1 binary 4fa427d | Requirement for final VeCI release |
| --- | --- | --- |
| Native VeCI default GUI | **Partial**: uHTTPd defaults prefer VeCI; root index **redirects LuCI** | Router root opens VeCI even after sysupgrade retaining configs; LuCI not routine UI (retain only emergency fallback until verified parity) |
| Complete native UI navigation | **Partial**: 11 pages, many older appearance patterns; Expert links to LuCI | Native Home, Internet, Wi-Fi, Devices, Cellular, Hotspot, Security, Network, System, Updates, Apps all operable; no false success |
| Wi-Fi MT7603 | Driver fix and observe-only guardian bundled | Physical SSID+BSSID scans on >=2 clients, no hang under load; independent counters and 72h evidence |
| LTE RNDIS/reconnect/SIM | Source bundled and offline gates passed | Live modem readiness, no self-induced DHCP flaps, LTE 72h monitoring with >=99% coverage |
| SMS Center | Native rpcd SMS inbox/send/delete, drafts/sent handlers and web UI present | Verify real SIM/modem inbox, read, copy, delete, reply, sent, drafts, multipart and AT lock on physical device |
| Operator-authenticated quota / USSD | Failed historical integration retired | OUT OF SCOPE for this release. Do not add carrier API, OTP, USSD or operator quota adapters. |
| Guest portal | Catalog descriptor and Hotspot page only; **no** guest RPC or captive portal in ROM | Optional add-on. Offline safety tests required for source; live Guest Portal UAT optional, not a base-release blocker. Do not auto-enable. |
| Voucher manager | Catalog descriptor only; **no** voucher RPC or credential engine | Optional add-on. Offline create/revoke/expiry/batch/cleanup tests required; physical Voucher UAT optional, not a base-release blocker. |
| Data meter | Not yet verified as working integrated counter in this image | Native LTE data-usage counter; optional locally entered estimate remains clearly labeled, never presented as actual operator quota |
| Router Apps | Catalog UI and constrained signed feed verifier; no `/etc/veci-release.json` in old image | Correct build metadata and matching **published, signed** feed, real APK install/remove/rollback; never install mismatched packages |
| Native configuration | Several native UI controls, some LuCI Expert fallback | Full native internet, Wi-Fi, DHCP, firewall, DDNS/VPN/speed controls and access security with targeted tests |
| OTA firmware | UI/rpcd validation present, signature gate blocks unsigned image | End-to-end verified-image flow, upload, sysupgrade -T, backup and rollback, no arbitrary force flash |
| Release identity | **Absent** from 4fa427d image | Visible full SHA-derived build identity from image filesystem; exact source/firmware matching |
| Release deployability | Image size, board and hash checked | Hardware compatibility, safe wired upgrade and recoverability; no repeated build loop |

The feature integration branch stages the root VeCI landing, exact commit
manifest, cache-busted client assets, native LTE Data Meter package and
reconciled source for Guest/Voucher/SQM/DDNS/WireGuard.
The optional app packages are source-staged, not installed in ROM. Guest and
Voucher remain independently installable after a matching-build signed APK
feed exists. Their physical UAT is optional and never blocks base-firmware
release; if not run, show those apps as unverified rather than tested.
Carrier-authenticated quota integration has been removed from the
active codebase after unsuccessful trials. This is NOT a release blocker.
The native LTE Data Meter and optional user-entered local estimate remain;
neither is actual carrier quota. This does not complete the base firmware
backlog. Firmware signing/compatibility, router recovery and core network
hardware acceptance remain separate requirements.
