"""Optional profile config-only lifecycle with native UCI and libubox; no services run."""
import os,json,subprocess,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[2]/"rebuild/veci-v2/packages/veci-v2-runtime"
UCI=os.environ.get("VECI_HOST_UCI","")
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
@unittest.skipUnless(Path(UCI).is_file() and Path(PREFIX,"bin/jshn").is_file(),"native tools required")
class OptionalNative(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.d=Path(t.name)
  d=self.d
  for name in ("config","delta","init","installed","rpcd","net"):(d/name).mkdir()
  (d/"board").write_text("zbtlink,zbt-we5927\n")
  (d/"net/usb0").mkdir()
  (d/"config/sqm").write_text("config queue 'other'\n option enabled '0'\n")
  (d/"config/firewall").write_text("config defaults\n option flow_offloading '0'\n option flow_offloading_hw '0'\n")
  (d/"config/ddns").write_text("config service 'veci'\n option enabled '1'\n")
  for n in ("sqm","ddns"):
   (d/"installed"/n).touch()
   self.cmd("rpcd/veci.app."+n,"#!/bin/sh\nexit 99\n")
   self.cmd("init/"+n,"#!/bin/sh\n[ \"$1\" = enabled ]\n")
  self.cmd("rpcd/veci.v2.firewall","#!/bin/sh\nexit 99\n")
  self.cmd("uci",f'#!/bin/sh\nexec "{UCI}" -c "{d}/config" -t "{d}/delta" "$@"\n')
  s=(R/"veci2-addon-profiles").read_text()
  for a,b in (("/usr/share/veci/apps-installed/","installed/"),("/usr/libexec/rpcd/","rpcd/"),("/etc/init.d/","init/"),("/etc/config/","config/"),("/sys/class/net/","net/"),("/var/lock/veci2-optional-services.lock","lock"),("/var/run/veci2-reboot-requested","pending")):s=s.replace(a,str(d)+"/"+b)
  (d/"profiles").write_text(s)
  s=(R/"veci2-addon").read_text().replace("/tmp/sysinfo/board_name",str(d/"board")).replace("/usr/libexec/veci2-addon-profiles",str(d/"profiles")).replace("/usr/share/libubox/jshn.sh",str(Path(PREFIX,"share/libubox/jshn.sh")))
  (d/"provider").write_text(s)
  self.env=dict(os.environ,PATH=str(d)+":"+str(Path(PREFIX,"bin"))+":"+os.environ["PATH"],LD_LIBRARY_PATH=str(Path(PREFIX,"lib")))
 def cmd(self,n,s):
  p=self.d/n;p.write_text(s);p.chmod(0o700)
 def call(self,method,**kw):
  r=subprocess.run(["busybox","ash",str(self.d/"provider"),"call",method],input=json.dumps(kw),env=self.env,text=True,capture_output=True,timeout=8)
  self.assertEqual(r.returncode,0,r.stderr);return json.loads(r.stdout)
 def test_sqm_save_toggle_rollback_and_ddns_disable(self):
  cfg=self.d/"config/sqm";before=cfg.read_bytes()
  a=dict(revision=self.call("sqmStatus")["revision"],confirmation="SAVE_SQM_NEXT_BOOT",interface="usb0",download="10000",upload="2000",qdisc="cake",script="piece_of_cake.qos")
  self.assertFalse(self.call("saveSqm",**(a|dict(download="0")))["ok"])
  (self.d/"pending").touch();self.assertEqual(self.call("saveSqm",**a)["error"],"reboot_pending");(self.d/"pending").unlink()
  u=self.d/"uci";orig=u.read_text();u.write_text(orig.replace('exec "', '"',1)+'rc=$?\ncase "$*" in *"commit sqm") exit 1;; esac\nexit "$rc"\n')
  self.assertEqual(self.call("saveSqm",**a)["error"],"commit_failed_rollback");self.assertEqual(cfg.read_bytes(),before)
  u.write_text(orig);result=self.call("saveSqm",**a);self.assertEqual(result["state"],"disabled");self.assertEqual(result["download"],"10000")
  toggle=dict(service="sqm",enabled="1",revision=result["revision"],confirmation="ENABLE_SQM_NEXT_BOOT")
  self.assertEqual(self.call("setOptionalStartup",**toggle)["state"],"enabled")
  self.assertEqual(self.call("setOptionalStartup",**toggle)["error"],"stale_configuration")
  toggle.update(enabled="0",revision=self.call("sqmStatus")["revision"],confirmation="DISABLE_SQM_NEXT_BOOT")
  self.assertEqual(self.call("setOptionalStartup",**toggle)["state"],"disabled")
  ddns=dict(service="ddns",enabled="0",revision=self.call("ddnsStatus")["revision"],confirmation="DISABLE_DDNS_NEXT_BOOT")
  self.assertEqual(self.call("setOptionalStartup",**ddns)["state"],"disabled")
  self.assertEqual(self.call("ddnsStatus")["runtime"],"unknown")
