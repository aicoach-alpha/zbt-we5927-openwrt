#!/bin/sh
# Read-only profile detector. It never changes GPIO, modem or network state.

PROFILE_ROOT="${ZBT_PROFILE_ROOT:-/usr/share/zbt-family}"

board_name="$(cat /tmp/sysinfo/board_name 2>/dev/null)"
if [ -z "$board_name" ]; then
  board_name="$(ubus call system board 2>/dev/null | jsonfilter -e '@.board_name' 2>/dev/null)"
fi

board_profile=''
board_status=''
if command -v jsonfilter >/dev/null 2>&1 && [ -d "$PROFILE_ROOT/boards" ]; then
  for f in "$PROFILE_ROOT"/boards/*.json; do
    [ -f "$f" ] || continue
    for c in $(jsonfilter -i "$f" -e '@.openwrt_compatible[*]' 2>/dev/null); do
      if [ "$c" = "$board_name" ]; then
        board_profile="$(jsonfilter -i "$f" -e '@.id' 2>/dev/null)"
        board_status="$(jsonfilter -i "$f" -e '@.status' 2>/dev/null)"
        break 2
      fi
    done
  done
fi

usb_ids=''
for d in /sys/bus/usb/devices/*; do
  [ -r "$d/idVendor" ] || continue
  [ -r "$d/idProduct" ] || continue
  v="$(cat "$d/idVendor" 2>/dev/null)"
  p="$(cat "$d/idProduct" 2>/dev/null)"
  [ -n "$v$p" ] || continue
  usb_ids="$usb_ids $v:$p"
done

modem_profile=''
modem_status=''
modem_usb_id=''
if command -v jsonfilter >/dev/null 2>&1 && [ -d "$PROFILE_ROOT/modems" ]; then
  for f in "$PROFILE_ROOT"/modems/*.json; do
    [ -f "$f" ] || continue
    id="$(jsonfilter -i "$f" -e '@.id' 2>/dev/null)"
    status="$(jsonfilter -i "$f" -e '@.status' 2>/dev/null)"
    [ -n "$id" ] || continue
    for expected in $(jsonfilter -i "$f" -e '@.usb_ids[*]' 2>/dev/null); do
      for present in $usb_ids; do
        if [ "$expected" = "$present" ]; then
          modem_profile="$id"
          modem_status="$status"
          modem_usb_id="$present"
          break 3
        fi
      done
    done
  done
fi

echo "board_name=$board_name"
echo "board_profile=${board_profile:-unknown}"
echo "board_status=${board_status:-unknown}"
echo "usb_ids=$(echo "$usb_ids" | sed 's/^ *//')"
echo "modem_profile=${modem_profile:-unknown}"
echo "modem_status=${modem_status:-unknown}"
echo "modem_usb_id=${modem_usb_id:-unknown}"

if [ "$board_status" != 'tested' ] && [ "$board_status" != 'community-tested' ]; then
  echo 'build_safe=no'
  echo 'reason=board profile is not validated'
  exit 2
fi

if [ "$modem_status" != 'tested' ] && [ "$modem_status" != 'community-tested' ]; then
  echo 'modem_auto_control_safe=no'
  echo 'reason=modem profile is not validated'
  exit 3
fi

echo 'build_safe=yes'
echo 'modem_auto_control_safe=yes'
