"""Exercise the packaged clock and NTP provider against real UCI and jshn binaries."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "rebuild/veci-v2/packages/veci-v2-runtime"
uci_binary = Path(sys.argv[1]).resolve(strict=True)
jshn_script = Path(sys.argv[2]).resolve(strict=True)
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    cfg, delta = root / "config", root / "delta"
    cfg.mkdir()
    delta.mkdir()
    system = cfg / "system"
    system.write_text("config system 'sys'\n option hostname 'office'\n option timezone 'JST-9'\n"
                      " option zonename 'Asia/Tokyo'\nconfig timeserver 'ntp'\n"
                      " option enable_server '0'\n list server 'old.example.org'\n")
    board = root / "board"
    board.write_text("zbtlink,zbt-we5927\n")
    provider = root / "time"
    provider.write_text((PACKAGE / "veci2-time").read_text().replace(
        "/usr/share/libubox/jshn.sh", str(jshn_script)).replace(
        "/tmp/sysinfo/board_name", str(board)).replace("/etc/config/system", str(system)))
    provider.chmod(0o700)
    uci = root / "uci"
    uci.write_text(f'#!/bin/sh\nexec "{uci_binary}" -c "{cfg}" -t "{delta}" "$@"\n')
    uci.chmod(0o700)
    env = dict(os.environ, PATH=f"{root}:" + os.environ["PATH"])
    def call(method, params=None):
        return json.loads(subprocess.check_output(["busybox", "ash", provider, "call", method], env=env,
                          input=json.dumps(params or {}), text=True, timeout=5))
    def get(option):
        return subprocess.check_output([uci, "get", option], text=True).strip()
    initial = call("status")
    assert initial["ok"] and initial["zone"] == "Asia/Tokyo" and initial["enabled"]
    assert initial["servers"] == "old.example.org" and initial["clock"].endswith(" UTC")
    args = dict(revision=initial["revision"], enabled="1", dhcp="0", zone="keep",
                servers="id.pool.ntp.org 192.0.2.4 2001:db8::1 ::ffff:192.0.2.5")
    before = system.read_bytes()
    for value in ("", "1.2.3.678", "ntp..invalid", "-q", "bad;name", "2001:::5", "2001::7::8"):
        for_test = dict(args, servers=value)
        assert not call("save", for_test)["ok"], value
        assert system.read_bytes() == before
    with provider.open() as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        assert call("save", args)["error"] == "busy"
    subprocess.run([uci, "set", "system.sys.hostname=pending"], check=True)
    assert call("save", args)["error"] == "pending_system_changes"
    assert get("system.sys.hostname") == "pending" and system.read_bytes() == before
    subprocess.run([uci, "revert", "system"], check=True)
    saved = call("save", args)
    assert saved["ok"] and saved["servers"] == args["servers"] and not saved["dhcp"]
    assert saved["zone"] == "Asia/Tokyo" and get("system.sys.timezone") == "JST-9"
    assert get("system.sys.hostname") == "office" and get("system.ntp.enable_server") == "0"
    assert call("save", args)["error"] == "stale_configuration"
    args.update(revision=saved["revision"], zone="Asia/Jakarta", servers="", dhcp="1")
    saved = call("save", args)
    assert saved["ok"] and saved["dhcp"] and not saved["servers"]
    assert get("system.sys.timezone") == "WIB-7"
    subprocess.run([uci, "delete", "system.ntp"], check=True)
    subprocess.run([uci, "commit", "system"], check=True)
    initial = call("status")
    assert initial["enabled"] is False
    assert call("save", dict(args, revision=initial["revision"]))["ok"]
    board.write_text("another-board\n")
    assert call("save", args)["error"] == "unsupported_board"
    acl = json.loads((PACKAGE / "veci2-time-acl.json").read_text())["veci-v2-time"]
    assert acl["read"]["ubus"]["veci.v2.time"] == ["status"]
    assert acl["write"]["ubus"]["veci.v2.time"] == ["save"]
    print("PASS clock status and UCI defaults, DNS/IPv4/IPv6, rejected input, session revision, lock, "
          "pending changes, new section, time zone, preservation, board and ACL")
