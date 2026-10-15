#!/bin/sh
# VeCI HTTPS-only controlled transition — owner router WE5927 only.
# Staging preserves HTTP; --switch requires verified HTTPS login first.
# Watchdog automatically restores prior uhttpd after 180s unless confirmed.
set -eu
umask 077
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL PATH
BASE=/root/veci-https-recovery-20261015
UHTTPD=/etc/config/uhttpd
CONTROL="$BASE/controller.sh"
BACKUP="$BASE/original-uhttpd"
PREPARED="$BASE/prepared-uhttpd.sha256"
PENDING="$BASE/pending"
CONFIRMED="$BASE/confirmed"
LOCK=/tmp/veci-https-migration.lock
WATCH_SECONDS=180
fail(){ printf 'VECI_HTTPS_STATUS=blocked\nVECI_HTTPS_REASON=%s\n' "$1"; exit 1; }
hash(){ sha256sum "$1" | cut -d' ' -f1; }
regular(){ [ -f "$1" ] && [ ! -L "$1" ]; }
valid_hash(){
 [ "${#1}" -eq 64 ] || return 1
 case "$1" in *[!0-9a-f]*) return 1 ;; esac
}
board_guard(){
 [ "$(id -u)" -eq 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
 grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_firmware
 command -v uci >/dev/null 2>&1 || fail uci_missing
 regular "$UHTTPD" || fail uhttpd_config_unsafe
}
has_http(){ [ -n "$(uci -q get uhttpd.main.listen_http 2>/dev/null || :)" ]; }
has_https(){ [ -n "$(uci -q get uhttpd.main.listen_https 2>/dev/null || :)" ]; }
tls_files(){
 cert="$(uci -q get uhttpd.main.cert 2>/dev/null || :)"
 key="$(uci -q get uhttpd.main.key 2>/dev/null || :)"
 [ -n "$cert" ] && [ -n "$key" ] || return 1
 regular "$cert" && regular "$key" && [ -s "$cert" ] && [ -s "$key" ]
}
status(){
 if has_http; then echo VECI_HTTPS_HTTP_LISTENER=enabled
 else echo VECI_HTTPS_HTTP_LISTENER=disabled; fi
 if has_https; then echo VECI_HTTPS_HTTPS_LISTENER=configured
 else echo VECI_HTTPS_HTTPS_LISTENER=missing; fi
 if tls_files; then echo VECI_HTTPS_TLS_FILES=present
 else echo VECI_HTTPS_TLS_FILES=missing; fi
 if regular "$PENDING"; then echo VECI_HTTPS_TRANSITION=pending_rollback
 elif regular "$CONFIRMED"; then echo VECI_HTTPS_TRANSITION=confirmed
 elif regular "$PREPARED"; then echo VECI_HTTPS_TRANSITION=prepared
 else echo VECI_HTTPS_TRANSITION=not_prepared; fi
 echo VECI_HTTPS_CHANGED_SERVICES=uhttpd_only
}
lock(){
 mkdir "$LOCK" 2>/dev/null || fail transition_in_progress
 trap 'rmdir "$LOCK" 2>/dev/null || :' EXIT
}
backup_guard(){
 [ -d "$BASE" ] && [ ! -L "$BASE" ] || fail backup_dir_missing
 regular "$BACKUP" && regular "$CONTROL" && regular "$PREPARED" || fail backup_files_missing
 # BusyBox/OpenWrt builds may omit the external "stat" applet.
 # ls -ldn is included in the target BusyBox image; inspect owner and
 # permission bits without following symlinks or reading sensitive content.
 [ "$(ls -ldn "$BACKUP" | awk '{print $3}')" = 0 ] || fail backup_owner_invalid
 [ "$(ls -ldn "$BACKUP" | awk '{print $1}')" = "-rw-------" ] || fail backup_mode_invalid
 [ "$(ls -ldn "$BASE" | awk '{print $1 " " $3}')" = "drwx------ 0" ] || fail backup_dir_mode_invalid
 original="$(cat "$BASE/original-uhttpd.sha256" 2>/dev/null || :)"
 valid_hash "$original" && [ "$(hash "$BACKUP")" = "$original" ] || fail backup_integrity_failed
}
restore(){
 backup_guard
 tmp="$UHTTPD.restore.$$"
 [ ! -e "$tmp" ] && [ ! -L "$tmp" ] || fail restore_temp_exists
 cp "$BACKUP" "$tmp" || fail restore_copy_failed
 chmod 600 "$tmp"
 [ "$(hash "$tmp")" = "$original" ] || fail restore_hash_failed
 mv -f "$tmp" "$UHTTPD" || fail restore_replace_failed
 uci -q revert uhttpd || :
 /etc/init.d/uhttpd restart >/dev/null 2>&1 || fail restore_uhttpd_restart_failed
 [ "$(hash "$UHTTPD")" = "$original" ] || fail restore_config_mismatch
 rm -f "$PENDING" "$CONFIRMED" "$PREPARED"
 printf 'rolled_back\n' > "$BASE/result"
 echo VECI_HTTPS_ROLLBACK=pass
}
prepare(){
 board_guard
 lock
 [ ! -e "$BASE" ] && [ ! -L "$BASE" ] || fail recovery_dir_already_exists
 has_http || fail http_not_enabled_no_transition_required
 regular "$0" || fail installer_source_not_regular
 # BusyBox ash supports a HUP-immune child; no nohup package required.
 command -v sh >/dev/null 2>&1 || fail watchdog_shell_missing
 command -v sleep >/dev/null 2>&1 || fail watchdog_sleep_missing
 tls_files || fail tls_certificate_or_key_missing
 mkdir -m 700 "$BASE" || fail recovery_dir_create_failed
 cp "$UHTTPD" "$BACKUP" || fail backup_create_failed
 chmod 600 "$BACKUP"
 hash "$BACKUP" > "$BASE/original-uhttpd.sha256"
 cp "$0" "$CONTROL" || fail controller_copy_failed
 chmod 700 "$CONTROL"
 # Ensure rollback works even if TLS stage fails before listener is committed.
 hash "$UHTTPD" > "$PREPARED"
 chmod 600 "$BASE/original-uhttpd.sha256" "$PREPARED"
 if ! has_https; then
   uci add_list uhttpd.main.listen_https='0.0.0.0:443' >/dev/null 2>&1 ||
     { restore; fail https_listener_setup_failed; }
   uci commit uhttpd >/dev/null 2>&1 ||
     { restore; fail https_commit_failed; }
   /etc/init.d/uhttpd restart >/dev/null 2>&1 ||
     { restore; fail https_restart_failed; }
 fi
 has_http && has_https && tls_files || { restore; fail prepare_validation_failed; }
 hash "$UHTTPD" > "$PREPARED"
 echo VECI_HTTPS_PREPARE=pass
 echo VECI_HTTPS_HTTP_PRESERVED=true
 echo VECI_HTTPS_VERIFY_BROWSER=https://192.168.1.1/veci/
 echo VECI_HTTPS_NEXT=verify_https_login_before_switch
}
# Safely refresh ONLY the watchdog controller after an already successful
# --prepare. The immutable original uhttpd backup and its SHA256 stay intact.
# Mandatory when the migration script was upgraded after prepare.
refresh_controller(){
 board_guard
 lock
 backup_guard
 [ ! -e "$PENDING" ] && [ ! -L "$PENDING" ] || fail transition_already_pending
 [ ! -e "$CONFIRMED" ] && [ ! -L "$CONFIRMED" ] || fail already_confirmed
 ready_hash="$(cat "$PREPARED")"
 valid_hash "$ready_hash" && [ "$(hash "$UHTTPD")" = "$ready_hash" ] ||
   fail config_changed_since_prepare
 has_http && has_https && tls_files || fail both_listeners_not_ready
 regular "$0" || fail controller_source_not_regular
 tmp="$BASE/controller-next.$"
 [ ! -e "$tmp" ] && [ ! -L "$tmp" ] || fail controller_temp_exists
 cp "$0" "$tmp" || fail controller_copy_failed
 chmod 700 "$tmp" || { rm -f "$tmp"; fail controller_mode_failed; }
 sh -n "$tmp" >/dev/null 2>&1 || { rm -f "$tmp"; fail controller_syntax_invalid; }
 [ "$(hash "$tmp")" = "$(hash "$0")" ] ||
   { rm -f "$tmp"; fail controller_copy_mismatch; }
 mv -f "$tmp" "$CONTROL" || fail controller_update_failed
 [ "$(hash "$CONTROL")" = "$(hash "$0")" ] || fail controller_integrity_changed
 [ "$(hash "$BACKUP")" = "$original" ] || fail backup_integrity_failed
 echo VECI_HTTPS_CONTROLLER_REFRESH=pass
 echo VECI_HTTPS_BACKUP_PRESERVED=true
 echo VECI_HTTPS_HTTP_PRESERVED=true
}
switch(){
 board_guard
 lock
 backup_guard
 [ ! -e "$PENDING" ] && [ ! -L "$PENDING" ] || fail transition_already_pending
 [ ! -e "$CONFIRMED" ] || fail already_confirmed
 ready_hash="$(cat "$PREPARED")"
 valid_hash "$ready_hash" && [ "$(hash "$UHTTPD")" = "$ready_hash" ] ||
   fail config_changed_since_prepare
 has_http && has_https && tls_files || fail both_listeners_not_ready
 command -v sh >/dev/null 2>&1 || fail watchdog_shell_missing
 command -v sleep >/dev/null 2>&1 || fail watchdog_sleep_missing
 regular "$CONTROL" && [ "$(hash "$CONTROL")" = "$(hash "$0")" ] ||
   fail controller_integrity_changed
 printf 'pending\n' > "$PENDING"
 # Detached BusyBox ash watchdog: ignore SSH hangup BEFORE exec, inherit
 # ignored SIGHUP, and close all SSH streams. No nohup binary/app needed.
 sh -c 'trap "" HUP; exec sh "$1" --watchdog' veci-watchdog "$CONTROL" \
   </dev/null >/dev/null 2>&1 &
 watcher="$!"
 echo "$watcher" > "$BASE/watchdog.pid"
 # Confirm worker stays alive before disabling HTTP; fail closed if not.
 sleep 1
 if ! kill -0 "$watcher" 2>/dev/null; then
   restore
   fail watchdog_start_failed
 fi
 uci -q delete uhttpd.main.listen_http || { restore; fail http_remove_failed; }
 uci commit uhttpd >/dev/null 2>&1 || { restore; fail http_commit_failed; }
 /etc/init.d/uhttpd restart >/dev/null 2>&1 || { restore; fail http_restart_failed; }
 ! has_http && has_https && tls_files || { restore; fail https_only_validation_failed; }
 echo VECI_HTTPS_SWITCH=pass
 echo VECI_HTTPS_AUTO_ROLLBACK_SECONDS=180
 echo VECI_HTTPS_NEXT=confirm_within_180s_after_https_login
}
confirm(){
 board_guard
 lock
 backup_guard
 regular "$PENDING" || fail no_pending_transition
 ! has_http && has_https && tls_files || fail https_only_not_configured
 printf 'confirmed\n' > "$CONFIRMED"
 rm -f "$PENDING"
 echo VECI_HTTPS_CONFIRM=pass
 echo VECI_HTTPS_HTTP_LISTENER=disabled
 echo VECI_HTTPS_ROLLBACK=available
}
watchdog(){
 board_guard
 [ "$0" = "$CONTROL" ] || fail invalid_watchdog_origin
 regular "$PENDING" || exit 0
 sleep "$WATCH_SECONDS"
 attempt=0
 while ! mkdir "$LOCK" 2>/dev/null; do
   attempt=$((attempt+1))
   [ "$attempt" -le 30 ] || exit 1
   sleep 1
 done
 trap 'rmdir "$LOCK" 2>/dev/null || :' EXIT
 if regular "$PENDING" && [ ! -e "$CONFIRMED" ]; then
   restore >/dev/null
 fi
}
[ "$#" -eq 1 ] || fail usage
case "$1" in
 --status) board_guard; status ;;
 --prepare) prepare ;;
 --refresh-controller) refresh_controller ;;
 --switch) switch ;;
 --confirm) confirm ;;
 --rollback) board_guard; lock; restore ;;
 --watchdog) watchdog ;;
 *) fail invalid_mode ;;
esac
