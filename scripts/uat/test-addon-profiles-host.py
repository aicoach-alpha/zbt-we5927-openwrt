"""Run profile discovery and guarded WireGuard startup writes with native UCI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

pkg = Path(__file__).resolve().parents[2] / "rebuild/veci-v2/packages/veci-v2-runtime"
binary, prefix = (Path(arg).resolve(strict=True) for arg in sys.argv[1:])
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    cfg, delta = root/"config", root/"delta"
    cfg.mkdir()
    delta.mkdir()
    (root/"board").write_text("zbtlink,zbt-we5927\n")
    for name, script in {
        "uci": f'exec "{binary}" -c "{cfg}" -t "{delta}" "$@"',
        "wg": 'test "$1" = pubkey && read -r key && test "$key" = fixture-private'
    }.items():
        path = root/name
        path.write_text("#!/bin/sh\n" + script)
        path.chmod(0o700)
    for name, source in [("provider","veci2-services"), ("helper","veci2-addon-profiles")]:
        data = (pkg/source).read_text()
        for orig, new in {"/tmp/sysinfo/board_name": root/"board",
                          "/usr/libexec/veci2-addon-profiles":root/"helper",
                          "/usr/share/libubox/jshn.sh":prefix/"share/libubox/jshn.sh",
                          "/usr/share/veci/apps-installed":root,
                          "/usr/libexec/rpcd":root,
                          "/var/lock/veci2-ipv6.lock":root/"lock"}.items():
            data = data.replace(orig,str(new))
        (root/name).write_text(data)
    env = dict(os.environ, PATH=f"{root}:{prefix}/bin:" + os.environ["PATH"], LD_LIBRARY_PATH=str(prefix/"lib"))
    def call(method, **kwargs):
        res = subprocess.check_output(["busybox","ash",root/"provider","call",method],input=json.dumps(kwargs),
                                      text=True,env=env,timeout=5)
        assert "fixture-private" not in res
        return json.loads(res)
    def write(expected, action):
        return call("setVpnStartup",expected=expected,action=action)
    assert call("addonProfiles") == dict(ok=True, wireguard="absent",guest="absent",voucher="absent")
    for name in ("wireguard","guest","voucher"):
        (root/name).touch()
        stub = root/("veci.app."+name)
        stub.touch()
        stub.chmod(0o700)
    assert call("addonProfiles")["wireguard"] == "unconfigured"
    network = cfg/"network"
    network.write_text("config interface 'veci_wg'\n option proto 'wireguard'\n option auto '0'\n"
                       " list addresses '10.0.0.1/24'\n option private_key 'fixture-private'\n"
                       "config interface 'lan'\n option ipaddr '192.168.1.1'\n")
    firewall = cfg/"firewall"
    firewall.write_text("config defaults\n option input 'REJECT'\n")
    for config, section_type, options in [("uspot","uspot","option auth_mode 'credentials'"),
                                          ("wireless","wifi-iface","option disabled '0'"),
                                          ("uhttpd","uhttpd","option enabled '1'")]:
        (cfg/config).write_text(f"config {section_type} 'veci_guest'\n {options}\n")
    assert call("addonProfiles") == dict(ok=True,wireguard="disabled",guest="enabled",voucher="enabled")
    assert write("disabled","unknown")["error"] == "confirmation_required"
    assert write("enabled","DISABLE_WIREGUARD_NEXT_BOOT")["error"] == "stale_selection"
    assert write("disabled","ENABLE_WIREGUARD_NEXT_BOOT")["wireguard"] == "enabled"
    assert write("enabled","DISABLE_WIREGUARD_NEXT_BOOT")["wireguard"] == "disabled"
    assert "192.168.1.1" in network.read_text() and "fixture-private" in network.read_text()
    assert firewall.read_text() == "config defaults\n option input 'REJECT'\n"
    subprocess.run([root/"uci","set","network.lan.ipaddr=192.168.2.1"],env=env,check=True)
    assert write("disabled","ENABLE_WIREGUARD_NEXT_BOOT")["error"] == "pending_changes"
    print("PASS missing/provisioned add-ons, Guest/Voucher eligibility, WG next-boot switch, stale and pending rejection, protected key and firewall preservation")
