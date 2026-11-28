import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
import we5927_cross_variant_verifier_20261128 as x
def fixture():
    v={x.CORE:b"core",x.POLICY:b"verify_only\n",x.CGI:b"cgi\n"}
    o=dict(v);o[x.CGI]+=x.REBOOT_GUARD
    o[x.ADAPTER]=b'[ "${QUERY_STRING:-}" = "" ] || {\n403 Forbidden\nexec /usr/libexec/oem-updated/shared-verify'
    o[x.STAGER]=b'shutil.copyfile(shared / "cgi-bin/veci2-verify", verify)\nshutil.copyfile(HERE / "backend/verify-only.sh", verify_gate)'
    o[x.MANIFEST]=json.dumps({"files":{k:x.sha(o[k]) for k in (x.CORE,x.POLICY,x.CGI)}}).encode()
    return v,o
class ParityTests(unittest.TestCase):
    def test_known_interlock_is_not_divergence(self):
        r=x.audit(*fixture());self.assertEqual(r["source_audit"],"PASS");self.assertFalse(r["flash_authorized"])
    def test_unknown_cgi_change(self):
        v,o=fixture();o[x.CGI]+=b"unknown"
        self.assertIn("CGI_DIVERGED",x.audit(v,o)["errors"])
    def test_core_divergence(self):
        v,o=fixture();o[x.CORE]=b"changed"
        self.assertIn("CORE_VERIFIER_DIVERGED",x.audit(v,o)["errors"])
    def test_unsafe_default_or_wrapper(self):
        v,o=fixture();o[x.POLICY]=b"manual";o[x.ADAPTER]=b"exec other"
        r=x.audit(v,o);self.assertIn("DEFAULT_NOT_VERIFY_ONLY",r["errors"]);self.assertIn("OEM_VERIFY_ONLY_WRAPPER_SHAPE_CHANGED",r["errors"])
    def test_ref_must_be_exact(self):
        with self.assertRaises(ValueError):x.load(Path("."),"HEAD",())
