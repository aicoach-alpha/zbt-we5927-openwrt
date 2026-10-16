#!/bin/sh
# Install only the optional, signed VeCI data-usage meter.
# Does not fetch true operator quota and cannot change SMS, LTE, Core, LuCI or USSD.
set -eu
umask 077
LC_ALL=C; PATH=/usr/sbin:/usr/bin:/sbin:/bin; export LC_ALL PATH
TAG=veci-data-meter-010-d17a99183575
BASE=https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/$TAG
APK=veci-data-meter-0.1.0-r1.apk
KEY=veci-data-meter-010.pem
APK_SHA=4578b170e4651ca0f1d3783610d3b5efd3c0eecf8a7d354b9638ce0ec186b850
KEY_SHA=9db0fd998e2157cb8e7284931376ab6f00014d6a85690da069836d03ee92d7ca
APK_BYTES=4788
CORE_PAGE=b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379
CORE_RPC=d08edadd38f0d9b992fc54d879eabf9f797bf54df83fa8c8cf7b59e55b9e99ce
LOCK=/tmp/veci-data-meter-install.lock
TMP=
APPLIED=0
DONE=0
fail(){ echo VECI_DATA_METER_010=blocked; echo "VECI_DATA_METER_REASON=$1"; exit 1; }
sha(){ sha256sum "$1" | awk '{print $1}'; }
check(){ [ -f "$1" ] && [ ! -L "$1" ] && [ "$(sha "$1")" = "$2" ]; }
installed(){ apk list -I 2>/dev/null | grep -q '^veci-data-meter-0.1.0-r1'; }
fresh(){
 for f in /usr/libexec/rpcd/veci.meter /usr/share/rpcd/acl.d/veci-data-meter.json /www/veci/data-meter.html /www/veci/data-meter.js; do
  [ ! -e "$f" ] && [ ! -L "$f" ] || return 1
 done
}
guard(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
 grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_firmware
 check /www/veci/js/pages/cellular.js "$CORE_PAGE" || fail core_page_changed
 check /usr/libexec/rpcd/veci "$CORE_RPC" || fail core_rpc_changed
 apk list -I 2>/dev/null | grep -q '^veci-telco-xl-native-0.3.7-' || fail xl_native_missing
 ubus -S list veci.ussd 2>/dev/null | grep -qx veci.ussd || fail legacy_ussd_rpc_missing
}
cleanup(){
 rc="$1"
 trap - EXIT INT TERM
 if [ "$APPLIED" = 1 ] && [ "$DONE" = 0 ]; then
  if apk --no-network del veci-data-meter >/dev/null 2>&1; then
   /etc/init.d/rpcd restart >/dev/null 2>&1 || :
   echo VECI_DATA_METER_AUTO_ROLLBACK=attempted
  else echo VECI_DATA_METER_AUTO_ROLLBACK=manual_review_required; fi
 fi
 [ -z "$TMP" ] || rm -rf "$TMP"
 rmdir "$LOCK" 2>/dev/null || :
 exit "$rc"
}
download(){
 TMP="$(mktemp -d /tmp/veci-data-meter.XXXXXX)" || fail tmp_missing
 mkdir "$TMP/keys"
 wget -qO "$TMP/$APK" "$BASE/$APK" || fail apk_download_failed
 wget -qO "$TMP/$KEY" "$BASE/$KEY" || fail key_download_failed
 check "$TMP/$APK" "$APK_SHA" || fail apk_checksum_invalid
 check "$TMP/$KEY" "$KEY_SHA" || fail public_key_checksum_invalid
 [ "$(wc -c < "$TMP/$APK" | tr -d '[:space:]')" = "$APK_BYTES" ] || fail apk_size_invalid
 for f in /etc/apk/keys/*; do
  [ -f "$f" ] && [ ! -L "$f" ] || continue
  cp "$f" "$TMP/keys/" || fail key_copy_failed
 done
 cp "$TMP/$KEY" "$TMP/keys/$KEY" || fail key_copy_failed
 apk --keys-dir "$TMP/keys" verify "$TMP/$APK" >/dev/null 2>&1 || fail signature_invalid
 apk --no-network --keys-dir "$TMP/keys" --simulate add "$TMP/$APK" > "$TMP/simulation" 2>&1 ||
  fail simulation_failed
 if grep -Ei '(^|[[:space:]])(Installing|Removing|Purging|Upgrading|Downgrading)[[:space:]]' "$TMP/simulation" |
    grep -Ev 'veci-data-meter' >/dev/null 2>&1; then
  fail unexpected_package_change
 fi
 echo VECI_DATA_METER_SIGNATURE=pass
 echo VECI_DATA_METER_SIMULATION=pass
}
[ "$#" -eq 1 ] || fail usage
case "$1" in --status|--verify|--install|--rollback) MODE="$1";; *) fail usage;; esac
guard
if [ "$MODE" = --status ]; then
 if installed; then echo VECI_DATA_METER_PACKAGE=installed
 else echo VECI_DATA_METER_PACKAGE=not_installed; fi
 if ubus -S list veci.meter 2>/dev/null | grep -qx veci.meter; then
  echo VECI_DATA_METER_RPC=registered
 else echo VECI_DATA_METER_RPC=not_registered; fi
 echo VECI_DATA_METER_CARRIER_AUTHENTICATED=false
 echo VECI_DATA_METER_MODEM_SMS_CHANGED=false
 exit 0
fi
mkdir "$LOCK" 2>/dev/null || fail operation_in_progress
trap 'cleanup $?' EXIT
trap 'exit 130' INT TERM
if [ "$MODE" = --rollback ]; then
 installed || fail package_not_installed
 apk --no-network del veci-data-meter >/dev/null 2>&1 || fail rollback_remove_failed
 /etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart_failed
 DONE=1
 echo VECI_DATA_METER_ROLLBACK=pass
 echo VECI_DATA_METER_BASELINE_UNCHANGED=true
 exit 0
fi
if [ "$MODE" = --install ] && installed; then
 echo VECI_DATA_METER_INSTALL=already_installed
 DONE=1
 exit 0
fi
installed && fail package_already_installed
fresh || fail unknown_target_file
free="$(df -k /overlay | awk 'NR==2{print $4}')"
case "$free" in ''|*[!0-9]*) fail overlay_space_unknown;; esac
[ "$free" -ge 64 ] || fail overlay_too_small
download
if [ "$MODE" = --verify ]; then
 echo VECI_DATA_METER_INSTALL=false
 DONE=1
 exit 0
fi
APPLIED=1
apk --no-network --keys-dir "$TMP/keys" add "$TMP/$APK" >"$TMP/install.log" 2>&1 ||
 fail package_install_failed
installed || fail package_not_registered
# Inspect the installed rpcd plugin *before* restarting the production RPC.
# A missing/broken plugin must not trigger repeated service restarts.
PLUGIN=/usr/libexec/rpcd/veci.meter
[ -f "$PLUGIN" ] && [ ! -L "$PLUGIN" ] && [ -x "$PLUGIN" ] ||
 fail rpc_plugin_missing_or_not_executable
methods="$("$PLUGIN" list 2>/dev/null || :)"
printf '%s' "$methods" | grep -Fq '"status"' ||
 fail rpc_plugin_manifest_invalid
printf '%s' "$methods" | grep -Fq '"setBaseline"' ||
 fail rpc_plugin_manifest_invalid
echo VECI_DATA_METER_PLUGIN_MANIFEST=pass
# Sometimes rpcd's exec plugin registration lags behind its service restart.
# Retry only registration/restart, NEVER the package installation.
attempt=0
registered=0
while [ "$attempt" -lt 3 ]; do
 attempt=$((attempt+1))
 /etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart_failed
 n=0
 while [ "$n" -lt 12 ]; do
  if ubus -S list veci.meter 2>/dev/null | grep -qx veci.meter; then
   registered=1
   break
  fi
  n=$((n+1)); sleep 1
 done
 [ "$registered" = 1 ] && break
done
[ "$registered" = 1 ] || fail rpc_not_registered
ubus -S call veci.meter status > "$TMP/status.json" 2>/dev/null || fail rpc_status_failed
[ "$(jsonfilter -i "$TMP/status.json" -e '@.carrier_authenticated' 2>/dev/null || :)" = false ] ||
 fail operator_balance_provenance_guard
guard
DONE=1
echo VECI_DATA_METER_INSTALL=pass
echo VECI_DATA_METER_RPC=registered
echo VECI_DATA_METER_CORE_PRESERVED=pass
echo VECI_DATA_METER_LUCI_CHANGED=false
echo VECI_DATA_METER_MODEM_SMS_UNCHANGED=true
echo VECI_DATA_METER_CARRIER_BALANCE=not_available
echo VECI_DATA_METER_ROLLBACK=available
echo VECI_DATA_METER_URL=https://192.168.1.1/veci/data-meter.html
