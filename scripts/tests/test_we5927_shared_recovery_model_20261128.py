import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
import we5927_shared_recovery_model_20261128 as x
from test_we5927_recovery_format_gate_20261127 import image_bytes
from we5927_recovery_image_format_gate_20261127 import FormatGateError,MTD3_LIMIT

def sha(b):return hashlib.sha256(b).hexdigest()
class SharedTests(unittest.TestCase):
    def test_both_role_formats_and_models(self):
        for role,kind in (("oem_reference","vendor"),("signed_veci_candidate","signed")):
            b=image_bytes(kind)
            r=x.evaluate(b,role,sha(b))
            self.assertEqual(len(r["models"]),2)
            self.assertTrue(all(m["image_sha256"]==sha(b) for m in r["models"]))
            self.assertTrue(all(m["protected_partition_hashes_unchanged"] for m in r["models"]))
            self.assertFalse(r["flash_authorized"])
            self.assertFalse(r["release_permitted"])
    def reject_before_model(self,b,role,digest,error):
        with patch.object(x,"simulate") as model:
            with self.assertRaisesRegex(FormatGateError,error):
                x.evaluate(b,role,digest)
            model.assert_not_called()
    def test_wrong_hash(self):
        self.reject_before_model(image_bytes(),"oem_reference","0"*64,"SHA256")
    def test_corrupt_payload_even_with_rehashed_input(self):
        b=bytearray(image_bytes());b[65]^=1;b=bytes(b)
        self.reject_before_model(b,"oem_reference",sha(b),"DATA_CRC32")
    def test_wrong_role(self):
        b=image_bytes("signed")
        self.reject_before_model(b,"oem_reference",sha(b),"ROLE_TRAILER")
    def test_ambiguous_trailer(self):
        b=image_bytes()[:-4]+b"ucert"+image_bytes()[-4:]
        self.reject_before_model(b,"oem_reference",sha(b),"ROLE_TRAILER")
    def test_oversize(self):
        b=b"\0"*(MTD3_LIMIT+1)
        self.reject_before_model(b,"signed_veci_candidate",sha(b),"SIZE_OUT")
    def test_mutable_input(self):
        b=bytearray(image_bytes())
        self.reject_before_model(b,"oem_reference",sha(b),"IMMUTABLE")
    def test_unknown_role(self):
        b=image_bytes()
        self.reject_before_model(b,"unknown",sha(b),"UNKNOWN_RESEARCH_ROLE")
