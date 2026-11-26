#!/bin/sh
# OEM contract translation only. Mutations exclusively use shared native RPC.
# Called from authenticated CGI with a bounded JSON request on stdin.
set -ef
umask 077
. /usr/share/libubox/jshn.sh
fail() { json_init; json_add_string code -4; json_add_string reason "$1"; json_dump; exit 0; }
read_field() { printf '%s' "$body" | jsonfilter -e "$1"; }
native_field() { printf '%s' "$native" | jsonfilter -e "$1"; }
rpc() {
    case "$1:$2" in veci.v2.dhcp:add|veci.v2.dhcp:delete|veci.v2.dhcp:status|veci.v2.system:setNtp|veci.v2.firewall:setDmz) ;; *) fail "unsupported RPC";; esac
    # Do not bypass the session's permission on the actual backend method.
    json_init; json_add_string ubus_rpc_session "$session"; json_add_string scope ubus
    json_add_string object "$1"; json_add_string function "$2"
    permit="$(ubus -t 3 call session access "$(json_dump)" | jsonfilter -e '@.access')" || fail "native permission unavailable"
    [ "$permit" = true ] || fail "native permission denied"
    native="$(ubus -t 20 call "$1" "$2" "$3")" || fail "native call failed"
    [ "$(native_field '@.ok')" = true ] || fail "native operation rejected"
}
[ "$#" = 2 ] || fail "invalid arguments"
op="$1"; session="$2"
case "$session" in ''|*[!0-9a-f]*|00000000000000000000000000000000) fail "invalid session";; esac
[ "${#session}" = 32 ] || fail "invalid session"
body="$(head -c 2049)"
[ "$(printf '%s' "$body" | wc -c)" -le 2048 ] || fail "request too large"
json_load "$body" || fail "invalid JSON"
case "$op" in
    set_static_dhcp)
        mac="$(read_field '@.mac')" || fail "MAC required"
        ip="$(read_field '@.ip')" || fail "IP required"
        name="$(read_field '@.name' || true)"
        lease="$(read_field '@.leasetime' || true)"
        default_lease="$(uci -q get dhcp.lan.leasetime || true)"
        [ -z "$lease" ] || [ "$lease" = "$default_lease" ] || fail "custom lease duration not supported"
        json_init; json_add_string mac "$mac"; json_add_string ip "$ip"; json_add_string name "$name"
        rpc veci.v2.dhcp add "$(json_dump)"
        ;;
    delete_static_dhcp)
        json_get_type typ maclist && [ "$typ" = array ] || fail "MAC list required"
        json_select maclist; json_get_keys keys; [ "$keys" = 1 ] || fail "select one reservation at a time"
        json_get_var mac 1; json_select ..
        mac="$(printf '%s' "$mac" | tr A-F a-f)"
        printf '%s\n' "$mac" | grep -Eiq '^([0-9a-f]{2}:){5}[0-9a-f]{2}$' || fail "invalid MAC"
        rpc veci.v2.dhcp status '{}'
        revision="$(native_field '@.revision')" || fail "revision unavailable"
        idx=0; match=""
        while [ "$idx" -lt 256 ]; do
            n="$(native_field "@.leases[$idx].index" || true)"
            [ -n "$n" ] || break
            [ "$n" = "$idx" ] || fail "invalid index"
            existing="$(native_field "@.leases[$idx].mac" | tr A-F a-f)"
            if [ "$existing" = "$mac" ]; then [ -z "$match" ] || fail "ambiguous lease"; match="$idx"; fi
            idx=$((idx+1))
        done
        [ -n "$match" ] || fail "reservation not found"
        json_init; json_add_int index "$match"; json_add_string revision "$revision"; json_add_string confirmation "DELETE_LEASE_$match"
        rpc veci.v2.dhcp delete "$(json_dump)"
        ;;
    set_ntp)
        first="$(read_field '@.server_primary')" || fail "NTP server required"
        second="$(read_field '@.server_secondary' || true)"
        client="$(read_field '@.enable_ntp_client')" || fail "NTP client flag required"
        server="$(read_field '@.enable_ntp_server')" || fail "NTP server flag required"
        timezone="$(read_field '@.timezone')" || fail "timezone required"
        [ "$client" = 1 ] || fail "disabling NTP client not supported"
        current_server="$(uci -q get system.ntp.enable_server || true)"
        [ "$server" = "${current_server:-0}" ] || fail "NTP server flag change not supported"
        [ "$timezone" = "$(uci -q get 'system.@system[0].timezone')" ] || fail "timezone change not supported"
        json_init; json_add_string first "$first"; json_add_string second "$second"; json_add_string confirmation SET_NTP
        rpc veci.v2.system setNtp "$(json_dump)"
        ;;
    set_dmz)
        enabled="$(read_field '@.enabled')" || fail "DMZ flag required"
        dest="$(read_field '@.ipaddr' || true)"
        ports="$(read_field '@.sport' || true)"
        confirm="$(read_field '@.confirmation')" || fail "explicit DMZ confirmation required"
        case "$enabled" in
            0) [ "$confirm" = DISABLE_DMZ ] || fail "confirmation mismatch"; dest=DISABLE;;
            1) [ "$ports" = 1-65535 ] || fail "custom port ranges not supported"; [ "$confirm" = "ENABLE_DMZ_$dest" ] || fail "confirmation mismatch";;
            *) fail "invalid DMZ flag";;
        esac
        json_init; json_add_string destination "$dest"; json_add_string confirmation "$confirm"
        rpc veci.v2.firewall setDmz "$(json_dump)"
        ;;
    *) fail "operation not implemented";;
esac
json_init; json_add_string code 1; json_add_string reason "native configuration saved"; json_dump
