#!/bin/sh
# No-write W907 SMS mode readiness. Does not read SMS or run USSD.
set -eu
LC_ALL=C; export LC_ALL
[ "$#" = 0 ] || exit 2
die() { printf '{"ok":false,"reason":"%s"}\n' "$1"; exit 1; }
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = zbtlink,zbt-we5927 ] || die board_mismatch
[ -x /usr/sbin/we5927-at ] || die at_transport_missing
command -v flock >/dev/null 2>&1 || die lock_missing
[ -c /dev/ttyUSB2 ] || die at_port_missing
real="$(readlink -f /sys/class/tty/ttyUSB2/device 2>/dev/null)" || die at_port_missing
case "$real" in /sys/devices/*:1.4/ttyUSB2) ;; *) die wrong_usb_interface ;; esac
parent="$(dirname "$(dirname "$real")")"
[ "$(cat "$parent/idVendor" 2>/dev/null)" = 05c6 ] || die wrong_usb_vendor
[ "$(cat "$parent/idProduct" 2>/dev/null)" = 902e ] || die wrong_usb_product

# Strict single response and terminal OK; never return the raw modem output.
parse_cmgf() {
  awk '
  { gsub(/\r/, "", $0); if ($0 == "") next }
  $0 == "AT+CMGF?" && !seen && !ok { next }
  $0 ~ /^\+CMGF:[ ]*0[ ]*$/ && !seen && !ok { seen=1; mode="pdu"; next }
  $0 ~ /^\+CMGF:[ ]*1[ ]*$/ && !seen && !ok { seen=1; mode="text"; next }
  $0 == "OK" && seen && !ok { ok=1; next }
  { bad=1 }
  END { if (!bad && seen && ok) print mode; else print "unknown" }
  '
}
parse_cscs() {
  awk '
  { gsub(/\r/, "", $0); if ($0 == "") next }
  $0 == "AT+CSCS?" && !seen && !ok { next }
  $0 ~ /^\+CSCS:[ ]*"[^"]+"[ ]*$/ && !seen && !ok {
    text=$0; sub(/^[^"]*"/,"",text); sub(/".*$/,"",text)
    if (text=="GSM" || text=="IRA" || text=="UCS2" ||
        text=="UTF-8" || text=="HEX") result=text
    else result="other"
    seen=1; next
  }
  $0 == "OK" && seen && !ok { ok=1; next }
  { bad=1 }
  END { if (!bad && seen && ok) print result; else print "unknown" }
  '
}
(
 flock -n -x 9 || die modem_busy
 raw="$(/usr/sbin/we5927-at /dev/ttyUSB2 'AT+CMGF?' 1500 2>/dev/null)" || raw=''
 mode="$(printf '%s\n' "$raw" | parse_cmgf)"
 raw="$(/usr/sbin/we5927-at /dev/ttyUSB2 'AT+CSCS?' 1500 2>/dev/null)" || raw=''
 charset="$(printf '%s\n' "$raw" | parse_cscs)"
 unset raw
 case "$mode" in pdu|text|unknown) ;; *) mode=unknown ;; esac
 case "$charset" in GSM|IRA|UCS2|UTF-8|HEX|other|unknown) ;; *) charset=unknown ;; esac
 printf '{"ok":true,"source":"read_only_at","sms_mode":"%s","charset":"%s"}\n' "$mode" "$charset"
) 9>/var/lock/we5927-at.lock
