"""No-network native myXL crypto equivalence and credential hygiene tests."""
import base64,hashlib,hmac,os,pathlib,subprocess,tempfile,unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=ROOT/"source/veci-telco-indonesia/veci-xl-crypto.c"
BIN=pathlib.Path(os.environ.get("VECI_XL_CRYPTO_BIN","/tmp/veci-xl-crypto-test"))

class MyXLCrypto(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if not BIN.exists():raise AssertionError("compile native veci-xl-crypto before tests")
 @classmethod
 def tearDownClass(cls):pass
 def setUp(self):
  self.d=tempfile.TemporaryDirectory()
  self.addCleanup(self.d.cleanup)
  self.base=pathlib.Path(self.d.name)
  self.aes=self.base/"aes"
  self.secret=self.base/"secret"
  self.token=self.base/"token"
  self.aes.write_bytes(b"a"*32)
  self.secret.write_bytes(b"test-offline-app-secret-not-a-live-secret")
  self.token.write_bytes(b"test-id-token")
  for p in (self.aes,self.secret,self.token):p.chmod(0o600)
 def run_cli(self,*a,stdin=b""):
  return subprocess.run([str(BIN),*map(str,a)],input=stdin,capture_output=True,timeout=5)
 def test_encrypted_xdata_decrypts_to_original_payload(self):
  try:from Crypto.Cipher import AES
  except ImportError:
   self.skipTest("install PyCryptodome in CI")
  xtime="1791987600000"
  for payload in [b'{"is_enterprise":false,"lang":"en","family_member_id":""}',b"x"*4096,b"16-char-length!"]:
   cp=self.run_cli("xdata",xtime,self.aes,stdin=payload)
   self.assertEqual(cp.returncode,0,cp.stderr.decode())
   digest=hashlib.sha256(xtime.encode()).hexdigest()
   iv=digest[:16].encode()
   ciphertext=base64.urlsafe_b64decode(cp.stdout.strip())
   plain=AES.new(b"a"*32,AES.MODE_CBC,iv).decrypt(ciphertext)
   pad=plain[-1]
   self.assertEqual(plain[-pad:],bytes([pad])*pad)
   self.assertEqual(plain[:-pad],payload)
 def test_decrypt_roundtrip_with_public_synthetic_payload(self):
  xtime="1791987600000"
  payload=b'{"data":{"quotas":[{"benefits":[{"data_type":"DATA","remaining":512,"total":1024}]}]}}'
  enc=self.run_cli("xdata",xtime,self.aes,stdin=payload)
  self.assertEqual(enc.returncode,0,enc.stderr.decode())
  dec=self.run_cli("decrypt",xtime,self.aes,stdin=enc.stdout.strip())
  self.assertEqual(dec.returncode,0,dec.stderr.decode())
  self.assertEqual(dec.stdout,payload)
  # URL-safe Base64 may arrive without trailing padding.
  dec2=self.run_cli("decrypt",xtime,self.aes,stdin=enc.stdout.strip().rstrip(b'='))
  self.assertEqual(dec2.returncode,0,dec2.stderr.decode())
  self.assertEqual(dec2.stdout,payload)
 def test_decrypt_rejects_corruption_and_bad_permissions(self):
  xtime="1791987600000"
  valid=self.run_cli("xdata",xtime,self.aes,stdin=b'{"status":"SUCCESS"}').stdout.strip()
  for cipher in (b"",b"***",b"a",b"aaaa",valid[:-2]+b"**",b"A"*6000):
   with self.subTest(cipher=cipher[:20]):
    dec=self.run_cli("decrypt",xtime,self.aes,stdin=cipher)
    self.assertNotEqual(dec.returncode,0)
    self.assertNotIn(b"SUCCESS",dec.stdout+dec.stderr)
  self.aes.chmod(0o644)
  self.assertNotEqual(self.run_cli("decrypt",xtime,self.aes,stdin=valid).returncode,0)
 def test_hmac_sha512_exact_reference_formula(self):
  ts="1791987600"
  cp=self.run_cli("signature",ts,self.secret,self.token)
  self.assertEqual(cp.returncode,0,cp.stderr.decode())
  k=f"test-offline-app-secret-not-a-live-secret;test-id-token;POST;api/v8/packages/quota-details;{ts}"
  msg=f"test-id-token;{ts};"
  expected=hmac.new(k.encode(),msg.encode(),hashlib.sha512).hexdigest()
  self.assertEqual(cp.stdout.strip().decode(),expected)
 def test_invalid_xtime_secret_or_payload_is_refused(self):
  for tm in ("0","1791987600000;rm","aaa1791987600"):
   self.assertNotEqual(self.run_cli("xdata",tm,self.aes,stdin=b"hi").returncode,0)
  self.assertNotEqual(self.run_cli("xdata","1791987600000",self.aes,stdin=b"x"*4097).returncode,0)
  self.aes.chmod(0o644)
  self.assertNotEqual(self.run_cli("xdata","1791987600000",self.aes,stdin=b"x").returncode,0)
 def test_no_leak_of_secret_on_errors(self):
  self.token.write_text("TOKEN_SUPER_SECRET\n");self.token.chmod(0o600)
  cp=self.run_cli("signature","wrong",self.secret,self.token)
  self.assertNotEqual(cp.returncode,0)
  self.assertNotIn(b"TOKEN_SUPER_SECRET",cp.stdout+cp.stderr)
  self.assertNotIn(b"test-offline",cp.stdout+cp.stderr)
 def test_source_has_no_api_credentials_embedded(self):
  s=SRC.read_text()
  self.assertNotIn("api.myxl.xlaxiata.co.id",s)
  self.assertNotIn("BASIC_AUTH=",s)
  self.assertNotIn("Ax-Api-Signature:",s)
  self.assertNotIn("AT+CMGR",s)
  self.assertNotIn("AT+CMGL",s)
  self.assertNotIn("system(",s)
  self.assertNotIn("exec(",s)

if __name__=="__main__":unittest.main()
