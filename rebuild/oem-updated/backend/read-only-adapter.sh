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
        veci.v2.system:ntp|veci.v2.dhcp:status|veci.v2.firewall:status|veci.v2.interfaces:status|veci.v2.wifi:info|veci.v2.wifi:status|veci.v2.lte:status|veci.v2.system:logs|veci.v2.routes:status|veci.v2.guest:status|veci.v2.updatepolicy:status|veci.v2.observability:trafficHistory) ;;
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
[ "$#" -ge 1 ] && [ "$#" -le 2 ] || error "operation required"
preview="${2:-}"
[ -z "$preview" ] || [ "$1" = get_4g ] || error "unexpected SIM preview"
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
        native="$(native_read veci.v2.interfaces status || true)"
        revision="$(field '@.revision' || true)"
        success "get lan config success"
        json_add_string revision "$revision"
        json_add_object data
        json_add_string proto "$proto"
        json_add_string ipaddr "$address"
        json_add_string netmask "$mask"
        json_add_string macaddr "$mac"
        json_close_object
        ;;
    get_dhcp_config)
        native="$(native_read veci.v2.dhcp status)" || error "DHCP revision unavailable"
        before="$(field '@.revision')" || error "DHCP revision unavailable"
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
        native="$(native_read veci.v2.dhcp status)" || error "DHCP revision unavailable"
        revision="$(field '@.revision')" || error "DHCP revision unavailable"
        [ "$before" = "$revision" ] || error "DHCP configuration changed"
        success "get dhcp config success"
        json_add_string revision "$revision"
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
        revision="$(field '@.revision' || true)"
        success "get wan config success"
        json_add_string revision "$revision"
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
    getWiFi2)
        # Use the exact-board Wi-Fi provider for primary-AP layout and
        # access policy. Do not import legacy MediaTek private controls.
        native="$(native_read veci.v2.wifi info)" || error "native Wi-Fi unavailable"
        enc="$(field '@.encryption')" || error "Wi-Fi encryption unavailable"
        case "$enc" in psk2|psk-mixed|sae|sae-mixed|none) ;; *) error "Wi-Fi encryption unsupported";; esac
        access="$(field '@.access')" || error "Wi-Fi access policy unavailable"
        case "$access" in disable|allow|deny) ;; *) error "Wi-Fi access policy unsupported";; esac
        macs="$(field '@.addresses[*]' || true)"
        native="$(native_read veci.v2.wifi status)" || error "native Wi-Fi state unavailable"
        visible="$(field '@.configured_visible')" || error "Wi-Fi visibility unavailable"
        case "$visible" in true) hidden=0;; false) hidden=1;; *) error "Wi-Fi visibility invalid";; esac
        channel="$(field '@.configured_channel')" || error "Wi-Fi channel unavailable"
        case "$channel" in auto) channel=0;; [1-9]|1[0-4]) ;; *) error "Wi-Fi channel invalid";; esac
        radio_disabled="$(get wireless.radio0.disabled || true)"
        ap_disabled="$(get wireless.default_radio0.disabled || true)"
        case "$radio_disabled:$ap_disabled" in *[!01:]*) error "Wi-Fi enabled state invalid";; esac
        enabled=1
        [ "$radio_disabled" != 1 ] && [ "$ap_disabled" != 1 ] || enabled=0
        ht="$(get wireless.radio0.htmode)" || error "Wi-Fi width unavailable"
        case "$ht" in HT20) ht=ht20;; HT40|HT40+|HT40-) ht=ht40;; *) error "Wi-Fi width unsupported";; esac
        ssid="$(get wireless.default_radio0.ssid)" || error "Wi-Fi SSID unavailable"
        snapshot="$(ubus -t 3 call network.wireless status '{}')" || error "wireless state unavailable"
        iface="$(printf '%s' "$snapshot" | jsonfilter -e '@.radio0.interfaces[@.section="default_radio0"].ifname' || true)"
        bssid=""
        if [ -n "$iface" ]; then
            case "$iface" in -*|*[!A-Za-z0-9_.-]*) error "Wi-Fi interface invalid";; esac
            bssid="$(cat "/sys/class/net/$iface/address" 2>/dev/null || true)"
        fi
        success "getWiFi2 success"
        json_add_string enabled "$enabled"
        json_add_string country "$(get wireless.radio0.country || true)"
        json_add_string channel "$channel"
        json_add_string htmode "$ht"
        json_add_string threshold "$(get wireless.radio0.frag || true)"
        json_add_string rts_threshold "$(get wireless.radio0.rts || true)"
        json_add_string wmm "$(get wireless.default_radio0.wmm || true)"
        json_add_string isolated "$(get wireless.default_radio0.isolate || true)"
        json_add_string bssid "$bssid"
        json_add_string ssid "$ssid"
        json_add_string hidden "$hidden"
        json_add_string encryption "$enc"
        # Never disclose stored Wi-Fi keys through periodic read requests.
        json_add_string key ""
        json_add_string macfilter "$access"
        json_add_string ApCliEnable "0"
        json_add_string channel_disabled "0"
        json_add_array maclist
        for mac in $macs; do json_add_string "" "$mac"; done
        json_close_array
        ;;
    get_pppoe_status)
        proto="$(get network.wan.proto)" || error "WAN protocol unavailable"
        status=0
        if [ "$proto" = pppoe ]; then
            state="$(ubus -t 3 call network.interface.wan status)" || error "PPPoE status unavailable"
            up="$(printf '%s' "$state" | jsonfilter -e '@.up')" || error "PPPoE link unavailable"
            case "$up" in true|false) ;; *) error "PPPoE link invalid";; esac
            addr="$(printf '%s' "$state" | jsonfilter -e '@["ipv4-address"][0].address' || true)"
            if [ "$up" = true ] && [ -n "$addr" ] && [ "$addr" != 0.0.0.0 ]; then status=1; fi
        fi
        success "get_pppoe_status success"
        json_add_string pppoe_status "$status"
        ;;
    get_4g)
        native="$(native_read veci.v2.lte status)" || error "LTE policy unavailable"
        apn="$(field '@.configured_apn')" || error "APN unavailable"
        [ -n "$apn" ] && [ "$apn" != null ] || error "APN unavailable"
        slot="$(field '@.configured_slot')" || error "configured SIM unavailable"
        case "$slot" in 1|2) ;; *) error "configured SIM invalid";; esac
        failover="$(field '@.auto_failover')" || error "failover state unavailable"
        case "$failover" in true) failover=1;; false) failover=0;; *) error "failover state invalid";; esac
        # Native policy is global, not a pair of vendor APN profiles.
        # Expose canonical slot labels instead of assuming GPIO polarity.
        case "$preview" in '' ) preview="SIM$slot";; SIM1|SIM2) ;; *) error "invalid SIM preview";; esac
        success "get 4g config success"
        json_add_object data
        json_add_string apn "$apn"
        json_add_string SIMX "$preview"
        json_add_string sim_set "SIM$slot"
        json_add_string switch_sim_enabled "$failover"
        json_add_string apn_scope "shared"
        json_add_string pin ""
        json_add_string dialnumber ""
        json_add_string username ""
        json_add_string password ""
        json_add_string mobile_priority ""
        json_add_string module_first ""
        json_add_string auth_apn "0"
        json_add_string band ""
        json_add_array band_list
        json_close_array
        json_add_array select_band_list
        json_close_array
        json_close_object
        json_add_array module_section_list
        json_add_string "" "4gwan"
        json_close_array
        json_add_array sim_list
        json_add_string "" "SIM1"
        json_add_string "" "SIM2"
        json_close_array
        ;;
    get_4g_log)
        native="$(native_read veci.v2.system logs)" || error "native log service unavailable"
        logs="$(field '@.logs')" || error "native logs unavailable"
        content="$(printf '%s\n' "$logs" | grep -Ei 'we5927-lte|veci2-lte|usb0|rndis_host' | tail -n 30 || true)"
        success "get 4g log success"
        json_add_string content "$content"
        ;;
    get_wifi_guest)
        native="$(native_read veci.v2.guest status)" || error "guest provider unavailable"
        installed="$(field '@.installed')" || error "guest status unavailable"
        configured="$(field '@.configured')" || error "guest configuration unavailable"
        enabled="$(field '@.enabled_configured')" || error "guest enabled state unavailable"
        case "$installed:$configured:$enabled" in true:true:true|true:true:false|true:false:false|false:false:false) ;; *) error "invalid guest status";; esac
        ssid=""
        if [ "$configured" = true ]; then
            ssid="$(get wireless.veci_guest.ssid)" || error "guest SSID unavailable"
        fi
        success "get wifi guest success"
        case "$enabled" in true) json_add_string guest_enabled 1;; false) json_add_string guest_enabled 0;; esac
        json_add_string guest_ssid "$ssid"
        json_add_string installed "$installed"
        json_add_string configured "$configured"
        json_add_string isolation_verified unknown
        ;;
    get_static_route)
        native="$(native_read veci.v2.routes status)" || error "route provider unavailable"
        (json_load "$native" && json_get_type typ entries && [ "$typ" = array ]) || error "route inventory invalid"
        revision="$(field '@.revision')" || error "route revision unavailable"
        success "get static route success"
        json_add_string revision "$revision"
        json_add_array interface_list
        for iface in $(uci -q show network | sed -nE 's/^network\.([a-zA-Z0-9_]+)=interface$/\1/p'); do
            [ "$iface" != loopback ] || continue
            json_add_string "" "$iface"
        done
        json_close_array
        json_add_array data
        idx=0
        while [ "$idx" -lt 256 ]; do
            section="$(field "@.entries[$idx].section" || true)"
            [ -n "$section" ] || break
            kind="$(field "@.entries[$idx].kind")" || error "route type unavailable"
            if [ "$kind" = route ]; then
                target="$(field "@.entries[$idx].target")" || error "route target unavailable"
                case "$target" in */*) prefix="${target##*/}"; target="${target%/*}";; *) prefix="";; esac
                mask=""
                case "$prefix" in '') ;; *[!0-9]*) error "route prefix invalid";; *) [ "$prefix" -le 32 ] || error "route prefix invalid"; mask="$(awk -v p="$prefix" 'BEGIN {for(i=0;i<4;i++){n=p>8?8:p;if(n<0)n=0;printf "%s%d",i?".":"",256-2^(8-n);p-=n}}')";; esac
                json_add_object ""
                json_add_string name "$section"
                json_add_string target "$target"
                json_add_string netmask "$mask"
                json_add_string interface "$(field "@.entries[$idx].interface" || true)"
                json_add_string gateway "$(field "@.entries[$idx].gateway" || true)"
                json_add_string table "$(field "@.entries[$idx].table" || true)"
                json_add_string editable "$(field "@.entries[$idx].editable" || true)"
                json_add_string metric "$(get "network.$section.metric" || true)"
                json_close_object
            fi
            idx=$((idx+1))
        done
        json_close_array
        ;;
    get_redirect_dnat)
        native="$(native_read veci.v2.firewall status)" || error "firewall provider unavailable"
        (json_load "$native" && json_get_type typ forwards && [ "$typ" = array ]) || error "forward inventory invalid"
        success "firewall redirect get success"
        json_add_array data
        idx=0
        while [ "$idx" -lt 256 ]; do
            name="$(field "@.forwards[$idx].name" || true)"
            index="$(field "@.forwards[$idx].index" || true)"
            [ -n "$name$index" ] || break
            if [ -n "$index" ]; then
                case "$index" in *[!0-9]*) error "invalid firewall index";; esac
                section="@redirect[$index]"
            else
                case "$name" in veci_port_tcp_*|veci_port_udp_*) section="$name";; *) error "unknown named forward";; esac
            fi
            [ "$(get "firewall.$section.target" || true)" = DNAT ] || { idx=$((idx+1)); continue; }
            json_add_object ""
            json_add_string name "$name"
            json_add_string proto "$(field "@.forwards[$idx].protocol" || true)"
            json_add_string src "$(get "firewall.$section.src" || true)"
            json_add_string src_dport "$(field "@.forwards[$idx].source_port" || true)"
            json_add_string dest "$(get "firewall.$section.dest" || true)"
            json_add_string dest_ip "$(field "@.forwards[$idx].destination" || true)"
            json_add_string dest_port "$(field "@.forwards[$idx].destination_port" || true)"
            enabled="$(get "firewall.$section.enabled" || true)"
            json_add_string enabled "${enabled:-1}"
            json_close_object
            idx=$((idx+1))
        done
        json_close_array
        json_add_array zone_list
        for zone in $(uci -q show firewall | sed -nE "s/^firewall\.[^.]+\.name='([a-zA-Z0-9_]+)'$/\1/p"); do
            case "$zone" in lan|wan|veci_guest) json_add_string "" "$zone";; esac
        done
        json_close_array
        ;;
    get_log_list)
        native="$(native_read veci.v2.system logs)" || error "native logs unavailable"
        logs="$(field '@.logs')" || error "native logs unavailable"
        success "get log list success"
        # OEM browser expects date, type and quoted text per line.
        # Escape quote delimiters in the already redacted native log text.
        formatted="$(printf '%s\n' "$logs" | awk 'NF>=5 {d=$2" "$3" "$4; sub(/^[^ ]+ +[^ ]+ +[^ ]+ +[^ ]+ +[^ ]+ +/,""); gsub(/"/,"\047"); printf "%s system: \"%s\"\n",d,$0}')"
        json_add_string data "$formatted"
        ;;
    get_lan_status|get_wan_status)
        case "$1" in get_lan_status) network=lan;; *) network=wan;; esac
        state="$(ubus -t 3 call "network.interface.$network" status '{}')" || error "interface state unavailable"
        live() { printf '%s' "$state" | jsonfilter -e "$1"; }
        up="$(live '@.up')" || error "link state unavailable"
        case "$up" in true|false) ;; *) error "invalid link state";; esac
        dev="$(live '@.l3_device' || live '@.device' || true)"
        case "$dev" in ''|.|..|-*|*[!a-zA-Z0-9_.-]*) error "interface unavailable";; esac
        proto="$(live '@.proto' || get "network.$network.proto")" || error "protocol unavailable"
        address="$(live '@["ipv4-address"][0].address' || true)"
        ipv6="$(live '@["ipv6-address"][*].address' || true)"
        uptime="$(live '@.uptime' || true)"
        [ "$up" = true ] || { address=""; ipv6=""; uptime=0; }
        mac="$(cat "/sys/class/net/$dev/address" 2>/dev/null || true)"
        rx="$(cat "/sys/class/net/$dev/statistics/rx_bytes" 2>/dev/null)" || error "RX unavailable"
        tx="$(cat "/sys/class/net/$dev/statistics/tx_bytes" 2>/dev/null)" || error "TX unavailable"
        case "$rx:$tx" in *[!0-9:]*|:*|*:) error "invalid counters";; esac
        # Bounded sampling; never fabricate rates from link speed or use a
        # shell-sourced shared cache. On counter reset, rate is unknown.
        rx_rate=""; tx_rate=""
        if [ "$up" = true ]; then
            sleep 1
            next_rx="$(cat "/sys/class/net/$dev/statistics/rx_bytes" 2>/dev/null || true)"
            next_tx="$(cat "/sys/class/net/$dev/statistics/tx_bytes" 2>/dev/null || true)"
            case "$next_rx:$next_tx" in *[!0-9:]*|:*|*:) ;; *)
                rx_rate="$(awk -v a="$rx" -v b="$next_rx" 'BEGIN{if(b>=a)printf "%.0f",b-a}')"
                tx_rate="$(awk -v a="$tx" -v b="$next_tx" 'BEGIN{if(b>=a)printf "%.0f",b-a}')"
                rx="$next_rx"; tx="$next_tx";;
            esac
        fi
        success "get interface status success"
        json_add_object data
        json_add_string rx "$rx_rate"; json_add_string tx "$tx_rate"
        json_add_string rxall "$rx"; json_add_string txall "$tx"
        json_add_string uptime "$uptime"; json_add_string proto "$proto"
        json_add_string ipaddr "$address"; json_add_string macaddr "$mac"
        json_add_array ipv6
        for ip in $ipv6; do json_add_string "" "$ip"; done
        json_close_array; json_close_object
        ;;
    get_system_status)
        uptime="$(cut -d. -f1 /proc/uptime)" || error "uptime unavailable"
        load="$(awk '{print $1" "$2" "$3}' /proc/loadavg)"
        memory="$(awk '/^MemTotal:/{t=$2}/^MemAvailable:/{a=$2;found=1}END{if(t>0&&found&&a<=t)printf "%.0f",100*(t-a)/t}' /proc/meminfo)"
        [ -n "$memory" ] || error "memory unavailable"
        first="$(awk '/^cpu /{s=0;for(i=2;i<=9;i++)s+=$i;print s,$5+$6;exit}' /proc/stat)"
        sleep 1
        second="$(awk '/^cpu /{s=0;for(i=2;i<=9;i++)s+=$i;print s,$5+$6;exit}' /proc/stat)"
        cpu="$(printf '%s\n%s\n' "$first" "$second" | awk 'NR==1{t=$1;i=$2}NR==2{d=$1-t;idle=$2-i;if(d>0&&idle>=0&&idle<=d)printf "%.0f",100*(d-idle)/d}')"
        native="$(native_read veci.v2.wifi info)" || native=""
        clients=""
        if [ -n "$native" ] && (json_load "$native" && json_get_type typ clients && [ "$typ" = array ]); then
            clients="$(field '@.clients[*]' | awk 'NF{n++}END{print n+0}')"
        fi
        success "get system status success"
        json_add_string uptime "$uptime"; json_add_string load_avg "$load"
        json_add_string cpu_usage "$cpu"; json_add_string memory_usage "$memory"
        json_add_string online_user_num "$clients"
        ;;
    get_wifi_client)
        native="$(native_read veci.v2.wifi info)" || error "Wi-Fi provider unavailable"
        (json_load "$native" && json_get_type typ clients && [ "$typ" = array ]) || error "client inventory unavailable"
        ssid="$(get wireless.default_radio0.ssid)" || error "SSID unavailable"
        clients="$(field '@.clients[*]' || true)"
        success "get wifi client success"
        json_add_string device_table 1
        json_add_array list
        for mac in $clients; do
            ip="$(awk -v mac="$mac" 'tolower($4)==tolower(mac)&&$3=="0x2"&&$6=="br-lan"{print $1;exit}' /proc/net/arp)"
            json_add_object ""
            json_add_string macaddr "$mac"; json_add_string ipaddr "$ip"
            json_add_string wifi_type_ssid "2.4G/$ssid"
            json_add_string rssi ""; json_add_string speed ""; json_add_string bandwidth ""
            json_add_string operation ""
            json_close_object
        done
        json_close_array
        ;;
    get_fw_setting)
        native="$(native_read veci.v2.firewall status)" || error "firewall unavailable"
        wan="$(field '@.wan_input')" || error "WAN policy unavailable"
        case "$wan" in ACCEPT) input=1;; REJECT|DROP) input=0;; *) error "invalid WAN policy";; esac
        revision="$(field '@.revision')" || error "firewall revision unavailable"
        success "get fw setting success"
        json_add_string revision "$revision"
        json_add_object data
        for option in drop_invalid disable_ipv6 syn_flood accept_redirects; do
            case "$option" in syn_flood) value="$(get firewall.@defaults[0].synflood_protect || true)";; *) value="$(get "firewall.@defaults[0].$option" || true)";; esac
            case "$value" in 0|1|'') ;; *) error "invalid firewall option";; esac
            json_add_string "$option" "$value"
        done
        json_add_string prohibit_wan_ping "$input"
        json_add_string wan_input "$wan"
        json_close_object
        ;;
    get_port|get_network_topology)
        native="$(ubus -t 5 call veci.v2 ethernetPorts '{}')" || error "Ethernet inventory unavailable"
        [ "$(field '@.available')" = true ] || error "Ethernet inventory unavailable"
        (json_load "$native" && json_get_type typ ports && [ "$typ" = array ]) || error "port inventory invalid"
        success "get status success"
        # No invented physical port labels. Report exact switch port numbers.
        if [ "$1" = get_network_topology ]; then
            state="$(ubus -t 3 call veci.v2 status '{}')" || error "native status unavailable"
            status_field() { printf '%s' "$state" | jsonfilter -e "$1"; }
            [ "$(status_field '@.board_supported')" = true ] || error "unsupported board"
            ap="$(status_field '@.wifi_ap_enabled')" || error "AP status unavailable"
            case "$ap" in true) wifi=1;; false) wifi=0;; *) wifi="";; esac
            route="$(ip -4 route show default | awk 'NR==1{for(i=1;i<NF;i++)if($i=="dev"){print $(i+1);exit}}')"
            case "$route" in usb0) internet=4g;; '') internet=none;; *) internet=ether;; esac
            lan="$(ubus -t 3 call network.interface.lan status '{}' | jsonfilter -e '@.up')" || error "LAN state unavailable"
            case "$lan" in true) lan=1;; false) lan=0;; *) error "invalid LAN state";; esac
            json_add_string internet "$internet"; json_add_string internet_verified unknown
            json_add_string lan "$lan"; json_add_string wifi2 "$wifi"; json_add_string wifi5 0
        fi
        json_add_array port
        i=0
        while [ "$i" -lt 5 ]; do
            port="$(field "@.ports[$i].port" || true)"
            [ -n "$port" ] || break
            case "$port" in 0|1|2|3|4) ;; *) error "invalid switch port";; esac
            link="$(field "@.ports[$i].link")" || error "link status unavailable"
            case "$link" in up) link=1;; down) link=0;; unknown) link="";; *) error "invalid link state";; esac
            json_add_object ""; json_add_string port "$port"; json_add_string status "$link"; json_close_object
            i=$((i+1))
        done
        json_close_array
        if [ "$1" = get_port ]; then
            json_add_string port_wan ""
            json_add_string enable_set_port 0
        fi
        ;;
    get_wan_traffic)
        native="$(ubus -t 3 call veci.v2 traffic '{}')" || error "traffic counters unavailable"
        [ "$(field '@.source')" = kernel_interface_counters ] || error "unexpected counter source"
        rx="$(field '@.rx_bytes')" || error "RX unavailable"
        tx="$(field '@.tx_bytes')" || error "TX unavailable"
        case "$rx:$tx" in *[!0-9:]*|:*|*:) error "invalid counters";; esac
        success "get traffic counters success"
        json_add_object data
        json_add_string interface usb0; json_add_string rxall "$rx"; json_add_string txall "$tx"
        json_close_object
        ;;
    online_upgrade_check)
        native="$(native_read veci.v2.updatepolicy status)" || error "update policy unavailable"
        mode="$(field '@.mode')" || error "update policy invalid"
        case "$mode" in manual|verify_only) ;; *) error "update policy invalid";; esac
        # There is no approved OEM release catalog yet. Never return an OTA URL.
        json_init; json_add_string code -6
        json_add_string reason "No verified OEM release catalog available"
        json_add_string update_policy "$mode"
        json_add_string release_status unverified
        ;;
    get_days_traffic|refresh_days_traffic)
        native="$(native_read veci.v2.observability trafficHistory)" || error "traffic history unavailable"
        [ "$(field '@.source')" = kernel_sampled_bytes ] || error "unexpected traffic source"
        # Return actual measured intervals and gaps, not invented seven-day
        # totals. The legacy history chart must be adapted to this contract.
        success "local traffic history"
        json_add_string history_state "$(field '@.state')"
        json_add_string persistent false
        json_add_string window_seconds 86400
        for key in samples first_epoch last_epoch lte_observed_seconds lan_observed_seconds lte_gaps lan_gaps lte_rx_bytes lte_tx_bytes lan_rx_bytes lan_tx_bytes; do
            value="$(field "@.$key" || true)"
            case "$value" in ''|null) json_add_string "$key" "";; *[!0-9]*) error "invalid traffic value";; *) json_add_string "$key" "$value";; esac
        done
        ;;
    get_disk)
        # Native storage inventory, not the legacy public /www/usb mount.
        success "get storage inventory success"
        json_add_array data
        for mount in /overlay /tmp; do
            stats="$(df -Pk "$mount" | awk 'NR==2{print $2,$3,$4,$5}')" || error "storage unavailable"
            set -- $stats
            [ "$#" = 4 ] || error "invalid storage counters"
            case "$1:$2:$3" in *[!0-9:]*|:*|*:) error "invalid storage counters";; esac
            json_add_object ""
            json_add_string disk_type "$(awk -v m="$mount" '$2==m{print $3;exit}' /proc/mounts)"
            json_add_string disk_size "${1} KiB"
            json_add_string disk_used "${2} KiB"
            json_add_string disk_available "${3} KiB"
            json_add_string disk_use_percent "$4"
            json_add_string disk_mounted "$mount"
            json_close_object
        done
        json_close_array
        ;;
    get_wifi_power)
        # OpenWrt txpower is dBm, not legacy percentage. Never invent a conversion.
        power="$(get wireless.radio0.txpower || true)"
        case "$power" in ''|*[!0-9]*) power="";; esac
        success "get native Wi-Fi power success"
        json_add_string wifi_power "native"
        json_add_string txpower_dbm "$power"
        json_add_string power_mode "$(if [ -n "$power" ]; then printf configured; else printf regulatory_auto; fi)"
        ;;
    search_ctcode_and_channals)
        native="$(native_read veci.v2.wifi info)" || error "Wi-Fi capabilities unavailable"
        country="$(get wireless.radio0.country || true)"
        channel="$(get wireless.radio0.channel || true)"
        (json_load "$native" && json_get_type typ channels && [ "$typ" = array ]) || error "live regulatory channels unavailable"
        success "get regulatory channels success"
        json_add_string country "$country"; json_add_string channel "$channel"
        json_add_array country_list
        [ -z "$country" ] || json_add_string "" "$country"
        json_close_array
        json_add_array channel_list
        for ch in $(field '@.channels[*]'); do
            case "$ch" in [1-9]|1[0-4]) json_add_string "" "$ch";; *) error "invalid native channel";; esac
        done
        json_close_array
        ;;
    get_imei)
        # Cached read only, never raw AT or hardware identifier modification.
        native="$(/usr/sbin/we5927-lte status-fast)" || error "modem status unavailable"
        imei="$(field '@.imei' || true)"
        case "$imei" in *[!0-9]*|'') imei="";; *) [ "${#imei}" = 15 ] || imei="";; esac
        success "get modem identity success"
        # Keep raw identifiers out of legacy OEM JSON; expose last four only.
        if [ -n "$imei" ]; then json_add_string imei "***********${imei#???????????}"; else json_add_string imei "NOT GET"; fi
        json_add_string set_imei "NOT SUPPORTED"
        ;;
    get_netwatchdog)
        native="$(native_read veci.v2.lte status)" || error "LTE monitor unavailable"
        interval="$(field '@.monitor_interval')" || error "monitor interval unavailable"
        case "$interval" in [5-9]|[1-9][0-9]|1[01][0-9]|120) ;; *) error "monitor interval invalid";; esac
        host1="$(get we5927_lte.main.ping_host)" || error "monitor host unavailable"
        threshold="$(get we5927_lte.main.fail_threshold)" || error "monitor threshold unavailable"
        case "$threshold" in [2-9]|1[0-9]|20) ;; *) error "monitor threshold invalid";; esac
        success "get anyos netwatchdog success"
        json_add_object data
        json_add_string detect_host1 "$host1"
        json_add_string detect_host2 ""
        json_add_string detect_itv "$interval"
        json_add_string fail_threshold "$threshold"
        # Do not represent native recovery as vendor global network restart.
        json_add_string action "lte_recovery"
        json_close_object
        ;;
    get_nat_acceleration)
        # Use the actual modern firewall option; this is not a hardware claim.
        offload="$(get firewall.@defaults[0].flow_offloading || true)"
        case "$offload" in 1) enabled=1;; ''|0) enabled=0;; *) error "invalid flow offload setting";; esac
        native="$(native_read veci.v2.firewall status)" || error "firewall revision unavailable"
        revision="$(field '@.revision')" || error "firewall revision unavailable"
        success "get net acceleration success"
        json_add_string revision "$revision"
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
