import test from 'node:test';
import assert from 'node:assert/strict';
import { wifiRuntimeState } from '../../source/veci-core/veci/js/pages/wifi.js';

const iface = { radio: { up: true }, iface: { section: 'default_radio0', ifname: 'phy0-ap0' } };
const healthy = { kernel_ifnames: ['phy0-ap0'], hostapd_ready_ifnames: ['phy0-ap0'] };

test('UCI enabled without netifd interface remains unavailable', () => {
	assert.equal(wifiRuntimeState({}, {}, null, healthy).label, 'AP unavailable');
});

test('stale netifd phy0-ap0 cannot mask a missing kernel interface', () => {
	assert.deepEqual(wifiRuntimeState({}, {}, iface, { kernel_ifnames: [], hostapd_ready_ifnames: [] }), {
		label: 'AP interface missing',
		tone: 'warning'
	});
});

test('kernel AP exists but hostapd is absent or disabled', () => {
	assert.equal(
		wifiRuntimeState({}, {}, iface, { kernel_ifnames: ['phy0-ap0'], hostapd_ready_ifnames: [] }).label,
		'AP not ready'
	);
});

test('kernel AP and hostapd both ready do not prove externally visible SSID', () => {
	const state = wifiRuntimeState({}, {}, iface, healthy);
	assert.equal(state.label, 'AP running · beacon unverified');
	assert.notEqual(state.tone, 'success');
});

test('missing evidence on older firmware never falsely reports broadcasting', () => {
	assert.equal(wifiRuntimeState({}, {}, iface, null).label, 'AP status unverified');
	assert.equal(wifiRuntimeState({}, {}, { radio: { up: true }, iface: { section: 'x' } }, healthy).label, 'AP status unverified');
});

test('radio down despite a configured interface is unavailable', () => {
	assert.equal(wifiRuntimeState({}, {}, { radio: { up: false }, iface: iface.iface }, healthy).label, 'AP unavailable');
});

test('explicit radio or AP disable is reflected correctly', () => {
	assert.equal(wifiRuntimeState({ disabled: '1' }, {}, null, healthy).label, 'Disabled');
	assert.equal(wifiRuntimeState({}, { disabled: '1' }, null, healthy).label, 'Disabled');
	assert.equal(wifiRuntimeState({ disabled: 1 }, {}, null, healthy).label, 'Disabled');
});
