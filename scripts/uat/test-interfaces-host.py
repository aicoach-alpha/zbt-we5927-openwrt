"""Exercise the installed WAN/LAN RPC with real UCI, BusyBox ash and libubox."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

pkg = Path(__file__).resolve().parents[2] / "rebuild/veci-v2/packages/veci-v2-runtime"
binary = Path(sys.argv[1]).resolve(strict=True)
jshn = Path(sys.argv[2]).resolve(strict=True)
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    config = root / "config"
    delta = root / "delta"
    config.mkdir()
    delta.mkdir()
    network = config / "network"
    network.write_text("""config interface 'lan'
 option device 'br-lan'
 option proto 'static'
 option ipaddr '192.168.1.1'
 option netmask '255.255.255.0'
 option ip6assign '0'
config interface 'wan'
 option device 'eth0.2'
 option proto 'dhcp'
 option metric '30'
config interface 'lte'
 option device 'usb0'
 option proto 'dhcp'
""")
    dhcp = config / "dhcp"
    dhcp.write_text("config dhcp 'lan'\n option interface 'lan'\n option start '100'\n option limit '100'\n")
    dhcp_lock = root / "dhcp.lock"
    lock = root / "lock"
    board = root / "board"
    board.write_text("zbtlink,zbt-we5927\n")
    fake_dev = root / "net"
    (fake_dev / "eth0.2").mkdir(parents=True)
    board_json = root / "board.json"
    board_json.write_text(json.dumps({"network":{"wan":{"device":"eth0.2"}}}))
    script = root / "provider"
    script.write_text((pkg / "veci2-interfaces").read_text().replace(
        "/etc/config/network", str(network)).replace("/tmp/sysinfo/board_name", str(board))
        .replace("/var/run/veci2-reboot-requested",str(root/"reboot-pending")).replace("/etc/board.json", str(board_json)).replace("/sys/class/net/",str(fake_dev)+"/")
        .replace("/etc/config/dhcp",str(dhcp)).replace("/var/lock/veci2-dhcp.lock",str(dhcp_lock))
        .replace("/var/lock/veci2-ipv6.lock", str(lock)).replace("/usr/share/libubox/jshn.sh", str(jshn)))
    uci = root / "uci"
    uci.write_text(f'#!/bin/sh\nexec "{binary}" -c "{config}" -t "{delta}" "$@"\n')
    uci.chmod(0o700)
    # Host libubox supplies jshn; the board-only jsonfilter lookup is isolated.
    filt=root/"jsonfilter"
    filt.write_text("""#!/usr/bin/env python3
import json,sys
assert len(sys.argv)==5 and sys.argv[1]=="-i" and sys.argv[3:]==["-e","@.network.wan.device"]
print(json.load(open(sys.argv[2]))["network"]["wan"]["device"])
""")
    filt.chmod(0o700)
    env = dict(os.environ, PATH=f"{root}:" + os.environ["PATH"])
    def call(method, params=None):
        return json.loads(subprocess.check_output(["busybox", "ash", script, "call", method], env=env,
                          text=True, input=json.dumps(params or {}), timeout=5))
    def get(key):
        return subprocess.check_output([uci, "get", "network." + key], text=True).strip()
    initial = call("status")
    assert initial["lan_mask"] == "255.255.255.0" and initial["wan_mode"] == "dhcp"
    # All ubus actions are confined to a disposable shim, no live netifd.
    u=root/"ubus"
    u.write_text("""#!/bin/sh
case "$*" in
 "-t 3 call network.interface.wan status {}") cat "$LIVE";;
 "-t 5 call network.interface.wan down {}"|"-t 5 call network.interface.wan up {}") printf '%s\n' "$*" >> "$ACTIONS";;
 *) exit 99;;
esac
""")
    u.chmod(0o700)
    live=root/"live.json";actions=root/"actions"
    env.update(LIVE=str(live),ACTIONS=str(actions))
    filt.write_text("""#!/usr/bin/env python3
import json,sys,re
try:
 if sys.argv[1]=="-i": data=json.load(open(sys.argv[2]));q=sys.argv[4]
 else: data=json.load(sys.stdin);q=sys.argv[2]
 for a,b,c in re.findall(r'\.([a-zA-Z0-9_]+)|\["([^"]+)"\]|\[(\d+)\]',q):
  data=data[a or b] if a or b else data[int(c)]
 print(str(data).lower() if isinstance(data,bool) else data)
except (KeyError,IndexError,TypeError,ValueError):sys.exit(1)
""")
    live.write_text(json.dumps(dict(proto="dhcp",up=True,pending=False,device="eth0.2")))
    assert call("pppoeStatus")["state"]=="not_configured"
    original=network.read_bytes()
    subprocess.run([uci,"set","network.wan.proto=pppoe"],check=True)
    subprocess.run([uci,"commit","network"],check=True)
    snapshot=network.read_bytes()
    rev=call("status")["revision"]
    payload=dict(revision=rev,action="disconnect",confirmation="DISCONNECT_ETHERNET_PPPOE")
    assert call("pppoeStatus")["state"]=="pending_activation"
    assert call("pppoeAction",payload)["error"]=="pending_activation"
    live.write_text(json.dumps(dict(proto="pppoe",up=True,pending=False,device="eth0.2",**{"ipv4-address":[{"address":"192.0.2.10"}]})))
    assert call("pppoeStatus")["state"]=="connected"
    assert call("pppoeAction",payload|dict(revision="stale"))["error"]=="stale_configuration"
    (root/"reboot-pending").touch()
    assert call("pppoeAction",payload)["error"]=="reboot_pending"
    (root/"reboot-pending").unlink()
    assert not actions.exists()
    assert call("pppoeAction",payload)["state"]=="pending_verification"
    assert call("pppoeAction",payload|dict(action="reconnect",confirmation="RECONNECT_ETHERNET_PPPOE"))["requested"]
    assert actions.read_text().splitlines()==["-t 5 call network.interface.wan down {}","-t 5 call network.interface.wan down {}","-t 5 call network.interface.wan up {}"]
    assert network.read_bytes()==snapshot
    live.write_text(json.dumps(dict(proto="pppoe",up=False,pending=False,device="eth0.2",**{"ipv4-address":[{"address":"192.0.2.10"}]})))
    assert call("pppoeStatus")["ipv4"]==""
    network.write_bytes(original)
    print("PASS PPPoE state and scoped action request fixtures")

    args = dict(revision=initial["revision"], confirm="SAVE_NETWORK", lan="192.168.2.1",
                lan_mask="24", wan_mode="static", wan="10.1.1.2", wan_mask="255.255.255.0", gateway="10.1.1.1")
    before = network.read_bytes()
    for override in (dict(lan="192.168.2.0"), dict(lan="192.168.2.255"),
                     dict(lan_mask="255.0.255.0"), dict(wan="192.168.2.2", gateway="192.168.2.3"),
                     dict(gateway="10.2.1.1"), dict(gateway="10.1.1.2"), dict(wan="224.0.0.5"),
                     dict(lan="1.2.3.256"), dict(confirm=""), dict(revision="bad")):
        assert not call("save", args | override)["ok"], override
        assert network.read_bytes() == before
    with lock.open() as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        assert call("save", args)["error"] == "busy"
    subprocess.run([uci, "set", "network.lte.metric=3"], check=True)
    assert call("save", args)["error"] == "pending_network_changes"
    assert get("lte.metric") == "3" and network.read_bytes() == before
    subprocess.run([uci, "revert", "network"], check=True)
    # An incompatible pool, static lease, or pending DHCP writer must not
    # mutate network or DHCP. Compatible change preserves DHCP bytes.
    base_dhcp=dhcp.read_bytes()
    with dhcp_lock.open("w") as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        assert call("save",args)["error"]=="dhcp_busy"
    for extra,expected in (("config host\n option ip '192.168.1.12'\n","reservation_conflicts_with_lan"),("config host\n option ip '192.168.2.1'\n","reservation_conflicts_with_lan")):
        dhcp.write_bytes(base_dhcp+extra.encode())
        snapshot=dhcp.read_bytes()
        assert call("save",args)["error"]==expected
        assert network.read_bytes()==before and dhcp.read_bytes()==snapshot
    dhcp.write_bytes(base_dhcp)
    assert call("save",args|dict(lan_mask="25"))["error"]=="dhcp_pool_conflicts_with_lan"
    subprocess.run([uci,"set","dhcp.lan.start=20"],check=True)
    assert call("save",args)["error"]=="pending_dhcp_changes"
    subprocess.run([uci,"revert","dhcp"],check=True)
    # Native guest's fixed subnet must not be accidentally invalidated.
    subprocess.run([uci,"set","network.veci_guest=interface"],check=True)
    subprocess.run([uci,"commit","network"],check=True)
    guest_args=args|dict(revision=call("status")["revision"])
    assert call("save",guest_args)["error"]=="guest_requires_standard_lan"
    subprocess.run([uci,"delete","network.veci_guest"],check=True)
    subprocess.run([uci,"commit","network"],check=True)
    args["revision"]=call("status")["revision"]
    dhcp.write_bytes(base_dhcp+b"config host\n option ip '192.168.2.12'\n")
    preserved=dhcp.read_bytes()
    saved = call("save", args)
    assert dhcp.read_bytes()==preserved
    print("PASS DHCP pool and reservation compatibility, pending DHCP and guest conflict guards")
    assert saved["ok"] and saved["lan_mask"] == "24" and saved["revision"] != initial["revision"], saved
    assert get("lan.ipaddr") == "192.168.2.1/24" and get("wan.ipaddr") == "10.1.1.2/24"
    assert get("wan.gateway") == "10.1.1.1" and get("lan.ip6assign") == "0"
    assert get("wan.metric") == "30" and get("wan.device") == "eth0.2" and get("lte.proto") == "dhcp"
    assert call("status") == saved
    assert call("save", args)["error"] == "stale_configuration"
    assert call("save", args | dict(revision=saved["revision"], wan_mode="dhcp"))["wan_mode"] == "dhcp"
    assert get("wan.proto") == "dhcp" and "gateway" not in network.read_text()
    # Explicit retirement of existing PPPoE only, not actual network activation.
    for target in ("dhcp","static"):
        subprocess.run([uci,"set","network.wan.proto=pppoe"],check=True)
        for key,value in (("username","FixtureAccount"),("password","FixtureOnly123"),("service","fixture"),("ac","fixture-ac")):
            subprocess.run([uci,"set","network.wan."+key+"="+value],check=True)
        subprocess.run([uci,"commit","network"],check=True)
        status=call("status")
        before=network.read_bytes()
        replace=args | dict(revision=status["revision"],wan_mode=target,confirm="REPLACE_PPPOE_NEXT_BOOT")
        for override in (dict(confirm="SAVE_NETWORK"),dict(revision="stale"),dict(lan="192.168.2.0")):
            assert not call("save",replace | override)["ok"],override
            assert network.read_bytes()==before
        board_json.write_text(json.dumps({"network":{"wan":{"device":"usb0"}}}))
        assert call("save",replace)["error"]=="ethernet_wan_unverified"
        assert network.read_bytes()==before
        board_json.write_text(json.dumps({"network":{"wan":{"device":"eth0.2"}}}))
        # LAN-only edit must preserve the original PPPoE profile.
        preserve=replace | dict(wan_mode="pppoe",confirm="SAVE_NETWORK")
        saved_ppp=call("save",preserve)
        assert saved_ppp["ok"],saved_ppp
        assert get("wan.proto")=="pppoe" and get("wan.service")=="fixture"
        replace["revision"]=saved_ppp["revision"]
        # Simulate a partial commit that writes configuration then reports failure.
        wrapper=uci.read_text()
        uci.write_text(wrapper.replace('exec "', '"',1).rstrip()+chr(10)+ 'rc=$?'+chr(10)+'case "$*" in *"commit network") exit 1;; esac'+chr(10)+'exit "$rc"'+chr(10))
        before=network.read_bytes()
        failed=call("save",replace)
        assert failed["error"]=="commit_failed_rollback",failed
        assert network.read_bytes()==before
        uci.write_text(wrapper)
        result=call("save",replace)
        assert result["ok"] and result["wan_mode"]==target,result
        for key in ("username","password","service","ac"):
            assert subprocess.run([uci,"-q","get","network.wan."+key],capture_output=True).returncode!=0
        assert get("lte.device")=="usb0" and get("wan.device")=="eth0.2" and get("wan.metric")=="30"
        assert "FixtureOnly123" not in json.dumps(result)
    print("PASS explicit PPPoE retirement to DHCP/static, LAN-only preservation, Ethernet guard and rollback")
    subprocess.run([uci, "add_list", "network.lan.ipaddr=172.16.1.1/24"], check=True)
    subprocess.run([uci, "commit", "network"], check=True)
    assert call("status")["error"] == "multiple_addresses"
    board.write_text("other")
    assert call("save", args)["error"] == "board_mismatch"
    print("PASS LAN IPv4, DHCP/static WAN roundtrip, CIDR/netmask, overlap and gateway rejection, pending edits, stale revision, lock, multiple addresses, LTE/IPv6/device/metric preservation and exact board")
