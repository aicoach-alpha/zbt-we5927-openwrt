"""Run the cron provider with native jshn, BusyBox ash and a temporary spool."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

runtime = Path(__file__).resolve().parents[2] / "rebuild/veci-v2/packages/veci-v2-runtime"
prefix = Path(sys.argv[1]).resolve(strict=True)
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    tab, board, provider = (root / name for name in ("root", "board", "provider"))
    board.write_text("zbtlink,zbt-we5927\n")
    source = (runtime / "veci2-cron").read_text()
    for old, new in {"/usr/bin/crontab":root / "crontab", "/etc/crontabs/root":tab, "/tmp/sysinfo/board_name":board,
            "/usr/libexec/veci2-cron.awk":runtime / "veci2-cron.awk",
            "/usr/share/libubox/jshn.sh":prefix / "share/libubox/jshn.sh"}.items():
        source = source.replace(old, str(new))
    provider.write_text(source)
    install = root / "crontab"
    install.write_text('#!/bin/sh\ncp "$1" "$SPOOL"\n')
    install.chmod(0o700)
    env = dict(os.environ, PATH=f"{root}:{prefix}/bin:" + os.environ["PATH"],
               LD_LIBRARY_PATH=str(prefix / "lib"), SPOOL=str(tab))
    def call(method, **args):
        output = subprocess.check_output(["busybox", "ash", provider, "call", method], text=True,
                                         env=env, input=json.dumps(args), timeout=4)
        return json.loads(output)
    assert call("status")["jobs"] == []
    before = "# OEM\nHOME=/root\n*/5 * * * * /usr/sbin/anywifi private  2>/dev/null\n@reboot special\n"
    tab.write_text(before)
    state = call("status")
    assert state["jobs"] == [dict(row="3", enabled=True, schedule="*/5 * * * *", label="anywifi")], state
    args = dict(row="3", enabled="0", schedule="10 6 * * 1-5", revision=state["revision"])
    for patch in [dict(schedule="60 * * * *"),dict(schedule="*/0 * * * *"),dict(schedule="* * * * *\ntrue"),
                  dict(row="2"),dict(row="4"),dict(enabled="yes"),dict(revision="bad")]:
        assert not call("save", **(args | patch))["ok"] and tab.read_text() == before
    with provider.open() as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        assert call("save", **args)["error"] == "busy"
    paused = call("save", **args)
    assert not paused["jobs"][0]["enabled"]
    assert tab.read_text() == before.replace("*/5 * * * *", "# VeCI paused: 10 6 * * 1-5")
    assert call("save", **args)["error"] == "stale_configuration"
    assert call("save", **dict(args, revision=paused["revision"], enabled="1", schedule="*/5 * * * *"))["ok"]
    assert tab.read_text() == before
    install.write_text("#!/bin/sh\nexit 1\n")
    assert call("save", **args)["error"] == "install_failed" and tab.read_text() == before
    tab.write_text(before.rstrip("\n"))
    assert call("save", **dict(args, revision=call("status")["revision"]))["error"] == "unsupported_layout"
    board.write_text("other\n")
    assert call("status")["error"] == "unsupported_board"
    print("PASS cron inventory, edit, pause/resume, command/other record preservation, invalid schedule, stale revision, lock, install failure and board guard")
