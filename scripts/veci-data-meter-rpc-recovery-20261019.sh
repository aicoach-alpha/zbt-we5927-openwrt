#!/bin/sh
# VeCI Data Meter 010 — bounded RPC repair/diagnostic.
# Run on ZBT WE5927 only. Does not change LuCI, LTE, SMS or modem.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin; export PATH
METER=/usr/libexec/rpcd/veci.meter
PKG=veci-data-meter
say(){ printf '%s=%s\n' "$1" "$2"; }
[ "$(id -u)" = 0 ] || { say VECI_METER_RESULT root_required; exit 1; }
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || { say VECI_METER_RESULT wrong_device; exit 1; }
grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || { say VECI_METER_RESULT wrong_firmware; exit 1; }
case "${1:-}" in --inspect|--repair) MODE="$1";; *) say VECI_METER_RESULT invalid_mode; exit 1;; esac
if ! apk list -I 2>/dev/null | grep -q '^veci-data-meter-'; then
 say VECI_METER_RESULT package_missing
 exit 1
fi
if [ ! -f "$METER" ] || [ -L "$METER" ]; then
 say VECI_METER_RESULT rpc_executable_missing_or_symlink
 exit 1
fi
if [ ! -x "$METER" ]; then
 say VECI_METER_RESULT rpc_not_executable
 # Do not chmod package-owned executable; fix APK metadata and re-sign package instead.
 exit 1
fi
say VECI_METER_BINARY present_executable
if ubus -S list veci.meter 2>/dev/null | grep -qx veci.meter; then
 say VECI_METER_RESULT registered
 exit 0
fi
if [ "$MODE" = --inspect ]; then
 say VECI_METER_RESULT rpc_not_registered
 exit 1
fi
# Single bounded restart only. No package uninstall/reinstall loops.
if ! /etc/init.d/rpcd restart >/dev/null 2>&1; then
 say VECI_METER_RESULT rpcd_restart_failed
 exit 1
fi
n=0
while [ "$n" -lt 5 ]; do
 if ubus -S list veci.meter 2>/dev/null | grep -qx veci.meter; then
  say VECI_METER_RESULT registered
  exit 0
 fi
 n=$((n+1)); sleep 1
done
say VECI_METER_RESULT rpc_not_registered_after_restart
# Operator records and secrets are never dumped to logs.
say VECI_METER_NEXT_STEP inspect_apk_rpc_entrypoint_protocol
exit 1
