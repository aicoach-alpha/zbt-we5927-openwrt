#!/bin/sh
# Physical WE5927 optional VeCI generic USSD dialer signed APK installer.
# No firmware flash, LuCI, SMS, SIM, LTE, original XL/Core packages or dial actions.
set -eu
umask 077
LC_ALL=C; PATH=/usr/sbin:/usr/bin:/sbin:/bin; export LC_ALL PATH
TAG=veci-generic-ussd-010-cb737a7734ca
BASE="https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/$TAG"
APK=veci-ussd-dialer-0.1.0-r1.apk
KEY=veci-ussd-010.pem
APK_SHA=afad39bae6fad338b9f82bc4a220faa7cf411ae15d5bf7045735dde535d457a7
KEY_SHA=e091858653ce1567c3710fa725b9f8f02b46c1d7465e5d685fa4fa5fb8461c89
APK_BYTES=12938
CELL_SHA=b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379
CORE_SHA=d08edadd38f0d9b992fc54d879eabf9f797bf54df83fa8c8cf7b59e55b9e99ce
QUOTA_SHA=5c1f66b5a5aa292be202897ef538f67ed7933e857ff3e11bcaabb075b75c692d
LOCK=/tmp/veci-generic-ussd-010.lock
WORK=
APPLIED=0
COMPLETE=0
fail(){ printf 'VECI_GENERIC_USSD_010=blocked\nVECI_GENERIC_USSD_REASON=%s\n' "$1"; exit 1; }
sha(){ sha256sum "$1" | awk '{print $1}'; }
check(){ [ -f "$1" ] && [ ! -L "$1" ] && [ "$(sha "$1")" = "$2" ]; }
installed(){ apk list -I 2>/dev/null | grep -q '^veci-ussd-dialer-0.1.0-r1'; }
no_files(){
 for x in /usr/libexec/veci-ussd-dialer-once /usr/libexec/veci-ussd-dialer /usr/libexec/rpcd/veci.dialer /usr/share/rpcd/acl.d/veci-ussd-dialer.json /www/veci/ussd-dialer.html /www/veci/ussd-dialer.js; do
  [ ! -e "$x" ] && [ ! -L "$x" ] || return 1
 done
}
board(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
 grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_firmware
}
guard(){
 board
 check /www/veci/js/pages/cellular.js "$CELL_SHA" || fail core_cellular_drift
 check /usr/libexec/rpcd/veci "$CORE_SHA" || fail core_rpc_drift
 check /www/veci/js/lib/native-quota.js "$QUOTA_SHA" || fail core_quota_drift
 apk list -I 2>/dev/null | grep -q '^veci-telco-xl-native-0.3.7-' || fail xl_037_missing
 ubus -S list veci.ussd 2>/dev/null | grep -qx 'veci.ussd' || fail legacy_ussd_missing
 [ -z "$(uci -q get uhttpd.main.listen_http 2>/dev/null || :)" ] || fail http_listener_enabled
 [ -n "$(uci -q get uhttpd.main.listen_https 2>/dev/null || :)" ] || fail https_listener_missing
}
cleanup(){
 rc="$1"
 trap - EXIT INT TERM
 if [ "$APPLIED" = 1 ] && [ "$COMPLETE" = 0 ]; then
  if apk --no-network del veci-ussd-dialer >/dev/null 2>&1; then
   /etc/init.d/rpcd restart >/dev/null 2>&1 || :
   echo VECI_GENERIC_USSD_010_ROLLBACK=attempted
  else
   echo VECI_GENERIC_USSD_010_ROLLBACK=manual_review_required
   [ -n "$WORK" ] && echo VECI_GENERIC_USSD_010_WORK_RETAINED="$WORK"
   WORK=
  fi
 fi
 [ -n "$WORK" ] && [ -d "$WORK" ] && rm -rf "$WORK" || :
 rmdir "$LOCK" 2>/dev/null || :
 exit "$rc"
}
download(){
 WORK="$(mktemp -d /tmp/veci-generic-ussd.XXXXXX)" || fail temp_unavailable
 mkdir "$WORK/keys" || fail temp_keys_failed
 wget -qO "$WORK/$APK" "$BASE/$APK" || fail download_apk_failed
 wget -qO "$WORK/$KEY" "$BASE/$KEY" || fail download_key_failed
 check "$WORK/$APK" "$APK_SHA" || fail apk_sha256_mismatch
 check "$WORK/$KEY" "$KEY_SHA" || fail key_sha256_mismatch
 [ "$(wc -c < "$WORK/$APK" | tr -d '[:space:]')" = "$APK_BYTES" ] || fail apk_size_mismatch
 for f in /etc/apk/keys/*; do
  [ -f "$f" ] && [ ! -L "$f" ] || continue
  cp "$f" "$WORK/keys/" || fail system_key_copy_failed
 done
 cp "$WORK/$KEY" "$WORK/keys/$KEY" || fail public_key_copy_failed
 apk --keys-dir "$WORK/keys" verify "$WORK/$APK" >/dev/null 2>&1 || fail apk_signature_invalid
 apk --no-network --keys-dir "$WORK/keys" --simulate add "$WORK/$APK" >"$WORK/plan" 2>&1 ||
  fail simulation_failed
 if grep -Ei '(^|[[:space:]])(Installing|Removing|Purging|Upgrading|Downgrading)[[:space:]]' "$WORK/plan" |
    grep -Ev 'veci-ussd-dialer' >/dev/null 2>&1; then
  fail unexpected_package_dependency_changes
 fi
 echo VECI_GENERIC_USSD_010_SIGNATURE=pass
 echo VECI_GENERIC_USSD_010_SIMULATION=pass
}
[ "$#" = 1 ] || fail usage
case "$1" in --status|--verify|--install|--rollback) MODE="$1";; *)fail usage;; esac
board
if [ "$MODE" = --status ]; then
 if installed; then
  echo VECI_GENERIC_USSD_010_PACKAGE=installed
  if ubus -S list veci.dialer 2>/dev/null | grep -qx 'veci.dialer'; then echo VECI_GENERIC_USSD_010_RPC=registered
  else echo VECI_GENERIC_USSD_010_RPC=not_registered;fi
 else echo VECI_GENERIC_USSD_010_PACKAGE=not_installed; fi
 echo VECI_GENERIC_USSD_010_MODEM_COMMANDS=false
 exit 0
fi
mkdir "$LOCK" 2>/dev/null || fail operation_in_progress
trap 'cleanup $?' EXIT
trap 'exit 130' INT TERM
guard
if [ "$MODE" = --rollback ]; then
 installed || fail package_not_installed
 apk --no-network del veci-ussd-dialer >/dev/null 2>&1 || fail rollback_package_failed
 /etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart_failed
 COMPLETE=1
 echo VECI_GENERIC_USSD_010_ROLLBACK=pass
 exit 0
fi
if [ "$MODE" = --install ] && installed; then
 echo VECI_GENERIC_USSD_010_INSTALL=already_installed
 COMPLETE=1
 exit 0
fi
installed && fail package_already_installed
no_files || fail existing_unknown_files
free="$(df -k /overlay | awk 'NR==2{print $4}')"
case "$free" in ''|*[!0-9]*) fail overlay_unknown;; esac
[ "$free" -ge 100 ] || fail overlay_low
download
if [ "$MODE" = --verify ]; then
 COMPLETE=1
 echo VECI_GENERIC_USSD_010_INSTALL=false
 exit 0
fi
APPLIED=1
apk --no-network --keys-dir "$WORK/keys" add "$WORK/$APK" >"$WORK/install.log" 2>&1 ||
 fail package_install_failed
installed || fail package_not_registered
/etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart_failed
tries=0
while [ "$tries" -lt 15 ]; do
 if ubus -S list veci.dialer 2>/dev/null | grep -qx 'veci.dialer'; then break;fi
 tries=$((tries+1)); sleep 1
done
ubus -S list veci.dialer 2>/dev/null | grep -qx 'veci.dialer' || fail rpc_not_registered
ubus -S call veci.dialer status >/dev/null 2>&1 || fail rpc_status_failed
guard
COMPLETE=1
echo VECI_GENERIC_USSD_010_INSTALL=pass
echo VECI_GENERIC_USSD_010_RPC=registered
echo VECI_GENERIC_USSD_010_CORE_PRESERVED=pass
echo VECI_GENERIC_USSD_010_LUCI_MODIFIED=false
echo VECI_GENERIC_USSD_010_SMS_MODEM_UNCHANGED=true
echo VECI_GENERIC_USSD_010_ROLLBACK=available
echo VECI_GENERIC_USSD_010_BROWSER_URL=https://192.168.1.1/veci/ussd-dialer.html
echo VECI_GENERIC_USSD_010_NETWORK_USSD_UAT=not_run
