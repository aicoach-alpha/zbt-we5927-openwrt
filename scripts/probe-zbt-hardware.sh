#!/bin/sh
# Read-only hardware probe for ZBT community support requests.
# Does not query IMEI/ICCID/IMSI and does not change network, GPIO or modem state.

echo '=== SYSTEM BOARD ==='
ubus call system board 2>/dev/null || true

echo
echo '=== OPENWRT RELEASE ==='
cat /etc/openwrt_release 2>/dev/null || true

echo
echo '=== MTD LAYOUT ==='
cat /proc/mtd 2>/dev/null || true

echo
echo '=== USB IDs ==='
for d in /sys/bus/usb/devices/*; do
  [ -r "$d/idVendor" ] || continue
  [ -r "$d/idProduct" ] || continue
  v="$(cat "$d/idVendor" 2>/dev/null)"
  p="$(cat "$d/idProduct" 2>/dev/null)"
  [ -n "$v$p" ] || continue
  printf '%s %s:%s\n' "$(basename "$d")" "$v" "$p"
done

echo
echo '=== TTY USB TOPOLOGY ==='
for t in /sys/class/tty/ttyUSB*; do
  [ -e "$t/device" ] || continue
  printf '%s -> %s\n' "/dev/$(basename "$t")" "$(readlink -f "$t/device" 2>/dev/null)"
done

echo
echo '=== NETWORK DEVICES ==='
for n in /sys/class/net/*; do
  printf '%s' "$(basename "$n")"
  if [ -e "$n/device" ]; then
    printf ' -> %s' "$(readlink -f "$n/device" 2>/dev/null)"
  fi
  printf '\n'
done

echo
echo '=== GPIOCHIPS ==='
for g in /sys/class/gpio/gpiochip*; do
  [ -e "$g" ] || continue
  printf '%s base=%s ngpio=%s label=%s\n' "$(basename "$g")" "$(cat "$g/base" 2>/dev/null)" "$(cat "$g/ngpio" 2>/dev/null)" "$(cat "$g/label" 2>/dev/null)"
done

echo
echo '=== NOTES ==='
echo 'This probe intentionally omits MAC addresses and cellular subscriber/device identifiers.'
