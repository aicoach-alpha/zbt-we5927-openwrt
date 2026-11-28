import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
import we5927_recovery_power_cut_20261128 as x
class PowerTests(unittest.TestCase):
    def test_single_slot_risk_both_policies(self):
        for policy in ("rounded_payload","whole_firmware"):
            r=x.simulate(b"A"*100000,b"B"*130000,policy);p=r["checkpoints"]
            self.assertEqual(len(p),6)
            self.assertTrue(p[0]["old_payload_exact"])
            self.assertTrue(p[1]["neither_payload_exact"])
            self.assertTrue(p[3]["neither_payload_exact"])
            self.assertTrue(p[4]["new_payload_exact"])
            self.assertFalse(p[4]["new_payload_readback_verified"])
            self.assertTrue(p[5]["new_payload_readback_verified"])
            self.assertTrue(all(c["protected_hashes_unchanged"] and c["bootability"]=="UNKNOWN" for c in p))
            self.assertFalse(r["automatic_rollback_proven"])
            self.assertFalse(r["flash_authorized"])
    def test_invalid_input(self):
        for a,b in ((b"",b"x"),(b"x",b""),(bytearray(b"x"),b"x")):
            with self.assertRaises(ValueError):x.simulate(a,b,"rounded_payload")
