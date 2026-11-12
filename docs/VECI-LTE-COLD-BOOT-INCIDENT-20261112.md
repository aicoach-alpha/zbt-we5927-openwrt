# WE5927 LTE cold boot incident — 2026-11-12

**Severity: active user connectivity incident.** No unverified production changes.

## Screenshot evidence (do NOT upload raw screenshots to public GitHub)
- The modem-local management page indicates SIM/IMSI error, operator unavailable, cellular data shown as disabled and no cellular IPv4 PDP data; it nevertheless advertises its own local USB-RNDIS gateway. The displayed `99` signal code may be the 3GPP `AT+CSQ` sentinel for *unknown/not detectable*, not actual +99 dBm. Confirm from AT logs rather than guessing the vendor rendering.
- OpenWrt LuCI shows RNDIS `usb0` IPv4 acquired and gateway reachable while cellular registration/operator/packet information is missing; VeCI mobile status shows no Internet.
- User reports Wi-Fi SSID visible before Ethernet LAN, LAN slow, LTE still unavailable after 10 minutes.
- LTE router-native page has a clock reading that may not match the OpenWrt clock; certificate-based HTTPS probes must not be treated as proof of loss without checking time.
- Do not copy IMEI, ICCID, SMS, Wi-Fi credentials, or proprietary APN/user information into public logs.

## P0 source findings
1. `/etc/hotplug.d/usb/30-we5927-lte` previously spawned a background worker after a fixed **2-second delay**, invoked `usb-repair`, and unconditionally called `ifup lte`. This can collide with ongoing netifd modem enumeration / DHCP and produce self-inflicted link flaps.
2. `/etc/init.d/we5927-lte` declared reload triggers on `network` and `firewall`, potentially restarting the LTE manager when only unrelated configuration changed.
3. LTE `ensure_network()` performed UCI network commits and firewall reload at daemon startup. This can reconfigure the MT7628 Ethernet switch and delay LAN availability. The new code checks expected lte device/protocol and **does not write UCI at runtime**. First-boot `uci-defaults` remains the sole owner of initial provisioning.
4. LTE startup treated local RNDIS DHCP address+gateway as sufficient to defer all modem initialization even if no operator registration or cellular PDP. The new **read-only** `modem_readiness_phase()` distinguishes USB device, AT availability, SIM READY/PIN/PUK, LTE registration, and packet attached/detached, without querying identities or sending a modem control AT command. It records a sanitized phase in `/tmp/veci-lte-performance.state`.
5. `status-fast` previously labeled the modem **online** when only local gateway and IPv4 existed. New status separately reports `data_link_up`, `internet_verified`, and `modem_phase`; Internet verification requires a **fresh** healthy/HTTPS stage.

All source-only changes in draft PR #18, inherited into draft RC PR #16. They are not installed in the running router.

## Read-only diagnostics on physical router (wired admin path)
Once SSH access is available, run from the authorized local Windows management terminal:

```powershell
ssh -T root@192.168.1.1 'echo UPTIME; uptime; echo RNDIS_LINK; test -e /sys/class/net/usb0 && echo PRESENT || echo MISSING; echo AT_TTY; test -c /dev/ttyUSB2 && echo PRESENT || echo MISSING; echo INTERFACE; ubus -S -t 2 call network.interface.lte status | jsonfilter -e "@.up" -e "@.pending" -e "@.available"'
ssh -T root@192.168.1.1 '/usr/sbin/we5927-lte status-full | jsonfilter -e "@.sim_status" -e "@.registration_status" -e "@.packet_status"'
```

No sysupgrade, `ifup/ifdown`, Wi-Fi reload, SIM GPIO write, CFUN, or power-cycle is used. These commands print only selected public diagnostic fields. The second command can briefly contend for the serialized AT channel and may fail closed if SMS access holds it; do not force unlock. If the router has an inaccessible/unknown SSH host key, verify its fingerprint through an independent trusted channel rather than disabling strict checking.

Also inspect the modem-native management UI from the local network. Confirm whether **Cellular Data** is truly disabled, whether SIM is physically present and `READY`, and whether the correct operator/APN is selected. Changing these values is a separate, intentional modem-level action; never assume `Current SIM Slot: 0` necessarily means no SIM because vendor slot numbering is model-specific.

If SIM status fails to reach READY or vendor UI displays an IMSI error persistently, investigate SIM seating, SIM GPIO/slot, PIN and modem firmware/power before attempting LTE DHCP tricks. Re-seat the SIM only with router safely powered off during an acceptable outage.

## Required UAT / go-no-go
- During cold boot: LAN DHCP comes up without LTE manager modifying UCI; Wi-Fi beacon present from independent external scanner; AT and RNDIS appear as separate milestones. Measure actual timestamps rather than assuming order from visual UI.
- Modem readiness result consistent with real vendor UI and registered operator. No `AT+CPIN/AT+CEREG/AT+CGATT` side effect, no use of IMSI/ICCID/IMEI and no SMS lock contention hang.
- Public Internet health remains independent from local RNDIS DHCP gateway. An ICMP-only failure must not trigger radio reset or DHCP release.
- Three or more ~122-minute intervals and 72h external SSID/Internet observation with coverage >=99%, hardware UAT.
- Full firmware build and host-arch `fwtool` metadata gate, exact image size, signed trust anchor, backup and rollback BEFORE production flashing.

**This change mitigates self-inflicted boot flaps and false status. It cannot guarantee operator registration if SIM or cellular data is disabled in the modem itself.**
