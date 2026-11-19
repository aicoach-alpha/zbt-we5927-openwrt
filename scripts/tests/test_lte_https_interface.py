"""Run the production LTE probe against a local HTTPS endpoint with real curl."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Endpoint(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(self.server.code)
        self.end_headers()

    def log_message(self, *args):
        pass


class LteHttpsTests(unittest.TestCase):
    def test_https_requires_lte_interface_tls_and_http_success(self):
        source = (ROOT / "source/we5927-lte/files/usr/sbin/we5927-lte").read_text()
        self.assertEqual(source, (ROOT / "files/usr/sbin/we5927-lte").read_text())
        probe = source.split("https_ok() {", 1)[1].split("\n}", 1)[0]
        with tempfile.TemporaryDirectory() as folder:
            cert, key = (Path(folder) / name for name in ("cert.pem", "key.pem"))
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                            "-subj", "/CN=localhost", "-addext", "subjectAltName=IP:127.0.0.1",
                            "-days", "1", "-out", str(cert), "-keyout", str(key)],
                           check=True, capture_output=True)
            with HTTPServer(("127.0.0.1", 0), Endpoint) as server:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(cert, key)
                server.socket = ctx.wrap_socket(server.socket, server_side=True)
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                try:
                    url = f"https://127.0.0.1:{server.server_port}"
                    script = ('cfg() { echo "$TEST_DEV"; }\nhttps_ok() {' +
                              probe.replace("https://1.1.1.1", url) + "\n}\nhttps_ok")
                    for dev, code, ca, ok in [
                        ("lo", 200, cert, True), ("veci-no-such-if", 200, cert, False),
                        ("lo", 302, cert, False), ("lo", 503, cert, False),
                        ("lo", 200, "/etc/ssl/certs/ca-certificates.crt", False),
                    ]:
                        with self.subTest(dev=dev, code=code, trusted=ca == cert):
                            server.code = code
                            env = dict(os.environ, TEST_DEV=dev, CURL_CA_BUNDLE=str(ca),
                                       https_proxy="http://127.0.0.1:1", no_proxy="", NO_PROXY="")
                            result = subprocess.run(["sh", "-c", script], env=env, timeout=8)
                            self.assertEqual(result.returncode == 0, ok)
                finally:
                    server.shutdown()
                    worker.join()
