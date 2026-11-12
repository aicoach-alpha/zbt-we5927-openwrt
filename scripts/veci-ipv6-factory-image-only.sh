#!/bin/sh
# Configure a STAGED factory image rootfs, never an installed/live router.
# Build-time use ONLY after exact-board + carrier preflight. It is NOT a boot
# hook and must NOT run on upgrades that preserve existing user settings.
set -eu
[ "$#" -eq 1 ] || { echo "usage: $0 <staged-rootfs>" >&2; exit 2; }
ROOT="$1"
[ -d "$ROOT" ] || { echo staged_root_missing >&2; exit 2; }
ROOT="$(cd "$ROOT" && pwd -P)"
case "$ROOT" in /|/etc|/overlay|/rom|/tmp|/root) echo unsafe_root >&2; exit 2;; esac
[ -f "$ROOT/.veci-factory-image-root" ] || { echo factory_marker_required >&2; exit 2; }
CFG="$ROOT/etc/config"
[ -f "$CFG/network" ] && [ -f "$CFG/dhcp" ] || { echo config_missing >&2; exit 2; }
command -v uci >/dev/null 2>&1 || { echo host_uci_missing >&2; exit 2; }
u() { uci -c "$CFG" "$@"; }
# Fail closed for IPv6-dependent IPv4 protocols, even for factory images.
for section in wan lte wan6; do
  proto="$(u -q get "network.$section.proto" 2>/dev/null || :)"
  case "$proto" in ds-lite|dslite|map|464xlat|clat|lw4o6)
    echo "ipv6_required_for_ipv4:$section:$proto" >&2; exit 3;;
  esac
done
[ "$(u -q get network.lan 2>/dev/null || :)" = interface ] ||
 { echo lan_interface_missing >&2; exit 2; }
[ "$(u -q get dhcp.lan 2>/dev/null || :)" = dhcp ] ||
 { echo lan_dhcp_missing >&2; exit 2; }
if [ "$(u -q get network.wan6 2>/dev/null || :)" = interface ]; then
  u -q set network.wan6.disabled=1
fi
for section in wan lte; do
  if [ "$(u -q get "network.$section" 2>/dev/null || :)" = interface ]; then
    u -q set "network.$section.ipv6=0"
  fi
done
u -q delete network.lan.ip6assign || :
u -q set dhcp.lan.ra=disabled
u -q set dhcp.lan.dhcpv6=disabled
u -q set dhcp.lan.ndp=disabled
u commit network
u commit dhcp
echo "factory_ipv6_policy=off_staged_only"
