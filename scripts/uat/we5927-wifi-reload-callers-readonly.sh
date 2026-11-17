#!/bin/sh
# Read-only WE5927 restart caller audit. No network/radio/model changes or iw.
# Output avoids SSIDs, passwords, device IDs, phone numbers and script bodies.
set -u
printf '%s\n' '===== AP_LOSS_BOOT_WINDOW ====='
if [ -r /proc/uptime ]; then
  uptime_s="$(awk '{printf "%.0f", $1}' /proc/uptime)"
  now_s="$(date +%s)"
  case "$uptime_s:$now_s" in *[!0-9:]*|'':*) echo 'uptime=unavailable' ;;
    *)
      boot_s=$((now_s - uptime_s))
      printf 'boot_epoch=%s\nfirst_wifi_change_epoch=%s\nlast_wifi_unregister_epoch=%s\n' \
        "$boot_s" "$((boot_s + 1028))" "$((boot_s + 1139))"
      echo 'time_estimates=boot_relative_approximate_ntp_changes_possible'
      ;;
  esac
fi
printf '%s\n' '===== PHY_DRIVER ====='
phy0_driver=unknown
if [ -e /sys/class/ieee80211/phy0/device/driver ]; then
  phy0_driver="$(readlink /sys/class/ieee80211/phy0/device/driver 2>/dev/null |
    awk -F/ '{print $NF}')"
fi
printf 'phy0_driver=%s\n' "$phy0_driver"
printf '%s\n' '===== ATH12K_HOTPLUG_GATE ====='
ath=/etc/hotplug.d/ieee80211/11-ath12k-trigger
if [ -f "$ath" ]; then
  if grep -Fq 'DRIVER=ath12k_pci' "$ath"; then
    echo 'ath12k_trigger_has_driver_gate=1'
    if [ "$phy0_driver" != unknown ] && [ "$phy0_driver" != ath12k_pci ]; then
      echo 'ath12k_trigger_for_phy0=excluded_driver_mismatch'
    else
      echo 'ath12k_trigger_for_phy0=needs_review'
    fi
  else
    echo 'ath12k_trigger_has_driver_gate=0_review_exact_local_script'
  fi
  if grep -Eq 'ubus call network reload|network.wireless (down|up)' "$ath"; then
    echo 'ath12k_trigger_contains_reload_functions=1_not_proof_of_execution'
  fi
else
  echo 'ath12k_trigger=not_installed'
fi
printf '%s\n' '===== POSSIBLE_CALLERS (file:line only; not execution history) ====='
for f in /etc/rc.local /etc/crontabs/* /etc/hotplug.d/ieee80211/* \
         /etc/hotplug.d/iface/* /etc/hotplug.d/net/* \
         /usr/libexec/rpcd/veci /usr/sbin/veci-wifi-guardian; do
  [ -f "$f" ] || continue
  grep -nE 'wifi[[:space:]]+(reload|up|down)|network[[:space:]]+(reload|restart)|network.wireless[[:space:]]+(up|down)' "$f" 2>/dev/null |
    cut -d: -f1 |
    while IFS= read -r line; do
      printf '%s:%s\n' "$f" "$line"
    done
done
printf '%s\n' '===== STATUS ====='
if [ -e /sys/class/net/phy0-ap0 ]; then
  echo 'kernel_ap=present'
else
  echo 'kernel_ap=missing'
fi
printf '%s\n' '===== DONE ====='
