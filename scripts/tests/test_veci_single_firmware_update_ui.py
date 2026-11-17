"""Regression guard: user-visible firmware update has ONE owner, Data Meter retired."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
WEB=ROOT/"source/veci-core/veci"
STAGE=(ROOT/"scripts/stage-veci-reliability-rc.sh").read_text()
CI=(ROOT/".github/workflows/veci-reliability-full-image-rc.yml").read_text()

class NativeUXGate(unittest.TestCase):
    def test_updates_only_in_updates_page(self):
        system=(WEB/"js/pages/system.js").read_text()
        updates=(WEB/"js/pages/updates.js").read_text()
        self.assertIn('id: \'updates\'', updates)
        self.assertIn('id="firmware-file"', updates)
        self.assertIn('id="apply-firmware"', updates)
        self.assertNotIn("bindFirmwareUpdates", system)
        for legacy in ('fw-upload', 'fw-check', 'fw-download', 'fw-apply',
                       'fw-file', 'fw-sha', 'Manual upload & OTA'):
            self.assertNotIn(legacy, system, legacy)
        self.assertFalse((WEB/"js/lib/firmware-updates.js").exists())
        self.assertNotIn('FIRMWARE UPDATE</p><h3>Manual upload', system)

    def test_data_meter_retired_from_rom_and_cellular(self):
        self.assertFalse((ROOT/"source/veci-data-meter").exists())
        cellular=(WEB/"js/pages/cellular.js").read_text()
        self.assertNotIn("/veci/data-meter.html",cellular)
        self.assertNotIn("Data Meter / LTE usage",cellular)
        self.assertNotIn("'veci-data-meter veci-data-meter'",STAGE)
        self.assertNotIn(" veci-data-meter; do",STAGE)
        self.assertNotIn(r"\nCONFIG_PACKAGE_veci-data-meter=y",CI)
        self.assertIn("test ! -e",CI)
        self.assertIn("! grep -Fq '/veci/data-meter.html'",CI)

    def test_updates_failures_distinguish_no_network_from_bad_manifest(self):
        core=(ROOT/"source/veci-core/files/rpcd-veci").read_text()
        agent=(ROOT/"source/veci-update-we5927/files/usr/sbin/veci-update-agent").read_text()
        self.assertIn("firmware_remote_error=manifest_fetch_failed",core)
        self.assertIn("firmware_remote_error=manifest_url_invalid",core)
        self.assertIn('record_status error network_or_manifest_fetch_failed',agent)
        stable=(ROOT/"source/veci-core/veci/js/pages/updates.js").read_text()
        self.assertIn("— (no staged image)",stable)
        html=(WEB/"index.html").read_text()
        app=(WEB/"js/app.js").read_text()
        self.assertIn("app.js?v=165",html)
        for name in ("system","updates"):
            self.assertIn(name+".js?v=164",app)
        self.assertIn("cellular.js?v=165",app)

    def test_lte_modem_and_sms_preserved(self):
        self.assertIn("cellular-reconnect", (WEB/"js/pages/cellular.js").read_text())
        self.assertIn("cellular-sms-inbox", (WEB/"js/pages/cellular.js").read_text())
        self.assertIn('veci-cellular-we5927', STAGE)
        self.assertIn('veci-update-we5927', STAGE)

if __name__=="__main__":
    unittest.main()
