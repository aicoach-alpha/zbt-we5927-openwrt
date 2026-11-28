import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
import we5927_recovery_bundle_20261128 as x
class BundleTests(unittest.TestCase):
    def test_crypto_failure_stops_format(self):
        with patch.object(x,"check",side_effect=ValueError("CRYPTO_FAIL")),patch.object(x,"evaluate") as model:
            with self.assertRaisesRegex(ValueError,"CRYPTO_FAIL"):x.run(b"o",b"v",b"k","f","u","s")
            model.assert_not_called()
    def test_wrong_crypto_binding_stops_format(self):
        with patch.object(x,"check",return_value={"image_sha256":"wrong","signature_against_pinned_nas_public_key":"PASS"}),patch.object(x,"evaluate") as model:
            with self.assertRaisesRegex(ValueError,"CRYPTO_EVIDENCE_MISMATCH"):x.run(b"o",b"v",b"k","f","u","s")
            model.assert_not_called()
    def test_mocked_success_is_not_flash_permission(self):
        def fmt(b,role,sha):return {"format":{"sha256":sha},"format_and_model_status":"PASS"}
        with patch.object(x,"check",return_value={"image_sha256":x.VECI_SHA,"signature_against_pinned_nas_public_key":"PASS"}),patch.object(x,"evaluate",side_effect=fmt):
            r=x.run(b"o",b"v",b"k","f","u","s")
            self.assertFalse(r["flash_authorized"]);self.assertEqual(r["physical_recovery"],"NOT_TESTED")
    def test_wrong_format_binding_rejected(self):
        with patch.object(x,"check",return_value={"image_sha256":x.VECI_SHA,"signature_against_pinned_nas_public_key":"PASS"}),patch.object(x,"evaluate",return_value={"format":{"sha256":"wrong"},"format_and_model_status":"PASS"}):
            with self.assertRaisesRegex(ValueError,"FORMAT_EVIDENCE_MISMATCH"):x.run(b"o",b"v",b"k","f","u","s")
