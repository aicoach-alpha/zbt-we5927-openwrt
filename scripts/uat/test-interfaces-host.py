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
        .replace("/etc/board.json", str(board_json)).replace("/sys/class/net/",str(fake_dev)+"/")
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
    saved = call("save", args)
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
