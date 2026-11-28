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
    for old, new in {"/var/run/veci2-reboot-requested":root/"reboot-pending", "/usr/bin/crontab":root / "crontab", "/etc/crontabs/root":tab, "/tmp/sysinfo/board_name":board,
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
    tab.unlink()
    # No real crontab or daemon is modified. Inject the result of the install call.
    install.write_text('#!/bin/sh\nif [ "$1" = -r ]; then rm "$SPOOL"; else cp "$1" "$SPOOL"; fi\n')
    new = dict(revision="", task="uptime", enabled="1", schedule="*/10 * * * *")
    for patch in (dict(task=";reboot"),dict(schedule="0 24 * * *"),dict(enabled="true"),dict(revision="x")):
        assert not call("add", **(new | patch))["ok"] and not tab.exists()
    assert not call("add", **{k:v for k,v in new.items() if k!="revision"})["ok"]
    first = call("add", **new)
    assert first["ok"] and first["jobs"][0]["label"]=="uptime"
    assert tab.read_text()=="*/10 * * * * /bin/busybox uptime | /bin/busybox logger -t veci-cron-uptime\n"
    assert call("add", **new)["error"]=="stale_configuration"
    tab.write_text(before + tab.read_text())
    changed = call("add", **(new | dict(task="memory", enabled="0", revision=call("status")["revision"])))
    assert changed["jobs"][-1]==dict(row="6", enabled=False, schedule=new["schedule"], label="memory")
    snapshot = tab.read_bytes()
    for row in ("1","2","4","99","0","-1","3;reboot"):
        assert not call("remove", row=row, revision=changed["revision"])["ok"] and tab.read_bytes()==snapshot
    assert call("remove", row="6", revision="bad")["error"]=="stale_configuration"
    removed = call("remove", row="5", revision=changed["revision"])
    assert removed["ok"] and removed["jobs"][-1]["row"]=="5" and "uptime" not in tab.read_text()
    removed = call("remove", row="5", revision=removed["revision"])
    assert removed["ok"] and tab.read_text()==before
    # Fail immediately after installing new bytes. The provider must restore the
    # previous revision or the absent spool; a concurrent third revision survives.
    install.write_text('#!/bin/sh\nif [ "$1" = -r ]; then rm "$SPOOL"; else cp "$1" "$SPOOL"; fi\nexit 1\n')
    assert call("remove", row="3", revision=removed["revision"])["error"]=="install_failed" and tab.read_text()==before
    tab.unlink()
    assert call("add", **new)["error"]=="install_failed" and not tab.exists()
    install.write_text('#!/bin/sh\necho "# external writer" > "$SPOOL"\nexit 1\n')
    assert call("add", **new)["error"]=="concurrent_update" and tab.read_text()=="# external writer\n"
    tab.unlink()
    tab.symlink_to(board)
    assert call("add", **new)["error"]=="unsupported_layout" and board.read_text()=="zbtlink,zbt-we5927\n"
    tab.unlink()
    initial=call("rebootStatus")
    assert initial["enabled"]=="0"
    args=dict(enabled="0",hour="4",minute="15",weekdays="1,3,5",revision=initial["revision"],confirmation="DISABLE_SCHEDULED_REBOOT")
    install.write_text('#!/bin/sh\ncp "$1" "$SPOOL"\n')
    (root/"reboot-pending").touch()
    assert call("setReboot",**args)["error"]=="reboot_pending"
    (root/"reboot-pending").unlink()
    saved=call("setReboot",**args)
    assert saved["enabled"]=="0" and saved["hour"]=="4" and saved["minute"]=="15"
    assert tab.read_text().startswith("# VeCI paused:")
    assert call("setReboot",**args)["error"]=="stale_configuration"
    print("PASS add/remove lifecycle, private OEM records, unknown task, stale revision, busy, post-install rollback, absent spool rollback, concurrent writer and symlink protection")
    board.write_text("other\n")
    assert call("status")["error"] == "unsupported_board"
    print("PASS cron inventory, edit, pause/resume, command/other record preservation, invalid schedule, stale revision, lock, install failure and board guard")
