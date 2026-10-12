#!/bin/sh
# WE5927 manual non-mutating SMS listing support test.
# ONLY AT+CMGL=? as specified by 3GPP TS 27.005, NOT AT+CMGL=4.
# Does not list/read messages, touch unread flags, persist raw AT,
# send SMS, start USSD, restart LTE or change modem modes/settings.
set -eu
umask 077
LC_ALL=C
export LC_ALL

fail() {
    case "$1" in
        board_mismatch|usb_not_verified|modem_busy|transport_missing)
            reason="$1" ;;
        *) reason=unavailable ;;
    esac
    printf '{"ok":false,"reason":"%s","cmgl_test":"not_tested"}\n' "$reason"
    exit 1
}
[ "$#" -eq 0 ] || exit 2
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = "zbtlink,zbt-we5927" ] ||
    fail board_mismatch
[ -x /usr/sbin/we5927-at ] || fail transport_missing
command -v flock >/dev/null 2>&1 || fail transport_missing
[ -c /dev/ttyUSB2 ] || fail usb_not_verified
real="$(readlink -f /sys/class/tty/ttyUSB2/device 2>/dev/null || :)"
case "$real" in /sys/devices/*:1.4/ttyUSB2) ;; *) fail usb_not_verified ;; esac
parent="$(dirname "$(dirname "$real")")"
[ "$(cat "$parent/idVendor" 2>/dev/null || :)" = 05c6 ] ||
    fail usb_not_verified
[ "$(cat "$parent/idProduct" 2>/dev/null || :)" = 902e ] ||
    fail usb_not_verified

parse_cmgl_test() {
    awk '
      { gsub(/\r/, "", $0); if ($0=="") next }
      $0=="AT+CMGL=?" && !seen && !ok && !echoed { echoed=1; next }
      $0 ~ /^\+CMGL:[ ]*\([0-9 ,.-]+\)[ ]*$/ && !seen && !ok {
          seen=1
          next
      }
      $0=="OK" && seen && !ok { ok=1; next }
      {bad=1}
      END { if (seen && ok && !bad) print "accepted"; else print "unknown" }
    '
}
(
    flock -n -x 9 || fail modem_busy
    raw="$(/usr/sbin/we5927-at /dev/ttyUSB2 'AT+CMGL=?' 3000 2>/dev/null)" ||
        raw=''
    result="$(printf '%s\n' "$raw" | parse_cmgl_test)"
    unset raw
    case "$result" in accepted|unknown) ;; *) result=unknown ;; esac
    printf '{"ok":true,"source":"read_only_at_test","cmgl_test":"%s","sms_messages_accessed":false}\n' "$result"
) 9>/var/lock/we5927-at.lock
