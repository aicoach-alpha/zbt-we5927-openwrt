#!/bin/sh
# VeCI v13x: exact orphan deployment cleanup + LAN-only HTTP (no UCI/netlink/ubus probes).
# Single scoped transaction. Does not claim to fix rpcd session.login.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
CFG=/etc/config/uhttpd
BACK=/etc/config/uhttpd.veci-v13x-original-20261028
TMP=/etc/config/.uhttpd.veci-v13x-staged-20261028
OLD_U=/etc/config/uhttpd.veci-v13u-before-http-20261028
OLD_V=/etc/config/uhttpd.veci-v13v-before-http-20261028
OLD_W=/etc/config/uhttpd.veci-v13w-before-http-20261028
SERVICE=/etc/init.d/uhttpd
fail(){ echo "VECI_V13X_ERROR=$1"; exit 1; }
echo VECI_V13X_STAGE=started
[ "$(id -u)" -eq 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_board
grep -Fqx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail unexpected_firmware
[ -s "$CFG" ] && [ -f "$CFG" ] && [ ! -L "$CFG" ] &&
[ -x "$SERVICE" ] || fail invalid_uhttpd_files
for item in "$OLD_U" "$OLD_V" "$OLD_W" "$BACK" "$TMP"; do
 [ ! -e "$item" ] && [ ! -L "$item" ] || fail previous_backup_or_stage_requires_review
done
# Confirm no prior HTTP listener and existing redirect=0 without UCI RPC or netlink.
awk '
 $1=="config" && $2=="uhttpd" {
   section=($3=="main" || $3=="'\''main'\''" || $3=="\"main\"")
   if (section) main++
 }
 ($1=="option" || $1=="list") && $2=="listen_http" { http++ }
 section && ($1=="option" || $1=="list") && $2=="listen_https" { tls++ }
 section && $1=="option" && $2=="redirect_https" {
   if ($3=="0" || $3=="'\''0'\''" || $3=="\"0\"") redirect++
 }
 END { if (main!=1 || http!=0 || tls<1 || redirect!=1) exit 17 }
' "$CFG" || fail unexpected_existing_http_configuration
echo VECI_V13X_STAGE=safe_preflight_pass
# Check exact PID and script argument; PID 1 parent and sleeping as in audited receipt.
for entry in '6052:v13u:/tmp/veci-v13u-lan-http-login-20261028.sh' '6081:v13v:/tmp/veci-v13v-http-no-auth-blocker-20261028.sh'; do
 pid="$(printf '%s' "$entry" | cut -d: -f1)"
 label="$(printf '%s' "$entry" | cut -d: -f2)"
 command="$(printf '%s' "$entry" | cut -d: -f3)"
 if [ ! -e "/proc/$pid" ]; then
  echo "VECI_V13X_OLD_$label=already_exited"
  continue
 fi
 [ -r "/proc/$pid/cmdline" ] || fail unreadable_old_pid
 if ! tr '\000' '\n' <"/proc/$pid/cmdline" | grep -Fqx "$command"; then
  fail pid_reused_or_not_old_script
 fi
 parent="$(awk '$1=="PPid:"{print $2;exit}' "/proc/$pid/status")"
 state="$(awk '$1=="State:"{print $2;exit}' "/proc/$pid/status")"
 [ "$parent" = 1 ] && [ "$state" = S ] || fail old_process_state_changed
 echo "VECI_V13X_OLD_$label=verified_orphan_pid_$pid"
done
echo VECI_V13X_STAGE=terminate_exact_orphans
for pid in 6052 6081; do
 [ -e "/proc/$pid" ] || continue
 case "$pid" in
  6052) path=/tmp/veci-v13u-lan-http-login-20261028.sh ;;
  6081) path=/tmp/veci-v13v-http-no-auth-blocker-20261028.sh ;;
 esac
 tr '\000' '\n' <"/proc/$pid/cmdline" | grep -Fqx "$path" ||
 fail old_process_changed_before_signal
 kill -TERM "$pid" || fail termination_signal_failed
done
sleep 1
for pid in 6052 6081; do
 [ -e "/proc/$pid" ] || continue
 case "$pid" in
  6052) path=/tmp/veci-v13u-lan-http-login-20261028.sh ;;
  6081) path=/tmp/veci-v13v-http-no-auth-blocker-20261028.sh ;;
 esac
 if tr '\000' '\n' <"/proc/$pid/cmdline" 2>/dev/null | grep -Fqx "$path"; then
  fail old_script_still_running_do_not_retry
 fi
done
echo VECI_V13X_OLD_PROCESSES=cleared
echo VECI_V13X_STAGE=backup_original
cp -p "$CFG" "$BACK" || fail backup_failed
chmod 600 "$BACK" || fail backup_permission_failed
# Minimal additive edit: insert one HTTP listener under existing uhttpd.main.
# Do not run UCI (a previous network.lan lookup was observed to hang).
awk '
 $1=="config" && $2=="uhttpd" &&
 ($3=="main" || $3=="'\''main'\''" || $3=="\"main\"") {
  print
  print "\tlist listen_http '\''192.168.1.1:80'\''"
  inserted++
  next
 }
 { print }
 END { if (inserted!=1) exit 17 }
' "$CFG" >"$TMP" || fail staged_http_edit_failed
chmod 600 "$TMP"
grep -Fq "list listen_http '192.168.1.1:80'" "$TMP" || fail staged_http_listener_missing
echo VECI_V13X_STAGE=commit_http_config
mv "$TMP" "$CFG" || fail config_atomic_replace_failed
echo VECI_V13X_STAGE=restart_uhttpd_only
if ! "$SERVICE" restart; then
 cp -p "$BACK" "$CFG" || fail restore_backup_failed
 "$SERVICE" restart || fail rollback_service_restart_failed
 fail uhttpd_restart_failed_original_restored
fi
echo VECI_V13X_STAGE=one_integrity_gate
grep -Fq "list listen_http '192.168.1.1:80'" "$CFG" || fail listener_integrity_failed
grep -Eq "^[[:space:]]*option[[:space:]]+redirect_https[[:space:]]+['\"]?0['\"]?" "$CFG" ||
 fail redirect_integrity_failed
pidof uhttpd >/dev/null 2>&1 || fail uhttpd_not_running
echo VECI_V13X_HTTP_LISTEN=192.168.1.1:80
echo VECI_V13X_TLS_LISTENER=retained
echo VECI_V13X_LTE=unchanged
echo VECI_V13X_INTEGRITY=pass
echo VECI_V13X_HTTP_CONFIG=applied
