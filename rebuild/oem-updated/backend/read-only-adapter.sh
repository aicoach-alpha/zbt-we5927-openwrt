#!/bin/sh
# Internal read-only adapter prototype. NOT a CGI. Never expose under /www
# or rpcd until authenticated ACL integration is complete.
set -e
set -f
# jshn uses optional unset namespace variables.
. /usr/share/libubox/jshn.sh
get() { uci -q get "$1"; }
error() {
    json_init
    json_add_string code "-4"
    json_add_string reason "$1"
    json_dump
    exit 1
}
success() {
    json_init
    json_add_string code "1"
    json_add_string reason "$1"
}
# Fixed native service allowlist: no arbitrary user-supplied RPC dispatch.
native_read() {
    case "$1:$2" in
        veci.v2.system:ntp|veci.v2.dhcp:status|veci.v2.firewall:status|veci.v2.interfaces:status) ;;
        *) return 1;;
    esac
    result="$(ubus -t 3 call "$1" "$2" '{}')" || return 1
    [ "$(printf '%s' "$result" | jsonfilter -e '@.ok')" = true ] || return 1
    printf '%s' "$result"
}
field() { printf '%s' "$native" | jsonfilter -e "$1"; }
# Only real, complete LAN neighbours are eligible for the OEM picker.
lan_neighbours() {
    awk 'NR>1 && $3=="0x2" && $6=="br-lan" && $4!="00:00:00:00:00:00" {print toupper($4) "(" $1 ")"}' /proc/net/arp
}
[ "$#" -eq 1 ] || error "operation required"
case "$1" in
    get_sys_version)
        version="$(ubus call system board | jsonfilter -e '@.release.version')" || error "version unavailable"
        [ -n "$version" ] || error "version unavailable"
        success "get sysversion success"
        json_add_string sysversion "$version"
        ;;
    get_lan_config)
        proto="$(get network.lan.proto)" || error "LAN protocol unavailable"
        address="$(get network.lan.ipaddr)" || error "LAN address unavailable"
        case "$address" in
            *' '*) error "multiple LAN addresses not supported yet" ;;
            */*)
                prefix="${address##*/}"
                address="${address%/*}"
                case "$prefix" in ''|*[!0-9]*) error "invalid prefix";; esac
                [ "$prefix" -le 32 ] || error "invalid prefix"
                mask="$(awk -v p="$prefix" 'BEGIN {for(i=0;i<4;i++){n=p>8?8:p; if(n<0)n=0; printf "%s%d",i?".":"",256-2^(8-n);p-=n}}')"
                ;;
            *) mask="$(get network.lan.netmask)" || error "LAN netmask unavailable" ;;
        esac
        mac="$(cat /sys/class/net/br-lan/address | tr 'a-z' 'A-Z')" || error "LAN MAC unavailable"
        [ -n "$mac" ] && [ -n "$address" ] && [ -n "$mask" ] || error "LAN unavailable"
        success "get lan config success"
        json_add_object data
        json_add_string proto "$proto"
        json_add_string ipaddr "$address"
        json_add_string netmask "$mask"
        json_add_string macaddr "$mac"
        json_close_object
        ;;
    get_dhcp_config)
        ignore="$(get dhcp.lan.ignore || true)"
        case "$ignore" in 1) enabled=0;; ''|0) enabled=1;; *) error "invalid DHCP flag";; esac
        start="$(get dhcp.lan.start)" || error "DHCP start unavailable"
        limit="$(get dhcp.lan.limit)" || error "DHCP limit unavailable"
        case "$start:$limit" in *[!0-9:]*|:*|*:) error "invalid DHCP range";; esac
        lease="$(get dhcp.lan.leasetime)" || error "DHCP lease unavailable"
        address="$(get network.lan.ipaddr)" || error "LAN address unavailable"
        address="${address%/*}"
        head="${address%.*}"
        options="$(get dhcp.lan.dhcp_option || true)"
        success "get dhcp config success"
        json_add_object data
        json_add_string dhcp_enabled "$enabled"
        json_add_string dhcp_start "$start"
        # Preserve original OEM wire convention, not an inclusive pool end.
        json_add_string dhcp_end "$((start+limit))"
        json_add_string dhcp_lease "$lease"
        json_add_string dhcp_head "$head"
        json_add_string dhcp_option "$options"
        json_close_object
        ;;
    get_module_status)
        # Exactly one physical modem (two selectable SIM slots).
        # Do not report public Internet from a USB DHCP address.
        [ "$(get network.lte.device)" = usb0 ] || error "LTE device mismatch"
        state="$(ubus -t 3 call network.interface.lte status)" || error "LTE state unavailable"
        [ -n "$state" ] || error "LTE state unavailable"
        up="$(printf '%s' "$state" | jsonfilter -e '@.up')" || error "LTE state invalid"
        case "$up" in true|false) ;; *) error "LTE state invalid";; esac
        uptime="$(printf '%s' "$state" | jsonfilter -e '@.uptime' || true)"
        addr="$(printf '%s' "$state" | jsonfilter -e '@["ipv4-address"][0].address' || true)"
        [ "$up" = true ] || { addr=""; uptime=0; }
        case "$uptime" in ''|*[!0-9]*) uptime=0;; esac
        mac="$(cat /sys/class/net/usb0/address 2>/dev/null | tr 'a-z' 'A-Z')" || error "LTE MAC unavailable"
        rx="$(cat /sys/class/net/usb0/statistics/rx_bytes 2>/dev/null)" || error "LTE counters unavailable"
        tx="$(cat /sys/class/net/usb0/statistics/tx_bytes 2>/dev/null)" || error "LTE counters unavailable"
        case "$rx:$tx" in *[!0-9:]*|:*|*:) error "LTE counters invalid";; esac
        [ -n "$mac" ] || error "LTE MAC unavailable"
        ipv6="$(printf '%s' "$state" | jsonfilter -e '@["ipv6-address"][*].address' || true)"
        success "get module status success"
        json_add_array data
        json_add_object ""
        json_add_string ifname usb0
        json_add_string host "${addr:-0.0.0.0}"
        json_add_string macaddr "$mac"
        json_add_string txall "$tx"
        json_add_string rxall "$rx"
        json_add_string uptime "$uptime"
        json_add_array ipv6
        if [ "$up" = true ]; then
            for address in $ipv6; do json_add_string "" "$address"; done
        fi
        json_close_array
        json_close_object
        json_close_array
        ;;
    get_ntp)
        native="$(native_read veci.v2.system ntp)" || error "native NTP unavailable"
        enabled="$(field '@.enabled')" || error "NTP state unavailable"
        case "$enabled" in 0|1) ;; *) error "NTP state unknown";; esac
        server="$(get system.ntp.enable_server || true)"
        case "$server" in ''|0) server=0;; 1) ;; *) error "NTP server state invalid";; esac
        timezone="$(get system.@system[0].timezone)" || error "timezone unavailable"
        [ -n "$timezone" ] || error "timezone unavailable"
        first="$(field '@.servers[0]' || true)"
        second="$(field '@.servers[1]' || true)"
        success "get ntp success"
        json_add_string enable_ntp_server "$server"
        json_add_string enable_ntp_client "$enabled"
        json_add_string server_primary "$first"
        json_add_string server_secondary "$second"
        json_add_string timezone "$timezone"
        # Only report the actual configured timezone until the picker has
        # a reviewed mapping to modern OpenWrt POSIX/TZ database values.
        json_add_array timezone_list
        json_add_string "" "$timezone"
        json_close_array
        ;;
    get_static_dhcp)
        native="$(native_read veci.v2.dhcp status)" || error "native DHCP unavailable"
        # Confirm the provider returned an array, not a partial error object.
        (json_load "$native" && json_get_type typ leases && [ "$typ" = array ]) || error "DHCP inventory invalid"
        neighbours="$(lan_neighbours)" || error "LAN neighbours unavailable"
        success "get_static_dhcp success"
        json_add_array arp_mac_list
        for neighbour in $neighbours; do json_add_string "" "$neighbour"; done
        json_close_array
        json_add_array data
        idx=0
        while [ "$idx" -lt 256 ]; do
            index="$(field "@.leases[$idx].index" || true)"
            [ -n "$index" ] || break
            [ "$index" = "$idx" ] || error "DHCP index mismatch"
            mac="$(field "@.leases[$idx].mac")" || error "DHCP MAC unavailable"
            ip="$(field "@.leases[$idx].ip")" || error "DHCP address unavailable"
            name="$(field "@.leases[$idx].name" || true)"
            json_add_object ""
            json_add_string name "$name"
            json_add_string mac "$mac"
            json_add_string ip "$ip"
            json_add_string leasetime ""
            json_close_object
            idx=$((idx+1))
        done
        json_close_array
        ;;
    get_dmz)
        native="$(native_read veci.v2.firewall status)" || error "native firewall unavailable"
        dest="$(field '@.dmz_destination')" || error "DMZ state unavailable"
        enabled=0
        ports=""
        if [ -n "$dest" ]; then
            # The shared VeCI DMZ contract supports all ports, not OEM
            # arbitrary ranges. Report only the canonical managed rule.
            [ "$(get firewall.veci_owner_dmz)" = redirect ] || error "DMZ rule unavailable"
            [ "$(get firewall.veci_owner_dmz.target)" = DNAT ] || error "DMZ rule invalid"
            [ "$(get firewall.veci_owner_dmz.src)" = wan ] || error "DMZ source invalid"
            [ "$(get firewall.veci_owner_dmz.dest)" = lan ] || error "DMZ destination invalid"
            [ -z "$(get firewall.veci_owner_dmz.src_dport || true)" ] || error "DMZ port range unsupported"
            case "$(get firewall.veci_owner_dmz.enabled || true)" in
                ''|1) enabled=1; ports=1-65535;; 0) ;; *) error "DMZ enabled state invalid";;
            esac
        fi
        success "get dmz success"
        json_add_string ipaddr "$dest"
        json_add_string sport "$ports"
        json_add_string enabled "$enabled"
        ;;
    get_module_signal)
        # Existing single modem service; never invoke raw AT from CGI.
        native="$(/usr/sbin/we5927-lte status-fast)" || error "modem state unavailable"
        (json_load "$native") || error "modem state invalid"
        operator="$(field '@.operator' || true)"
        model="$(field '@.model' || true)"
        sim="$(field '@.sim')" || error "SIM state unavailable"
        case "$sim" in 1|2) ;; *) error "SIM state invalid";; esac
        signal="$(field '@.signal_dbm' || true)"
        case "$signal" in -[0-9]|-[0-9][0-9]|-1[0-9][0-9]) ;; *) signal="";; esac
        tech="$(field '@.access_tech' || true)"
        success "get module signal success"
        json_add_array data
        json_add_object ""
        json_add_string operator "$operator"
        json_add_string model "$model"
        # No subscriber identifiers in polling responses.
        json_add_string imei ""
        json_add_string iccid ""
        json_add_string signal "$signal"
        json_add_string module_sim "SIM$sim"
        json_add_string net_type "$tech"
        json_close_object
        json_close_array
        ;;
    get_arp)
        # Consume the kernel neighbour table, not vendor collection daemons.
        [ -r /proc/net/arp ] || error "neighbour table unavailable"
        success "success"
        json_add_array list
        while read -r ip hw flags mac mask device; do
            [ "$flags" = 0x2 ] && [ "$device" = br-lan ] || continue
            [ "$mac" != 00:00:00:00:00:00 ] || continue
            json_add_object ""
            json_add_string ipaddr "$ip"
            json_add_string macaddr "$mac"
            json_add_string interface "$device"
            json_close_object
        done < /proc/net/arp
        json_close_array
        ;;
    get_dhcp_allocation)
        # dnsmasq is the authoritative source. Never eval a lease hostname.
        [ -r /tmp/dhcp.leases ] || error "DHCP lease table unavailable"
        now="$(date +%s)"
        case "$now" in ''|*[!0-9]*) error "clock unavailable";; esac
        success "get dhcp allocation success"
        json_add_array data
        while read -r expiry mac ip host rest; do
            case "$expiry" in 0|[1-9]|[1-9][0-9]*) ;; *) continue;; esac
            case "$expiry" in *[!0-9]*) continue;; esac
            # Reject overflow before arithmetic, and skip expired leases.
            [ "${#expiry}" -le 10 ] || continue
            [ "$expiry" -eq 0 ] || [ "$expiry" -gt "$now" ] || continue
            remain=0
            [ "$expiry" -eq 0 ] || remain=$((expiry-now))
            [ "$host" != "*" ] || host=""
            json_add_object ""
            json_add_string dhcp_remain_lease "$remain"
            json_add_string dhcp_mac "$mac"
            json_add_string dhcp_ip "$ip"
            json_add_string dhcp_host "$host"
            json_close_object
        done < /tmp/dhcp.leases
        json_close_array
        ;;
    get_wan_config)
        native="$(native_read veci.v2.interfaces status)" || error "native WAN unavailable"
        mode="$(field '@.wan_mode')" || error "WAN mode unavailable"
        case "$mode" in dhcp|static) ;; *) error "WAN mode unsupported";; esac
        state="$(ubus -t 3 call network.interface.wan status)" || error "WAN state unavailable"
        live() { printf '%s' "$state" | jsonfilter -e "$1"; }
        up="$(live '@.up')" || error "WAN link state unavailable"
        case "$up" in true|false) ;; *) error "WAN link state invalid";; esac
        dev="$(live '@.device' || true)"
        case "$dev" in ''|*[!a-zA-Z0-9_.-]*) error "WAN device unavailable";; esac
        mac="$(cat "/sys/class/net/$dev/address" 2>/dev/null)" || error "WAN MAC unavailable"
        [ -n "$mac" ] || error "WAN MAC unavailable"
        if [ "$mode" = static ]; then
            address="$(field '@.wan')" || error "WAN address unavailable"
            mask="$(field '@.wan_mask')" || error "WAN mask unavailable"
            gateway="$(field '@.gateway')" || error "WAN gateway unavailable"
        else
            address="$(live '@["ipv4-address"][0].address' || true)"
            mask="$(live '@["ipv4-address"][0].mask' || true)"
            gateway="$(live "@.route[@.target='0.0.0.0' && !@.table].nexthop" | head -n 1)"
            [ "$up" = true ] || { address=""; mask=""; gateway=""; }
        fi
        case "$mask" in
            '' ) ;;
            *.*) ;;
            *[!0-9]*) error "WAN mask invalid";;
            *) [ "$mask" -le 32 ] || error "WAN mask invalid"
               mask="$(awk -v p="$mask" 'BEGIN {for(i=0;i<4;i++){n=p>8?8:p;if(n<0)n=0;printf "%s%d",i?".":"",256-2^(8-n);p-=n}}')" ;;
        esac
        dns="$(get network.wan.dns || true)"
        dns1="$(printf '%s' "$dns" | awk '{print $1}')"
        dns2="$(printf '%s' "$dns" | awk '{print $2}')"
        nameserver="$(live '@["dns-server"][0]' || true)"
        ipv6="$(live '@["ipv6-address"][*].address' || true)"
        [ "$up" = true ] || { nameserver=""; ipv6=""; }
        success "get wan config success"
        json_add_object data
        json_add_string proto "$mode"
        json_add_string macaddr "$mac"
        json_add_string ipaddr "${address:-0.0.0.0}"
        json_add_string netmask "$mask"
        json_add_string gateway "$gateway"
        json_add_string dns_primary "$dns1"
        json_add_string dns_secondary "$dns2"
        json_add_string nameserver "$nameserver"
        json_add_string username ""
        json_add_string password ""
        json_add_string service ""
        json_add_string ac ""
        json_add_array ipv6
        for address in $ipv6; do json_add_string "" "$address"; done
        json_close_array
        json_close_object
        ;;
    get_netwatchdog)
        # Do not claim legacy settings are active before native policy migration.
        host1="$(get oem_updated.watchdog.detect_host1)" || error "OEM policy not configured"
        host2="$(get oem_updated.watchdog.detect_host2)" || error "OEM policy not configured"
        interval="$(get oem_updated.watchdog.detect_itv)" || error "OEM policy not configured"
        success "get anyos netwatchdog success"
        json_add_object data
        json_add_string detect_host1 "$host1"
        json_add_string detect_host2 "$host2"
        json_add_string detect_itv "$interval"
        json_add_string mobile_priority "1"
        json_add_string action "netrestart"
        json_close_object
        ;;
    get_nat_acceleration)
        # Use the actual modern firewall option; this is not a hardware claim.
        offload="$(get firewall.@defaults[0].flow_offloading || true)"
        case "$offload" in 1) enabled=1;; ''|0) enabled=0;; *) error "invalid flow offload setting";; esac
        success "get net acceleration success"
        json_add_object data
        json_add_string status "$enabled"
        json_close_object
        ;;
    get_web_msg)
        version="$(ubus call system board | jsonfilter -e '@.release.version')" || error "version unavailable"
        address="$(get network.lan.ipaddr)" || error "LAN unavailable"
        address="${address%/*}"
        mac="$(cat /sys/class/net/br-lan/address | tr 'a-z' 'A-Z')" || error "LAN unavailable"
        uptime="$(cut -d. -f1 /proc/uptime)"
        timezone="$(get system.@system[0].timezone || true)"
        success "get web msg success"
        json_add_object data
        json_add_string board "WE2825-2SIM"
        json_add_string sysversion "$version"
        json_add_string ipaddr "$address"
        json_add_string macaddr "$mac"
        json_add_string mode "route"
        json_add_string systime "$(date +%s)"
        json_add_string uptime "$uptime"
        json_add_string timezone "$timezone"
        json_close_object
        ;;
    *) error "operation not implemented" ;;
esac
json_dump
