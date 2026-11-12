# WE5927 LAN not detected — read-only PHY and bridge diagnosis

2026-11-12. **No router changes, no service reload, no flash.**

Observed: laptop Wi-Fi connects to `192.168.1.1` and obtains DHCP,
but the same laptop's Realtek Ethernet adapter reports **Media disconnected**
(no negotiated copper Ethernet carrier). This is **not evidence of a DHCP
failure** unless a physical link was independently established. Ensure a
known-good Ethernet cable is actually plugged in, and try the labeled LAN
ports without resetting the router. Keep a working Wi-Fi connection as
management access.

On a trusted authenticated Wi-Fi SSH session to the router:

```sh
swconfig dev switch0 show | grep 'link:'
uci -q get network.lan.device
uci -q get network.lan.ifname
ubus -t 2 call network.interface.lan status
```

Or run `scripts/veci-lan-phy-readonly.sh` **manually** after copying it to the
router's `/tmp` (tmpfs only). It records only board, interface labels, external
switch port link up/down, bridge state, and aggregate link-event counts. It
never reads MACs, passwords, APN, mobile identifiers or Wi-Fi credentials and
never invokes `swconfig set/apply`, `wifi reload`, `ifup`, `ifdown`, reboot,
network reload or any flash operation.

## Interpret without guessing

- **External ports all link:down** while laptop says Media disconnected
  *and* cable is confirmed plugged into router: check Ethernet cable, port
  label, PC NIC/cable, and PHY/switch electrical reset or pinmux. Swconfig is
  the physical-port truth; `eth0` CPU interface and `br-lan` carrier can
  look up even while copper ports are down.
- **One external port link:up**, laptop link up, but no address: diagnose VLAN
  / `br-lan` and dnsmasq. DO NOT change `switch_vlan` before identifying
  actual external port numbers. The board profile currently sets ports 0–3
  as LAN, 4 as WAN and CPU port 6, but mapping has not been independently
  confirmed for every physical WE5927/WE2825 variant.
- **PHY link drops near modem restart/network reload**: known OpenWrt rt3050
  switch behavior: https://github.com/openwrt/openwrt/issues/14951 .
  Source-level PR #18 prevents runtime LTE config commits and narrows
  reload triggers, but has not been flashed. Do not trigger reload on an
  unstable production router just to reproduce the bug.

The failed GitHub full-image CI run #43153710850 is separate: firmware
compilation passed, post-build verifier selected a MIPS **target** `fwtool`
instead of the native x86-64 **host** binary, producing exit code 126.
This cannot affect the running router because the image was not deployed.
PR #16 has since staged a host-path correction and another full-image CI
run. No successful final-image metadata/signature/UAT was established at
the time this note was written.

Release blocker: preserve Wi-Fi and LTE; collect PHY state with a verified
cable, then classify the fault before making any driver, switch or firmware
change. Do not force-link all switch ports or factory-reset as a diagnostic.
