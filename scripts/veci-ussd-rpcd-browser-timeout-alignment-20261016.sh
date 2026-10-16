#!/bin/sh
# VE5927 generic-USSD timeout fix. RPCD=50s, browser=55s, uhttpd>=60s.
# Changes ONLY /etc/config/rpcd timeout plus the optional dialer JS.
# No dial, LuCI, modem, SIM, HTTPS, signed APK or VeCI core modifications.
set -eu
umask 077
LC_ALL=C; PATH=/usr/sbin:/usr/bin:/sbin:/bin; export LC_ALL PATH
CONF=/etc/config/rpcd
UI=/www/veci/ussd-dialer.js
BACKUP=/root/veci-ussd-timeout-20261016
LOCK=/tmp/veci-ussd-timeout.lock
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/cf61015bb1827514bbf60301eeb1e5af075d5736/source/veci-ussd-dialer/files/www/veci/ussd-dialer.js
OLD_UI=8824597e1892f43845d5bac27d88b90f9bbb66ce204f83d5695a398d2868acd6
NEW_UI=9d55f6cbf31ae1da32ccb27524ba84d5074d61b7e404164f1daaa557477f70ed
CORE_RPC=d08edadd38f0d9b992fc54d879eabf9f797bf54df83fa8c8cf7b59e55b9e99ce
CORE_PAGE=b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379
TMP=
DIRTY=0
COMPLETE=0
fail(){ echo VECI_USSD_TIMEOUT_FIX=blocked; echo "VECI_USSD_TIMEOUT_REASON=$1"; exit 1; }
hash(){ sha256sum "$1" | awk '{print $1}'; }
same(){ [ -f "$1" ] && [ ! -L "$1" ] && [ "$(hash "$1")" = "$2" ]; }
uci_timeout(){ uci -q get 'rpcd.@rpcd[0].timeout' 2>/dev/null || :; }
process_timeout(){
 for pid in $(pidof rpcd 2>/dev/null || :); do
  [ -r "/proc/$pid/cmdline" ] || continue
  tr '\000' '\n' < "/proc/$pid/cmdline" | awk '$0=="-t"{getline;print;exit}'
  return 0
 done
 return 0
}
ready(){
 expected="$1"
 n=0
 while [ "$n" -lt 20 ]; do
  if [ "$(process_timeout)" = "$expected" ] &&
   ubus -S list veci.dialer 2>/dev/null | grep -qx veci.dialer &&
   ubus -S call veci.dialer status >/dev/null 2>&1 &&
   ubus -S list veci.ussd 2>/dev/null | grep -qx veci.ussd; then
   return 0
  fi
  n=$((n+1)); sleep 1
 done
 return 1
}
guard(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
 grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_firmware
 same /usr/libexec/rpcd/veci "$CORE_RPC" || fail core_rpc_changed
 same /www/veci/js/pages/cellular.js "$CORE_PAGE" || fail core_page_changed
 apk list -I 2>/dev/null | grep -q '^veci-ussd-dialer-0.1.0-r1' || fail dialer_not_installed
 [ -f "$CONF" ] && [ ! -L "$CONF" ] || fail rpcd_config_invalid
 [ -x /etc/init.d/rpcd ] && [ ! -L /etc/init.d/rpcd ] || fail rpcd_init_invalid
 grep -Fq 'rpcd.@rpcd[0].timeout' /etc/init.d/rpcd || fail unsupported_rpcd_init
 [ -z "$(uci -q get uhttpd.main.listen_http 2>/dev/null || :)" ] || fail http_enabled
 [ -n "$(uci -q get uhttpd.main.listen_https 2>/dev/null || :)" ] || fail https_not_configured
 web="$(uci -q get uhttpd.main.script_timeout 2>/dev/null || :)"
 [ -n "$web" ] || web=60
 case "$web" in ''|*[!0-9]*) fail uhttpd_timeout_invalid;; esac
 [ "$web" -ge 60 ] || fail uhttpd_timeout_below_60
}
status(){
 echo "VECI_USSD_RPCD_CONFIG_TIMEOUT=$(uci_timeout)"
 echo "VECI_USSD_RPCD_PROCESS_TIMEOUT=$(process_timeout)"
 web="$(uci -q get uhttpd.main.script_timeout 2>/dev/null || :)"
 [ -n "$web" ] || web=default_60
 echo "VECI_USSD_UHTTPD_SCRIPT_TIMEOUT=$web"
 if same "$UI" "$NEW_UI"; then echo VECI_USSD_BROWSER_TIMEOUT=55
 elif same "$UI" "$OLD_UI"; then echo VECI_USSD_BROWSER_TIMEOUT=37
 else echo VECI_USSD_BROWSER_TIMEOUT=unknown; fi
 if [ -d "$BACKUP" ] && [ ! -L "$BACKUP" ]; then
  echo VECI_USSD_TIMEOUT_ROLLBACK=available
 else echo VECI_USSD_TIMEOUT_ROLLBACK=not_prepared; fi
 echo VECI_USSD_TIMEOUT_MODEM_REQUESTS=false
}
cleanup(){
 rc="$1"
 trap - EXIT INT TERM
 if [ "$DIRTY" = 1 ] && [ "$COMPLETE" = 0 ]; then
  echo VECI_USSD_TIMEOUT_AUTO_ROLLBACK=attempted
  if [ -f "$BACKUP/rpcd.before" ] && [ -f "$BACKUP/ui.before" ]; then
   if cp "$BACKUP/rpcd.before" "$CONF" &&
      cp "$BACKUP/ui.before" "$UI" &&
      chmod 644 "$UI" &&
      /etc/init.d/rpcd restart >/dev/null 2>&1 &&
      ready 30; then
    echo VECI_USSD_TIMEOUT_AUTO_ROLLBACK=pass
   else echo VECI_USSD_TIMEOUT_AUTO_ROLLBACK=manual_review_required; fi
  else echo VECI_USSD_TIMEOUT_AUTO_ROLLBACK=backup_unavailable; fi
 fi
 [ -n "$TMP" ] && [ -d "$TMP" ] && rm -rf "$TMP" || :
 rm -f "$UI.next.$$"
 rmdir "$LOCK" 2>/dev/null || :
 exit "$rc"
}
[ "$#" = 1 ] || fail usage
case "$1" in --status|--verify|--apply|--rollback) MODE="$1";; *) fail usage;; esac
guard
if [ "$MODE" = --status ]; then status; exit 0; fi
mkdir "$LOCK" 2>/dev/null || fail busy
trap 'cleanup $?' EXIT
trap 'exit 130' INT TERM
if [ "$MODE" = --rollback ]; then
 [ "$(uci_timeout)" = 50 ] && [ "$(process_timeout)" = 50 ] || fail not_in_expected_state
 same "$UI" "$NEW_UI" || fail active_js_not_expected
 [ -d "$BACKUP" ] && [ ! -L "$BACKUP" ] || fail backup_missing
 [ -f "$BACKUP/rpcd.before" ] && [ -f "$BACKUP/rpcd.after.sha" ] || fail backup_incomplete
 [ "$(hash "$CONF")" = "$(cat "$BACKUP/rpcd.after.sha")" ] || fail config_changed_since_install
 same "$BACKUP/ui.before" "$OLD_UI" || fail saved_js_changed
 DIRTY=1
 cp "$BACKUP/rpcd.before" "$CONF" || fail restore_rpcd
 cp "$BACKUP/ui.before" "$UI" || fail restore_ui
 chmod 644 "$UI"
 /etc/init.d/rpcd restart >/dev/null 2>&1 || fail restart_rollback
 ready 30 || fail original_rpcd_not_ready
 same "$UI" "$OLD_UI" || fail restored_js_sha
 COMPLETE=1
 echo VECI_USSD_TIMEOUT_ROLLBACK=pass
 exit 0
fi
[ "$(uci_timeout)" = 30 ] && [ "$(process_timeout)" = 30 ] || fail rpcd_baseline_not_30
same "$UI" "$OLD_UI" || fail ui_baseline_changed
[ ! -e "$BACKUP" ] && [ ! -L "$BACKUP" ] || fail existing_backup_requires_review
free="$(df -k /overlay | awk 'NR==2{print $4}')"
case "$free" in ''|*[!0-9]*) fail overlay_unknown;; esac
[ "$free" -ge 64 ] || fail overlay_low
TMP="$(mktemp -d /tmp/veci-ussd-timeout.XXXXXX)" || fail temp_unavailable
wget -qO "$TMP/next.js" "$URL" || fail ui_download
same "$TMP/next.js" "$NEW_UI" || fail ui_sha256
echo VECI_USSD_TIMEOUT_SHA256=pass
echo VECI_USSD_TIMEOUT_TARGET_RPCD=50
echo VECI_USSD_TIMEOUT_TARGET_BROWSER=55
if [ "$MODE" = --verify ]; then
 echo VECI_USSD_TIMEOUT_CONFIG_CHANGED=false
 echo VECI_USSD_TIMEOUT_SERVICES_RESTARTED=false
 COMPLETE=1
 exit 0
fi
mkdir -m 700 "$BACKUP" || fail backup_dir
cp "$CONF" "$BACKUP/rpcd.before" || fail backup_rpcd
cp "$UI" "$BACKUP/ui.before" || fail backup_ui
chmod 600 "$BACKUP/rpcd.before" "$BACKUP/ui.before" || fail backup_mode
same "$BACKUP/ui.before" "$OLD_UI" || fail backup_js_hash
[ "$(hash "$BACKUP/rpcd.before")" = "$(hash "$CONF")" ] || fail backup_config_hash
DIRTY=1
uci set 'rpcd.@rpcd[0].timeout=50' || fail uci_set_failed
uci commit rpcd || fail uci_commit_failed
[ "$(uci_timeout)" = 50 ] || fail uci_not_50
hash "$CONF" > "$BACKUP/rpcd.after.sha" || fail save_change_hash
chmod 600 "$BACKUP/rpcd.after.sha"
cp "$TMP/next.js" "$UI.next.$$" || fail stage_js
chmod 644 "$UI.next.$$" || fail stage_js_mode
mv -f "$UI.next.$$" "$UI" || fail activate_js
same "$UI" "$NEW_UI" || fail active_js_hash
/etc/init.d/rpcd restart >/dev/null 2>&1 || fail restart_rpcd
ready 50 || fail new_timeout_not_effective
guard
COMPLETE=1
echo VECI_USSD_TIMEOUT_FIX=pass
echo VECI_USSD_RPCD_TIMEOUT_SECONDS=50
echo VECI_USSD_BROWSER_TIMEOUT_SECONDS=55
echo VECI_USSD_UHTTPD_UNCHANGED=true
echo VECI_USSD_CORE_AND_LUCI_UNCHANGED=true
echo VECI_USSD_LTE_SMS_UNCHANGED=true
echo VECI_USSD_REAL_DIAL_SENT=false
echo VECI_USSD_TIMEOUT_ROLLBACK=available
