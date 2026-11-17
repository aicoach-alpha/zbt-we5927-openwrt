"""Verify feature-evidence fidelity and fail-closed release of v2 rebuild."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/"rebuild/veci-v2"
CONTRACT = json.loads((BASE/"contracts/veci-v2-rebuild-contract.json").read_text())
LUCI = json.loads((BASE/"contracts/luci-25.12-feature-index.json").read_text())
OEM = json.loads((BASE/"contracts/oem-we5927-2sim.json").read_text())
SPEC = importlib.util.spec_from_file_location("veci_v2_gate", BASE/"ci/release-gate.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class FeatureContract(unittest.TestCase):
    def test_exact_oem_luci_openwrt_pins_and_counts(self):
        self.assertEqual(CONTRACT["board_id"], "ZBT-WE5927-DSIM")
        self.assertEqual(CONTRACT["openwrt_version"], "25.12.6")
        self.assertEqual(CONTRACT["kernel_version"], "6.12.112")
        self.assertEqual(CONTRACT["firmware_slots"], 1)
        self.assertEqual(CONTRACT["flash_mtd_bytes"], 7995392)
        self.assertEqual(CONTRACT["oem_sha256"], OEM["source_sha256"])
        self.assertEqual(CONTRACT["luci_revision"], LUCI["source_revision"])
        self.assertEqual(LUCI["source_branch"], "openwrt-25.12")
        self.assertEqual(LUCI["application_count"], 107)
        self.assertEqual(len(LUCI["applications"]), 107)
        self.assertEqual(len(LUCI["core_modules"]), 11)
        self.assertEqual(len(CONTRACT["required_core"]), 37)
        self.assertEqual(len({f["id"] for f in CONTRACT["required_core"]}), 37)

    def test_no_false_claim_about_luci_full_migration(self):
        self.assertTrue(all(x["migration"] == "not_ported" for x in LUCI["applications"]))
        self.assertTrue(all(x["compatibility"] == "not_assessed" for x in LUCI["applications"]))
        self.assertTrue(all(x["physical_uat"] == "not_run" for x in CONTRACT["required_core"]))
        self.assertEqual(CONTRACT["release_state"], "DEVELOPMENT_NOT_FLASHABLE")
        self.assertFalse(CONTRACT["flash_authorized"])

    def test_key_requirements_represented_in_contract(self):
        keys={x["id"] for x in CONTRACT["required_core"]}
        for key in ("lte_dual_sim_manual","lte_ussd","sms_inbox",
                    "sms_sent_and_drafts","sms_send_and_delete",
                    "sms_multipart_pdu","system_signed_github_ota",
                    "system_manual_sysupgrade","addon_signed_package_manager",
                    "firewall_zones_nat","wifi_ap_2g","wifi_survey_channel",
                    "firmware_gpio_hardware_watchdog","firmware_24x7_observability"):
            self.assertIn(key,keys)

    def test_flash_denied_without_real_hardware_proof(self):
        blockers=GATE.evaluate(CONTRACT,{})
        self.assertIn("contract_disallows_flash", blockers)
        self.assertTrue(any(x.startswith("hardware_uat_missing:") for x in blockers))
        self.assertIn("signed_image_not_verified",blockers)

    def test_even_fake_pass_evidence_cannot_override_contract(self):
        f=json.loads(json.dumps(CONTRACT))
        evidence={x:True for x in f["mandatory_gates"]}
        evidence.update(signed_image_hash_verified=True,firmware_image_bytes=6500000)
        blockers=GATE.evaluate(f,evidence)
        self.assertIn("contract_disallows_flash",blockers)
        self.assertTrue(any(x.startswith("hardware_uat_missing:") for x in blockers))

    def test_sandbox_staging_preserves_verified_sms_source(self):
        script=(BASE/"ci/stage-v2-source.sh").read_text()
        self.assertIn("veci-v2-sms",script)
        self.assertIn("sms_origin",script)
        self.assertIn("cmp -s",script)
        self.assertIn("wrong_openwrt_source_commit",script)
        self.assertIn("NOT_A_FINISHED_IMAGE_NOT_SIGNED_NOT_FLASHABLE",script)
        for bad in ("sysupgrade ", "reboot ", "wifi reload", "ifdown lte",
                    "/sys/class/gpio/gpio"):
            self.assertNotIn(bad,script)

    def test_sms_v2_package_does_not_depend_on_v1_ui(self):
        pkg=(BASE/"packages/veci-v2-sms/Makefile").read_text()
        self.assertIn("CONFLICTS:=veci-cellular-we5927",pkg)
        self.assertIn("DEPENDS:=+we5927-lte +rpcd +jsonfilter",pkg)
        self.assertNotIn("DEPENDS:=+veci ",pkg)
        self.assertIn("veci-sms-parse",pkg)
        self.assertIn("veci-sms-send-one",pkg)
        self.assertIn("veci-sms-sent-history",pkg)
        self.assertIn("veci-sms-drafts",pkg)
        acl=json.loads((BASE/"packages/veci-v2-sms/veci-v2-sms-acl.json").read_text())
        self.assertIn("sendMessage",acl["veci-v2-sms-admin"]["write"]["ubus"]["veci.sms"])

    def test_ui_requires_explicit_auth_no_persistent_session(self):
        ui=(BASE/"packages/veci-v2-ui/files/www/veci2")
        html=(ui/"index.html").read_text()
        js=(ui/"app.js").read_text()
        self.assertIn("autocomplete=\"current-password\"",html)
        self.assertIn("ROOT_SID",js)
        self.assertIn("session', 'login'",js)
        self.assertIn("session', 'destroy'",js)
        self.assertIn("window.confirm",js)
        self.assertIn("veci.v2.pkg', 'preflight'",js)
        self.assertNotIn("localStorage",js)
        self.assertNotIn("sessionStorage",js)
        self.assertNotIn("innerHTML",js)
        self.assertNotIn("AT+CMGS",js)
        for element in re.findall(r"el\('([a-z][a-z0-9-]*)'\)",js):
            self.assertIn('id="'+element+'"',html,element)
        self.assertIn("preview",html.lower())


if __name__=="__main__":
    unittest.main()
