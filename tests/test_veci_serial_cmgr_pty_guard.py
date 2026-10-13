"""Offline W907 PTY +CMGR: held flock + opened-FD attestation + one-time ACL/CSRF consent.
No real /dev/ttyUSB opened and no router, SIM, phone-number or real OTP data.
"""
import ctypes
import errno
import fcntl
import os
from pathlib import Path
import pty
import select
import subprocess
import tempfile
import threading
import time
import tty
import unittest

from test_veci_sms_cmgr_frame import fixture, Policy, Sms

SRC=Path(__file__).resolve().parents[1]/"source/we5927-lte/src"

class CmgrPTY(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir=tempfile.TemporaryDirectory()
        cls.so=str(Path(cls.dir.name)/"lib-pty-cmgr.so")
        names=["veci-serial-cmgr-pty-guard.c","veci-sms-cmgr-frame.c",
               "veci-sms-read-slot-policy.c","veci-sms-pdu-decode.c",
               "veci-at-framing.c","veci-modem-identity.c",
               "veci-modem-session-lock.c"]
        proc=subprocess.run(["cc","-std=c99","-O2","-Wall","-Wextra","-Werror",
                             "-DVECI_ENABLE_OFFLINE_PTY_HARNESS",
                             "-fPIC","-shared",*[str(SRC/n) for n in names],
                             "-o",cls.so],capture_output=True,text=True,timeout=25)
        if proc.returncode:raise AssertionError(proc.stderr)
        cls.lib=ctypes.CDLL(cls.so)
        cls.lib.veci_sms_read_arm.argtypes=[ctypes.POINTER(Policy),ctypes.c_uint,
            ctypes.c_uint64,ctypes.c_uint64,ctypes.c_uint64,
            ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int]
        cls.lib.veci_serial_cmgr_pty_once.argtypes=[
            ctypes.c_int,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p,
            ctypes.POINTER(Policy),ctypes.c_int,ctypes.POINTER(Sms)]
        cls.lib.veci_serial_cmgr_pty_once.restype=ctypes.c_int
        cls.lib.veci_sms_clear.argtypes=[ctypes.POINTER(Sms)]

    @classmethod
    def tearDownClass(cls):cls.dir.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.lock=str(self.root/"at-mock.lock").encode()
        self.master,self.slave=pty.openpty()
        tty.setraw(self.slave)
        self.addCleanup(lambda: os.close(self.master))
        self.addCleanup(lambda: os.close(self.slave))
        self.threads=[]
        self.slot=4
        self.policy=Policy()
        self.sms=Sms()
        self.fake_sysfs(self.root/"sysroot")

    def fake_sysfs(self,root,vid="05c6",inter="1-1:1.4"):
        cls=root/"class/tty/ttyUSB2"
        cls.mkdir(parents=True,exist_ok=True)
        link=root/"devices/usb1/1-1"/inter/"ttyUSB2"
        link.mkdir(parents=True,exist_ok=True)
        target=cls/"device"
        if not target.exists():
            target.symlink_to(os.path.relpath(link,cls))
        d=os.fstat(self.slave).st_rdev
        (cls/"dev").write_text(f"{os.major(d)}:{os.minor(d)}")
        (root/"devices/usb1/1-1/idVendor").write_text(vid)
        (root/"devices/usb1/1-1/idProduct").write_text("902e")
        driver=root/"bus/usb-serial/drivers/option1"
        driver.mkdir(parents=True,exist_ok=True)
        (link.parent/"driver").symlink_to(os.path.relpath(driver,link.parent))
        self.sysfs=root

    def approve(self,slot=None,flags=(1,1,1,1,1)):
        slot=self.slot if slot is None else slot
        return self.lib.veci_sms_read_arm(ctypes.byref(self.policy),
                slot,123456,987654,333444,*flags)

    def execute(self,timeout=600):
        return self.lib.veci_serial_cmgr_pty_once(
            self.slave,str(self.sysfs).encode(),b"ttyUSB2",self.lock,
            ctypes.byref(self.policy),timeout,ctypes.byref(self.sms))

    def reply(self,chunks,slot=None,delay=0.002):
        slot=self.slot if slot is None else slot
        def work():
            request=b""
            end=time.monotonic()+2
            while not request.endswith(b"\r") and time.monotonic()<end:
                if select.select([self.master],[],[],0.1)[0]:
                    request+=os.read(self.master,100)
            self.assertEqual(request,f"AT+CMGR={slot}\r".encode())
            for c in chunks:
                os.write(self.master,c if isinstance(c,bytes) else c.encode())
                time.sleep(delay)
        t=threading.Thread(target=work,daemon=True)
        self.threads.append(t)
        t.start()

    def test_one_message_gsm7_full_transaction_and_no_replay(self):
        self.assertEqual(self.approve(),0)
        pdu,n=fixture("HELLO 1234")
        self.reply([f"+CMGR: 0,,{n}\r\n",pdu+"\r\n","OK\r\n"])
        self.assertEqual(self.execute(),0)
        self.assertEqual(self.sms.text,b"HELLO 1234")
        self.assertEqual(self.policy.state,3)
        self.assertEqual(self.execute(100),-errno.EACCES)
        self.lib.veci_sms_clear(ctypes.byref(self.sms))
        self.assertEqual(bytes(self.sms),bytes(ctypes.sizeof(Sms)))

    def test_fragmented_ucs2(self):
        self.assertEqual(self.approve(),0)
        pdu,n=fixture("Halo",ucs2=True)
        data=f"AT+CMGR=4\r\n+CMGR: 0,,{n}\r\n{pdu}\r\nOK\r\n"
        self.reply([data[i:i+3] for i in range(0,len(data),3)],delay=0.001)
        self.assertEqual(self.execute(1000),0)
        self.assertEqual(self.sms.text.decode(),"Halo")

    def test_unapproved_cannot_send_at(self):
        self.assertEqual(self.execute(100),-errno.EACCES)
        self.assertEqual(select.select([self.master],[],[],0.02)[0],[])
        self.assertEqual(self.policy.state,4)

    def test_stale_urc_refuses_command(self):
        self.assertEqual(self.approve(),0)
        os.write(self.master,b'+CUSD: 0,"0041",72\r\n')
        self.assertEqual(self.execute(),-errno.EAGAIN)
        self.assertEqual(select.select([self.master],[],[],0.02)[0],[])
        self.assertEqual(self.policy.state,4)

    def test_wrong_modem_fd_identity_refuses_command(self):
        self.assertEqual(self.approve(),0)
        (self.sysfs/"devices/usb1/1-1/idVendor").write_text("12d1")
        self.assertNotEqual(self.execute(),0)
        self.assertEqual(select.select([self.master],[],[],0.02)[0],[])

    def test_lock_contention_denies_transmission(self):
        self.assertEqual(self.approve(),0)
        fd=os.open(self.lock,os.O_CREAT|os.O_RDWR,0o600)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.assertEqual(self.execute(),-errno.EBUSY)
            self.assertEqual(select.select([self.master],[],[],0.02)[0],[])
        finally:
            fcntl.flock(fd,fcntl.LOCK_UN)
            os.close(fd)

    def test_one_command_then_error_poison(self):
        self.assertEqual(self.approve(),0)
        self.reply(["+CMS ERROR: 321\r\n"])
        self.assertNotEqual(self.execute(),0)
        self.assertEqual(self.policy.state,4)
        self.assertEqual(bytes(self.sms),bytes(ctypes.sizeof(Sms)))
        self.assertEqual(select.select([self.master],[],[],0.02)[0],[])

    def test_timeout_never_retransmits(self):
        self.assertEqual(self.approve(),0)
        self.reply([])
        self.assertEqual(self.execute(150),-errno.ETIMEDOUT)
        self.assertEqual(self.policy.state,4)
        self.assertEqual(select.select([self.master],[],[],0.02)[0],[])

    def test_extra_sms_record_is_rejected(self):
        self.assertEqual(self.approve(),0)
        pdu,n=fixture("TEST")
        self.reply([f"+CMGR: 0,,{n}\r\n{pdu}\r\n",
                    f"+CMGR: 0,,{n}\r\n{pdu}\r\nOK\r\n"])
        self.assertNotEqual(self.execute(),0)
        self.assertEqual(bytes(self.sms),bytes(ctypes.sizeof(Sms)))

    def test_compile_gate_and_no_actual_port_open(self):
        proc=subprocess.run(["cc","-std=c99","-fsyntax-only",
                             str(SRC/"veci-serial-cmgr-pty-guard.c")],
                            capture_output=True,text=True)
        self.assertNotEqual(proc.returncode,0)
        self.assertIn("OFFLINE PTY ONLY",proc.stderr)
        code=(SRC/"veci-serial-cmgr-pty-guard.c").read_text()
        self.assertNotIn("/dev/ttyUSB",code)
        self.assertNotIn("AT+CMGS=",code)
        self.assertNotIn("AT+CMGD=",code)
        self.assertNotIn("syslog(",code)

    def tearDown(self):
        for th in self.threads:
            th.join(1.2)
            self.assertFalse(th.is_alive(),"mock modem thread did not finish")

if __name__=="__main__":
    unittest.main()
