"""Exercise primary SSID changes using host UCI. Pass the native uci executable."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "rebuild/veci-v2/packages/veci-v2-runtime"
uci = Path(sys.argv[1]).resolve(strict=True)
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    for folder in ("config", "delta"):
        (root / folder).mkdir()
    config = root / "config/wireless"
    config.write_text("config wifi-iface 'default_radio0'\n option device 'radio0'\n"
                      " option mode 'ap'\n option ssid 'Old'\n option hidden '1'\n"
                      " option encryption 'psk2'\nconfig wifi-iface 'guest'\n option ssid 'Guest'\n")
    board = root / "board"
    board.write_text("zbtlink,zbt-we5927\n")
    provider = root / "provider"
    provider.write_text((RUNTIME / "veci2-wifi").read_text().replace("/tmp/sysinfo/board_name", str(board)))
    provider.chmod(0o700)
    commands = {
        "uci": f'#!/bin/sh\nexec "{uci}" -c "{root}/config" -t "{root}/delta" "$@"\n',
        "jsonfilter": "#!/usr/bin/env python3\nimport sys,json\nprint(json.loads(sys.argv[2])[sys.argv[4][2:]])\n",
    }
    for command, body in commands.items():
        file = root / command
        file.write_text(body)
        file.chmod(0o700)
    env = dict(os.environ, PATH=f"{root}:" + os.environ["PATH"])

    def call(method, **params):
        p = subprocess.run([provider, "call", method], input=json.dumps(params), text=True,
                           env=env, capture_output=True, check=True)
        return json.loads(p.stdout)

    def config_value(key):
        return subprocess.check_output([root / "uci", "get", "wireless." + key], env=env)[:-1]

    assert call("status")["ssid_hex"] == b"Old".hex()
    for name in ("Kantor 2", "é" * 16, " A'\"$;\\ akhir "):
        raw = name.encode()
        result = call("setSsid", ssid_hex=raw.hex())
        assert result == {"ok": True, "configured_visible": False, "ssid_hex": raw.hex()}, result
        assert config_value("default_radio0.ssid") == raw
        assert config_value("guest.ssid") == b"Guest"
        assert config_value("default_radio0.encryption") == b"psk2"
        saved = config.stat()
        assert call("setSsid", ssid_hex=raw.hex()) == result
        assert config.stat().st_mtime_ns == saved.st_mtime_ns
    before = config.read_bytes()
    for bad in ("", "a", "zz", "00", "0a", "7f", "61" * 33):
        assert call("setSsid", ssid_hex=bad)["error"] == "invalid_ssid"
    with provider.open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert call("setSsid", ssid_hex="61")["error"] == "busy"
    subprocess.run([root / "uci", "set", "wireless.guest.ssid=Pending"], env=env, check=True)
    assert call("setSsid", ssid_hex="61")["error"] == "pending_wireless_changes"
    assert config_value("guest.ssid") == b"Pending" and config.read_bytes() == before
    acl = json.loads((RUNTIME / "veci2-status-acl.json").read_text())["veci-v2-wifi"]
    assert "setSsid" in acl["write"]["ubus"]["veci.v2.wifi"]
    assert "setSsid" not in acl["read"]["ubus"]["veci.v2.wifi"]
    print("PASS: native UCI, exact SSID bytes including UTF-8, limits, punctuation, "
          "idempotence, guest, encryption, hidden flag, lock, pending changes and RPC ACL")
