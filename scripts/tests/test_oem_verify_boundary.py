"""OEM verify-only wrapper and unverified catalog; no flash or restore execution."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[2]/"rebuild/oem-updated"
PREFIX=os.environ.get("VECI_LIBUBOX_PREFIX","")
class VerifyBoundary(unittest.TestCase):
 def test_wrapper_refuses_all_nonempty_queries(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);marker=d/"called";stub=d/"verify";stub.write_text('#!/bin/sh\nprintf "fixture verifier"\n');stub.chmod(0o700)
   p=d/"wrapper";p.write_text((BASE/"backend/verify-only.sh").read_text().replace("/usr/libexec/oem-updated/shared-verify",str(stub)))
   for query in ("apply","stable","stable-apply","other","%61pply"):
    r=subprocess.check_output(["sh",str(p)],env=dict(os.environ,QUERY_STRING=query))
    self.assertIn(b"403 Forbidden",r);self.assertIn(b"installation_locked",r);self.assertNotIn(b"fixture verifier",r)
   self.assertEqual(subprocess.check_output(["sh",str(p)],env=dict(os.environ,QUERY_STRING="")),b"fixture verifier")
 @unittest.skipUnless(Path(PREFIX,"bin/jshn").is_file(),"native libubox required")
 def test_catalog_never_offers_unverified_install(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);p=d/"adapter";p.write_text((BASE/"backend/read-only-adapter.sh").read_text().replace("/usr/share/libubox/jshn.sh",str(Path(PREFIX,"share/libubox/jshn.sh"))))
   for n,script in (("ubus",'#!/bin/sh\nprintf \'{"ok":true,"mode":"%s"}\' "$MODE"\n'),("jsonfilter",'#!/usr/bin/env python3\nimport json,sys\nx=json.load(sys.stdin)[sys.argv[2][2:]]\nprint(str(x).lower() if isinstance(x,bool) else x)\n')):
    q=d/n;q.write_text(script);q.chmod(0o700)
   for mode in ("verify_only","manual"):
    r=subprocess.check_output(["bash",str(p),"online_upgrade_check"],env=dict(os.environ,MODE=mode,PATH=str(d)+":"+str(Path(PREFIX,"bin"))+":"+os.environ["PATH"],LD_LIBRARY_PATH=str(Path(PREFIX,"lib"))))
    data=json.loads(r);self.assertEqual(data["code"],"-6");self.assertFalse(data["install_allowed"]);self.assertFalse(data["catalog_verified"]);self.assertNotIn("url",data)
