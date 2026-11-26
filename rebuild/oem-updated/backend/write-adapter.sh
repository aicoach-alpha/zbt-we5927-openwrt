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
    case "$1:$2" in veci.v2.dhcp:add|veci.v2.dhcp:delete|veci.v2.dhcp:status|veci.v2.dhcp:setPool|veci.v2.addon:setPortalStartup|veci.v2.addon:setOptionalStartup|veci.v2.addon:ddnsLookup|veci.v2.system:setNtp|veci.v2.firewall:setDmz|veci.v2.firewall:setDefaults|veci.v2.firewall:setOffload|veci.v2.firewall:setMacBlock|veci.v2.firewall:setTtl|veci.v2.interfaces:status|veci.v2.interfaces:save|veci.v2.interfaces:pppoeAction|veci.v2.interfaces:pppoeDiscovery|veci.v2.lte:status|veci.v2.lte:setApn|veci.v2.lte:setFailover|veci.v2.lte:setMonitor|veci.v2.sim:switchSim|veci.v2.wifi:setSsid|veci.v2.wifi:setChannel|veci.v2.wifi:setAutoChannel|veci.v2.wifi:setVisibility|veci.v2.wifi:setAuth|veci.v2.wifi:setAccess|veci.v2.wifi:setPower|veci.v2.cron:setReboot|veci.v2.routes:save|veci.v2.routes:remove|veci.v2.firewall:addForward|veci.v2.firewall:deleteForward) ;; *) fail "unsupported RPC";; esac
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
    ddns_detection)
        [ "$(read_field '@.confirmation')" = CHECK_DDNS_LOOKUP ] || fail "confirmation required"
        rpc veci.v2.addon ddnsLookup '{}'
        output="$(native_field '@.output' || true)"
        rc="$(native_field '@.exit_code')" || fail "lookup result unavailable"
        json_init; json_add_string code 1; json_add_string reason "DNS lookup only; update not verified"
        json_add_string detection_ret "$output"; json_add_string exit_code "$rc"
        json_add_string provider_update_verified false; json_dump; exit 0
        ;;
    set_ddns|set_qos_status)
        revision="$(read_field '@.revision')" || fail "profile revision required"
        confirmation="$(read_field '@.confirmation')" || fail "confirmation required"
        if [ "$op" = set_ddns ]; then
            service=ddns; enabled="$(read_field '@.enabled')" || fail "enabled flag required"
            case "$enabled:$confirmation" in 1:ENABLE_DDNS_NEXT_BOOT|0:DISABLE_DDNS_NEXT_BOOT) ;; *) fail "confirmation mismatch";; esac
            # Do not accept a legacy combined profile replacement here.
            for field_name in services username password domain poll_time log_path; do
                [ -z "$(read_field "@.$field_name" || true)" ] || fail "profile editing unsupported"
            done
        else
            service=sqm; enabled="$(read_field '@.qos_enabled')" || fail "enabled flag required"
            case "$enabled:$confirmation" in 1:ENABLE_SQM_NEXT_BOOT|0:DISABLE_SQM_NEXT_BOOT) ;; *) fail "confirmation mismatch";; esac
        fi
        json_init; json_add_string service "$service"; json_add_string enabled "$enabled"
        json_add_string revision "$revision"; json_add_string confirmation "$confirmation"
        rpc veci.v2.addon setOptionalStartup "$(json_dump)"
        json_init; json_add_string code 1; json_add_string reason "profile startup setting saved"
        json_add_string apply_state pending_manual_activation; json_dump; exit 0
        ;;
    pppoe_disconnect|pppoe_reconnect|pppoe_detection)
        confirmation="$(read_field '@.confirmation')" || fail "confirmation required"
        case "$op" in
            pppoe_detection)
                [ "$confirmation" = DISCOVER_ETHERNET_PPPOE ] || fail "confirmation mismatch"
                rpc veci.v2.interfaces pppoeDiscovery '{}'
                output="$(native_field '@.output' || true)"
                rc="$(native_field '@.exit_code')" || fail "discovery result unavailable"
                json_init; json_add_string code 1; json_add_string reason "discovery completed; inspect exit code"
                json_add_object data
                json_add_string pppoe_detection "$output"; json_add_string exit_code "$rc"
                json_close_object; json_dump; exit 0;;
            pppoe_disconnect) action=disconnect; expected=DISCONNECT_ETHERNET_PPPOE;;
            pppoe_reconnect) action=reconnect; expected=RECONNECT_ETHERNET_PPPOE;;
        esac
        [ "$confirmation" = "$expected" ] || fail "confirmation mismatch"
        revision="$(read_field '@.revision')" || fail "revision required"
        json_init; json_add_string action "$action"; json_add_string revision "$revision"
        json_add_string confirmation "$confirmation"
        rpc veci.v2.interfaces pppoeAction "$(json_dump)"
        json_init; json_add_string code 1; json_add_string reason "Ethernet PPPoE action requested"
        json_add_string apply_state pending_verification
        json_dump; exit 0
        ;;
    set_ttl)
        enabled="$(read_field '@.ttl_enabled')" || fail "TTL flag required"
        ttl="$(read_field '@.ttl_cnt' || true)"
        revision="$(read_field '@.revision')" || fail "revision required"
        confirmation="$(read_field '@.confirmation')" || fail "confirmation required"
        case "$enabled:$confirmation" in 0:DISABLE_FORWARD_TTL|1:ENABLE_FORWARD_TTL) ;; *) fail "confirmation mismatch";; esac
        json_init; json_add_string enabled "$enabled"; json_add_string ttl "$ttl"
        json_add_string revision "$revision"; json_add_string confirmation "$confirmation"
        rpc veci.v2.firewall setTtl "$(json_dump)"
        json_init; json_add_string code 1; json_add_string reason "TTL policy saved"
        json_add_string runtime "$(native_field '@.runtime')"; json_add_string packet_verified false
        json_dump; exit 0
        ;;
    set_wifi_power)
        dbm="$(read_field '@.dbm')" || fail "native power value required"
        expected="$(read_field '@.expected')" || fail "previous power required"
        confirm="$(read_field '@.confirmation')" || fail "confirmation required"
        [ "$confirm" = SAVE_TXPOWER_NEXT_BOOT ] || fail "confirmation mismatch"
        json_init; json_add_string dbm "$dbm"; json_add_string expected "$expected"
        json_add_string confirmation "$confirm"
        rpc veci.v2.wifi setPower "$(json_dump)"
        ;;
    setAutoreboot)
        enabled="$(read_field '@.enabled')" || fail "schedule enable state required"
        hour="$(read_field '@.hour')" || fail "hour required"
        minute="$(read_field '@.minute')" || fail "minute required"
        weekdays="$(read_field '@.weekdays')" || fail "weekdays required"
        revision="$(read_field '@.revision' || true)"
        confirm="$(read_field '@.confirmation')" || fail "confirmation required"
        case "$enabled:$confirm" in 1:ENABLE_SCHEDULED_REBOOT|0:DISABLE_SCHEDULED_REBOOT) ;; *) fail "confirmation mismatch";; esac
        json_init; json_add_string enabled "$enabled"; json_add_string hour "$hour"
        json_add_string minute "$minute"; json_add_string weekdays "$weekdays"
        json_add_string revision "$revision"; json_add_string confirmation "$confirm"
        rpc veci.v2.cron setReboot "$(json_dump)"
        ;;
    set_wifi_client)
        mac="$(read_field '@.macaddr')" || fail "MAC required"
        operation="$(read_field '@.operation')" || fail "operation required"
        revision="$(read_field '@.revision')" || fail "firewall revision required"
        confirm="$(read_field '@.confirmation')" || fail "confirmation required"
        printf '%s\n' "$mac" | grep -Eiq '^[0-9a-f][02468ace](:[0-9a-f]{2}){5}$' || fail "invalid MAC"
        mac="$(printf '%s' "$mac" | tr A-F a-f)"
        [ "$mac" != 00:00:00:00:00:00 ] || fail "invalid MAC"
        case "$operation:$confirm" in REJECT:BLOCK_CLIENT|ACCEPT:UNBLOCK_CLIENT) ;; *) fail "confirmation mismatch";; esac
        rpc veci.v2.firewall status '{}'
        [ "$(native_field '@.revision')" = "$revision" ] || fail "stale firewall configuration"
        (json_load "$native" && json_get_type typ blocked_macs && [ "$typ" = array ]) || fail "MAC inventory unavailable"
        addresses=""; found=0
        for entry in $(native_field '@.blocked_macs[*]' || true); do
            printf '%s\n' "$entry" | grep -Eiq '^[0-9a-f]{2}(:[0-9a-f]{2}){5}$' || fail "invalid existing MAC"
            entry="$(printf '%s' "$entry" | tr A-F a-f)"
            if [ "$entry" = "$mac" ]; then found=1; continue; fi
            addresses="${addresses:+$addresses }$entry"
        done
        if [ "$operation" = REJECT ]; then addresses="${addresses:+$addresses }$mac"; fi
        # Idempotent request, preserve all other entries. Native revision guard
        # prevents races with the full-list editor.
        if [ "$operation:$found" != ACCEPT:0 ] && [ "$operation:$found" != REJECT:1 ]; then
            json_init; json_add_string revision "$revision"; json_add_string confirmation SAVE_MAC_BLOCK
            json_add_string addresses "$addresses"
            rpc veci.v2.firewall setMacBlock "$(json_dump)"
        fi
        json_init; json_add_string code 1; json_add_string reason "native client policy accepted"
        json_add_string return_operation "$operation"; json_add_string scope lan_to_wan
        json_dump; exit 0
        ;;
    set_mac_blacklist)
        revision="$(read_field '@.revision')" || fail "firewall revision required"
        confirm="$(read_field '@.confirmation')" || fail "explicit confirmation required"
        [ "$confirm" = SAVE_MAC_BLOCK ] || fail "confirmation mismatch"
        json_get_type typ mac_blacklist && [ "$typ" = array ] || fail "MAC array required"
        json_select mac_blacklist; json_get_keys keys
        addresses=""
        for key in $keys; do
            json_get_type kind "$key" && [ "$kind" = string ] || fail "MAC must be string"
            json_get_var mac "$key"
            printf '%s\n' "$mac" | grep -Eiq '^[0-9a-f]{2}(:[0-9a-f]{2}){5}$' || fail "invalid MAC"
            addresses="${addresses:+$addresses }$mac"
        done
        json_select ..
        json_init; json_add_string revision "$revision"; json_add_string confirmation "$confirm"
        json_add_string addresses "$addresses"
        rpc veci.v2.firewall setMacBlock "$(json_dump)"
        ;;
    set_fw_setting|set_nat_acceleration)
        revision="$(read_field '@.revision')" || fail "firewall revision required"
        confirm="$(read_field '@.confirmation')" || fail "explicit confirmation required"
        if [ "$op" = set_fw_setting ]; then
            [ "$confirm" = SAVE_FIREWALL_DEFAULTS ] || fail "confirmation mismatch"
            drop="$(read_field '@.drop_invalid')" || fail "drop-invalid flag required"
            syn="$(read_field '@.syn_flood')" || fail "SYN flood flag required"
            wan="$(read_field '@.prohibit_wan_ping' || true)"
            case "$wan" in ''|0) ;; *) fail "WAN management exposure refused";; esac
            for option in disable_ipv6 accept_redirects; do
                requested="$(read_field "@.$option" || true)"
                current="$(uci -q get "firewall.@defaults[0].$option" || true)"
                [ -z "$requested" ] || [ "$requested" = "${current:-0}" ] || fail "unsupported firewall option change"
            done
            json_init; json_add_string revision "$revision"; json_add_string confirmation "$confirm"
            json_add_string drop_invalid "$drop"; json_add_string syn_flood "$syn"
            rpc veci.v2.firewall setDefaults "$(json_dump)"
        else
            [ "$confirm" = SAVE_SOFTWARE_OFFLOAD ] || fail "confirmation mismatch"
            enabled="$(read_field '@.status')" || fail "offload state required"
            json_init; json_add_string revision "$revision"; json_add_string confirmation "$confirm"
            json_add_string enabled "$enabled"
            rpc veci.v2.firewall setOffload "$(json_dump)"
        fi
        ;;
    set_wifi_guest)
        enabled="$(read_field '@.guest_enabled')" || fail "guest enable flag required"
        expected="$(read_field '@.expected')" || fail "previous guest state required"
        confirmation="$(read_field '@.confirmation')" || fail "explicit confirmation required"
        case "$expected" in enabled|disabled) ;; *) fail "guest addon requires safe provisioning first";; esac
        case "$enabled:$confirmation" in
            1:ENABLE_PORTAL_AP) action=ENABLE_PORTAL_AP;;
            0:DISABLE_PORTAL_AP) action=DISABLE_PORTAL_AP;;
            *) fail "confirmation mismatch";;
        esac
        # The native startup provider saves only the guest AP flag.
        # Do not use the legacy live enable path, network restart or wifi reload.
        json_init; json_add_string action "$action"; json_add_string expected "$expected"
        rpc veci.v2.addon setPortalStartup "$(json_dump)"
        case "$enabled:$(native_field '@.guest')" in 1:enabled|0:disabled) ;; *) fail "guest setting not confirmed";; esac
        ;;
    set_dhcp_config)
        start="$(read_field '@.dhcp_start')" || fail "DHCP start required"
        end="$(read_field '@.dhcp_end')" || fail "DHCP end required"
        lease="$(read_field '@.dhcp_lease')" || fail "DHCP lease required"
        # OEM original sends seconds; native OpenWrt accepts a duration suffix.
        case "$lease" in *[!0-9]*) ;; '') fail "invalid lease";; *) lease="${lease}s";; esac
        enabled="$(read_field '@.dhcp_enabled')" || fail "DHCP enable flag required"
        revision="$(read_field '@.revision')" || fail "DHCP revision required"
        confirm="$(read_field '@.confirmation')" || fail "explicit DHCP confirmation required"
        [ "$confirm" = SAVE_DHCP_POOL ] || fail "confirmation mismatch"
        # OEM's end is exclusive, native limit is the number of addresses.
        for n in "$start" "$end"; do
            case "$n" in ''|0*|*[!0-9]*) fail "invalid pool";; esac
            [ "${#n}" -le 5 ] || fail "invalid pool"
        done
        [ "$end" -gt "$start" ] || fail "invalid pool"
        # Do not change DHCP options via this endpoint.
        options="$(read_field '@.dhcp_option' || true)"
        [ -z "$options" ] || [ "$options" = "$(uci -q get dhcp.lan.dhcp_option || true)" ] || fail "custom DHCP options unsupported"
        json_init; json_add_string start "$start"; json_add_string limit "$((end-start))"
        json_add_string lease "$lease"; json_add_string enabled "$enabled"
        json_add_string revision "$revision"; json_add_string confirmation "$confirm"
        rpc veci.v2.dhcp setPool "$(json_dump)"
        ;;
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
        json_select maclist; json_get_keys keys; set -- $keys; [ "$#" = 1 ] && [ "$1" = 1 ] || fail "select one reservation at a time"
        json_get_var mac 1; json_select ..
        mac="$(printf '%s' "$mac" | tr A-F a-f)"
        printf '%s\n' "$mac" | grep -Eiq '^([0-9a-f]{2}:){5}[0-9a-f]{2}$' || fail "invalid MAC"
        rpc veci.v2.dhcp status '{}'
        revision="$(native_field '@.revision')" || fail "revision unavailable"
        [ "$(read_field '@.revision')" = "$revision" ] || fail "stale reservation list"
        [ "$(read_field '@.confirmation')" = DELETE_RESERVATION ] || fail "confirmation required"
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
            requested_mac="$(read_field '@.macaddr' || true)"
            current_mac="$(cat /sys/class/net/br-lan/address 2>/dev/null || true)"
            [ -z "$requested_mac" ] || [ "$(printf '%s' "$requested_mac" | tr A-F a-f)" = "$(printf '%s' "$current_mac" | tr A-F a-f)" ] || fail "LAN MAC override unsupported"
        else
            mode="$(read_field '@.proto')" || fail "WAN protocol required"
            case "$mode" in dhcp) wan=""; wan_mask=""; gateway="";;
                static) wan="$(read_field '@.ipaddr')" || fail "WAN address required"
                    wan_mask="$(read_field '@.netmask')" || fail "WAN mask required"
                    gateway="$(read_field '@.gateway')" || fail "WAN gateway required";;
                *) fail "WAN protocol unsupported";;
            esac
            # Do not silently discard a DNS or PPPoE change.
            dns="$(uci -q get network.wan.dns || true)"
            dns1="$(printf '%s' "$dns" | awk '{print $1}')"
            dns2="$(printf '%s' "$dns" | awk '{print $2}')"
            [ "$(read_field '@.dns_primary' || true)" = "$dns1" ] &&
            [ "$(read_field '@.dns_secondary' || true)" = "$dns2" ] || fail "use native DNS settings for DNS changes"
            for key in username password service ac; do
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
    set_static_route)
        revision="$(read_field '@.revision')" || fail "route revision required"
        name="$(read_field '@.name')" || fail "route name required"
        action="$(read_field '@.confirmation')" || fail "explicit route confirmation required"
        case "$name" in veci2_route_*) name="${name#veci2_route_}";; esac
        case "$name" in ''|*[!a-zA-Z0-9_]*) fail "invalid route name";; esac
        [ "${#name}" -le 24 ] || fail "invalid route name"
        json_init; json_add_string name "$name"; json_add_string revision "$revision"
        case "$action" in
            DELETE_ROUTE)
                [ "$(read_field '@.name_delete' || true)" = 1 ] || fail "delete flag required"
                rpc veci.v2.routes remove "$(json_dump)";;
            SAVE_ROUTE)
                [ -z "$(read_field '@.name_delete' || true)" ] || fail "unexpected delete flag"
                target="$(read_field '@.target')" || fail "route target required"
                mask="$(read_field '@.netmask')" || fail "route mask required"
                iface="$(read_field '@.interface')" || fail "interface required"
                gateway="$(read_field '@.gateway' || true)"
                metric="$(read_field '@.metric' || true)"
                case "$metric" in ''|0) ;; *) fail "custom route metric unsupported";; esac
                prefix="$(awk -v m="$mask" 'BEGIN{if(split(m,a,"[.]")!=4)exit 1; v=0; for(i=1;i<=4;i++){if(a[i]!~/^(0|[1-9][0-9]?[0-9]?)$/||a[i]>255)exit 1;v=v*256+a[i]} for(p=0;p<=32;p++)if(v==4294967296-2^(32-p)){print p;exit}exit 1}')" || fail "invalid route mask"
                json_add_string kind route; json_add_string prefix "$target/$prefix"
                json_add_string interface "$iface"; json_add_string gateway "$gateway"; json_add_string table 254
                rpc veci.v2.routes save "$(json_dump)";;
            *) fail "confirmation mismatch";;
        esac
        ;;
    set_redirect_dnat)
        action="$(read_field '@.action')" || fail "explicit forwarding action required"
        confirm="$(read_field '@.confirmation')" || fail "explicit forwarding confirmation required"
        case "$action" in
            ADD_FORWARD)
                from="$(read_field '@.src_dport')" || fail "source port required"
                to="$(read_field '@.dest_port')" || fail "destination port required"
                proto="$(read_field '@.proto')" || fail "protocol required"
                dest="$(read_field '@.dest_ip')" || fail "destination required"
                [ "$(read_field '@.src')" = wan ] && [ "$(read_field '@.dest')" = lan ] || fail "unsupported zones"
                [ "$(read_field '@.enabled')" = 1 ] || fail "disabled forward unsupported"
                for port in "$from" "$to"; do
                    case "$port" in ''|0*|*[!0-9]*) fail "single nonzero port required";; esac
                    [ "${#port}" -le 5 ] && [ "$port" -le 65535 ] || fail "invalid port"
                done
                [ "$confirm" = "FORWARD_$from" ] || fail "confirmation mismatch"
                json_init; json_add_int from_port "$from"; json_add_int to_port "$to"
                json_add_string protocol "$proto"; json_add_string destination "$dest"; json_add_string confirmation "$confirm"
                rpc veci.v2.firewall addForward "$(json_dump)";;
            DELETE_FORWARD)
                name="$(read_field '@.name')" || fail "forward name required"
                [ "$confirm" = "DELETE_$name" ] || fail "confirmation mismatch"
                json_init; json_add_string name "$name"; json_add_string confirmation "$confirm"
                rpc veci.v2.firewall deleteForward "$(json_dump)";;
            *) fail "unsupported forwarding action";;
        esac
        ;;
    *) fail "operation not implemented";;
esac
json_init; json_add_string code 1; json_add_string reason "native operation accepted"
case "$op" in set_lan_config|set_wan_config|setWiFi2|set_static_route|set_wifi_guest|set_wifi_power) json_add_string apply_state pending_manual_activation;; esac
json_dump
