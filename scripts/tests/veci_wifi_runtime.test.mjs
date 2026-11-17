import test from 'node:test';
import assert from 'node:assert/strict';
import { wifiRuntimeState } from '../../source/veci-core/veci/js/pages/wifi.js';

test('no AP runtime is marked unavailable, not Broadcasting', () => {
	assert.deepEqual(wifiRuntimeState({ disabled: '0' }, {}, null), {
		label: 'AP unavailable',
		tone: 'warning'
	});
});

test('radio up alone must not imply an AP interface', () => {
	assert.equal(wifiRuntimeState({}, {}, { radio: { up: true } }).label, 'AP unavailable');
});

test('radio down despite configured interface is unavailable', () => {
	const state = wifiRuntimeState({}, {}, { radio: { up: false }, iface: { section: 'default_radio0' } });
	assert.equal(state.label, 'AP unavailable');
});

test('runtime AP configuration never asserts external beacon visibility', () => {
	const state = wifiRuntimeState({}, {}, { radio: { up: true }, iface: { section: 'default_radio0' } });
	assert.equal(state.label, 'AP configured · beacon unverified');
	assert.equal(state.tone, 'warning');
});

test('disabled radio or iface remains disabled', () => {
	assert.equal(wifiRuntimeState({ disabled: '1' }, {}, null).label, 'Disabled');
	assert.equal(wifiRuntimeState({}, { disabled: '1' }, null).label, 'Disabled');
});
