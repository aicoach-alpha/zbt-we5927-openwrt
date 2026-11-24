"""Mock only the post-CMGS receipt parser. Never open a modem or send an SMS."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "source/veci-cellular-we5927/files/usr/libexec/veci-sms-send-one"


def parse_receipt(result, rc):
    text = WRAPPER.read_text()
    start = text.index("normalize_cmgs_result() {")
    stop = text.index("\n}\n", start) + 2
    # Isolate the pure shell function: invoking the full script would contact
    # the modem and is strictly prohibited during offline tests.
    script = text[start:stop] + '\nnormalize_cmgs_result "$1" "$2"\n'
    process = subprocess.run(["sh", "-c", script, "receipt-test",
                              str(rc), result], capture_output=True, text=True,
                             check=False, timeout=2)
    if process.returncode != 0:
        raise AssertionError(process.stderr)
    return process.stdout.strip()


OK = '{"ok":true,"status":"accepted_by_modem"}'
UNKNOWN = '{"ok":false,"reason":"outcome_unknown"}'


class CMGSResultTests(unittest.TestCase):
    def test_firmware_package_releases_updated_wrapper(self):
        make = (ROOT / "source/veci-cellular-we5927/Makefile").read_text()
        self.assertIn("PKG_RELEASE:=4", make)
        self.assertIn("veci-sms-send-one", make)

    def test_plain_success_kept(self):
        self.assertEqual(parse_receipt(OK, 0), OK)

    def test_requested_report_receipt_is_still_modem_accepted(self):
        for mr in (0, 1, 99, 255):
            with self.subTest(mr=mr):
                result = ('{"ok":true,"status":"accepted_by_modem","mr":'
                          + str(mr) + ',"report_requested":true}')
                self.assertEqual(parse_receipt(result, 0), OK)

    def test_invalid_report_receipt_rejected_without_claiming_delivery(self):
        for mr in ("-1", "256", "x", "0000", '9,"recipient":"secret'):
            with self.subTest(mr=mr):
                result = ('{"ok":true,"status":"accepted_by_modem","mr":'
                          + mr + ',"report_requested":true}')
                self.assertEqual(parse_receipt(result, 0), UNKNOWN)

    def test_nonzero_transport_exit_does_not_claim_acceptance(self):
        self.assertEqual(parse_receipt(OK, 1), UNKNOWN)
        self.assertEqual(parse_receipt(
            '{"ok":true,"status":"accepted_by_modem","mr":7,"report_requested":true}',
            1), UNKNOWN)

    def test_known_negative_receipts_preserved(self):
        for reason in ("network_rejected", "outcome_unknown", "prompt_unavailable"):
            receipt = '{"ok":false,"reason":"' + reason + '"}'
            self.assertEqual(parse_receipt(receipt, 1), receipt)

    def test_unknown_or_broken_receipt_is_uncertain_not_send_unavailable(self):
        for receipt in ("", "garbage", '{"ok":false,"reason":"invalid_submit"}',
                        '{"ok":true,"status":"accepted_by_modem","mr":10}',
                        'PDU:001122334455'):
            with self.subTest(receipt=receipt):
                self.assertEqual(parse_receipt(receipt, 1), UNKNOWN)
                self.assertNotIn("001122334455", parse_receipt(receipt, 1))


if __name__ == "__main__":
    unittest.main()
