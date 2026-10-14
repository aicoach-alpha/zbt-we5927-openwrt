"""Real WE5927 regression: od applet absent; XL USSD generates safe session tokens.

This test never accesses an actual modem, carrier, SMS or external network.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/veci-xl-ussd-v17-staged/veci-xl-ussd"

class XLOdFreeSession(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        d=self.dir
        bindir=d/"bin"
        bindir.mkdir()
        for name in ("flock","sha256sum","head","awk","wc","date","cat","dirname",
                     "chmod","mv","rm","sed"):
            original=shutil.which(name)
            self.assertIsNotNone(original,name)
            (bindir/name).symlink_to(original)
        j=bindir/"jsonfilter"
        j.write_text("""#!/usr/bin/python3
import json,sys
try:
 a=sys.argv
 o=json.loads(a[a.index('-s')+1])
 key=a[a.index('-e')+1]
 val=o[key.replace('@.','')]
 print(str(val).lower() if isinstance(val,bool) else val)
except Exception:
 sys.exit(1)
""")
        j.chmod(0o700)
        native=d/"native"
        native.write_text("""#!/bin/sh
printf '{"ok":true,"source":"operator_ussd","mode":1,"dcs":15,"text_supported":true,"interactive":true,"text":"1. Cek kuota"}\n'
""")
        native.chmod(0o700)
        lte=d/"lte"
        lte.write_text("""#!/bin/sh
printf '{"operator":"XL XL","sim":1}\n'
""")
        lte.chmod(0o700)
        (d/"tty").write_text("mock")
        (d/"vendor").write_text("05c6")
        (d/"product").write_text("902e")
        src=SOURCE.read_text()
        self.assertNotRegex(src,r"\bod\b")
        self.assertIn("head -c 32 /dev/urandom | sha256sum",src)
        values=[
            ("BIN=/usr/libexec/veci-xl-ussd-once","BIN="+str(native)),
            ("LTE=/usr/sbin/we5927-lte","LTE="+str(lte)),
            ("STATE=/tmp/veci-xl-ussd.session","STATE="+str(d/"state")),
            ("LOCK=/var/lock/we5927-at.lock","LOCK="+str(d/"lock")),
            ('[ "$(id -u)" = 0 ]','[ 0 = 0 ]'),
            ('"$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"','"zbtlink,zbt-we5927"'),
            ("[ -c /dev/ttyUSB2 ]","[ -f "+str(d/"tty")+" ]"),
            ('port="$(readlink -f /sys/class/tty/ttyUSB2/device 2>/dev/null || :)"',
             'port="/sys/devices/1-1:1.4/ttyUSB2"'),
            ('"$(cat "$parent/idVendor" 2>/dev/null || :)"','"$(cat '+str(d/'vendor')+' 2>/dev/null || :)"'),
            ('"$(cat "$parent/idProduct" 2>/dev/null || :)"','"$(cat '+str(d/'product')+' 2>/dev/null || :)"'),
        ]
        for old,new in values:
            self.assertIn(old,src,old)
            src=src.replace(old,new)
        self.worker=d/"worker"
        self.worker.write_text(src)
        self.worker.chmod(0o700)
        self.env=os.environ.copy()
        self.env["PATH"]=str(bindir)
    def call(self,*args):
        return subprocess.run(["/bin/sh",str(self.worker),*args],
                              capture_output=True,text=True,env=self.env,timeout=4)
    def test_start_without_od_applet(self):
        cp=self.call("--start")
        self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
        data=json.loads(cp.stdout)
        self.assertTrue(data["ok"])
        self.assertTrue(data["interactive"])
        self.assertRegex(data["session"],r"^[0-9a-f]{24}$")
        self.assertNotIn("od",cp.stderr)
        self.assertTrue((self.dir/"state").exists())
        token=(self.dir/"state").read_text().split("|")[0]
        self.assertEqual(token,data["session"])
    def test_menu_reply_reuses_token_without_od(self):
        start=self.call("--start")
        self.assertEqual(start.returncode,0,start.stdout+start.stderr)
        token=json.loads(start.stdout)["session"]
        reply=self.call("--reply",token,"1")
        self.assertEqual(reply.returncode,0,reply.stdout+reply.stderr)
        self.assertEqual(json.loads(reply.stdout)["session"],token)
    def test_invalid_choice_does_not_call_native_modem(self):
        start=self.call("--start")
        self.assertEqual(start.returncode,0)
        token=json.loads(start.stdout)["session"]
        reply=self.call("--reply",token,"1;AT+CMGS")
        self.assertNotEqual(reply.returncode,0)
        self.assertEqual(json.loads(reply.stdout)["reason"],"invalid_choice")

if __name__=="__main__":
    unittest.main()
