# VeCI General-Cafe slim resource profile — ZBT WE5927

Goal: free firmware storage for additional signed VeCI applications, without
sacrificing LTE/WAN, authentication, captive portal, voucher, Wi-Fi driver,
firewall, or a reliable recovery administrative UI.

## Removed from firmware package selection

- luci (meta collection), luci-light (meta collection): would add redundant
  components, including an additional package management application.
- luci-mod-admin-full, luci-mod-status: remove redundant status modules that
  duplicate VeCI's dashboard, while keeping the LuCI recovery network,
  system and firewall administration modules.
- luci-app-package-manager: overlapping UI with VeCI Apps. The underlying
  APK package manager, its trust keys and signed-feed verifier remain enabled.
- rpcd-mod-rrdns: used for the omitted LuCI status view.
- MAC80211_MESH and MAC80211_DEBUGFS: unnecessary mesh/debug support for the
  current stand-alone cafe hotspot. Wi-Fi drivers and normal SSID functions
  remain included.

Eight explicit selection flags are turned off. Dependencies might change
the count of resulting packages: do not claim a byte or RAM saving until
a real firmware manifest and booted-device measurement exist.

## Preserved and checked as required

- LuCI recovery interface: luci-base, luci-mod-network, luci-mod-system,
  luci-app-firewall and luci-theme-bootstrap; served by uhttpd.
- VeCI Core, cellular LTE modem controller, admin dashboard, app catalog,
  secure signed APK feed and package manager.
- uspot, uspot-www, Guest Portal, Voucher and their safe removal handlers.
- firewall4, dnsmasq, rpcd, dropbear, wpad-basic-mbedtls, MT7603 Wi-Fi
  driver, USB LTE/RNDIS/serial modem components, IPv6 and PPPoE support.

Do not remove access-control or essential network packages just to
save flash space; nor disable BPF, because uspot explicitly depends on
ucode-mod-bpf and kmod-sched-bpf in this pinned OpenWrt package source.

## Verification and deployment

1. Apply source/openwrt-we5927.config to an isolated pinned OpenWrt build,
   stage current source with scripts/prepare-veci.sh, then run
   scripts/prepare-veci-general-cafe-profile.sh. Kconfig must not
   reenable removed packages.
2. Complete the original active build unchanged before any restaging;
   rebuild the latest source in the isolated bounded Docker environment.
3. Verify actual image size <= 7,995,392 bytes, manifest required/forbidden
   packages, exact immutable source pin, embedded Guest/Voucher scripts,
   firmware metadata, APK keys and checksums.
4. Measure real RAM (/proc/meminfo MemAvailable) and free overlay
   (df -Pk /overlay) using scripts/veci-apps-readiness.sh before and
   after a separate operator-approved flash. The existing app readiness
   gate requires at least 8 MiB available RAM and 2 MiB free overlay
   plus a verified signed feed. This is a lower bound for safe install,
   not a promise that a specific third-party app will fit.
5. Preserve wired recovery and backup; perform real LTE/WAN, HTTPS/UI,
   Wi-Fi, Guest/Voucher and optional-app install/uninstall UAT.
   Until those pass: FLASH_DECISION=NO_GO.

LuCI is loaded on request, so removing its status/package-manager views
primarily saves firmware flash. Removing mesh/debugfs may reduce kernel
image overhead, but no specific ongoing RAM reduction is asserted here.
