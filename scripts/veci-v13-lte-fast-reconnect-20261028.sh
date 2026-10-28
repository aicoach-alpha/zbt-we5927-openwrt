#!/bin/sh
# VeCI LTE fast reconnect v13 — tune existing watchdog; keep SIM, APN, LTE path.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
die(){ echo "VECI_FAST_RECONNECT_ERROR=$1"; exit 1; }
[ "$#" -eq 1 ] || die invalid_arguments
MODE="$1"
CFG=/etc/config/we5927_lte
BACK=/etc/config/we5927_lte.veci-before-fast-20261028
FLAG=/etc/config/we5927_lte.veci-fast-enabled-before-20261028
SERVICE=/etc/init.d/we5927-lte
numeric(){ case "$1" in ''|*[!0-9]*) return 1;; esac; [ "$1" -le 999 ]; }
daemon_running(){
 ps w 2>/dev/null | grep '[w]e5927-lte daemon' >/dev/null 2>&1 && return 0
 ubus -S call service list '{"name":"we5927-lte"}' 2>/dev/null |
  grep -Eq '"running"[[:space:]]*:[[:space:]]*true'
}
service_state(){ if "$SERVICE" enabled >/dev/null 2>&1; then echo enabled; else echo disabled; fi; }
[ "$(id -u)" -eq 0 ] || die root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || die wrong_router
grep -Fq "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || die unexpected_firmware
[ -f "$CFG" ] && [ ! -L "$CFG" ] && [ -x "$SERVICE" ] &&
 [ -x /usr/sbin/we5927-lte ] || die existing_lte_service_missing
case "$MODE" in
 --status)
  echo "VECI_FAST_RECONNECT_INTERVAL=$(uci -q get we5927_lte.main.ping_interval || echo unknown)"
  echo "VECI_FAST_RECONNECT_THRESHOLD=$(uci -q get we5927_lte.main.fail_threshold || echo unknown)"
  if daemon_running; then echo VECI_FAST_RECONNECT_WATCHDOG=running
  else echo VECI_FAST_RECONNECT_WATCHDOG=not_running; fi
  echo VECI_FAST_RECONNECT_STATUS=read_only
  exit 0 ;;
 --rollback)
  [ -f "$BACK" ] && [ ! -L "$BACK" ] && [ -f "$FLAG" ] && [ ! -L "$FLAG" ] ||
   die original_backup_missing
  cp -p "$BACK" "$CFG" || die original_config_restore_failed
  if [ "$(cat "$FLAG")" = disabled ]; then "$SERVICE" disable || die restore_service_disabled_failed
  else "$SERVICE" enable || die restore_service_enabled_failed; fi
  "$SERVICE" restart || die original_watchdog_restart_failed
  echo VECI_FAST_RECONNECT_ROLLBACK=restored_original_config
  exit 0 ;;
 --apply) ;;
 *) die use_apply_status_or_rollback ;;
esac
[ ! -e "$BACK" ] && [ ! -L "$BACK" ] &&
 [ ! -e "$FLAG" ] && [ ! -L "$FLAG" ] || die previous_backup_preserved
[ "$(uci -q get we5927_lte.main.enabled || echo 1)" = 1 ] || die watchdog_explicitly_disabled
CURRENT_INTERVAL="$(uci -q get we5927_lte.main.ping_interval || true)"
CURRENT_THRESHOLD="$(uci -q get we5927_lte.main.fail_threshold || true)"
numeric "$CURRENT_INTERVAL" && numeric "$CURRENT_THRESHOLD" &&
 [ "$CURRENT_INTERVAL" -ge 1 ] && [ "$CURRENT_THRESHOLD" -ge 1 ] ||
 die invalid_existing_watchdog_policy
[ "$CURRENT_INTERVAL" -ge 10 ] && [ "$CURRENT_THRESHOLD" -ge 3 ] ||
 die already_faster_policy_do_not_slow
SIM_BEFORE="$(uci -q get we5927_lte.main.auto_failover || echo missing)"
SLOT_BEFORE="$(uci -q get we5927_lte.main.sim || echo missing)"
APN_BEFORE="$(uci -q get we5927_lte.main.apn || echo missing)"
ENABLE_BEFORE="$(service_state)"
cp -p "$CFG" "$BACK" || die backup_failed
printf '%s\n' "$ENABLE_BEFORE" > "$FLAG" || die service_state_backup_failed
uci set we5927_lte.main.ping_interval=10
uci set we5927_lte.main.fail_threshold=3
uci commit we5927_lte || die uci_commit_failed
"$SERVICE" enable || die watchdog_enable_failed
# One scoped watchdog restart (not a router or network restart).
if ! "$SERVICE" restart; then
 echo VECI_FAST_RECONNECT_RESTART=failed_attempting_restore
 cp -p "$BACK" "$CFG" || die failed_restart_restore_failed
 if [ "$ENABLE_BEFORE" = disabled ]; then "$SERVICE" disable || :; fi
 "$SERVICE" restart || :
 die restart_failed_rollback_attempted
fi
# Single integrity gate, without inducing a synthetic outage.
[ "$(uci -q get we5927_lte.main.ping_interval)" = 10 ] || die interval_not_applied
[ "$(uci -q get we5927_lte.main.fail_threshold)" = 3 ] || die threshold_not_applied
[ "$(uci -q get we5927_lte.main.auto_failover || echo missing)" = "$SIM_BEFORE" ] ||
 die auto_failover_changed
[ "$(uci -q get we5927_lte.main.sim || echo missing)" = "$SLOT_BEFORE" ] ||
 die sim_slot_changed
[ "$(uci -q get we5927_lte.main.apn || echo missing)" = "$APN_BEFORE" ] ||
 die apn_changed
daemon_running || die watchdog_not_running_after_restart
echo "VECI_FAST_RECONNECT_PREVIOUS=$CURRENT_INTERVAL-s_x_$CURRENT_THRESHOLD"
echo VECI_FAST_RECONNECT_POLICY=10s_x_3
echo VECI_FAST_RECONNECT_WATCHDOG=running
echo VECI_FAST_RECONNECT_AUTO_SIM=unchanged
echo VECI_FAST_RECONNECT_INTEGRITY=pass
echo VECI_FAST_RECONNECT_RELEASE=live_pass
