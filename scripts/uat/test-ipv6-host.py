"""Exercise shipped first boot, boot sysctls and settings RPC against native UCI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

base = Path(__file__).resolve().parents[2] / "rebuild/veci-v2/packages/veci-v2-ipv6/files"
binary = Path(sys.argv[1]).resolve(strict=True)
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    cfg = root / "config"
    cfg.mkdir()
    (root / "delta").mkdir()
    (root / "board").write_text("zbtlink,zbt-we5927\n")
    shutil.copy(base / "etc/config/veci2_ipv6", cfg)
    (cfg / "network").write_text("config interface 'lan'\n option ipaddr '192.168.1.1'\n"
                                 "config interface 'wan'\nconfig interface 'wan6'\nconfig interface 'lte'\n")
    (cfg / "dhcp").write_text("config dhcp 'lan'\n option start '100'\n option interface 'lan'\n")
    for name in ["default", "all"]:
        path = root / name / "disable_ipv6"
        path.parent.mkdir()
        path.write_text("0\n")
    commands = {
        "uci": f'#!/bin/sh\ncase " $* " in *" $FAIL_OP "*) [ -z "$FAIL_OP" ] || exit 1;; esac\nexec "{binary}" -c "{cfg}" -t "{root}/delta" "$@"\n',
        "jsonfilter": '#!/usr/bin/env python3\nimport json,sys\nv=json.loads(sys.argv[2])[sys.argv[4][2:]]\nprint(str(v).lower() if isinstance(v,bool) else v)\n',
        "id": "#!/bin/sh\necho 0\n", "logger": "#!/bin/sh\nexit 0\n",
    }
    for name, body in commands.items():
        p = root / name
        p.write_text(body)
        p.chmod(0o700)
    env = dict(os.environ, PATH=f"{root}:" + os.environ["PATH"], FAIL_OP="")
    def run(args, **opts):
        return subprocess.run(args, env=env, capture_output=True, text=True, **opts)
    def value(key):
        return run(["uci", "get", key], check=True).stdout.strip()
    def script(rel):
        return (base / rel).read_text().replace("/tmp/sysinfo/board_name", str(root / "board")).replace(
            "/etc/config/", str(cfg) + "/").replace("/proc/sys/net/ipv6/conf/", str(root) + "/").replace(
            "/var/lock/veci2-ipv6.lock", str(root / "lock"))
    init = script("etc/uci-defaults/90-veci2-ipv6-initial")
    boot = script("etc/init.d/veci2-ipv6") + "\nstart"
    rpc = script("usr/libexec/rpcd/veci2-ipv6")
    def save(on, confirm):
        return json.loads(run(["sh", "-c", rpc, "rpc", "call", "save"], check=True,
                              input=json.dumps(dict(enabled=on, confirm=confirm))).stdout)
    env["FAIL_OP"] = "set network.wan6.disabled=1"
    assert run(["sh", "-c", init]).returncode != 0
    assert value("veci2_ipv6.main.initialized") == "0"
    env["FAIL_OP"] = ""
    run(["sh", "-c", init], check=True)
    assert value("network.wan6.disabled") == "1" and value("dhcp.lan.ra") == "disabled"
    assert value("network.lte.ipv6") == "0" and value("veci2_ipv6.main.initialized") == "1"
    run(["sh", "-c", boot], check=True)
    assert all((root / n / "disable_ipv6").read_text().strip() == "1" for n in ("all", "default"))
    assert save(True, "invalid")["error"] == "explicit_confirmation_required"
    run(["uci", "set", "network.lan.ipaddr=192.168.9.1"], check=True)
    assert save(True, "IPV6_ENABLE")["error"] == "pending_configuration_changes"
    assert value("network.lan.ipaddr") == "192.168.9.1"
    run(["uci", "revert", "network"], check=True)
    before = {p: p.read_bytes() for p in cfg.iterdir()}
    env["FAIL_OP"] = "commit dhcp"
    assert save(True, "IPV6_ENABLE")["error"] == "commit_failed"
    assert all(p.read_bytes() == content for p, content in before.items())
    env["FAIL_OP"] = ""
    assert save(True, "IPV6_ENABLE")["saved"] and value("dhcp.lan.dhcpv6") == "server"
    assert value("network.lan.ipaddr") == "192.168.1.1" and value("dhcp.lan.start") == "100"
    assert (root / "all/disable_ipv6").read_text().strip() == "1"
    run(["sh", "-c", init], check=True)
    assert value("veci2_ipv6.main.enabled") == "1"
    run(["sh", "-c", boot], check=True)
    assert (root / "all/disable_ipv6").read_text().strip() == "0"
    assert save(False, "IPV6_DISABLE")["saved"] and value("network.wan6.disabled") == "1"
    ra = script("usr/libexec/rpcd/veci2-ra")
    def profile(method, **params):
        return json.loads(run(["busybox", "ash", "-c", ra, "ra", "call", method], check=True,
                              input=json.dumps(params)).stdout)
    assert profile("status")["enabled"] == 0
    assert profile("save")["error"] == "ipv6_disabled"
    assert save(True, "IPV6_ENABLE")["saved"]
    for target in ("slaac", "mixed", "disabled", "slaac"):
        revision = profile("status")["revision"]
        args = dict(profile=target, revision=revision, confirm="SAVE_RA")
        assert profile("save", **(args | dict(revision="stale")))["error"] == "stale_configuration"
        assert profile("save", **(args | dict(confirm="")))["error"] == "confirmation_required"
        assert profile("save", **(args | dict(profile="relay")))["error"] == "invalid_profile"
        assert profile("save", **args)["profile"] == target
        assert value("dhcp.lan.dhcpv6") == ("server" if target == "mixed" else "disabled")
    assert save(False, "IPV6_DISABLE")["saved"] and value("dhcp.lan.ra") == "disabled"
    assert save(True, "IPV6_ENABLE")["saved"] and value("dhcp.lan.ra") == "server"
    assert value("dhcp.lan.dhcpv6") == "disabled" and profile("status")["profile"] == "slaac"
    assert value("dhcp.lan.start") == "100" and value("network.lan.ipaddr") == "192.168.1.1"
    print("PASS RA/DHCPv6 profiles, master-off refusal, stale revision, invalid relay, explicit confirmation, profile roundtrip across master off/on")
    print("PASS native UCI: initialization, retry, boot, confirmation, pending edits, rollback, enable/disable, IPv4 preservation")
