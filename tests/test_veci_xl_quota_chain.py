"""VeCI XL quota chain: offline integration without a carrier, keys or modem.

These tests patch ONLY a disposable copy of the script to insert fake local
tools. Production source has fixed paths, fixed read-only method and root-only
credentials. This tests plumbing, failure states and data-leak prevention;
it does not qualify any operator login or quota as LIVE.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "source/veci-telco-indonesia/files/usr/libexec/veci-xl-quota-chain"
PUBLIC = {"xtime":1791987600000,"xdata":"AAAAAAAAAAAAAAAAAAAAAA=="}
PARSED = {"ok":True,"parsed_only":True,"provider":"xl","remaining_bytes":512,"total_bytes":1024}


class QuotaChainTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.private = self.root / "private"
        self.private.mkdir(mode=0o700)
        self.secret = self.private / "xdata_key"
        self.secret.write_text("a"*32)
        self.secret.chmod(0o600)
        self.envelope = self.root / "envelope.json"
        self.envelope.write_text(json.dumps(PUBLIC))
        self.expected_plain = '{"data":{"quotas":[{"benefits":[{"data_type":"DATA","remaining":512,"total":1024}]}]},"auth_token":"DO_NOT_LEAK"}'
        self.native = {}
        for name in ("http","crypto","parser","jsonfilter"):
            p = self.root / name
            self.native[name] = p
        self.write_mock("http", f"#!/bin/sh\ncat '{self.envelope}'\n")
        self.write_mock("crypto", f"#!/bin/sh\nprintf '%s' '{self.expected_plain}'\n")
        self.write_mock("parser", f"#!/bin/sh\ncat >/dev/null\nprintf '%s\\n' '{json.dumps(PARSED,separators=(',',':'))}'\n")
        self.write_mock("jsonfilter",
            "#!/usr/bin/env python3\n"
            "import sys,json\n"
            "args=sys.argv[1:]\n"
            "try:\n"
            "  data=json.load(open(args[args.index('-i')+1]))\n"
            "  path=args[args.index('-e')+1]\n"
            "  assert path.startswith('@.')\n"
            "  v=data[path[2:]]\n"
            "  print(str(v).lower() if isinstance(v,bool) else v)\n"
            "except Exception: sys.exit(1)\n")
        script = SRC.read_text()
        subs = {
            "HTTP=/usr/libexec/veci-xl-quota-http":f"HTTP={self.native['http']}",
            "CRYPTO=/usr/libexec/veci-xl-crypto":f"CRYPTO={self.native['crypto']}",
            "PARSER=/usr/libexec/veci-xl-quota-normalize":f"PARSER={self.native['parser']}",
            "JSONFILTER=/usr/bin/jsonfilter":f"JSONFILTER={self.native['jsonfilter']}",
            "PRIVATE=/tmp/veci-telco-private":f"PRIVATE={self.private}",
            '[ "$(id -u)" = "0" ] || fail root_required':'[ "0" = "0" ] || fail root_required',
        }
        for before, after in subs.items():
            assert before in script,before
            script = script.replace(before, after)
        self.script = self.root / "chain"
        self.script.write_text(script)
        self.script.chmod(0o700)

    def write_mock(self,name,source):
        self.native[name].write_text(source)
        self.native[name].chmod(0o700)

    def run_chain(self):
        return subprocess.run(
            ["sh",str(self.script),"--read-only"],capture_output=True,
            text=True,timeout=8)

    def test_raw_secret_never_exposed_and_cache_not_marked_authenticated(self):
        p=self.run_chain()
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout),PARSED)
        self.assertNotIn("DO_NOT_LEAK",p.stdout+p.stderr)
        self.assertNotIn("carrier_authenticated",p.stdout)
        self.assertFalse((self.root/"quota-xl.json").exists())

    def test_missing_local_xdata_key_exits_before_network(self):
        stamp=self.root/"network-touched"
        self.write_mock("http",f"#!/bin/sh\n: > '{stamp}'\n")
        self.secret.unlink()
        p=self.run_chain()
        self.assertNotEqual(p.returncode,0)
        self.assertFalse(stamp.exists())
        self.assertIn("session_not_configured",p.stderr)

    def test_bad_envelope_fails_closed(self):
        for bad in (
            '{"xtime":"wrong","xdata":"AAAA=="}',
            '{"xtime":1791987600000,"xdata":"@@@@!"}',
            '{"xtime":1791987600000}',
            '{"xtime":1791987600000,"xdata":"A\\nAAAA=="}',
        ):
            with self.subTest(bad=bad):
                self.envelope.write_text(bad)
                p=self.run_chain()
                self.assertNotEqual(p.returncode,0)
                self.assertEqual(p.stdout,"")
                self.assertNotIn("DO_NOT_LEAK",p.stderr)

    def test_reject_parser_without_parsed_only_provenance(self):
        self.write_mock("parser",'#!/bin/sh\nprintf \'{"ok":true,"parsed_only":false,"provider":"xl","remaining_bytes":42}\\n\'\n')
        p=self.run_chain()
        self.assertNotEqual(p.returncode,0)
        self.assertEqual(p.stdout,"")

    def test_no_credentials_literal_or_cache_write_in_staged_source(self):
        source=SRC.read_text()
        for x in ("AT+CMGR","AT+CUSD","apikey=", "http://",
                  "source=carrier_authenticated","quota-xl.json",
                  "myXL / 8.", "/etc/init.d/", "sysupgrade"):
            self.assertNotIn(x,source)
        self.assertIn("parsed_only",source)
        self.assertIn('umask 077',source)
        p=subprocess.run(["sh","-n",str(SRC)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)


if __name__=="__main__":
    unittest.main()
