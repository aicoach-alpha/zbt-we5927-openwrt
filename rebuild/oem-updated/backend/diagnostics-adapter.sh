#!/bin/sh
# Bounded OEM diagnostic translation. No arbitrary command or raw AT.
set -ef
umask 077
. /usr/share/libubox/jshn.sh
fail() { json_init; json_add_string code -4; json_add_string reason "$1"; json_dump; exit 0; }
[ "$#" = 4 ] || fail "invalid request"
op="$1"; host="$2"; version="$3"; session="$4"
case "$session" in ''|*[!0-9a-f]*|00000000000000000000000000000000) fail "invalid session";; esac
[ "${#session}" = 32 ] || fail "invalid session"
case "$version" in 4|6) ;; *) fail "invalid IP version";; esac
if [ "$op" = site_survey ]; then
    json_init; json_add_string ubus_rpc_session "$session"; json_add_string scope ubus
    json_add_string object veci.v2.wifi; json_add_string function survey
    permit="$(ubus -t 3 call session access "$(json_dump)" | jsonfilter -e '@.access')" || fail "permission unavailable"
    [ "$permit" = true ] || fail "permission denied"
    native="$(ubus -t 18 call veci.v2.wifi survey '{}')" || fail "survey unavailable"
    field() { printf '%s' "$native" | jsonfilter -e "$1"; }
    [ "$(field '@.ok')" = true ] || fail "native survey refused"
    (json_load "$native" && json_get_type typ networks && [ "$typ" = array ]) || fail "survey inventory invalid"
    json_init; json_add_string code 1; json_add_string reason "native Wi-Fi survey"
    json_add_array data
    i=0
    while [ "$i" -lt 100 ]; do
        bssid="$(field "@.networks[$i].bssid" || true)"
        [ -n "$bssid" ] || break
        freq="$(field "@.networks[$i].frequency_mhz")" || fail "frequency unavailable"
        case "$freq" in *[!0-9]*|'') fail "invalid frequency";; esac
        if [ "$freq" = 2484 ]; then channel=14
        else
            [ "$freq" -ge 2412 ] && [ "$freq" -le 2472 ] && [ $(( (freq-2407)%5 )) = 0 ] || fail "unsupported frequency"
            channel=$(( (freq-2407)/5 ))
        fi
        json_add_object ""
        json_add_string bssid "$bssid"
        json_add_string ssid "$(field "@.networks[$i].ssid" || true)"
        json_add_string channel "$channel"
        json_add_string signal "$(field "@.networks[$i].signal_dbm" || true)"
        json_add_string enc "unknown"
        json_close_object
        i=$((i+1))
    done
    json_close_array; json_dump; exit 0
fi
# Domain or IP literal only; never accept flags, URLs or shell fragments.
case "$host" in ''|-*|.*|*[!a-zA-Z0-9.:-]*) fail "invalid host";; esac
[ "${#host}" -le 253 ] || fail "host too long"
rc=0
case "$op" in
    test_ping)
        if [ "$version" = 4 ]; then output="$(timeout 10 ping -c 4 -W 2 "$host" 2>&1)" || rc=$?
        else output="$(timeout 10 ping6 -c 4 -W 2 "$host" 2>&1)" || rc=$?; fi;;
    test_nslookup) output="$(timeout 10 nslookup "$host" 2>&1)" || rc=$?;;
    test_traceroute)
        if [ "$version" = 4 ]; then output="$(timeout 15 traceroute -m 5 -q 1 -w 2 "$host" 2>&1)" || rc=$?
        else output="$(timeout 15 traceroute6 -m 5 -q 1 -w 2 "$host" 2>&1)" || rc=$?; fi;;
    *) fail "unsupported diagnostic";;
esac
json_init; json_add_string code 1
if [ "$rc" = 0 ]; then json_add_string reason "diagnostic command completed"
else json_add_string reason "diagnostic command failed or timed out"; fi
json_add_int exit_code "$rc"
json_add_string data "$(printf '%s' "$output" | head -c 4096)"
json_dump
