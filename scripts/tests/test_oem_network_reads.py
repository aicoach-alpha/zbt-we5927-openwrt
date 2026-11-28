"""Exercise actual OEM network adapter using isolated native provider fixtures."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

BASE=Path(__file__).resolve().parents[2]/"rebuild/oem-updated/backend"

class NetworkReads(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d=Path(tmp.name)
        self.cmd("jshn", """json_init() { :; }
json_add_string() { printf '%s=%s\\n' "$1" "$2"; }
json_add_int() { printf '%s=%s\\n' "$1" "$2"; }
json_add_array() { printf 'array:%s\\n' "$1"; }
json_add_object() { :; }
json_close_object() { :; }
json_close_array() { :; }
json_dump() { :; }
json_load() { [ -n "$1" ]; }
""")
        self.cmd("lte", "#!/bin/sh\n[ \"$1\" = status-fast ] && printf '%s' \"$MODEM\"\n")
        self.cmd("date", "#!/bin/sh\necho 1000\n")
        self.cmd("ubus", """#!/bin/sh
case "$4:$5" in
 veci.v2.interfaces:status) printf '%s' "$NATIVE";;
 network.interface.wan:status) printf '%s' "$LIVE";;
 *) exit 1;;
esac
""")
        self.cmd("uci", "#!/bin/sh\n[ \"$3\" = network.wan.dns ] && echo '1.1.1.1 8.8.8.8'\n")
        self.cmd("cat", """#!/bin/sh
case "$1" in
 /sys/class/net/eth0.2/address) echo aa:bb:cc:dd:ee:ff;;
 *) exit 1;;
esac
""")
        self.cmd("jsonfilter", """#!/usr/bin/env python3
import json,re,sys
try:
 x=json.load(sys.stdin)
 q=sys.argv[2]
 if q=="@.route[@.target='0.0.0.0' && !@.table].nexthop":
  x=next(r["nexthop"] for r in x["route"] if r["target"]=="0.0.0.0" and "table" not in r)
 elif q=='@["ipv6-address"][*].address':
  print("\\n".join(r["address"] for r in x["ipv6-address"]));sys.exit()
 else:
  for a,b,c in re.findall(r'\\.([A-Za-z_][A-Za-z0-9_]*)|\\["([^"]+)"\\]|\\[(\\d+)\\]',q):
   x=x[a or b] if (a or b) else x[int(c)]
 if isinstance(x,bool): print(str(x).lower())
 elif isinstance(x,(str,int)): print(x)
 else: sys.exit(1)
except (KeyError,IndexError,TypeError,ValueError,StopIteration): sys.exit(1)
""")
        (self.d/"arp").write_text("IP address HW type Flags HW address Mask Device\n192.168.1.2 0x1 0x2 aa:bb:cc:dd:ee:ff * br-lan\n192.168.7.1 0x1 0x2 aa:bb:cc:dd:ee:01 * usb0\n192.168.1.9 0x1 0x0 00:00:00:00:00:00 * br-lan\n")
        (self.d/"leases").write_text("1200 aa:bb:cc:dd:ee:ff 192.168.1.2 client *\n900 aa:bb:cc:dd:ee:01 192.168.1.3 expired *\n0 aa:bb:cc:dd:ee:02 192.168.1.4 * *\n1200 aa:bb:cc:dd:ee:03 192.168.1.5 $(touch\u0020/tmp/no-oem-exec) *\n9999999999999999999999 aa:bb:cc:dd:ee:04 192.168.1.6 overflow *\n")
        s=(BASE/"read-only-adapter.sh").read_text()
        for old,new in [("/usr/share/libubox/jshn.sh",self.d/"jshn"),("/usr/sbin/we5927-lte",self.d/"lte"),("/proc/net/arp",self.d/"arp"),("/tmp/dhcp.leases",self.d/"leases")]:
            s=s.replace(old,str(new))
        (self.d/"adapter").write_text(s)

    def cmd(self,name,body):
        p=self.d/name;p.write_text(body);p.chmod(0o755)

    def invoke(self,op,**env):
        defaults={"MODEM":json.dumps({"sim":1,"operator":"Example","model":"4108","signal_dbm":-85,"access_tech":"LTE","imei":"secret","iccid":"secret2"}),
          "NATIVE":json.dumps({"ok":True,"wan_mode":"dhcp"}),
          "LIVE":json.dumps({"up":True,"device":"eth0.2","ipv4-address":[{"address":"192.168.2.2","mask":24}],"route":[{"target":"0.0.0.0","mask":0,"nexthop":"192.168.2.1"}],"dns-server":["1.1.1.1"],"ipv6-address":[{"address":"2001:db8::1"}]})}
        defaults.update(env)
        return subprocess.run(["sh",str(self.d/"adapter"),op],env=dict(os.environ,PATH=str(self.d)+":"+os.environ["PATH"],**defaults),capture_output=True,text=True,timeout=5)

    def test_radio_lte_policy_and_masked_identity(self):
        self.cmd("ubus", """#!/bin/sh
case "$4:$5" in
 veci.v2.lte:status) printf '%s' "$LTE";;
 veci.v2.wifi:power) printf '%s' "$POWER";;
 *) exit 1;;
esac
""")
        self.cmd("uci", """#!/bin/sh
case "$3" in
 we5927_lte.main.ping_host) echo 1.1.1.1;;
 we5927_lte.main.fail_threshold) echo 3;;
 *) exit 1;;
esac
""")
        state=dict(ok=True,configured_apn="lab.example",configured_slot=2,auto_failover=True,monitor_interval=60)
        for op,wanted in (("get_4g",["apn=lab.example","sim_set=SIM2","apn_scope=shared"]),("get_netwatchdog",["detect_itv=60","action=lte_recovery"])):
            out=self.invoke(op,LTE=json.dumps(state))
            self.assertEqual(out.returncode,0,out.stderr)
            for v in wanted:self.assertIn(v,out.stdout)
        self.assertNotEqual(self.invoke("get_4g",LTE=json.dumps(state|dict(configured_slot=3))).returncode,0)
        out=self.invoke("get_wifi_power",POWER=json.dumps(dict(ok=True,configured="15",safe_max_dbm="20")))
        self.assertIn("configured=15",out.stdout)
        self.assertIn("live_power_verified=false",out.stdout)
        self.assertNotEqual(self.invoke("get_wifi_power",POWER=json.dumps(dict(ok=True,configured="99"))).returncode,0)
        out=self.invoke("get_imei",MODEM=json.dumps(dict(imei="123456789012345")))
        self.assertIn("imei=***********2345",out.stdout)
        self.assertNotIn("123456789012345",out.stdout)

    def test_egress_rate_and_route_change(self):
        self.cmd("ip", """#!/bin/sh
if [ -e "$CHANGED" ]; then echo 'default dev eth0.2'; else echo 'default dev usb0'; fi
""")
        self.cmd("cut", """#!/bin/sh
if [ -e "$SAMPLED" ]; then echo 102.00; else echo 100.00; fi
""")
        self.cmd("sleep", """#!/bin/sh
touch "$SAMPLED"
[ "${CHANGE:-0}" = 0 ] || touch "$CHANGED"
""")
        self.cmd("cat", """#!/bin/sh
case "$1" in
 */rx_bytes) if [ -e "$SAMPLED" ]; then echo 300; else echo 100; fi;;
 */tx_bytes) if [ -e "$SAMPLED" ]; then echo 120; else echo 100; fi;;
 *) exit 1;;
esac
""")
        env=dict(SAMPLED=str(self.d/"sampled"),CHANGED=str(self.d/"changed"))
        out=self.invoke("app_home",**env)
        self.assertEqual(out.returncode,0,out.stderr)
        for expected in ("rx=100","tx=10","internet_status=unknown"):self.assertIn(expected,out.stdout)
        (self.d/"sampled").unlink()
        out=self.invoke("app_home",CHANGE="1",**env)
        self.assertIn("rx=\n",out.stdout)
        self.assertIn("tx=\n",out.stdout)

    def test_initial_version_lan_dhcp_reads(self):
        self.cmd("ubus", """#!/bin/sh
case "$*" in
 *"system board"*) echo '{"release":{"version":"25.12.6"}}';;
 *) printf '%s' "$NATIVE";;
esac
""")
        self.cmd("uci", """#!/bin/sh
case "$3" in
 network.lan.proto) echo static;;
 network.lan.ipaddr) echo 192.168.1.1/24;;
 dhcp.lan.start) echo 100;;
 dhcp.lan.limit) echo 150;;
 dhcp.lan.leasetime) echo 12h;;
 dhcp.lan.ignore) echo 0;;
 *) exit 1;;
esac
""")
        self.cmd("cat", '#!/bin/sh\ncase "$1" in */br-lan/address) echo aa:bb:cc:dd:ee:ff;; *) /bin/cat "$@";; esac\n')
        native=json.dumps({"ok":True,"revision":"a"*64})
        for op,expected in (
            ("get_sys_version",["sysversion=25.12.6"]),
            ("get_lan_config",["ipaddr=192.168.1.1","netmask=255.255.255.0","revision="+"a"*64]),
            ("get_dhcp_config",["dhcp_start=100","dhcp_end=250","dhcp_lease=12h","dhcp_enabled=1","revision="+"a"*64])):
            with self.subTest(op=op):
                r=self.invoke(op,NATIVE=native)
                self.assertEqual(r.returncode,0,r.stderr)
                for field in expected:self.assertIn(field,r.stdout)
        for op in ("get_lan_config","get_dhcp_config"):
            r=self.invoke(op,NATIVE='{"ok":false}')
            self.assertNotEqual(r.returncode,0)
            self.assertNotIn("code=1",r.stdout)

    def test_mptcp_read_never_claims_aggregation(self):
        path=self.d/"mptcp"
        adapter=self.d/"adapter"
        adapter.write_text(adapter.read_text().replace("/proc/sys/net/mptcp/enabled",str(path)))
        self.cmd("cat",'#!/bin/sh\n/bin/cat "$@"\n')
        self.assertIn("state=unavailable",self.invoke("get_mptcp_info").stdout)
        for value,state in (("0","disabled"),("1","enabled")):
            path.write_text(value)
            r=self.invoke("get_mptcp_info")
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn("state="+state,r.stdout)
            self.assertIn("aggregation_verified=false",r.stdout)
        path.write_text("bad")
        self.assertNotEqual(self.invoke("get_mptcp_info").returncode,0)

    def test_optional_smb_inventory_no_credentials(self):
        adapter=self.d/"adapter"
        adapter.write_text(adapter.read_text().replace("/etc/init.d/samba4",str(self.d/"samba4")).replace("/etc/init.d/ksmbd",str(self.d/"ksmbd")))
        self.cmd("pidof",'#!/bin/sh\nexit 1\n')
        r=self.invoke("get_samba_info")
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("state=absent",r.stdout)
        self.assertIn("runtime=unknown",r.stdout)
        self.cmd("samba4",'#!/bin/sh\nexit 0\n')
        r=self.invoke("get_samba_info")
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("state=installed",r.stdout)
        self.assertIn("runtime=process_not_observed",r.stdout)
        self.assertIn("smb_passwd=\n",r.stdout)
        self.assertIn("share_verified=false",r.stdout)
        self.cmd("pidof",'#!/bin/sh\necho 123\n')
        self.assertIn("runtime=process_present",self.invoke("get_samba_info").stdout)

    def test_uplink_read_and_stale_link_redaction(self):
        self.cmd("uci", """#!/bin/sh
case "$2:$3" in
 show:wireless)
   case "${PROFILE:-named}" in
    none) :;;
    anonymous) echo "wireless.@wifi-iface[1].mode='sta'";;
    multiple) printf '%s\n' "wireless.sta.mode='sta'" "wireless.other.mode='sta'";;
    *) echo "wireless.sta.mode='sta'";;
   esac;;
 get:wireless.sta.device) echo radio0;;
 get:wireless.sta.network) echo "${BIND:-wwan}";;
 get:wireless.sta.disabled) echo "${DISABLED:-0}";;
 get:wireless.sta.ssid) echo Example;;
 get:wireless.sta.encryption) echo psk2;;
 get:wireless.sta.key) echo secret-passphrase;;
 *) exit 1;;
esac
""")
        self.cmd("ubus",'#!/bin/sh\nprintf "%s" "$NATIVE"\n')
        self.cmd("cat", """#!/bin/sh
case "$1" in
 */rx_bytes) echo 123;;
 */tx_bytes) echo 456;;
 *) exit 1;;
esac
""")
        live={"up":True,"proto":"dhcp","l3_device":"wlan0","ipv4-address":[{"address":"192.0.2.2"}],"uptime":10}
        for op in ("get_wifi_apclient_config","get_wifi_apclient_status"):
            r=self.invoke(op,NATIVE=json.dumps(live))
            self.assertEqual(r.returncode,0,r.stderr)
            for value in ("ssid=Example","enabled=1","apclient_ip=192.0.2.2","apclient_rx=123","apclient_tx=456"):
                self.assertIn(value,r.stdout)
            self.assertNotIn("secret-passphrase",r.stdout)
            for kwargs,state in (({"DISABLED":"1"},live),({},dict(live,up=False)),({},dict(live,proto="static")),({"PROFILE":"none"},live)):
                r=self.invoke(op,NATIVE=json.dumps(state),**kwargs)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertNotIn("192.0.2.2",r.stdout)
            for kwargs in ({"PROFILE":"anonymous"},{"PROFILE":"multiple"},{"BIND":"lan"}):
                self.assertNotEqual(self.invoke(op,**kwargs).returncode,0)

    def test_mesh_driver_inventory(self):
        self.cmd("iw", """#!/bin/sh
case "$*" in
 "dev")
   [ "${FAIL_IW:-0}" = 0 ] || exit 1
   printf '%s\n' "phy#0" " Interface wlan0" "  type AP"
   [ "${MESH:-0}" = 0 ] || printf '%s\n' " Interface mesh0" "  type mesh point"
   exit 0;;
 "dev mesh0 station dump")
   [ "${FAIL_PEERS:-0}" = 0 ] || exit 1
   printf '%s\n' "Station aa:bb:cc:dd:ee:ff (on mesh0)" "Station aa:bb:cc:dd:ee:01 (on mesh0)";;
 *) exit 1;;
esac
""")
        r=self.invoke("get_mesh_topology")
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("interface_count=0",r.stdout)
        self.assertIn("state=no_mesh_interface",r.stdout)
        r=self.invoke("get_mesh_topology",MESH="1")
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("interface=mesh0",r.stdout)
        self.assertIn("observed_station_count=2",r.stdout)
        self.assertIn("topology_verified=false",r.stdout)
        self.assertNotIn("aa:bb",r.stdout)
        r=self.invoke("get_mesh_topology",MESH="1",FAIL_PEERS="1")
        self.assertIn("observed_station_count=\n",r.stdout)
        self.assertNotEqual(self.invoke("get_mesh_topology",FAIL_IW="1").returncode,0)

    def test_n2n_inventory_and_link_state(self):
        self.cmd("uci", """#!/bin/sh
case "$2:$3" in
 show:network)
    [ "${EMPTY:-0}" = 1 ] || printf "%s\n" "network.vpn0.proto='n2n'" "network.vpn0.key='secret-community-key'"
    exit 0;;
 get:network.vpn0) echo interface;;
 get:network.vpn0.auto) echo 1;;
 get:network.vpn0.server) echo vpn.example;;
 get:network.vpn0.port) echo 1234;;
 get:network.vpn0.key) echo secret-community-key;;
 *) exit 1;;
esac
""")
        self.cmd("ubus",'#!/bin/sh\nprintf "%s" "$NATIVE"\n')
        r=self.invoke("get_n2n",EMPTY="1")
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("state=unconfigured",r.stdout)
        self.assertIn("profile_count=0",r.stdout)
        for op in ("get_n2n","get_n2n_status"):
            r=self.invoke(op,NATIVE=json.dumps({"proto":"n2n","up":True,"ipv4-address":[{"address":"192.0.2.2"}],"uptime":20}))
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn("n2n_name=vpn0",r.stdout)
            self.assertIn("profile_count=1",r.stdout)
            self.assertNotIn("secret-community-key",r.stdout)
            if op.endswith("status"):
                self.assertIn("runtime=link_up",r.stdout)
                self.assertIn("tunnel_verified=false",r.stdout)
        r=self.invoke("get_n2n_status",NATIVE=json.dumps({"proto":"n2n","up":False,"ipv4-address":[{"address":"192.0.2.2"}]}))
        self.assertIn("runtime=down",r.stdout)
        self.assertNotIn("192.0.2.2",r.stdout)

    def test_shadowsocks_profile_inventory(self):
        adapter=self.d/"adapter"
        cfg=self.d/"ss-config"
        adapter.write_text(adapter.read_text().replace("/etc/config/shadowsocks-libev",str(cfg)))
        self.cmd("uci", """#!/bin/sh
case "$2:$3" in
 show:shadowsocks-libev)
    printf "%s\n" "shadowsocks-libev.dns=ss_tunnel" "shadowsocks-libev.other=ss_tunnel" "shadowsocks-libev.redirect=ss_redir" "shadowsocks-libev.server.password='secret'"
    ;;
 get:*.disabled) echo "${DISABLED:-1}";;
 get:*.mode) echo tcp_only;;
 get:*.local_port) echo 5353;;
 *) exit 1;;
esac
""")
        for op,n in (("get_ss_dns",1),("get_ss_tunnel_info",2),("get_ss_redir",1)):
            with self.subTest(op=op):
                if cfg.exists(): cfg.unlink()
                r=self.invoke(op)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertIn("state=absent",r.stdout)
                cfg.touch()
                r=self.invoke(op)
                self.assertEqual(r.returncode,0,r.stderr)
                self.assertIn("profile_count="+str(n),r.stdout)
                self.assertIn("enabled=0",r.stdout)
                self.assertIn("runtime=unknown",r.stdout)
                self.assertNotIn("secret",r.stdout)
                self.assertNotEqual(self.invoke(op,DISABLED="bad").returncode,0)

    def test_optional_openvpn_profile_status(self):
        self.cmd("ubus",'#!/bin/sh\nprintf "%s" "$NATIVE"\n')
        self.cmd("uci", """#!/bin/sh
case "$3" in
 openvpn.sample_client) echo openvpn;;
 openvpn.sample_client.enabled) echo 0;;
 openvpn.sample_client.remote) echo vpn.example;;
 openvpn.sample_client.key) echo secret_private_key;;
 *) exit 1;;
esac
""")
        for state in ("absent","unconfigured","disabled"):
            r=self.invoke("get_openvpn_msg",NATIVE=json.dumps({"ok":True,"state":state,"revision":"a"*64,"eligible":False}))
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn("state="+state,r.stdout)
            self.assertIn("eligible=false",r.stdout)
            self.assertNotIn("secret_private_key",r.stdout)
        r=self.invoke("get_openvpn_msg",NATIVE='{"ok":false}')
        self.assertNotEqual(r.returncode,0)

    def test_signal_native_and_no_subscriber_id(self):
        r=self.invoke("get_module_signal")
        self.assertEqual(r.returncode,0,r.stderr)
        for value in ["signal=-85","module_sim=SIM1","net_type=LTE","operator=Example"]:
            self.assertIn(value,r.stdout)
        self.assertNotIn("secret",r.stdout)
        r=self.invoke("get_module_signal",MODEM='{"sim":3}')
        self.assertNotEqual(r.returncode,0)

    def test_optional_tunnel_profiles_and_live_counters(self):
        self.cmd("ubus", '#!/bin/sh\nprintf "%s" "$LIVE"\n')
        self.cmd("uci", """#!/bin/sh
case "$3" in
 network.pptp.proto) echo pptp;; network.l2tp.proto) echo l2tp;;
 *.server) echo vpn.example;; *.auto) echo 0;; *.defaultroute) echo 1;;
 *) exit 1;;
esac
""")
        self.cmd("cat", """#!/bin/sh
case "$1" in */statistics/rx_bytes) echo 17400;; */statistics/tx_bytes) echo 400;; *) exit 1;; esac
""")
        for proto in ("pptp", "l2tp"):
            state = dict(up=True, proto=proto, l3_device=f"{proto}-{proto}",
                         uptime=123, **{"ipv4-address": [{"address": "10.8.0.7"}]})
            def invoke(suffix, **override):
                return self.invoke(f"get_{proto}_{suffix}", LIVE=json.dumps(state | override))
            with self.subTest(protocol=proto):
                config = invoke("msg")
                self.assertIn("server=vpn.example", config.stdout)
                self.assertIn("enabled=0", config.stdout)
                self.assertIn("password=\n", config.stdout)
                live = invoke("status")
                self.assertEqual(live.returncode, 0, live.stdout + live.stderr)
                for key, val in (("ip","10.8.0.7"),("uptime","123"),("rx","17400"),("tx","400")):
                    self.assertIn(f"{proto}_{key}={val}", live.stdout)
                self.assertIn(f"{proto}_status=1", invoke("sl_status").stdout)
                down = invoke("status", up=False)
                self.assertIn(f"{proto}_status=0", down.stdout)
                self.assertNotIn("10.8.0.7", down.stdout)
                self.assertNotEqual(invoke("status", l3_device="br-lan").returncode, 0)
                self.assertNotEqual(invoke("status", proto="dhcp").returncode, 0)

    def test_arp_lan_only(self):
        r=self.invoke("get_arp")
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("ipaddr=192.168.1.2",r.stdout)
        self.assertNotIn("192.168.7.1",r.stdout)
        self.assertNotIn("192.168.1.9",r.stdout)

    def test_dhcp_current_and_nonexecuted_host(self):
        r=self.invoke("get_dhcp_allocation")
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("dhcp_remain_lease=200",r.stdout)
        self.assertIn("dhcp_ip=192.168.1.4",r.stdout)
        self.assertIn("dhcp_host=$(touch",r.stdout)
        self.assertNotIn("expired",r.stdout)
        self.assertNotIn("overflow",r.stdout)

    def test_wan_dhcp_and_static(self):
        r=self.invoke("get_wan_config")
        self.assertEqual(r.returncode,0,r.stderr)
        for value in ["proto=dhcp","ipaddr=192.168.2.2","netmask=255.255.255.0","gateway=192.168.2.1","dns_primary=1.1.1.1","=2001:db8::1"]:
            self.assertIn(value,r.stdout)
        r=self.invoke("get_wan_config",NATIVE=json.dumps({"ok":True,"wan_mode":"static","wan":"10.0.0.2","wan_mask":"24","gateway":"10.0.0.1"}))
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("ipaddr=10.0.0.2",r.stdout)
        self.assertIn("gateway=10.0.0.1",r.stdout)

    def test_pppoe_uses_only_main_unicast_default_gateway(self):
        # netifd ubus.c interface_ip_dump_route_list emits target, mask,
        # nexthop and optional numeric type/table. Only a real gateway counts.
        route = {"target": "0.0.0.0", "mask": 0, "nexthop": "192.0.2.9"}
        routes = [route | {"mask": 8}, route | {"table": 100},
                  route | {"type": 6}, route | {"nexthop": "0.0.0.0"},
                  route | {"table": 254, "type": 1, "nexthop": "192.0.2.1"}]
        r = self.invoke("get_wan_config", NATIVE=json.dumps({"ok": True, "wan_mode": "pppoe"}),
                        LIVE=json.dumps({"up": True, "device": "eth0.2", "route": routes}))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("proto=pppoe", r.stdout)
        self.assertIn("gateway=192.0.2.1\n", r.stdout)
        self.assertNotIn("192.0.2.9", r.stdout)

    def test_wan_failure_closed(self):
        for native in ['{"ok":false}', '{"ok":true,"wan_mode":"unknown"}']:
            r=self.invoke("get_wan_config",NATIVE=native)
            self.assertNotEqual(r.returncode,0)
        r=self.invoke("get_wan_config",LIVE='{"device":"../../etc"}')
        self.assertNotEqual(r.returncode,0)

    def test_wan_down_does_not_return_stale_dhcp_address(self):
        r=self.invoke("get_wan_config",LIVE=json.dumps({"up":False,"device":"eth0.2","ipv4-address":[{"address":"192.168.2.2","mask":24}],"route":[{"target":"0.0.0.0","mask":0,"nexthop":"192.168.2.1"}],"dns-server":["1.1.1.1"],"ipv6-address":[{"address":"2001:db8::1"}]}))
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("ipaddr=0.0.0.0",r.stdout)
        self.assertNotIn("192.168.2.1",r.stdout)
        self.assertNotIn("2001:db8::1",r.stdout)
