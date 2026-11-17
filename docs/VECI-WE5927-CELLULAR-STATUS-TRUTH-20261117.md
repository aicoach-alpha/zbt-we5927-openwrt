# VeCI cellular link vs Internet reachability — source fix

## Field evidence

On the physical router the modem gateway was reachable, USB0 had a
192.168.7.x DHCP address/default route, and router-originated Internet ICMP
succeeded 30/30 attempts in a 15-sample observation window.

Yet the installed VeCI Cellular page rendered "Data link down" and
"Internet Unavailable". On the 2026-11-17 office wired UAT, three router
ICMP samples all succeeded while Wi-Fi AP runtime failed.

## Root cause in the installed 75433f7 image

The modem manager provides independent status_fast_json fields:

- data_link_up: live usb0 IPv4 plus default gateway;
- internet_verified and online: time-limited daemon monitor state.

The veci.cellular RPCD provider discarded data_link_up and internet_verified,
so the Cellular UI reused online for physical link state. When online was false,
it displayed "Data link down" even if an LTE IP and gateway were present, and
never called internetStatus for an independent read-only reachability check.

## Corrected logic

- Provider passes both data_link_up and internet_verified, preserves online
  for legacy callers.
- UI uses data_link_up for the LTE link badge, with IPv4+gateway fallback
  for older providers. Independently calls router Internet check whenever
  the LTE link is present; it cannot reconnect modem or reload Wi-Fi.
- The router Internet check allows up to two seconds per ICMP target.
  Failed public ICMP probes without other evidence yield "Not verified",
  not the categorical "Unavailable".
- Even a verified router uplink does NOT prove LAN/Wi-Fi client NAT/DHCP;
  dedicated client tests are still required.
- The modem's own WLAN setting ("Disabled" in 192.168.7.1 admin UI) is
  distinct from the ZBT-WE5927 OpenWrt MT7603 Wi-Fi radio. Wi-Fi runtime
  failure cannot be diagnosed from the modem's WLAN toggle alone.

## Deployment gate

Source and simulated contracts are not proof of router deployment.
Requires full target image build, board/size/package checks, image signing
with the currently trusted release key, sysupgrade -T on the physical router,
LAN + Wi-Fi + LTE UAT and verified rollback. Do not flash an unsigned artifact
or reset working LTE to change a cosmetic status.
