import pathlib, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
WF=ROOT/'.github/workflows/veci-general-cafe-candidate.yml'
class WorkflowTests(unittest.TestCase):
    def test_manual_only_no_push_and_no_flash_publish(self):
        s=WF.read_text()
        self.assertIn('on:\n  workflow_dispatch:',s)
        self.assertNotIn('\n  push:',s)
        self.assertNotIn('\n  schedule:',s)
        self.assertIn('permissions:\n  contents: read',s)
        for forbidden in ('sysupgrade -F','sysupgrade -n','sysupgrade -T',
                          'gh release create', 'git push origin','curl -X POST'):
            self.assertNotIn(forbidden,s)
        self.assertIn('FLASH_DECISION=NO_GO',s)
    def test_pinned_sources_and_tests_and_image_gates(self):
        s=WF.read_text()
        for required in ('OPENWRT_COMMIT','PACKAGES_COMMIT','LUCI_COMMIT','ROUTING_COMMIT',
                         'TELEPHONY_COMMIT','VIDEO_COMMIT',
                         'prepare-veci-general-cafe-profile.sh',
                         'verify-veci-general-cafe-image.sh',
                         '--filter=blob:none','sha256sum -c SHA256SUMS','make -j2',
                         "python3 -B -m unittest discover -s tests -p 'test_*.py'"):
            self.assertIn(required,s)
        self.assertIn('Expected exactly one board image + manifest',s)
if __name__=='__main__':unittest.main()
