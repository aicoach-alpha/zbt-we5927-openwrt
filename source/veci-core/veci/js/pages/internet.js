import { badge, escapeHtml, setBusy } from '../lib/dom.js';
import { firstAddress, humanProtocol } from '../lib/format.js';

function isUplink(iface) {
	return (
		(iface.route || []).some(route => route.target === '0.0.0.0' || route.target === '::') ||
		/^(wan|wan6|lte|wwan|cellular|modem)/i.test(iface.interface || '')
	);
}

function isCellular(iface, capabilities) {
	return Boolean(capabilities && capabilities.cellular && /^(lte|wwan|cellular|modem)/i.test(iface.interface || ''));
}

function validIpv4(value, allowBlank) {
	if (allowBlank && !value) return true;
	const parts = String(value || '').split('.');
	return (
		parts.length === 4 && parts.every(part => /^\d{1,3}$/.test(part) && Number(part) >= 0 && Number(part) <= 255)
	);
}

function parseDns(value) {
	const servers = String(value || '')
		.split(/[\s,]+/)
		.map(item => item.trim())
		.filter(Boolean);
	if (servers.some(server => !validIpv4(server, false))) throw new Error('DNS servers must be valid IPv4 addresses.');
	return servers;
}

function listText(value) {
	if (Array.isArray(value)) return value.join(' ');
	return String(value || '');
}

function runtimeDns(iface) {
	const value = iface['dns-server'] || iface.dns_server || [];
	if (Array.isArray(value)) return value.join(', ');
	return String(value || 'Automatic');
}

export default {
	id: 'internet',
	title: 'Internet',
	eyebrow: 'CONNECTIVITY',
	icon: 'globe',

	async render({ api, state, root, toast, navigate, confirm }) {
		const results = await Promise.all([api.interfaces(), api.uciGet('network').catch(() => ({ values: {} }))]);
		const interfaces = results[0].interface || [];
		const configs = results[1].values || {};
		state.interfaces = interfaces;

		const ordered = interfaces.slice().sort((a, b) => Number(isUplink(b)) - Number(isUplink(a)));
		const editable = new Map();

		const cards = ordered
			.map(iface => {
				const config = configs[iface.interface] || {};
				const cellular = isCellular(iface, state.capabilities);
				const currentProto = config.proto || iface.proto || '';
				const canEdit =
					isUplink(iface) &&
					!cellular &&
					config['.type'] === 'interface' &&
					(currentProto === 'dhcp' || currentProto === 'static');
				if (canEdit) editable.set(iface.interface, { iface, config });

				const route = (iface.route || []).find(item => item.nexthop);
				let actions = '';
				if (cellular) {
					actions +=
						'<button class="button button-secondary" data-go-cellular type="button">Manage cellular</button>';
				}
				if (canEdit) {
					actions +=
						'<button class="button button-secondary" data-edit-internet="' +
						escapeHtml(iface.interface) +
						'" type="button">Internet settings</button>';
				}
				if (isUplink(iface) && !cellular) {
					actions +=
						'<button class="button button-secondary" data-iface="' +
						escapeHtml(iface.interface) +
						'" data-action="' +
						(iface.up ? 'down' : 'up') +
						'" type="button">' +
						(iface.up ? 'Disconnect' : 'Connect') +
						'</button>';
				}

				return (
					'<article class="connection-card ' +
					(isUplink(iface) ? 'connection-uplink' : '') +
					'">' +
					'<div class="connection-main"><div class="connection-icon">' +
					(isUplink(iface) ? '↗' : '↔') +
					'</div><div><div class="connection-title"><h3>' +
					escapeHtml(iface.interface) +
					'</h3>' +
					badge(iface.up ? 'Online' : 'Offline', iface.up ? 'success' : 'neutral') +
					(isUplink(iface) ? badge('Internet', 'info') : '') +
					(cellular ? badge('Cellular managed', 'neutral') : '') +
					'</div><p>' +
					escapeHtml(humanProtocol(iface.proto)) +
					' · ' +
					escapeHtml(iface.l3_device || iface.device || 'No device') +
					'</p></div></div>' +
					'<div class="connection-meta">' +
					'<div><span>IP address</span><strong>' +
					escapeHtml(firstAddress(iface)) +
					'</strong></div>' +
					'<div><span>Gateway</span><strong>' +
					escapeHtml((route && route.nexthop) || '—') +
					'</strong></div>' +
					'<div><span>DNS</span><strong>' +
					escapeHtml(runtimeDns(iface)) +
					'</strong></div>' +
					'<div><span>Uptime</span><strong>' +
					(iface.uptime ? escapeHtml(String(Math.floor(iface.uptime / 60))) + ' min' : '—') +
					'</strong></div>' +
					'</div><div class="connection-actions">' +
					actions +
					'</div></article>'
				);
			})
			.join('');

		root.innerHTML =
			'<div class="page-intro"><div><h2>Internet connections</h2><p>See how this router reaches the Internet. Normal DHCP and static uplinks can be edited here; modem-managed links stay on Cellular.</p></div><a class="button button-secondary" href="/cgi-bin/luci/admin/network/network">Advanced interfaces</a></div>' +
			'<div class="card-list">' +
			cards +
			'</div>' +
			'<section id="internet-editor" class="panel editor-panel hidden">' +
			'<div class="panel-heading"><div><p class="eyebrow">INTERNET SETTINGS</p><h3 id="internet-editor-title">Uplink</h3></div><button id="internet-editor-close" class="button button-secondary" type="button">Cancel</button></div>' +
			'<form id="internet-editor-form"><input id="internet-section" type="hidden" />' +
			'<div class="editor-grid"><label class="field"><span>Connection type</span><select id="internet-proto"><option value="dhcp">Automatic IP (DHCP)</option><option value="static">Static IPv4</option></select></label>' +
			'<label class="field field-wide"><span>DNS servers (optional)</span><input id="internet-dns" type="text" placeholder="1.1.1.1 1.0.0.1" autocomplete="off" /><small>Leave blank to use automatic DNS on DHCP connections.</small></label></div>' +
			'<div id="static-internet-fields" class="editor-grid hidden"><label class="field"><span>IPv4 address</span><input id="internet-ipaddr" type="text" inputmode="decimal" placeholder="192.0.2.10" /></label>' +
			'<label class="field"><span>Netmask</span><input id="internet-netmask" type="text" inputmode="decimal" value="255.255.255.0" /></label>' +
			'<label class="field"><span>Gateway</span><input id="internet-gateway" type="text" inputmode="decimal" placeholder="192.0.2.1" /></label></div>' +
			'<div class="editor-warning">Applying Internet settings reloads OpenWrt networking and may temporarily disconnect this router from the Internet.</div>' +
			'<div class="editor-actions"><button id="internet-save" class="button button-primary" type="submit">Apply Internet settings</button></div></form></section>';

		const editor = root.querySelector('#internet-editor');
		const form = root.querySelector('#internet-editor-form');
		const proto = root.querySelector('#internet-proto');
		const staticFields = root.querySelector('#static-internet-fields');

		function updateProtocolFields() {
			staticFields.classList.toggle('hidden', proto.value !== 'static');
		}

		function closeEditor() {
			editor.classList.add('hidden');
			form.reset();
			updateProtocolFields();
		}

		root.querySelectorAll('[data-go-cellular]').forEach(button => {
			button.addEventListener('click', () => navigate('cellular'));
		});

		root.querySelectorAll('[data-edit-internet]').forEach(button => {
			button.addEventListener('click', () => {
				const entry = editable.get(button.dataset.editInternet);
				if (!entry) return;
				const config = entry.config;
				const iface = entry.iface;
				root.querySelector('#internet-section').value = iface.interface;
				root.querySelector('#internet-editor-title').textContent = iface.interface;
				proto.value = config.proto || iface.proto || 'dhcp';
				root.querySelector('#internet-dns').value = listText(config.dns);
				root.querySelector('#internet-ipaddr').value = String(config.ipaddr || '');
				root.querySelector('#internet-netmask').value = String(config.netmask || '255.255.255.0');
				root.querySelector('#internet-gateway').value = String(config.gateway || '');
				updateProtocolFields();
				editor.classList.remove('hidden');
				editor.scrollIntoView({ behavior: 'smooth', block: 'start' });
			});
		});

		root.querySelector('#internet-editor-close')?.addEventListener('click', closeEditor);
		proto?.addEventListener('change', updateProtocolFields);

		form?.addEventListener('submit', async event => {
			event.preventDefault();
			const section = root.querySelector('#internet-section').value;
			if (!editable.has(section)) return;

			const protocol = proto.value;
			let dns;
			try {
				dns = parseDns(root.querySelector('#internet-dns').value);
			} catch (error) {
				toast(error.message, 'error');
				return;
			}

			const values = { proto: protocol };
			if (protocol === 'static') {
				const ipaddr = root.querySelector('#internet-ipaddr').value.trim();
				const netmask = root.querySelector('#internet-netmask').value.trim();
				const gateway = root.querySelector('#internet-gateway').value.trim();
				if (!validIpv4(ipaddr, false) || !validIpv4(netmask, false) || !validIpv4(gateway, false)) {
					toast('Static IP, netmask and gateway must be valid IPv4 addresses.', 'error');
					return;
				}
				values.ipaddr = ipaddr;
				values.netmask = netmask;
				values.gateway = gateway;
			}

			if (dns.length) {
				values.dns = dns;
				if (protocol === 'dhcp') values.peerdns = '0';
			} else if (protocol === 'dhcp') {
				values.peerdns = '1';
			}

			const allowed = await confirm({
				title: 'Apply Internet settings to ' + section + '?',
				message: 'OpenWrt networking will reload and Internet access may drop briefly.',
				confirmLabel: 'Apply settings'
			});
			if (!allowed) return;

			const save = root.querySelector('#internet-save');
			setBusy(save, true, 'Applying…');
			try {
				await api.uciSet('network', section, values);
				if (protocol === 'dhcp') {
					for (const option of ['ipaddr', 'netmask', 'gateway']) {
						await api.uciDelete('network', section, option).catch(() => {});
					}
				}
				if (!dns.length) await api.uciDelete('network', section, 'dns').catch(() => {});
				await api.uciCommit('network');
				const result = await api.veci('serviceAction', { service: 'network', action: 'reload' });
				if (result.ok === false) throw new Error(result.error || 'Network reload failed');
				toast(section + ' settings applied.', 'success');
				closeEditor();
				setTimeout(() => window.dispatchEvent(new HashChangeEvent('hashchange')), 1600);
			} catch (error) {
				toast(error.message || 'Could not apply Internet settings.', 'error');
			} finally {
				setBusy(save, false);
			}
		});

		root.querySelectorAll('[data-iface][data-action]').forEach(button => {
			button.addEventListener('click', async () => {
				const iface = button.dataset.iface;
				const action = button.dataset.action;
				setBusy(button, true);
				try {
					await api.interfaceAction(iface, action);
					toast(iface + ': ' + (action === 'up' ? 'connect requested' : 'disconnect requested'), 'success');
					setTimeout(() => window.dispatchEvent(new HashChangeEvent('hashchange')), 1200);
				} catch (error) {
					toast(error.message, 'error');
				} finally {
					setBusy(button, false);
				}
			});
		});
	}
};
