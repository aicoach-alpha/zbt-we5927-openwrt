import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const rpc = readFileSync(new URL('../../source/veci-core/files/rpcd-veci', import.meta.url), 'utf8');
const functionBody = name => {
	const start = rpc.indexOf(name + '() {');
	assert.ok(start >= 0, 'missing ' + name);
	const end = rpc.indexOf('\n}\n', start);
	assert.ok(end > start, 'unclosed ' + name);
	return rpc.slice(start, end);
};

test('RPC script remains syntactically valid shell', () => {
	execFileSync('sh', ['-n', new URL('../../source/veci-core/files/rpcd-veci', import.meta.url).pathname]);
});

test('network service audit logs after validation and before execution', () => {
	const fn = functionBody('method_service_action');
	assert.match(fn, /network_service_\$\{action\}_requested/);
	assert.match(fn, /logger -t veci-rpc-net/);
	assert.ok(fn.indexOf('network_service_') < fn.indexOf('if "$script" "$action"'));
	assert.ok(fn.indexOf('case "$service"') < fn.indexOf('network_service_'));
	assert.ok(fn.indexOf('case "$action"') < fn.indexOf('network_service_'));
});

test('Wi-Fi RPC logs request before reload and sanitized outcome after', () => {
	const fn = functionBody('method_wifi_reload');
	assert.match(fn, /wifi_reload_requested/);
	assert.match(fn, /wifi_reload_succeeded/);
	assert.match(fn, /wifi_reload_failed/);
	assert.ok(fn.indexOf('wifi_reload_requested') < fn.indexOf('if wifi reload'));
	assert.doesNotMatch(fn, /\$password|\$key|\$ssid|\$mac|\$imei|\$iccid/);
});
