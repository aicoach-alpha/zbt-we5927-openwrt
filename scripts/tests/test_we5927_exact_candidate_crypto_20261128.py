import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
import we5927_exact_candidate_crypto_20261128 as x
class CryptoInputTests(unittest.TestCase):
    def test_wrong_image_rejected(self):
        with self.assertRaisesRegex(x.GateError,"CANDIDATE_MISMATCH"):x.validate_inputs(b"x",b"y")
    def test_wrong_public_key_rejected(self):
        b=b"x"*5899090
        with patch.object(x,"VECI_SHA",hashlib.sha256(b).hexdigest()):
            with self.assertRaisesRegex(x.GateError,"PUBLIC_KEY_MISMATCH"):x.validate_inputs(b,b"y")
    def test_exact_pins_allow_input_validation_only(self):
        b=b"x"*5899090;k=b"y"
        with patch.object(x,"VECI_SHA",hashlib.sha256(b).hexdigest()),patch.object(x,"PUB_SHA",hashlib.sha256(k).hexdigest()):
            self.assertIsNone(x.validate_inputs(b,k))
