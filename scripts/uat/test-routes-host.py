"""Exercise the packaged routing RPC with native UCI and BusyBox."""
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
    script.write_text((pkg / "veci2-routes").read_text().replace(
        "/etc/config/network", str(network)).replace("/tmp/sysinfo/board_name", str(board))
        .replace("/var/run/veci2-reboot-requested",str(root/"reboot-pending")).replace("/var/lock/veci2-ipv6.lock", str(lock)).replace("/usr/share/libubox/jshn.sh", str(jshn)))
    uci = root / "uci"
    failure = root / "fail-commit"
    uci.write_text(f'#!/bin/sh\nif test -f "{failure}"; then for arg do test "$arg" != commit || exit 1; done; fi\nexec "{binary}" -c "{config}" -t "{delta}" "$@"\n')
    uci.chmod(0o700)
    env = dict(os.environ, PATH=f"{root}:" + os.environ["PATH"])
    def call(method, params=None):
        return json.loads(subprocess.check_output(["busybox", "ash", script, "call", method], env=env,
                          text=True, input=json.dumps(params or {}), timeout=5))
    def get(key):
        return subprocess.check_output([uci, "get", "network." + key], text=True).strip()
    with network.open('a') as stream:
        stream.write("config rule\n option priority '555'\n option lookup '150'\n"
                     "config route 'veci2_route_legacy'\n option target '203.0.113.0/24'\n")
    acl = json.loads((pkg / "veci2-routes-acl.json").read_text())["veci-v2-routes"]
    assert acl["read"] == {"ubus": {"veci.v2.routes": ["status"]}}
    assert acl["write"] == {"ubus": {"veci.v2.routes": ["save", "remove"]}}
    initial = call("status")
    assert len(initial["entries"]) == 2 and not any(e["editable"] for e in initial["entries"])
    route = dict(revision=initial["revision"], name="office", kind="route", interface="wan",
                 prefix="192.0.2.0/24", gateway="192.168.1.2", table="120")
    before = network.read_bytes()
    for values in (dict(prefix="1.2.3.4/24"), dict(prefix="10.0.0.0/33"), dict(table="255"),
                   dict(name="../lan"), dict(interface="missing"), dict(gateway="224.0.0.1"),
                   dict(prefix="192.0.2.0.24"), dict(prefix="192/0/2/0/24"),
                   dict(gateway="192/168/1/2"), dict(kind="interface"), dict(name="legacy"), dict(revision="old")):
        assert not call("save", route | values)["ok"], values
        assert network.read_bytes() == before
    with lock.open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        assert call("save", route)["error"] == "busy"
    failure.touch()
    assert call("save", route)["error"] == "commit_failed_rollback"
    assert before == network.read_bytes() and call("status") == initial
    failure.unlink()
    (root/"reboot-pending").touch()
    assert call("save",route)["error"]=="reboot_pending"
    (root/"reboot-pending").unlink()
    wrapper=uci.read_text()
    uci.write_text(wrapper.replace('exec "', '"',1)+'rc=$?'+chr(10)+'case "$*" in *"commit network") exit 1;; esac'+chr(10)+'exit "$rc"'+chr(10))
    assert call("save",route)["error"]=="commit_failed_rollback"
    assert network.read_bytes()==before
    uci.write_text(wrapper)
    result = call("save", route)
    assert result["ok"] and get("veci2_route_office.table") == "120"
    assert call("save", route)["error"] == "stale_configuration"
    result = call("save", route | dict(revision=result["revision"], gateway=""))
    assert result["ok"] and "gateway" not in next(e for e in result["entries"] if e["editable"])
    rule = dict(name="branch", kind="rule", prefix="198.51.100.0/24", table="120",
                priority="600", revision=result["revision"])
    assert call("save", rule | dict(priority="555"))["error"] == "priority_in_use"
    assert call("save", rule | dict(prefix="0.0.0.0/0"))["error"] == "source_required"
    result = call("save", rule)
    assert result["ok"] and get("veci2_route_branch.lookup") == "120"
    assert call("remove", dict(revision=result["revision"], name="legacy"))["error"] == "unmanaged_section"
    for name in ("office", "branch"):
        result = call("remove", dict(revision=result["revision"], name=name))
        assert result["ok"]
    assert result["entries"] == initial["entries"] and get("lte.device") == "usb0"
    subprocess.run([uci, "set", "network.wan.metric=90"], check=True)
    assert call("save", route)["error"] == "pending_changes" and get("wan.metric") == "90"
    board.write_text("unrelated\n")
    assert call("status")["error"] == "wrong_board"
    print("PASS native UCI routing: IPv4 CIDR and gateway validation, interface/table/priority,"
          " stale revision, shared lock, external rules, managed CRUD, pending network preservation,"
          " failed commit preserves config bytes, malformed separators rejected, least-privilege ACL")
