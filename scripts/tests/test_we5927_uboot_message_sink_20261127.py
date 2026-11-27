import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ci"))
import we5927_uboot_message_sink_20261127 as x
from test_we5927_uboot_pic_got_20261127 import fixture

def expanded(spills=True):
    d=fixture()
    if spills:
        struct.pack_into("<III",d,0x400,0xafa50010,0xafa60014,0xafa70018)
    for i in range(8):
        offset=0x680+i*16
        msg=("Message %d\n"%i).encode()
        d[offset:offset+len(msg)]=msg
        struct.pack_into("<6I",d,0x1200+i*24,0x8f840010,0x8f990020,0x10000001,0x24840000|(offset-0x600),0x0320f809,0)
    return d

class SinkTests(unittest.TestCase):
    def test_message_sink_supported_not_validator(self):
        r=x.inspect(expanded())
        c=r["shared_callee_candidates"][0]
        self.assertEqual(c["classification"],"LIKELY_MESSAGE_SINK")
        self.assertEqual(c["distinct_text_arguments"],9)
        self.assertFalse(c["validator_proven"])
        self.assertFalse(r["flash_authorized"])
    def test_missing_spill_evidence(self):
        self.assertEqual(x.inspect(expanded(False))["shared_callee_candidates"][0]["classification"],"UNCLASSIFIED")
    def test_one_string_insufficient(self):
        self.assertEqual(x.inspect(fixture())["shared_callee_candidates"][0]["classification"],"UNCLASSIFIED")
    def test_unterminated_or_binary_text_rejected(self):
        self.assertIsNone(x.text_at(b"hello",0))
        self.assertIsNone(x.text_at(b"abc\xff\0",0))
        self.assertEqual(x.text_at(b"hello\n\0",0),b"hello\n")
    def test_no_mapping_never_approved(self):
        r=x.inspect(bytes(8192))
        self.assertEqual(r["shared_callee_candidates"],[])
        self.assertFalse(r["release_permitted"])
