#!/bin/sh
# Offline OpenWrt build profile. NO live router access, install or flashing.
set -eu
[ "$#" -eq 1 ] || { echo "usage: $0 /path/to/pinned/openwrt-build-tree" >&2; exit 2; }
root="$1"
[ -f "$root/.config" ] && [ -f "$root/rules.mk" ] &&
  [ -x "$root/scripts/feeds" ] && [ -f "$root/package/veci-app-voucher/Makefile" ] ||
  { echo 'STOP: OpenWrt source tree with staged VeCI Guest/Voucher packages required' >&2; exit 3; }
config="$root/.config"
grep -qx 'CONFIG_TARGET_ramips_mt76x8_DEVICE_zbtlink_zbt-we5927=y' "$config" ||
  { echo 'STOP: wrong build profile/board' >&2; exit 4; }
grep -qx 'CONFIG_SIGNED_PACKAGES=y' "$config" ||
  { echo 'STOP: signed APK metadata disabled' >&2; exit 5; }
for pkg in veci veci-default-ui veci-cellular-we5927 veci-app-catalog-we5927 \
  veci-update-we5927; do
  grep -qx "CONFIG_PACKAGE_$pkg=y" "$config" ||
    { echo "STOP: essential Core package $pkg not built in" >&2; exit 6; }
done
python3 - "$config" <<'PY'
import pathlib, re, sys
path=pathlib.Path(sys.argv[1])
data=path.read_text()
required=('uspot','uspot-www','veci-app-guest','veci-app-voucher',
          'luci-base','luci-mod-network','luci-mod-system','luci-app-firewall',
          'luci-theme-bootstrap','uhttpd','uhttpd-mod-ubus','rpcd',
          'rpcd-mod-luci','firewall4','dnsmasq','we5927-lte','wpad-basic-mbedtls')
excluded=('luci','luci-light','luci-mod-admin-full','luci-mod-status',
          'luci-app-package-manager','rpcd-mod-rrdns',
          'MAC80211_MESH','MAC80211_DEBUGFS')
for pkg in excluded:
    pattern=re.compile(r'(?m)^(?:CONFIG_PACKAGE_'+re.escape(pkg)+r'=[^\n]*|# CONFIG_PACKAGE_'+re.escape(pkg)+r' is not set)\n?')
    data=pattern.sub('',data)
    data+='# CONFIG_PACKAGE_'+pkg+' is not set\n'
for pkg in required:
    pattern=re.compile(r'(?m)^(?:CONFIG_PACKAGE_'+re.escape(pkg)+r'=[^\n]*|# CONFIG_PACKAGE_'+re.escape(pkg)+r' is not set)\n?')
    data=pattern.sub('',data)
    data+='CONFIG_PACKAGE_'+pkg+'=y\n'
path.write_text(data)
PY
make -C "$root" defconfig >/dev/null
for pkg in uspot uspot-www veci-app-guest veci-app-voucher \
  luci-base luci-mod-network luci-mod-system luci-app-firewall \
  luci-theme-bootstrap uhttpd uhttpd-mod-ubus rpcd rpcd-mod-luci \
  firewall4 dnsmasq we5927-lte wpad-basic-mbedtls; do
    grep -qx "CONFIG_PACKAGE_$pkg=y" "$config" ||
      { echo "STOP: Kconfig did not select $pkg=y" >&2; exit 7; }
done
grep -qx 'CONFIG_SIGNED_PACKAGES=y' "$config" ||
  { echo 'STOP: signed package configuration changed' >&2; exit 8; }
for pkg in luci luci-light luci-mod-admin-full luci-mod-status \
  luci-app-package-manager rpcd-mod-rrdns MAC80211_MESH MAC80211_DEBUGFS; do
  if grep -Eq "^CONFIG_PACKAGE_$pkg=(y|m)$" "$config" ||
     ! grep -qx "# CONFIG_PACKAGE_$pkg is not set" "$config"; then
    echo "STOP: $pkg is a redundant/unused package still selected" >&2
    exit 9
  fi
done
echo 'SLIM_CAFE=LuCI_rescue_network_system_firewall_only;no_duplicate_package_manager_or_mesh_debugfs'
echo GENERAL_CAFE_PROFILE_CONFIGURED
echo REQUIRED_BUILTIN=uspot,uspot-www,veci-app-guest,veci-app-voucher
echo NEXT=build_image_then_validate_size_metadata_manifest_and_UAT
