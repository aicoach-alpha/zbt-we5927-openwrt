"""Never synthesize board/release metadata when finalizing an image."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"scripts/finalize-sysupgrade.sh"


class SafeFinalization(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p=Path(self.temp.name)
        self.raw=self.p/"candidate.bin"
        self.raw.write_bytes(b"\x01\x02\x03fake signed-agnostic test")
        self.output=self.p/"result.bin"
        self.fwtool=self.p/"fwtool"
        self.fwtool.write_text("""#!/bin/sh
[ "$1" = "-i" ] || exit 1
[ -f "$MOCK_META" ] || exit 1
cp "$MOCK_META" "$2"
""")
        self.fwtool.chmod(0o700)
        self.meta=self.p/"meta.json"
        self.meta.write_text(json.dumps({
            "supported_devices":["zbtlink,zbt-we5927"],
            "version":{"target":"ramips/mt76x8","version":"25.12.6"}}))
        self.env=dict(os.environ,MOCK_META=str(self.meta))

    def run_finalize(self):
        return subprocess.run(["sh",str(SCRIPT),str(self.raw),str(self.output),
                               str(self.fwtool)],env=self.env,capture_output=True,
                              text=True,timeout=5)

    def test_valid_exact_image_copy(self):
        r=self.run_finalize()
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(self.raw.read_bytes(),self.output.read_bytes())
        self.assertIn("NO_SIGNING_NO_FLASH",r.stdout)

    def test_old_release_is_rejected_without_output(self):
        meta=json.loads(self.meta.read_text())
        meta["version"]["version"]="25.12.5"
        self.meta.write_text(json.dumps(meta))
        self.assertNotEqual(self.run_finalize().returncode,0)
        self.assertFalse(self.output.exists())

    def test_wrong_board_is_rejected(self):
        meta=json.loads(self.meta.read_text())
        meta["supported_devices"]=["different,zbt-we5927"]
        self.meta.write_text(json.dumps(meta))
        self.assertNotEqual(self.run_finalize().returncode,0)
        self.assertFalse(self.output.exists())

    def test_missing_trailer_is_rejected_not_invented(self):
        self.meta.unlink()
        r=self.run_finalize()
        self.assertNotEqual(r.returncode,0)
        self.assertFalse(self.output.exists())
        self.assertIn("metadata_missing",r.stderr)

    def test_destination_exists_is_rejected(self):
        self.output.write_bytes(b"previous")
        self.assertNotEqual(self.run_finalize().returncode,0)
        self.assertEqual(self.output.read_bytes(),b"previous")

    def test_bad_source_symlink_is_rejected(self):
        data=self.p/"actual.bin"
        self.raw.rename(data)
        self.raw.symlink_to(data)
        self.assertNotEqual(self.run_finalize().returncode,0)
        self.assertFalse(self.output.exists())


if __name__=="__main__":
    unittest.main()
