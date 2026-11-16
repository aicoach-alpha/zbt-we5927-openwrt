# Post-flash WE5927: LTE diagnosis and native VeCI UI cleanup (2026-11-16)

Installed baseline: ZBT-WE5927 OpenWrt 25.12.5, source build
75433f7c672ef796059d00d0a1649aac9628a55e. User confirmed actual router
returned after signed sysupgrade and LuCI was absent.

## Verified against actual router (user-supplied read-only SSH output)

- network.interface.lte UP; usb0 = 192.168.7.186/24; gateway and
  DHCP server = 192.168.7.1; default route via usb0 metric 5.
- Gateway 192.168.7.1 responded to 2/2 ICMP attempts (3.3 ms average).
- 1.1.1.1 did not respond to 2/2 ICMP attempts.
- This PROVES local RNDIS networking and gateway IP reachability at sample
  time. It does NOT prove that modem HTTP server accepts TCP or
  that HTTPS to the public Internet is unavailable (ICMP may be filtered).
- User's combined logread/grep over Windows SSH was
  misquoted and produced ash pipeline errors. udhcpc fragments lacked
  timestamps; do not infer current/repeated USB loss from that output.

## Safe next evidence, on the office laptop

These commands DO NOT change the router:

    ssh root@192.168.1.1 "uclient-fetch -4 -T 8 -O /dev/null https://www.cloudflare.com/cdn-cgi/trace"
    ssh root@192.168.1.1 "wget -T 5 -O /dev/null http://192.168.7.1/"
    ssh root@192.168.1.1 "logread -e we5927-lte"
    ssh root@192.168.1.1 "logread -e udhcpc"
    Test-NetConnection 192.168.7.1 -Port 80

If modem HTTP is reachable from router but not from laptop, use a local
SSH tunnel instead of relaxing firewall or exposing modem admin to all LAN:

    ssh -N -L 127.0.0.1:18071:192.168.7.1:80 root@192.168.1.1

Browse http://127.0.0.1:18071/ from the office laptop.

Do not reset USB, toggle SIM/GPIO, send CFUN, restart network, or flash
another firmware solely on basis of ICMP-only failure.

## Source changes being prepared

- System's duplicate firmware controls removed. Updates page is the only
  update/upload/OTA page. Other System administration remains intact.
- Old Data Meter/LTE usage links and ROM package removed completely;
  no carrier-quota estimator is restored. LTE, SMS and cellular management
  remain installed.
- Firmware manifest fetch failures are reported distinctly from invalid JSON,
  because offline LTE must not appear as invalid GitHub manifest.
- No claim that internet instability is cured by these UI fixes.
- Physical hardware/UAT is needed before replacing installed 75433f7.
