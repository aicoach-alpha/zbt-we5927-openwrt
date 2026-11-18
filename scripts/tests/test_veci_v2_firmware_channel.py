"""Exercise manual stable-channel discovery through the native UI event handler."""
from pathlib import Path
import subprocess
import unittest

UI = Path(__file__).resolve().parents[2] / "rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2"


class FirmwareChannelTests(unittest.TestCase):
    def test_channel_manifest_and_request(self):
        script = """
const fs = require('fs'), vm = require('vm'), assert = require('assert/strict');
const nodes = new Map();
function node(id) {
  if (!nodes.has(id)) nodes.set(id, {addEventListener(type, fn) { this[type] = fn; }});
  return nodes.get(id);
}
const base = {schema:1, channel:'stable', board:'zbtlink,zbt-we5927', target:'ramips/mt76x8',
  supported_devices:['zbtlink,zbt-we5927'], available:true, size:7995392, sha256:'a'.repeat(64),
  firmware_url:'https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/v2/fw.bin'};
let body, calls = 0;
const document = {getElementById:node, addEventListener() {}};
const fetch = async (url, options) => {
  calls++;
  if (url === '/cgi-bin/veci2-verify?stable') {
    assert.equal(options.method,'POST');
    assert.equal(options.credentials,'omit');
    assert.equal(await options.body.text(), '1'.repeat(32) + base.sha256 + '7995392' + String.fromCharCode(10) + 'v2' + String.fromCharCode(10) + 'fw.bin' + String.fromCharCode(10));
    return {ok:true, json:async () => ({verified:true,sha256:base.sha256})};
  }
  assert.equal(url,'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/app-feed/channel-stable.json');
  assert.equal(options.credentials,'omit');
  assert.equal(options.referrerPolicy,'no-referrer');
  assert.equal(options.redirect,'error');
  return {ok:true, json:async () => body};
};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8') + ";sid='1'.repeat(32);",
  {document, Blob, fetch, setTimeout, clearTimeout, AbortController});
assert.equal(calls,0);
(async () => {
  for (const [change, message] of [
    [{available:false}, /Belum ada/], [{}, /7995392 byte/],
    [{available:'false'}, /gagal/], [{size:7995393}, /gagal/], [{sha256:'x'}, /gagal/],
    [{firmware_url:'https://example.org/fw'}, /gagal/], [{target:'other'}, /gagal/],
    [{supported_devices:[]}, /gagal/]
  ]) {
    body = {...base,...change};
    await node('firmware-channel-check').click();
    assert.match(node('firmware-channel-result').textContent, message);
    assert.equal(node('firmware-channel-check').disabled,false);
  }
  body = base;
  await node('firmware-channel-check').click();
  assert.equal(node('firmware-channel-verify').hidden,false);
  await node('firmware-channel-verify').click();
  assert.match(node('firmware-channel-result').textContent,/terverifikasi di router/);
})().catch(error => { console.error(error); process.exitCode=1; });
"""
        subprocess.run(["node", "-e", script, str(UI / "app.js")], check=True, timeout=8)
