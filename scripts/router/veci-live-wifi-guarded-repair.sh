#!/bin/sh
# VeCI only-router guarded Wi-Fi repair. No reboot/flash/restart-network.
# Run on the ZBT-WE5927 via local Ethernet SSH as root, not from andre-nas.
set -eu
umask 077
tag=veci-owner-wifi-uat
die() { echo "WIFI_REPAIR_STOP=$1"; exit 2; }
get() { uci -q get "$1" 2>/dev/null || :; }
[ "$(id -u)" = 0 ] || die root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = "zbtlink,zbt-we5927" ] || die wrong_board
[ -f /etc/config/wireless ] && [ ! -L /etc/config/wireless ] || die wireless_config_missing
[ "$(get wireless.radio0)" = wifi-device ] || die missing_radio_section
[ "$(get wireless.radio0.band)" = 2g ] || die unsupported_radio_band
[ "$(get wireless.default_radio0)" = wifi-iface ] || die missing_primary_ap
[ "$(get wireless.default_radio0.device)" = radio0 ] || die wrong_primary_ap_radio
[ "$(get wireless.default_radio0.mode)" = ap ] || die primary_ap_not_ap_mode
[ -e /sys/class/ieee80211/phy0 ] || die phy0_missing
[ -d /sys/class/net/br-lan ] || die wired_lan_missing
ip -4 route show default | grep -q ' dev usb0 ' || die lte_default_route_missing
command -v wpad >/dev/null 2>&1 || die wpad_missing
# Never execute /sbin/wifi up: the shipped OpenWrt helper also triggers
# 'ubus call network reload' and can interrupt the working LTE connection.
# Keep the attempt explicitly restricted to netifd's radio0 object.
command -v ubus >/dev/null 2>&1 || die ubus_missing
ubus -S -t 3 list network.wireless 2>/dev/null | grep -Fxq network.wireless ||
  die network_wireless_ubus_missing
command -v jsonfilter >/dev/null 2>&1 || die jsonfilter_missing
[ -z "$(uci -q changes wireless 2>/dev/null || :)" ] || die pending_wireless_changes
if dmesg 2>/dev/null | grep -Eiq 'mt76.*(mcu.*timeout|reset failed|timed out)|mt7603.*(timeout|failed)'; then
  die prior_mt76_kernel_timeout_abort_to_preserve_router
fi
if [ "$(get wireless.radio0.disabled)" != 1 ] &&
   [ "$(get wireless.default_radio0.disabled)" != 1 ]; then
  echo "WIFI_REPAIR_STOP=radio_not_explicitly_disabled_use_readonly_diagnosis"; exit 2
fi

backup_dir=/root/veci-router-uat
mkdir -p "$backup_dir" || die backup_dir_not_writable
chmod 700 "$backup_dir" || die backup_dir_chmod_failed
stamp="$(date -u '+%Y%m%dT%H%M%SZ')"
backup="$backup_dir/wireless-before-$stamp.uci"
cp -p /etc/config/wireless "$backup" || die backup_failed
chmod 600 "$backup" || die backup_chmod_failed
cmp -s "$backup" /etc/config/wireless || die backup_verify_failed
echo "WIFI_BACKUP=$backup"
root="$(mktemp -d /tmp/veci-wifi-apply.XXXXXX)" || die tmp_dir_failed
chmod 700 "$root"
success_flag="$root/success"
rollback_flag="$root/rollback"
# Safety watchdog in a separate process; restores original radio settings
# even if our SSH connection is lost. Never changes LAN/LTE/network/firewall.
(
  sleep 75
  if [ ! -f "$success_flag" ]; then
    uci -q revert wireless >/dev/null 2>&1 || :
    cp -p "$backup" /etc/config/wireless || :
    # Restore UCI only. Do NOT command a radio reset or restart netifd:
    # known MT76 MCU hang may make such operations unsafe.
    touch "$rollback_flag"
    logger -t "$tag" "WiFi UCI restored; radio runtime may require separate diagnosis" || :
  fi
) </dev/null >/dev/null 2>&1 &
watchdog_pid=$!
restored=no
restore_now() {
  [ "$restored" = yes ] && return
  restored=yes
  uci -q revert wireless >/dev/null 2>&1 || :
  if cp -p "$backup" /etc/config/wireless &&
     cmp -s "$backup" /etc/config/wireless; then
    echo 'WIFI_UCI_ROLLBACK=PASS'
  else
    echo 'WIFI_UCI_ROLLBACK=FAILED_MANUAL_REVIEW_REQUIRED'
  fi
  touch "$rollback_flag"
  logger -t "$tag" "WiFi UCI restored after guarded attempt failure; no radio reset" || :
}
cleanup() {
  status="$?"
  if [ "$status" -ne 0 ] && [ ! -f "$rollback_flag" ]; then
    restore_now
  fi
  if [ "$status" -eq 0 ]; then
    touch "$success_flag"
  fi
}
trap 'cleanup' EXIT
trap 'exit 130' INT TERM HUP

# Do not expose unencrypted OpenWrt default SSID or overwrite valid WPA2 keys.
new_key=no
existing_key="$(get wireless.default_radio0.key)"
encryption="$(get wireless.default_radio0.encryption)"
key_length="$(printf %s "$existing_key" | wc -c | tr -d ' ')"
case "$encryption" in psk2|sae|sae-mixed|psk-mixed)
  if [ "$key_length" -ge 8 ] && [ "$key_length" -le 63 ]; then
    key="$existing_key"
  else
    new_key=yes
  fi
  ;;
  *) new_key=yes ;;
esac
if [ "$new_key" = yes ]; then
  key="$(dd if=/dev/urandom bs=1 count=24 2>/dev/null | od -An -tx1 | tr -d ' \n')"
  [ "$(printf %s "$key" | wc -c)" = 48 ] || die key_generation_failed
  uci -q set 'wireless.default_radio0.encryption=psk2' || die set_encryption_failed
  uci -q set "wireless.default_radio0.key=$key" || die set_key_failed
fi
unset existing_key
# Preserve existing SSIDs except the insecure factory default.
ssid="$(get wireless.default_radio0.ssid)"
if [ -z "$ssid" ] || [ "$ssid" = OpenWrt ]; then
  uci -q set 'wireless.default_radio0.ssid=VeCI-WE5927' || die set_ssid_failed
fi
uci -q set 'wireless.default_radio0.mode=ap' || die set_mode_failed
uci -q set 'wireless.default_radio0.network=lan' || die set_network_binding_failed
uci -q set 'wireless.radio0.disabled=0' || die set_radio_failed
uci -q set 'wireless.default_radio0.disabled=0' || die set_ap_failed
uci -q commit wireless || die commit_failed

echo 'WIFI_APPLY_ATTEMPT=bounded_ubus_only_radio0_no_network_reload'
# If radio0 was already reported up but had no AP interface, this method
# may legitimately be a no-op. Do not force a down/reload or a driver reset.
ubus -S -t 12 call network.wireless up '{"device":"radio0"}' >/dev/null 2>&1 ||
  die radio0_targeted_up_rpc_failed
attempt=0
confirmed=no
while [ "$attempt" -lt 9 ]; do
  attempt=$((attempt + 1))
  wireless="$(ubus -S -t 3 call network.wireless status '{}' 2>/dev/null || :)"
  up="$(printf %s "$wireless" | jsonfilter -e '@.radio0.up' 2>/dev/null || :)"
  iface="$(printf %s "$wireless" | jsonfilter -e '@.radio0.interfaces[@.section="default_radio0"].ifname' 2>/dev/null || :)"
  case "$iface" in ''|*[!a-zA-Z0-9_.-]*) iface= ;; esac
  if [ "$up" = true ] && [ -n "$iface" ] && [ -e "/sys/class/net/$iface/phy80211" ]; then
    state="$(ubus -S -t 3 call "hostapd.$iface" get_status '{}' 2>/dev/null |
      jsonfilter -e '@.status' 2>/dev/null || :)"
    if [ "$state" = ENABLED ]; then confirmed=yes; break; fi
  fi
  sleep 2
done
[ "$confirmed" = yes ] || die hostapd_ap_not_enabled_rollback
[ -d /sys/class/net/br-lan ] || die ethernet_bridge_lost_rollback
ip -4 route show default | grep -q ' dev usb0 ' || die lte_default_route_lost_rollback
touch "$success_flag"
echo 'WIFI_AP_SERVICE=PASS_HOSTAPD_ENABLED'
echo 'WIFI_FIRMWARE_DRIVER=NOT_YET_CLIENT_ASSOCIATION_TESTED'
echo 'WIFI_CLIENT_BROWSING=NOT_YET_TESTED'
if [ "$new_key" = yes ]; then
  printf 'WIFI_SSID=%s\n' "$(get wireless.default_radio0.ssid)"
  printf 'NEW_WIFI_PASSWORD_PRIVATE_DO_NOT_SHARE=%s\n' "$key"
  echo 'IMPORTANT=Write_this_wifi_password_down_locally_do_not_paste_into_chat'
else
  echo 'WIFI_PASSWORD=existing_key_preserved_not_printed'
fi
echo "WIFI_REPAIR_STATUS=AP_STARTED_CONFIGURATION_SAVED"
echo 'WIFI_FINAL_ROLLBACK=not_needed_based_on_hostapd_ubus'
logger -t "$tag" "WiFi guarded AP provisioning passed hostapd (client association untested)" || :
exit 0
