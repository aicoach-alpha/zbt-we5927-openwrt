#!/usr/bin/env python3
"""Targeted mocked OpenWrt uhttpd transition test. No networking or router."""
from pathlib import Path
import subprocess
import tempfile
import time
import signal
import hashlib
import os

SOURCE=Path("scripts/veci-https-only-guarded-migration-20261015.sh").read_text()

def invoke(cmd, timeout=10):
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)

def setup(tmp, cert=True):
    p=Path(tmp)
    mock=p/"mock";mock.mkdir()
    cfg=p/"uhttpd";cfg.write_text("config uhttpd 'main'\n\tlist listen_http '0.0.0.0:80'\n")
    certfile=p/"uhttpd.crt";keyfile=p/"uhttpd.key"
    certfile.write_text("TEST-ONLY-CERT")
    keyfile.write_text("TEST-ONLY-KEY")
    if not cert:certfile.unlink()
    board=p/"board";board.write_text("zbtlink,zbt-we5927\n")
    release=p/"release";release.write_text("DISTRIB_RELEASE='25.12.5'\n")
    state=p/"state";state.write_text("http=1\nhttps=0\n")
    uci=mock/"uci"
    uci.write_text(f'''#!/bin/sh
state='{state}'
cfg='{cfg}'
cmd="$1"
if [ "$cmd" = -q ]; then shift; cmd="$1"; fi
case "$cmd" in
 get)
   case "$2" in
     uhttpd.main.listen_http) grep -q '^http=1$' "$state" && echo '0.0.0.0:80' ;;
     uhttpd.main.listen_https) grep -q '^https=1$' "$state" && echo '0.0.0.0:443' ;;
     uhttpd.main.cert) echo '{certfile}' ;;
     uhttpd.main.key) echo '{keyfile}' ;;
   esac ;;
 add_list)
   sed -i 's/^https=0$/https=1/' "$state"
   echo "list listen_https '0.0.0.0:443'" >> "$cfg" ;;
 delete)
   sed -i 's/^http=1$/http=0/' "$state"
   sed -i '/list listen_http /d' "$cfg" ;;
 commit|revert) : ;;
 *) exit 1 ;;
esac
''')
    uci.chmod(0o755)
    restart=mock/"uhttpd-restart"; restart.write_text("#!/bin/sh\nexit 0\n"); restart.chmod(0o755)
    dest=p/"migration.sh"
    s=SOURCE
    for a,b in [
      ("/root/veci-https-recovery-20261015",str(p/"backup")),
      ("UHTTPD=/etc/config/uhttpd",f"UHTTPD={cfg}"),
      ("/tmp/veci-https-migration.lock",str(p/"lock")),
      ("/tmp/sysinfo/board_name",str(board)),
      ("/etc/openwrt_release",str(release)),
      ("/etc/init.d/uhttpd",str(restart)),
      ("PATH=/usr/sbin:/usr/bin:/sbin:/bin",f"PATH={mock}:/usr/sbin:/usr/bin:/sbin:/bin"),
      ("WATCH_SECONDS=180","WATCH_SECONDS=2"),
    ]:
      assert a in s,a
      s=s.replace(a,b)
    dest.write_text(s)
    dest.chmod(0o700)
    assert invoke(["sh","-n",str(dest)]).returncode==0
    return dest,cfg,p/"backup"

def test():
  assert os.geteuid()==0,"Run focused test with sudo"
  # Preparation keeps plain HTTP, and a switch left unconfirmed is restored.
  with tempfile.TemporaryDirectory(prefix="veci-https-test-") as tmp:
    script,cfg,backup=setup(tmp)
    orig=cfg.read_bytes()
    r=invoke(["sh",str(script),"--prepare"])
    assert r.returncode==0,(r.stdout,r.stderr)
    assert "VECI_HTTPS_PREPARE=pass" in r.stdout
    assert "listen_http '" in cfg.read_text()
    assert "listen_https '" in cfg.read_text()
    assert (backup/"original-uhttpd").read_bytes()==orig
    r=invoke(["sh",str(script),"--switch"])
    assert r.returncode==0,(r.stdout,r.stderr)
    assert "VECI_HTTPS_SWITCH=pass" in r.stdout
    assert "listen_http '" not in cfg.read_text(),(r.stdout,r.stderr,cfg.read_text())
    # A detached BusyBox-compatible watchdog must ignore an SSH hangup
    # without relying on /usr/bin/nohup. Inject HUP and ensure rollback.
    watchdog=int((backup/"watchdog.pid").read_text().strip())
    os.kill(watchdog, signal.SIGHUP)
    time.sleep(4)
    assert cfg.read_bytes()==orig,("watchdog did not restore uhttpd",cfg.read_text())
    assert not (backup/"pending").exists()
    print("VECI_HTTPS_TEST=sighup_ignored_and_auto_rollback_pass")
  # Confirming a verified HTTPS path makes HTTPS-only persist, with manual
  # rollback retaining the original exact config.
  with tempfile.TemporaryDirectory(prefix="veci-https-test-") as tmp:
    script,cfg,backup=setup(tmp)
    orig=cfg.read_bytes()
    assert invoke(["sh",str(script),"--prepare"]).returncode==0
    assert invoke(["sh",str(script),"--switch"]).returncode==0
    r=invoke(["sh",str(script),"--confirm"])
    assert r.returncode==0,(r.stdout,r.stderr)
    time.sleep(3)
    assert "listen_http '" not in cfg.read_text()
    assert "listen_https '" in cfg.read_text()
    assert invoke(["sh",str(script),"--rollback"]).returncode==0
    assert cfg.read_bytes()==orig
    print("VECI_HTTPS_TEST=confirm_then_manual_rollback_pass")
  # Missing TLS material must not change uhttpd.
  with tempfile.TemporaryDirectory(prefix="veci-https-test-") as tmp:
    script,cfg,backup=setup(tmp,cert=False)
    orig=cfg.read_bytes()
    r=invoke(["sh",str(script),"--prepare"])
    assert r.returncode!=0
    assert "tls_certificate_or_key_missing" in r.stdout
    assert cfg.read_bytes()==orig
    assert not backup.exists()
    print("VECI_HTTPS_TEST=missing_certificate_fails_closed_pass")
  print("VECI_HTTPS_MIGRATION_FOCUSED=pass")

if __name__=="__main__":test()
