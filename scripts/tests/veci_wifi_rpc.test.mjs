import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const rpc = readFileSync(new URL('../../source/veci-core/files/rpcd-veci', import.meta.url), 'utf8');
const acl = JSON.parse(readFileSync(new URL('../../source/veci-core/rpcd-acl.json', import.meta.url), 'utf8'));
const api = readFileSync(new URL('../../source/veci-core/veci/js/lib/api.js', import.meta.url), 'utf8');

test('RPC entrypoint is valid POSIX shell', () => {
	execFileSync('sh', ['-n', new URL('../../source/veci-core/files/rpcd-veci', import.meta.url).pathname]);
});

test('authenticated read-only RPC advertises and permits Wi-Fi runtime evidence', () => {
	assert.match(rpc, /"wifiRuntimeEvidence": \{\}/);
	assert.match(rpc, /wifiRuntimeEvidence\) method_wifi_runtime_evidence/);
	assert.ok(acl.veci.read.ubus.veci.includes('wifiRuntimeEvidence'));
	assert.equal(acl.veci.write.ubus.veci.includes('wifiRuntimeEvidence'), false);
	assert.match(api, /wifiRuntimeEvidence\(\)/);
});

test('evidence collector uses kernel sysfs, bounded hostapd RPC and no reset', () => {
	const start = rpc.indexOf('method_wifi_runtime_evidence() {');
	assert.ok(start >= 0);
	const end = rpc.indexOf('\n}\n', start);
	assert.ok(end > start);
	const fn = rpc.slice(start, end).split('\n').filter(line => !line.trimStart().startsWith('#')).join('\n');
	assert.match(fn, /\/sys\/class\/net\/\*/);
	assert.match(fn, /phy80211/);
	assert.match(fn, /hostapd\.\*/);
	assert.match(fn, /ubus -S -t [12]/);
	assert.match(fn, /json_add_array kernel_ifnames/);
	assert.match(fn, /json_add_array hostapd_ready_ifnames/);
	assert.doesNotMatch(fn, /\b(?:wifi\s+(?:reload|up|down)|ifup|ifdown|reboot|sysupgrade|rmmod|modprobe)\b/);
	assert.doesNotMatch(fn, /\buci\s+(?:set|commit|delete)\b/);
});
