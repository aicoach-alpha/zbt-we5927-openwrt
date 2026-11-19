"""Exercise board panel RPC with BusyBox ash, native jshn and sysfs fixtures."""
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
    leds, keys, buttons = (root / name for name in ("leds", "keys", "buttons"))
    for directory in (leds, keys, buttons):
        directory.mkdir()
    board = root / "board"
    board.write_text("zbtlink,zbt-we5927\n")
    (keys / "reset").mkdir()
    (keys / "reset/label").write_bytes(b"reset\x00")
    (buttons / "reset").write_text("#!/bin/sh\nexit 1\n")
    (buttons / "reset").chmod(0o755)
    for name, trigger in (("green:lan-1", "[none] timer"), ("green:wan", "none [netdev]"),
                          ("green:wlan", "[none] phy0tpt")):
        lamp = leds / name
        lamp.mkdir()
        (lamp / "trigger").write_text(trigger + "\n")
        (lamp / "brightness").write_text("0\n")
        (lamp / "max_brightness").write_text("255\n")
    provider = root / "provider"
    source = (pkg / "veci2-leds").read_text().replace("/tmp/sysinfo/board_name", str(board))
    for path, dest in (("/sys/class/leds", leds), ("/sys/firmware/devicetree/base/keys", keys),
                       ("/etc/rc.button", buttons), ("/usr/share/libubox/jshn.sh", prefix / "share/libubox/jshn.sh")):
        source = source.replace(path, str(dest))
    # Inspect the pulse while active. Simulate a concurrent kernel trigger takeover on demand.
    lamp = leds / "green:lan-1"
    source = source.replace("  sleep 1", f'''  cat "{lamp}/brightness" > "{root}/observed"
  if [ -f "{root}/takeover" ]; then echo 'none [netdev]' > "{lamp}/trigger"; fi''')
    provider.write_text(source)
    def call(method, **args):
        env = dict(os.environ, PATH=f"{prefix}/bin:" + os.environ["PATH"], LD_LIBRARY_PATH=str(prefix / "lib"))
        return json.loads(subprocess.check_output(["busybox", "ash", provider, "call", method],
                          input=json.dumps(args), text=True, env=env, timeout=5))
    status = call("status")
    assert status["buttons"] == [{"name": "reset", "handler": True}]
    assert {v["name"] for v in status["leds"] if v["identify"]} == {"green:lan-1"}
    for value in ("green:wlan", "green:wan", "../reset", "sim_select"):
        assert call("identify", name=value)["error"] == "led_unavailable"
    assert call("identify", name="green:lan-1")["ok"]
    assert (root / "observed").read_text().strip() == "255"
    assert (lamp / "brightness").read_text().strip() == "0"
    (root / "takeover").touch()
    assert call("identify", name="green:lan-1")["ok"]
    assert (lamp / "brightness").read_text().strip() == "255"
    assert (lamp / "trigger").read_text().strip() == "none [netdev]"
    board.write_text("other\n")
    assert call("status")["error"] == "unsupported_board"
    print("PASS board panel inventory, DT reset handler, LED eligibility, protected lamps, "
          "pulse and restoration, trigger takeover, wrong board")
