"""Fixture tests for OEM translation of canonical VeCI RPC results."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "rebuild/oem-updated/backend"

class NativeReuse(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        jshn = self.root / "jshn"
        jshn.write_text("""
json_init() { :; }
json_add_string() { printf '%s=%s\\n' "$1" "$2"; }
json_add_array() { printf 'array:%s\\n' "$1"; }
json_add_object() { :; }
json_close_object() { :; }
json_close_array() { :; }
json_dump() { :; }
json_load() { :; }
json_get_type() { typ="${ARRAY_TYPE:-array}"; }
""")
        # The fixture only replaces OS dependencies, not adapter logic.
        p = self.root / "adapter"
        p.write_text((ROOT/"read-only-adapter.sh").read_text().replace(
            "/usr/share/libubox/jshn.sh", str(jshn)).replace(
            "/proc/net/arp", str(self.root/"arp")))
        (self.root/"arp").write_text(
            "IP address HW type Flags HW address Mask Device\n"
            "192.168.1.2 0x1 0x2 aa:bb:cc:dd:ee:ff * br-lan\n"
            "192.168.7.1 0x1 0x2 aa:bb:cc:dd:ee:01 * usb0\n")
        self.cmd("ubus", """#!/bin/sh
case "$4:$5" in
 veci.v2.system:ntp|veci.v2.dhcp:status|veci.v2.firewall:status) printf '%s' "$NATIVE";;
 *) exit 1;;
esac
""")
        self.cmd("uci", """#!/bin/sh
case "$3" in
 system.ntp.enable_server) echo 0;;
 'system.@system[0].timezone') echo WIB-7;;
 firewall.veci_owner_dmz) echo redirect;;
 firewall.veci_owner_dmz.target) echo DNAT;;
 firewall.veci_owner_dmz.src) echo wan;;
 firewall.veci_owner_dmz.dest) echo lan;;
 firewall.veci_owner_dmz.enabled) echo "${ENABLED:-1}";;
 firewall.veci_owner_dmz.src_dport) [ -n "${PORTS:-}" ] && echo "$PORTS";;
 *) exit 1;;
esac
""")
        self.cmd("jsonfilter", """#!/usr/bin/env python3
import json,re,sys
try:
 x=json.load(sys.stdin)
 for key in re.findall(r'\\.([A-Za-z_]+)|\\[(\\d+)\\]',sys.argv[2]):
  x=x[key[0]] if key[0] else x[int(key[1])]
 if isinstance(x,bool): print(str(x).lower())
 elif isinstance(x,(str,int)): print(x)
 else: sys.exit(1)
except (KeyError,IndexError,TypeError,ValueError): sys.exit(1)
""")

    def cmd(self, name, content):
        p=self.root/name
        p.write_text(content)
        p.chmod(0o755)

    def invoke(self, op, payload, **env):
        import json
        return subprocess.run(["sh",str(self.root/"adapter"),op],
            env=dict(os.environ,PATH=str(self.root)+":"+os.environ["PATH"],
                     NATIVE=json.dumps(payload),**env),
            text=True,capture_output=True,timeout=5)

    def test_ntp_native_translation(self):
        r=self.invoke("get_ntp",{"ok":True,"enabled":"1","servers":["a.example","b.example"]})
        self.assertEqual(r.returncode,0,r.stderr)
        for s in ["enable_ntp_client=1","server_primary=a.example","server_secondary=b.example","timezone=WIB-7"]:
            self.assertIn(s,r.stdout)

    def test_static_dhcp_native_translation(self):
        r=self.invoke("get_static_dhcp",{"ok":True,"leases":[{"index":0,"mac":"aa:bb:cc:dd:ee:ff","ip":"192.168.1.2","name":"client"}]})
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("AA:BB:CC:DD:EE:FF(192.168.1.2)",r.stdout)
        self.assertIn("name=client",r.stdout)
        self.assertNotIn("192.168.7.1",r.stdout)

    def test_dmz_native_translation(self):
        for enabled,expected in [("1","enabled=1"),("0","enabled=0")]:
            r=self.invoke("get_dmz",{"ok":True,"dmz_destination":"192.168.1.4"},ENABLED=enabled)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertIn(expected,r.stdout)
        r=self.invoke("get_dmz",{"ok":True,"dmz_destination":"192.168.1.4"},PORTS="443")
        self.assertNotEqual(r.returncode,0)

    def test_provider_failure_and_invalid_array(self):
        for op in ["get_ntp","get_static_dhcp","get_dmz"]:
            r=self.invoke(op,{"ok":False,"error":"offline"})
            self.assertNotEqual(r.returncode,0)
            self.assertNotIn("code=1",r.stdout)
        r=self.invoke("get_static_dhcp",{"ok":True,"leases":{}},ARRAY_TYPE="object")
        self.assertNotEqual(r.returncode,0)
