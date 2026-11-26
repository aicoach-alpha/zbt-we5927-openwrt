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
    case "$1:$2" in veci.v2.dhcp:add|veci.v2.dhcp:delete|veci.v2.dhcp:status|veci.v2.system:setNtp|veci.v2.firewall:setDmz|veci.v2.interfaces:status|veci.v2.interfaces:save|veci.v2.lte:status|veci.v2.lte:setApn|veci.v2.lte:setFailover|veci.v2.lte:setMonitor|veci.v2.sim:switchSim|veci.v2.wifi:setSsid|veci.v2.wifi:setChannel|veci.v2.wifi:setAutoChannel|veci.v2.wifi:setVisibility|veci.v2.wifi:setAuth|veci.v2.wifi:setAccess) ;; *) fail "unsupported RPC";; esac
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
    set_lan_config|set_wan_config)
        confirm="$(read_field '@.confirmation')" || fail "explicit network confirmation required"
        [ "$confirm" = SAVE_NETWORK ] || fail "confirmation mismatch"
        rpc veci.v2.interfaces status '{}'
        revision="$(native_field '@.revision')" || fail "revision unavailable"
        expected="$(read_field '@.revision')" || fail "revision required"
        [ "$revision" = "$expected" ] || fail "stale network configuration"
        lan="$(native_field '@.lan')" || fail "LAN unavailable"
        lan_mask="$(native_field '@.lan_mask')" || fail "LAN mask unavailable"
        mode="$(native_field '@.wan_mode')" || fail "WAN mode unavailable"
        wan="$(native_field '@.wan' || true)"
        wan_mask="$(native_field '@.wan_mask' || true)"
        gateway="$(native_field '@.gateway' || true)"
        if [ "$op" = set_lan_config ]; then
            lan="$(read_field '@.ipaddr')" || fail "LAN address required"
            lan_mask="$(read_field '@.netmask')" || fail "LAN mask required"
        else
            mode="$(read_field '@.proto')" || fail "WAN protocol required"
            case "$mode" in dhcp) wan=""; wan_mask=""; gateway="";;
                static) wan="$(read_field '@.ipaddr')" || fail "WAN address required"
                    wan_mask="$(read_field '@.netmask')" || fail "WAN mask required"
                    gateway="$(read_field '@.gateway')" || fail "WAN gateway required";;
                *) fail "WAN protocol unsupported";;
            esac
            # Do not silently discard a DNS or PPPoE change.
            for key in dns_primary dns_secondary username password service ac; do
                [ -z "$(read_field "@.$key" || true)" ] || fail "separate DNS or PPPoE configuration required"
            done
        fi
        json_init
        json_add_string revision "$revision"; json_add_string confirm "$confirm"
        json_add_string lan "$lan"; json_add_string lan_mask "$lan_mask"
        json_add_string wan_mode "$mode"; json_add_string wan "$wan"
        json_add_string wan_mask "$wan_mask"; json_add_string gateway "$gateway"
        rpc veci.v2.interfaces save "$(json_dump)"
        ;;
    set_4g)
        # Single explicit action avoids partly applying a legacy multi-field form.
        action="$(read_field '@.action')" || fail "explicit LTE action required"
        case "$action" in
            SET_APN)
                apn="$(read_field '@.apn')" || fail "APN required"
                json_init; json_add_string apn "$apn"
                rpc veci.v2.lte setApn "$(json_dump)";;
            ENABLE_FAILOVER|DISABLE_FAILOVER)
                json_init; json_add_string action "$action"
                rpc veci.v2.lte setFailover "$(json_dump)";;
            *) fail "unsupported LTE action";;
        esac
        ;;
    set_4g_sim)
        slot="$(read_field '@.slot')" || fail "SIM slot required"
        confirm="$(read_field '@.confirmation')" || fail "confirmation required"
        case "$slot:$confirm" in 1:SWITCH_SIM_1|2:SWITCH_SIM_2) ;; *) fail "SIM confirmation mismatch";; esac
        json_init; json_add_int slot "$slot"; json_add_string confirmation "$confirm"
        rpc veci.v2.sim switchSim "$(json_dump)"
        ;;
    set_netwatchdog)
        interval="$(read_field '@.detect_itv')" || fail "monitor interval required"
        expected="$(read_field '@.expected')" || fail "previous interval required"
        action="$(read_field '@.action')" || fail "recovery policy required"
        [ "$action" = lte_recovery ] || fail "global network reset is unsupported"
        host="$(read_field '@.detect_host1')" || fail "monitor host required"
        [ "$host" = "$(uci -q get we5927_lte.main.ping_host)" ] || fail "monitor host change unsupported"
        [ -z "$(read_field '@.detect_host2' || true)" ] || fail "second monitor host unsupported"
        json_init; json_add_string interval "$interval"; json_add_string expected "$expected"
        rpc veci.v2.lte setMonitor "$(json_dump)"
        ;;
    setWiFi2)
        # Explicitly scoped saves; no global reload or implicit AP activation.
        action="$(read_field '@.action')" || fail "explicit Wi-Fi action required"
        case "$action" in
            SET_SSID)
                ssid="$(read_field '@.ssid_hex')" || fail "encoded SSID required"
                json_init; json_add_string ssid_hex "$ssid"
                rpc veci.v2.wifi setSsid "$(json_dump)";;
            SET_CHANNEL)
                channel="$(read_field '@.channel')" || fail "channel required"
                if [ "$channel" = 0 ]; then
                    json_init; json_add_string action AUTO_CHANNEL_2G
                    rpc veci.v2.wifi setAutoChannel "$(json_dump)"
                else
                    json_init; json_add_string channel "$channel"
                    rpc veci.v2.wifi setChannel "$(json_dump)"
                fi;;
            SHOW_SSID|HIDE_SSID)
                json_init; json_add_string action "$action"
                rpc veci.v2.wifi setVisibility "$(json_dump)";;
            SET_AUTH)
                mode="$(read_field '@.encryption')" || fail "security mode required"
                key="$(read_field '@.key_hex')" || fail "encoded key required"
                json_init; json_add_string mode "$mode"; json_add_string key_hex "$key"
                rpc veci.v2.wifi setAuth "$(json_dump)";;
            SET_ACCESS)
                mode="$(read_field '@.macfilter')" || fail "access mode required"
                macs="$(read_field '@.addresses')" || fail "MAC list required"
                json_init; json_add_string mode "$mode"; json_add_string addresses "$macs"
                rpc veci.v2.wifi setAccess "$(json_dump)";;
            *) fail "unsupported Wi-Fi action";;
        esac
        ;;
    *) fail "operation not implemented";;
esac
json_init; json_add_string code 1; json_add_string reason "native operation accepted"
case "$op" in set_lan_config|set_wan_config|setWiFi2) json_add_string apply_state pending_manual_activation;; esac
json_dump
