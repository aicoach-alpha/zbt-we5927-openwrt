#!/bin/sh
# Internal read-only adapter prototype. NOT a CGI. Never expose under /www
# or rpcd until authenticated ACL integration is complete.
set -eu
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
        json_add_object
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
