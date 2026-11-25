# 2026-11-25 — LTE public egress outage with healthy local modem, not duplicate netifd

## Owner physical diagnostic evidence (do not infer more than supported)
- network.interface.lte: up=true, pending=false, autostart=true, proto=dhcp, uptime=61991 seconds, device/l3_device=usb0, metric=5
- usb0 IPv4 assigned 192.168.7.120/24, route default via 192.168.7.1 metric5, source 192.168.7.120; ip route get 1.1.1.1 correctly chooses modem gateway
- Modem admin HTTP http://192.168.7.1/ returned 200, curl exit0 bound to usb0.
- Public numeric HTTPS https://1.1.1.1/ returned HTTP000, curl exit35 (TLS handshake failure; not proof ICMP, IP routing, or DNS failure).
- Public hostname HTTPS https://www.cloudflare.com/cdn-cgi/trace returned HTTP000, curl exit28 (timeout; exact DNS-vs-connect failure not shown because no verbose/proxy detail).
- Generated router resolver /tmp/resolv.conf.d/resolv.conf.auto: 94.140.14.14 and 94.140.15.15, AdGuard public upstream pair. Modem-offered DHCP peer DNS 192.168.7.1 was inactive.
- Only netifd PID1366, unlike previous duplicate PID16862 incident. Two udhcpc PIDs alone do not establish duplicate WAN DHCP clients or error without inspecting command lines.
- Therefore do not kill netifd, force reconnect LTE, power-cycle modem, change SIM, reset or flash based on this evidence. The upstream outage could involve DNS policy, modem WAN NAT/PDP, operator external transit, or HTTPS/TLS handling. These require discriminating read-only checks.

## Confirmed source-level issue and repair (new build only)
- The firmware initial cellular UCI defaults forcibly used peerdns=0 and hard-coded the AdGuard pair, matching live router's current generated DNS. Peer DNS 192.168.7.1 would be excluded.
- Replace *new interface initial defaults* with peerdns=1, no static DNS entries, in BOTH source/we5927-lte/files/etc/uci-defaults/99-we5927-lte and pinned OpenWrt source patch.
- Preserve existing user-saved network.lte interface and DNS on upgrades. Never rewrite the live router's network or reload modem automatically. GUI may continue offering explicit custom DNS choice.
- Three source tests verify fresh config follows peer DHCP DNS, existing custom remains untouched, and patched/defaulted sources agree. Tests are not physical proof this was sole cause of the outage.
- Already-signed firmware from source SHA a187353e7eb54b9096ed5429201d7098924d8964 was built before these changes. It does NOT include peer-DNS fix; never relabel it as repaired build.
- Any successor build needs fresh source-gate hash receipts and CI+offline signing+owner physical preflight again. No default auto-flashing.

## Pending read-only discrimination
1. During outage, public HTTP to numeric 1.1.1.1 via usb0 (no DNS/TLS).
2. HTTPS with SNI while bypassing DNS using --resolve one.one.one.one:443:1.1.1.1.
3. BusyBox nslookup same hostname independently against public AdGuard 94.140.14.14 and modem DNS 192.168.7.1 (timeouts bounded); optional public resolver 1.1.1.1.
4. Read exact network.lte.peerdns, network.lte.dns, DHCP dnsmasq noresolv and server config. Do not modify config.
5. Conditional next actions only after identifying layer: if peer DNS works and AdGuard blocked, prefer scoped DNS backup + rollback; if both public HTTP/TLS fail with modem UI responsive, investigate operator PDP/upstream and RNDIS NAT without blind modem resets.
