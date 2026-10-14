"""Offline tests of the standalone POSIX sh quota cache + bounded JSON status.
No live router, no carrier account, no OTP, no external HTTP requests.
jsonfilter is mocked only because Ubuntu CI does not ship OpenWrt libubox.
"""
import datetime
import json
import os
import pathlib
import subprocess
import tempfile
import time
import unittest

BASE=pathlib.Path(__file__).resolve().parents[1]/"source/veci-telco-indonesia"
CACHE=BASE/"files/usr/libexec/veci-quota-cache"
MOCK_JSONFILTER='''#!/usr/bin/env python3
import json
import sys
args=sys.argv[1:]
try:
    filename=args[args.index("-i")+1]
    key=args[args.index("-e")+1]
    assert key.startswith("@.")
    obj=json.load(open(filename))
    value=obj.get(key[2:])
    if value is not None:
        if isinstance(value, (list,dict)):
            sys.exit(2)
        print(value)
except Exception:
    sys.exit(1)
'''

class CacheSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base=pathlib.Path(self.temporary.name)
        self.cache_dir=self.base/"cache"
        self.cache_dir.mkdir(mode=0o700)
        self.file=self.cache_dir/"quota-xl.json"
        self.bin=self.base/"bin"
        self.bin.mkdir()
        mock=self.bin/"jsonfilter"
        mock.write_text(MOCK_JSONFILTER)
        mock.chmod(0o755)
        self.env=os.environ.copy()
        self.env["PATH"]=str(self.bin)+os.pathsep+self.env.get("PATH","")

    def data(self,**overrides):
        obj={
            "schema":1, "provider":"xl", "state":"ready",
            "source":"carrier_authenticated",
            "total_bytes":10_000_000_000,
            "remaining_bytes":4_000_000_000,
            "fetched_epoch":int(time.time()),
            "fetched_at":datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            # Raw operator fields must NEVER be echoed to rpcd/browser/logs.
            "msisdn":"6281234567890",
            "auth_token":"SECRET_TOKEN_MUST_NOT_LEAK",
            "buckets":[{"label":"secret", "remaining_bytes":1}]
        }
        obj.update(overrides)
        return obj

    def put(self,obj):
        self.file.write_text(json.dumps(obj))
        self.file.chmod(0o600)

    def read(self,source=None):
        return subprocess.run(
            ["sh",str(CACHE),"status",str(source or self.file)],
            env=self.env,text=True,capture_output=True,timeout=8
        )

    def decoded(self,source=None):
        p=self.read(source)
        self.assertEqual(p.returncode,0,p.stderr)
        return json.loads(p.stdout),p.stdout

    def test_missing_cache_not_connected(self):
        obj,text=self.decoded()
        self.assertEqual(obj["state"],"not_connected")
        self.assertIsNone(obj["remaining_bytes"])
        self.assertNotIn("SECRET",text)

    def test_valid_authenticated_cache_is_sanitized(self):
        self.put(self.data())
        obj,text=self.decoded()
        self.assertEqual(obj["state"],"ready")
        self.assertEqual(obj["provider"],"xl")
        self.assertEqual(obj["remaining_bytes"],4_000_000_000)
        self.assertEqual(obj["total_bytes"],10_000_000_000)
        self.assertEqual(obj["source"],"carrier_authenticated")
        self.assertEqual(obj["buckets"],[])
        for secret in ("SECRET_TOKEN","6281234567890","auth_token","secret"):
            self.assertNotIn(secret,text)

    def test_expired_cache_does_not_display_last_balance_as_current(self):
        self.put(self.data(fetched_epoch=int(time.time())-3600))
        obj,_=self.decoded()
        self.assertEqual(obj["state"],"stale")
        self.assertIsNone(obj["remaining_bytes"])

    def test_future_clock_fails_closed(self):
        self.put(self.data(fetched_epoch=int(time.time())+180))
        obj,_=self.decoded()
        self.assertEqual(obj["state"],"unavailable")

    def test_malformed_json_fails_closed(self):
        self.file.write_text('{"bad":')
        self.file.chmod(0o600)
        obj,_=self.decoded()
        self.assertEqual(obj["state"],"unavailable")

    def test_invalid_numbers_fail_closed(self):
        for rem in (-1,"abc",2.5,"4\\nINJECT",10**15,None,True):
            with self.subTest(rem=repr(rem)):
                self.put(self.data(remaining_bytes=rem))
                obj,_=self.decoded()
                self.assertEqual(obj["state"],"unavailable")

    def test_impossible_totals_never_display_as_carrier_quota(self):
        for patch in (
            {"total_bytes":None},
            {"total_bytes":0},
            {"total_bytes":"unknown"},
            {"total_bytes":-1},
            {"total_bytes":4_000_000_000-1},
            {"remaining_bytes":11_000_000_000},
        ):
            with self.subTest(patch=patch):
                self.put(self.data(**patch))
                status,display=self.decoded()
                self.assertEqual(status["state"],"unavailable")
                self.assertIsNone(status["remaining_bytes"])
                self.assertNotIn("SECRET_TOKEN",display)

    def test_signed_source_and_provider_are_mandatory(self):
        for patch in ({"source":"router_traffic"},{"provider":"axis"},
                      {"state":"otp_required"},{"schema":2}):
            with self.subTest(patch=patch):
                self.put(self.data(**patch))
                obj,_=self.decoded()
                self.assertEqual(obj["state"],"unavailable")

    def test_misconfigured_cache_permissions_rejected(self):
        self.put(self.data())
        self.file.chmod(0o644)
        obj,_=self.decoded()
        self.assertEqual(obj["state"],"unavailable")
        self.file.chmod(0o600)
        self.cache_dir.chmod(0o755)
        obj,_=self.decoded()
        self.assertEqual(obj["state"],"unavailable")

    def test_symlinked_cache_rejected(self):
        outside=self.base/"outside.json"
        outside.write_text(json.dumps(self.data()))
        outside.chmod(0o600)
        self.file.symlink_to(outside)
        obj,_=self.decoded()
        self.assertEqual(obj["state"],"unavailable")

    def test_oversized_cache_rejected(self):
        self.put(self.data(unnecessary_padding="X"*5000))
        obj,_=self.decoded()
        self.assertEqual(obj["state"],"unavailable")

    def test_invalid_timestamp_string_never_injected(self):
        self.put(self.data(fetched_at='2026-10-12T03:00:00Z";"token":"leak'))
        obj,text=self.decoded()
        self.assertEqual(obj["state"],"ready")
        self.assertIsNone(obj["fetched_at"])
        self.assertNotIn("leak",text)

    def test_no_network_or_secrets_in_helper(self):
        content=CACHE.read_text()
        self.assertNotIn("curl ",content)
        self.assertNotIn("wget ",content)
        self.assertNotIn("https://",content)
        self.assertNotIn("stat -c",content)
        self.assertNotIn("ACCESS_TOKEN",content)
        self.assertNotIn("--no-check-certificate",content)
        r=subprocess.run(["sh","-n",str(CACHE)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

if __name__=="__main__":
    unittest.main()
