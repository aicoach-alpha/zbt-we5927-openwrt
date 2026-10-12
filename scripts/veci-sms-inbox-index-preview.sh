#!/bin/sh
# WE5927 one-shot, operator-only PDU SMS metadata preview.
# WARNING: AT+CMGL=4 may mark unread SMS as read (3GPP TS 27.005).
# No SMS contents, sender, PDU, OTP or raw AT reply is ever printed.
# NO package installation, daemon, RPC, retry, mode changes or persistence.
set -eu
umask 077
LC_ALL=C
export LC_ALL

fail() {
    case "$1" in
        explicit_consent_required|board_mismatch|unverified_modem|modem_busy|transport_missing|pdu_mode_required|response_unavailable|invalid_response) reason="$1" ;;
        *) reason=unavailable ;;
    esac
    printf '{"ok":false,"reason":"%s","messages":[]}\n' "$reason"
    exit 1
}
# Two deliberate CLI acknowledgements, not supplied by an untrusted web
# request. Running as root over private, authenticated SSH is required.
[ "$#" -eq 2 ] || fail explicit_consent_required
[ "$1" = "--show-indices-only" ] &&
[ "$2" = "--ack-unread-may-be-marked-read" ] ||
    fail explicit_consent_required
[ "$(id -u)" -eq 0 ] || fail explicit_consent_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] ||
    fail board_mismatch
[ -x /usr/sbin/we5927-at ] || fail transport_missing
command -v flock >/dev/null 2>&1 || fail transport_missing
# Confirm physical identity only AFTER the shared lock is held.
# This still does NOT replace production opened-FD attestation.

# Strict parser: reject unsolicited lines, nonhex PDUs, duplicates,
# truncation, invalid TPDU lengths, more than 16 entries and post-OK data.
# Output only after final OK, never before. No raw bytes emitted.
parse_list() {
    awk '
      function decimal(v, limit) {
        return v ~ /^[0-9]+$/ && length(v) <= 5 && v+0 <= limit
      }
      function invalid() { bad=1 }
      function parse_head(line, a,n,id,status,len,i) {
        sub(/^\+CMGL:[ ]*/, "", line)
        gsub(/[ ]/, "", line)
        n=split(line,a,",")
        if (n != 4 || !decimal(a[1],65535) ||
            !decimal(a[2],4) || a[3] != "" ||
            !decimal(a[4],240) || (a[4]+0) < 1) return 0
        id=a[1]+0
        for (i=1; i<=count; i++)
          if (idx[i] == id) return 0
        pending_index=id
        pending_status=a[2]+0
        pending_len=a[4]+0
        return 1
      }
      function check_pdu(v, upper, bytes, smsclen,hi,lo) {
        upper=toupper(v)
        if (length(upper)%2 || length(upper) > 512 ||
            length(upper) < 4 || upper ~ /[^0-9A-F]/) return 0
        hi=index("0123456789ABCDEF",substr(upper,1,1))-1
        lo=index("0123456789ABCDEF",substr(upper,2,1))-1
        if (hi<0 || lo<0) return 0
        smsclen=16*hi+lo
        bytes=length(upper)/2
        return bytes > 1+smsclen && (bytes-1-smsclen)==pending_len
      }
      {
        if (length($0)>1024) { invalid(); next }
        gsub(/\r/, "", $0)
        if ($0=="") next
        if (bad) next
        if (done) { invalid(); next }
        if (!echoed && !count && !pending && $0=="AT+CMGL=4") {
          echoed=1; next
        }
        if (pending) {
          if (!check_pdu($0)) { invalid(); next }
          count++
          if (count>16) { invalid(); next }
          idx[count]=pending_index
          stat[count]=pending_status
          length_tpdu[count]=pending_len
          pending=0
          next
        }
        if ($0 ~ /^\+CMGL:[ ]*/) {
          if (count>=16 || !parse_head($0)) { invalid(); next }
          pending=1; next
        }
        if ($0=="OK" && !pending) { done=1; next }
        invalid()
      }
      END {
        if (bad || pending || !done) exit 1
        printf "{\"ok\":true,\"source\":\"on_demand_cmgl\",\"side_effect_acknowledged\":true,\"count\":%d,\"messages\":[",count
        for (i=1; i<=count; i++) {
          if (i>1) printf ","
          printf "{\"index\":%d,\"status\":%d,\"tpdu_octets\":%d}",idx[i],stat[i],length_tpdu[i]
        }
        print "]}"
      }
    '
}
parse_mode() {
    awk '
      {gsub(/\r/,"",$0);if($0=="")next}
      $0=="AT+CMGF?" && !seen && !ok {next}
      $0 ~ /^\+CMGF:[ ]*0[ ]*$/ && !seen && !ok {seen=1;next}
      $0=="OK" && seen && !ok {ok=1;next}
      {bad=1}
      END{if(!bad && seen && ok)print "pdu";else print "unknown"}
    '
}

# Lock covers mode check AND actual CMGL query. Avoid raw temporary files.
# This CLI can change unread flags: only run on deliberate user command.
(
    flock -n -x 9 || fail modem_busy
    [ -c /dev/ttyUSB2 ] || fail unverified_modem
    port="$(readlink -f /sys/class/tty/ttyUSB2/device 2>/dev/null || :)"
    case "$port" in /sys/devices/*:1.4/ttyUSB2) ;; *) fail unverified_modem ;; esac
    parent="$(dirname "$(dirname "$port")")"
    [ "$(cat "$parent/idVendor" 2>/dev/null || :)" = 05c6 ] ||
        fail unverified_modem
    [ "$(cat "$parent/idProduct" 2>/dev/null || :)" = 902e ] ||
        fail unverified_modem
    raw="$(/usr/sbin/we5927-at /dev/ttyUSB2 'AT+CMGF?' 1500 2>/dev/null)" ||
        fail response_unavailable
    mode="$(printf '%s\n' "$raw" | parse_mode)"
    unset raw
    [ "$mode" = pdu ] || fail pdu_mode_required
    raw="$(/usr/sbin/we5927-at /dev/ttyUSB2 'AT+CMGL=4' 5000 2>/dev/null)" ||
        fail response_unavailable
    # No stdout before parser successfully validates entire message set.
    parsed="$(printf '%s\n' "$raw" | parse_list)" ||
        fail invalid_response
    unset raw
    printf '%s\n' "$parsed"
) 9>/var/lock/we5927-at.lock
