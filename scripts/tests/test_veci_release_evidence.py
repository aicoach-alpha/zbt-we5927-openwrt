"""Offline checks for fail-closed CI source-to-image provenance."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "scripts/veci_release_evidence.py"
spec = importlib.util.spec_from_file_location("veci_release_evidence", SRC)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

BUILD = "a" * 40
HEAD = "b" * 40
BASE = "c" * 40
IMAGE = "d" * 64
PIN = "e" * 40
META = {"version": {"target": "ramips/mt76x8", "version": "25.12.5"},
        "supported_devices": ["zbtlink,zbt-we5927"]}


def pr_report(**changes):
    values = dict(meta=META, pin=PIN, size=5898530, maximum=7995392,
                  image_sha=IMAGE, build_sha=BUILD,
                  reviewed_head=HEAD, reviewed_base=BASE,
                  event="pull_request", parents=[BASE, HEAD],
                  export_requested=False, ref="refs/pull/16/merge")
    values.update(changes)
    return module.make_report(**values)


class ReleaseEvidenceTests(unittest.TestCase):
    def test_pr_merge_has_reviewed_head_and_merge_sha(self):
        result = pr_report()
        self.assertEqual(result["schema"], "veci.we5927.rc1.ci-evidence.v2")
        self.assertEqual(result["github_build_sha"], BUILD)
        self.assertEqual(result["reviewed_head_sha"], HEAD)
        self.assertEqual(result["reviewed_base_sha"], BASE)
        self.assertEqual(result["remaining_bytes"], 2096862)
        self.assertEqual(result["checks"]["reviewed_checkout_provenance"], "pass")
        self.assertFalse(result["flash_permission"])
        self.assertEqual(result["checks"]["release_signing_and_trust_anchor"],
                         "not_verified")

    def test_wrong_head_is_not_proven_by_a_green_build(self):
        with self.assertRaisesRegex(ValueError, "does not contain reviewed"):
            pr_report(reviewed_head="f" * 40)

    def test_wrong_base_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not contain reviewed"):
            pr_report(reviewed_base="f" * 40)

    def test_pr_must_be_a_two_parent_checkout(self):
        with self.assertRaisesRegex(ValueError, "does not contain reviewed"):
            pr_report(parents=[HEAD])

    def test_pr_ci_cannot_export_unsigned_binary(self):
        with self.assertRaisesRegex(ValueError, "cannot export"):
            pr_report(export_requested=True)

    def test_dispatch_requires_reviewed_source_branch_for_binary_export(self):
        values = dict(event="workflow_dispatch", reviewed_head=BUILD,
                      reviewed_base="", parents=[], ref="refs/heads/main",
                      export_requested=True)
        with self.assertRaisesRegex(ValueError, "requires reviewed RC"):
            pr_report(**values)
        values["ref"] = "refs/heads/integration/veci-reliability-rc1-20261112"
        result = pr_report(**values)
        self.assertTrue(result["unsigned_candidate_export_requested"])
        self.assertFalse(result["flash_permission"])

    def test_bad_metadata_and_partition_fit_rejected(self):
        with self.assertRaisesRegex(ValueError, "wrong board"):
            pr_report(meta={"version": {"target":"ramips/mt76x8",
                                        "version": "25.12.6"},
                            "supported_devices": ["zbtlink,zbt-we5927"]})
        with self.assertRaisesRegex(ValueError, "invalid firmware MTD"):
            pr_report(size=8000000)

    def test_unknown_event_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            pr_report(event="push")

    def test_workflow_does_not_confuse_pr_merge_with_reviewed_source(self):
        workflow = (ROOT / ".github/workflows/veci-reliability-full-image-rc.yml").read_text()
        self.assertIn("REVIEWED_HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}",
                      workflow)
        self.assertIn("REVIEWED_BASE_SHA: ${{ github.event.pull_request.base.sha || '' }}",
                      workflow)
        self.assertIn('scripts/veci_release_evidence.py', workflow)
        self.assertIn('--build-sha "$GITHUB_SHA"', workflow)
        self.assertIn('--reviewed-head "$REVIEWED_HEAD_SHA"', workflow)


if __name__ == "__main__":
    unittest.main()
