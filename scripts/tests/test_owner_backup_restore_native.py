"""Execute VeCI backup restore preflight and CGI against disposable fake services.

Never invokes real sysupgrade -r: the fake records would-be restores only.
"""
import hashlib,io,json,os,subprocess,tarfile,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
UI=ROOT/"rebuild/veci-v2/packages/veci-v2-ui"
RUNTIME=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime"
CHECK=RUNTIME/"veci2-restore-check"
CGI=UI/"files/www/cgi-bin/veci2-restore"

LTE=b"""config modem 'main'
 option usb_vid '05c6'
 option usb_pid '902e'
 option sim_gpio '46'
 option sim1_value '1'
 option sim2_value '0'
"""
NETWORK=b"config interface 'lan'\n option ipaddr '192.168.1.1'\n"


class RestoreSourceAcceptance(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix="veci-restore-native-")
        self.addCleanup(temp.cleanup)
        t=Path(temp.name)
        self.t=t
        self.board=t/"board";self.board.write_text("zbtlink,zbt-we5927\n")
        self.receipt=t/"receipt"
        self.restored=t/"restored.log"
        self.authfile=t/"permit";self.authfile.write_text("true\n")
        stub=t/"ubus"
        stub.write_text("""#!/bin/sh
[ "$*" != "" ] || exit 9
printf '{"access":%s}\\n' "$(cat "$TEST_AUTH")"
""")
        stub.chmod(0o755)
        filt=t/"jsonfilter"
        filt.write_text("""#!/usr/bin/env python3
import json,sys
obj=json.load(sys.stdin)
print('true' if obj.get('access') is True else 'false')
""")
        filt.chmod(0o755)
        sysupgrade=t/"sysupgrade"
        sysupgrade.write_text("""#!/bin/sh
case "$1" in
  -b) : > "$2"; printf 'placeholder' > "$2" ;;
  -r) printf '%s\\n' "$2" >> "$TEST_RESTORES"; exit 0 ;;
  *) exit 1 ;;
esac
""")
        sysupgrade.chmod(0o755)
        self.check=t/"check"
        self.check.write_text(CHECK.read_text())
        self.check.chmod(0o755)
        self.cgi=t/"cgi"
        self.cgi.write_text(CGI.read_text()
             .replace("/usr/libexec/veci2-restore-check",str(self.check))
             .replace("/tmp/sysinfo/board_name",str(self.board))
             .replace("/var/run/veci2-restore.receipt",str(self.receipt))
             .replace("/var/run/veci2-restore.action.lock",str(t/"restore.lock")))
        self.cgi.chmod(0o755)
        self.env={**os.environ,"PATH":str(t)+":"+os.environ.get("PATH",""),
            "TEST_AUTH":str(self.authfile),"TEST_RESTORES":str(self.restored)}
        self.session="a"*32
    @staticmethod
    def pack(members):
        buf=io.BytesIO()
        with tarfile.open(fileobj=buf,mode="w:gz") as tf:
            for name,value in members:
                if isinstance(value,tuple):
                    link=tarfile.TarInfo(name)
                    link.type=tarfile.SYMTYPE
                    link.linkname=value[1]
                    tf.addfile(link)
                else:
                    info=tarfile.TarInfo(name);info.size=len(value);info.mode=0o600
                    tf.addfile(info,io.BytesIO(value))
        return buf.getvalue()
    def valid(self):
        return self.pack([("etc/config/we5927_lte",LTE),
                          ("etc/config/network",NETWORK)])
    def validate(self,archive):
        location=self.t/"archive.tgz";location.write_bytes(archive)
        return subprocess.run(["busybox","ash",str(self.check),str(location)],
            env=self.env,capture_output=True,text=True,timeout=10)
    def cgi_call(self,phase,archive,token="",session=None,https="on"):
        session=session or self.session
        digest=hashlib.sha256(archive).hexdigest()
        body=(session+digest+token).encode()+archive
        env={**self.env,"HTTPS":https,"REQUEST_METHOD":"POST",
            "CONTENT_TYPE":"application/octet-stream",
            "CONTENT_LENGTH":str(len(body)),"QUERY_STRING":phase}
        p=subprocess.run(["busybox","ash",str(self.cgi)],env=env,input=body,
                         capture_output=True,timeout=22)
        self.assertEqual(p.returncode,0,p.stderr.decode(errors="replace"))
        if p.stdout.startswith(b"Status: 400"):
            trace=subprocess.run(["busybox","ash","-x",str(self.cgi)],env=env,input=body,
                       capture_output=True,timeout=16)
            _ = trace.stderr
        head,data=p.stdout.split(b"\r\n\r\n",1)
        return head.decode(),json.loads(data)
    def test_exact_board_ordinary_archive_passes_without_writing_router(self):
        archive=self.valid()
        result=self.validate(archive)
        if result.returncode:
            detail=subprocess.run(["busybox","ash","-x",str(self.check),str(self.t/"archive.tgz")],
                capture_output=True,text=True,env=self.env,timeout=9)
            _ = detail.stderr
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("VALIDATED_EXACT_BOARD_CONFIG_BACKUP",result.stdout)
        self.assertFalse(self.restored.exists())
    def test_rejects_wrong_board_traversal_symlinks_and_unknown_entries(self):
        candidates=[
           self.pack([("etc/config/we5927_lte",LTE.replace(b"05c6",b"1234")),("etc/config/network",NETWORK)]),
           self.pack([("etc/config/we5927_lte",LTE),("../etc/passwd",b"bad")]),
           self.pack([("etc/config/we5927_lte",LTE),("/etc/config/network",NETWORK)]),
           self.pack([("etc/config/we5927_lte",LTE),("etc/config/network",("link","../../etc/shadow"))]),
           self.pack([("etc/config/we5927_lte",LTE),("root/.ssh/id_rsa",b"KEY")]),
           self.pack([("etc/config/network",NETWORK)]),
        ]
        for i,archive in enumerate(candidates):
            with self.subTest(case=i):
                self.assertNotEqual(self.validate(archive).returncode,0)
        self.assertFalse(self.restored.exists())
    def test_https_admin_digest_and_two_phase_receipt(self):
        archive=self.valid()
        head,response=self.cgi_call("inspect",archive)
        if not response["ok"]:
            _ = (head,response,len(archive))
        self.assertTrue(response["ok"],response)
        ticket=response["ticket"]
        self.assertEqual(len(ticket),64)
        self.assertFalse(self.restored.exists())
        _,denied=self.cgi_call("apply",archive,"b"*64)
        self.assertEqual(denied["error"],"inspection_expired_or_replaced")
        _,bad_https=self.cgi_call("inspect",archive,https="off")
        self.assertEqual(bad_https["error"],"access_denied")
        self.authfile.write_text("false\n")
        _,denied=self.cgi_call("apply",archive,ticket)
        self.assertEqual(denied["error"],"access_denied")
        self.authfile.write_text("true\n")
        _,other_session=self.cgi_call("apply",archive,ticket,session="b"*32)
        self.assertEqual(other_session["error"],"inspection_not_bound_to_session")
        _,success=self.cgi_call("apply",archive,ticket)
        self.assertTrue(success["ok"],success)
        self.assertTrue(success["reboot_required"])
        self.assertEqual(len(self.restored.read_text().splitlines()),1)
        _,repeat=self.cgi_call("apply",archive,ticket)
        self.assertEqual(repeat["error"],"inspection_required")
    def test_ui_acl_install_and_shell_syntax(self):
        runtime=(RUNTIME/"Makefile").read_text()
        web=(UI/"Makefile").read_text()
        self.assertIn("veci2-restore-check",runtime)
        self.assertIn("veci2-restore",web)
        acl=json.loads((RUNTIME/"veci2-status-acl.json").read_text())
        self.assertEqual(set(acl["veci-v2-backup"]["write"]["ubus"]["veci.v2.backup"]),
             {"export","inspect","restore"})
        js=(UI/"files/www/veci2/backup.js").read_text()
        self.assertIn("backup-restore-apply",js)
        self.assertIn("window.confirm",js)
        self.assertIn("crypto.subtle.digest",js)
        html=(UI/"files/www/veci2/index.html").read_text()
        self.assertIn('id="backup-restore-file"',html)
        for path in (CGI,CHECK):
            subprocess.run(["busybox","ash","-n",str(path)],check=True,capture_output=True)
        subprocess.run(["node","--check",str(UI/"files/www/veci2/backup.js")],check=True,capture_output=True)

if __name__=="__main__":unittest.main()
