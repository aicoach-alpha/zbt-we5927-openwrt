"""Non-live pseudo-terminal tests for WE5927's native AT serial helper.

Compile host C with the same logic as MIPS build, connect to a fake PTY,
and deliberately split terminal lines across serial reads.
Never connect a real modem or send SMS/USSD.
"""
import os
import pathlib
import pty
import select
import subprocess
import tempfile
import time
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
AT_SOURCE=ROOT/"source/we5927-lte/src/we5927-at.c"

class SerialTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory()
        cls.binary=str(pathlib.Path(cls.build.name)/"we5927-at-host")
        proc=subprocess.run(["cc","-std=gnu99","-O2","-Wall","-Wextra","-Werror",str(AT_SOURCE),
            "-o",cls.binary],capture_output=True,text=True)
        if proc.returncode:
            raise AssertionError(proc.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def transaction(self,pieces,command="AT+CMGF=?",timeout=900,delay=0.035):
        master,slave=pty.openpty()
        self.addCleanup(os.close,master)
        self.addCleanup(os.close,slave)
        process=subprocess.Popen([self.binary,os.ttyname(slave),command,str(timeout)],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            # Wait for command to actually reach the simulated modem before
            # feeding the reply, so tcflush() cannot erase the test payload.
            sent=b""
            end=time.monotonic()+2
            while not sent.endswith(b"\r") and time.monotonic()<end:
                ready,_,_=select.select([master],[],[],0.15)
                if ready:
                    sent+=os.read(master,512)
            self.assertTrue(sent.endswith(b"\r"),repr(sent))
            for chunk in pieces:
                os.write(master,chunk)
                time.sleep(delay)
            out,err=process.communicate(timeout=3)
            return process.returncode,out,err,sent
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_split_ok_line_across_reads(self):
        code,out,err,cmd=self.transaction(
            [b"\r\n+CMGF: (0,1)\r\n",b"\r\nO",b"K",b"\r\n"])
        self.assertEqual(cmd,b"AT+CMGF=?\r")
        self.assertEqual(code,0,err)
        self.assertIn(b"+CMGF: (0,1)",out)
        self.assertIn(b"\r\nOK\r\n",out)

    def test_split_error_line_is_failure(self):
        code,out,err,_=self.transaction([b"\r\n+CMS ER",b"ROR: 322\r\n"])
        self.assertEqual(code,1,err)
        self.assertIn(b"+CMS ERROR: 322",out)

    def test_response_contains_ok_substring_not_terminal(self):
        code,_,err,_=self.transaction([b"\r\nBOOKING\r\n"],timeout=280)
        self.assertEqual(code,1,err)

    def test_response_no_carrier_is_failure(self):
        code,_,err,_=self.transaction([b"\r\nNO CARRIER\r\n"])
        self.assertEqual(code,1,err)

    def test_partial_incomplete_success_is_failure(self):
        code,_,err,_=self.transaction([b"\r\n+CMGF: (0,1)\r\nOK"],timeout=300)
        self.assertEqual(code,1,err)

    def test_nominal_timeout_is_failure(self):
        code,_,err,_=self.transaction([b"\r\n+CMGF: (0,1)\r\n"],timeout=300)
        self.assertEqual(code,1,err)

    def test_large_response_line_fails_closed(self):
        code,_,err,_=self.transaction([b"\r\n"+b"A"*1250+b"\r\n"])
        self.assertEqual(code,1)
        self.assertIn(b"exceeded limit",err)

    def test_at_command_crlf_injection_blocked(self):
        for command in ("AT+CMGF=?\rAT+CFUN=1","AT+CMGF=?\nAT+CGSN", "at+CSQ","AT"+("X"*600)):
            with self.subTest(command=repr(command)[:25]):
                p=subprocess.run([self.binary,"/dev/null",command,"1000"],
                    capture_output=True,timeout=2)
                self.assertEqual(p.returncode,2)
                self.assertIn(b"invalid AT command",p.stderr)

    def test_invalid_timeouts_rejected(self):
        for timeout in ("junk","0","-1","50000","300ms"):
            with self.subTest(timeout=timeout):
                p=subprocess.run([self.binary,"/dev/null","AT",timeout],
                    capture_output=True,timeout=2)
                self.assertEqual(p.returncode,2)
                self.assertIn(b"invalid timeout",p.stderr)

    def test_original_status_commands_still_supported(self):
        code,out,err,cmd=self.transaction([b"\r\n+CSQ: 19,99\r\n\r\nOK\r\n"],command="AT+CSQ")
        self.assertEqual(code,0,err)
        self.assertEqual(cmd,b"AT+CSQ\r")
        self.assertIn(b"+CSQ: 19,99",out)

    def test_no_live_modem_or_sms_code_in_transport(self):
        s=AT_SOURCE.read_text()
        self.assertNotIn("AT+CMGS=",s)
        self.assertNotIn("AT+CUSD=1",s)
        self.assertIn("AT_RESPONSE_MAX 8192",s)
        self.assertIn("terminal_line(line)",s)
        self.assertIn("valid_command(cmd)",s)

if __name__=="__main__":
    unittest.main()
