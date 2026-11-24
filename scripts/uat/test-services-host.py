"""Run the installed provider with BusyBox ash and native OpenWrt jshn."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

pkg = Path(__file__).resolve().parents[2] / "rebuild/veci-v2/packages/veci-v2-runtime"
prefix = Path(sys.argv[1]).resolve(strict=True)
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    init = root / "init.d"
    rc = root / "rc.d"
    init.mkdir()
    rc.mkdir()
    board = root / "board"
    board.write_text("zbtlink,zbt-we5927\n")
    provider = root / "provider"
    provider.write_text((pkg / "veci2-services").read_text()
                        .replace("/etc/init.d", str(init)).replace("/etc/rc.d", str(rc))
                        .replace("/tmp/sysinfo/board_name", str(board))
                        .replace("/usr/share/libubox/jshn.sh", str(prefix / "share/libubox/jshn.sh")))
    env = dict(os.environ, PATH=f"{prefix}/bin:" + os.environ["PATH"],
               LD_LIBRARY_PATH=str(prefix / "lib"))
    for name in ("cron", "sysntpd", "we5927-lte", "network"):
        script = init / name
        script.write_text('#!/bin/sh\ncase "$1" in\n'
                          f'enable) ln -s ../init.d/{name} "{rc}/S50{name}" ;;\n'
                          f'disable) rm "{rc}/S50{name}" ;;\n'
                          '*) exit 1 ;;\nesac\n')
        script.chmod(0o755)

    def call(method, **args):
        result = subprocess.run(["busybox", "ash", provider, "call", method],
                                input=json.dumps(args), capture_output=True,
                                text=True, check=True, timeout=4, env=env)
        return json.loads(result.stdout)

    def select(name, expected, enabled):
        return call("save", name=name, expected=expected, enabled=enabled)

    def state(data):
        return {s["name"]: (s["enabled"], s["mutable"]) for s in data["services"]}

    assert state(call("status")) == {"cron": (False, True), "sysntpd": (False, True),
                                     "we5927-lte": (False, False), "network": (False, False)}
    assert state(select("cron", "0", "1"))["cron"] == (True, True)
    assert select("cron", "0", "1")["error"] == "stale_selection"
    assert state(select("cron", "1", "1"))["cron"] == (True, True)
    assert state(select("cron", "1", "0"))["cron"] == (False, True)
    for name in ("network", "we5927-lte", "../cron", ""):
        assert select(name, "0", "1")["error"] == "protected_service"
    assert select("cron", "true", "1")["error"] == "invalid_mode"
    with provider.open() as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        assert select("sysntpd", "0", "1")["error"] == "busy"
    (init / "sysntpd").write_text("#!/bin/sh\nexit 0\n")
    assert select("sysntpd", "0", "1")["error"] == "change_failed"
    (init / "sysntpd").unlink()
    (init / "sysntpd").symlink_to(init / "network")
    assert select("sysntpd", "0", "1")["error"] == "init_unavailable"
    board.write_text("other\n")
    assert call("status")["error"] == "unsupported_board"
    acl = json.loads((pkg / "veci2-services-acl.json").read_text())["veci-v2-services"]
    assert acl["read"]["ubus"]["veci.v2.services"] == ["status"]
    assert acl["write"]["ubus"]["veci.v2.services"] == ["save"]
    print("PASS startup inventory, enable/disable, idempotence, stale selection, lock, "
          "network/LTE protection, failed write, symlink rejection, exact board and ACL")
