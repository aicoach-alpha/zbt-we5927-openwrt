import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { canActivateGuestOnRadio } from '../../source/veci-core/veci/js/pages/wifi.js';

const mainAp = [{
	radio: 'radio0',
	config: { mode: 'ap', disabled: '0' },
	runtime: { iface: { ifname: 'phy0-ap0' } }
}];
const healthy = { kernel_ifnames: ['phy0-ap0'], hostapd_ready_ifnames: ['phy0-ap0'] };

test('guest can activate only when parent AP exists and hostapd enabled', () => {
	assert.equal(canActivateGuestOnRadio(mainAp, 'radio0', healthy), true);
	assert.equal(canActivateGuestOnRadio(mainAp, 'radio0', { kernel_ifnames: [], hostapd_ready_ifnames: [] }), false);
	assert.equal(canActivateGuestOnRadio(mainAp, 'radio0', { kernel_ifnames: ['phy0-ap0'], hostapd_ready_ifnames: [] }), false);
});

test('stale netifd AP with no kernel interface cannot trigger guest activation', () => {
	assert.equal(canActivateGuestOnRadio(mainAp, 'radio0', null), false);
	assert.equal(canActivateGuestOnRadio(mainAp, 'radio0', {}), false);
});

test('guest creation cannot use another radio as evidence', () => {
	assert.equal(canActivateGuestOnRadio(mainAp, 'radio1', healthy), false);
	assert.equal(canActivateGuestOnRadio([{ ...mainAp[0], config: { mode: 'ap', disabled: '1' } }], 'radio0', healthy), false);
});

test('guest removal skips wireless reload when already disabled', () => {
	const source = readFileSync(new URL('../../source/veci-core/veci/js/pages/wifi.js', import.meta.url), 'utf8');
	assert.match(source, /reloadGuestServices\(api, \{ reloadWireless: !boolOption\(managedGuest\?\.disabled\) \}\)/);
	assert.match(source, /if \(!reloadWireless\) return/);
	assert.match(source, /Guest Wi-Fi cannot be activated: existing AP is unavailable or unverified/);
});
