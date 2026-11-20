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
    script = root / "provider"
    script.write_text((pkg / "veci2-interfaces").read_text().replace(
        "/etc/config/network", str(network)).replace("/tmp/sysinfo/board_name", str(board))
        .replace("/var/lock/veci2-ipv6.lock", str(lock)).replace("/usr/share/libubox/jshn.sh", str(jshn)))
    uci = root / "uci"
    uci.write_text(f'#!/bin/sh\nexec "{binary}" -c "{config}" -t "{delta}" "$@"\n')
    uci.chmod(0o700)
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
    subprocess.run([uci, "add_list", "network.lan.ipaddr=172.16.1.1/24"], check=True)
    subprocess.run([uci, "commit", "network"], check=True)
    assert call("status")["error"] == "multiple_addresses"
    board.write_text("other")
    assert call("save", args)["error"] == "board_mismatch"
    print("PASS LAN IPv4, DHCP/static WAN roundtrip, CIDR/netmask, overlap and gateway rejection, pending edits, stale revision, lock, multiple addresses, LTE/IPv6/device/metric preservation and exact board")
