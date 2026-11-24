import { escapeHtml, setBusy } from '../lib/dom.js?v=163';

function byType(config, type) {
	return Object.entries(config?.values || {})
		.filter(([, item]) => item['.type'] === type)
		.map(([id, data]) => ({ id, ...data }));
}

function safe(value) {
	return escapeHtml(value === undefined || value === null ? '—' : value);
}

function rows(items, cols, empty) {
	if (!items.length) return '<p class="panel-copy">' + safe(empty) + '</p>';
	return '<div class="table-scroll"><table class="veci-table"><thead><tr>' +
		cols.map(col => '<th>' + safe(col[0]) + '</th>').join('') +
		'</tr></thead><tbody>' +
		items.map(item => '<tr>' + cols.map(col =>
			'<td>' + safe(item[col[1]] || '—') + '</td>').join('') + '</tr>').join('') +
		'</tbody></table></div>';
}

export default {
	id: 'advanced',
	title: 'Advanced',
	eyebrow: 'NATIVE ADMINISTRATION',
	icon: 'system',
	async render({ api, root, toast, confirm }) {
		const [dhcp, firewall, network, system] = await Promise.all([
			api.uciGet('dhcp').catch(() => ({ values: {} })),
			api.uciGet('firewall').catch(() => ({ values: {} })),
			api.uciGet('network').catch(() => ({ values: {} })),
			api.uciGet('system').catch(() => ({ values: {} }))
		]);
		const lan = byType(dhcp, 'dhcp').find(s => s.interface === 'lan') || null;
		const zones = byType(firewall, 'zone');
		const routes = [...byType(network, 'route'), ...byType(network, 'route6')];
		const ntp = byType(system, 'timeserver')[0];
		const ntpServers = Array.isArray(ntp?.server) ? ntp.server.join(', ') : (ntp?.server || 'Not configured');
		root.innerHTML = [
			'<div class="page-intro"><div><h2>Advanced VeCI administration</h2>',
			'<p>Native router configuration. Changes are applied only when explicitly confirmed.</p></div></div>',
			'<article class="panel"><div class="panel-heading"><div><p class="eyebrow">DHCP</p><h3>LAN address pool</h3></div></div>',
			lan ? [
				'<form id="native-dhcp" class="inline-setting-form">',
				'<label class="field"><span>Start offset (1–254)</span><input name="start" type="number" min="1" max="254" required value="' + safe(lan.start || 100) + '"></label>',
				'<label class="field"><span>Address count (1–254)</span><input name="limit" type="number" min="1" max="254" required value="' + safe(lan.limit || 150) + '"></label>',
				'<label class="field"><span>Lease duration (e.g. 12h)</span><input name="leasetime" maxlength="12" required value="' + safe(lan.leasetime || '12h') + '"></label>',
				'<button class="button button-primary" type="submit">Save DHCP pool</button></form>',
				'<p class="panel-copy">Changes can affect clients at lease renewal. No automatic network restart.</p>'
			].join('') : '<p class="panel-copy">No LAN DHCP section; editing is unavailable.</p>',
			'</article>',
			'<article class="panel"><div class="panel-heading"><div><p class="eyebrow">FIREWALL</p><h3>Zones and default policies</h3></div></div>',
			rows(zones, [['Zone', 'name'], ['Networks', 'network'], ['Incoming', 'input'], ['Outgoing', 'output'], ['Forwarding', 'forward']], 'No firewall zones returned.'),
			'<p class="panel-copy">For editable firewall rules and port forwarding use the Security page. Critical zone policies are shown read-only to avoid accidental LAN lockout.</p>',
			'<a class="button button-secondary" href="#/security">Manage firewall rules</a></article>',
			'<article class="panel"><div class="panel-heading"><div><p class="eyebrow">ROUTING</p><h3>Configured static routes</h3></div></div>',
			rows(routes, [['Interface', 'interface'], ['Destination', 'target'], ['Netmask', 'netmask'], ['Gateway', 'gateway']], 'No additional static routes configured.'),
			'<a class="button button-secondary" href="#/internet">Manage interfaces</a></article>',
			'<article class="panel"><div class="panel-heading"><div><p class="eyebrow">TIME</p><h3>NTP servers</h3></div></div>',
			'<p class="panel-copy">' + safe(ntpServers) + '</p></article>',
			'<article class="panel"><div class="panel-heading"><div><p class="eyebrow">SERVICES</p><h3>Selective service reload</h3></div></div>',
			'<div class="cellular-actions"><button type="button" data-reload="dnsmasq" class="button button-secondary">Reload DNS/DHCP</button>',
			'<button type="button" data-reload="firewall" class="button button-secondary">Reload firewall</button></div>',
			'<p class="panel-copy">Network and Wi-Fi are not restarted from this page.</p></article>',
			'<article class="panel"><div class="panel-heading"><div><p class="eyebrow">SECURITY</p><h3>Change administrator password</h3></div></div>',
			'<form id="native-password" class="inline-setting-form">',
			'<label class="field"><span>New password (8–72 characters)</span><input name="password" type="password" minlength="8" maxlength="72" autocomplete="new-password" required></label>',
			'<label class="field"><span>Confirm new password</span><input name="confirm" type="password" minlength="8" maxlength="72" autocomplete="new-password" required></label>',
			'<button class="button button-primary" type="submit">Change password</button></form></article>',
			'<article class="panel"><div class="panel-heading"><div><p class="eyebrow">BACKUP</p><h3>Download router configuration</h3></div></div>',
			'<p class="panel-copy">Creates an OpenWrt sysupgrade configuration archive on the router in temporary RAM, downloads it over this authenticated session, and removes the temporary copy. The backup contains credentials; store it securely.</p>',
			'<button id="native-backup" class="button button-primary" type="button">Download backup (.tar.gz)</button>',
			'<p id="native-backup-status" role="status" class="panel-copy">No backup generated.</p></article>'
		].join('');

		const dhcpForm = root.querySelector('#native-dhcp');
		dhcpForm?.addEventListener('submit', async event => {
			event.preventDefault();
			const start = Number(dhcpForm.elements.namedItem('start').value);
			const limit = Number(dhcpForm.elements.namedItem('limit').value);
			const leasetime = dhcpForm.elements.namedItem('leasetime').value.trim();
			if (!Number.isInteger(start) || !Number.isInteger(limit) || start < 1 ||
				limit < 1 || start > 254 || limit > 254 || start + limit > 255 ||
				!/^([1-9][0-9]{0,5})([smhdw])$/.test(leasetime)) {
				toast('Invalid DHCP pool or lease duration.', 'error');
				return;
			}
			if (!(await confirm({ title: 'Save DHCP pool?', message: 'Affected devices may receive new addresses when their lease renews.', confirmLabel: 'Save DHCP' }))) return;
			const button = dhcpForm.querySelector('button');
			setBusy(button, true, 'Saving…');
			try {
				await api.uciSet('dhcp', lan.id, { start: String(start), limit: String(limit), leasetime });
				await api.uciCommit('dhcp');
				const result = await api.veci('serviceAction', { service: 'dnsmasq', action: 'reload' });
				if (!result.ok) throw Error(result.error || 'DNS/DHCP reload unsuccessful');
				toast('DHCP pool saved and service reloaded.', 'success');
			} catch (error) {
				toast(error.message || 'DHCP change not completed.', 'error');
			} finally {
				setBusy(button, false);
			}
		});

		root.querySelectorAll('[data-reload]').forEach(button => button.addEventListener('click', async () => {
			const service = button.dataset.reload;
			if (!['dnsmasq', 'firewall'].includes(service)) return;
			if (!(await confirm({ title: 'Reload ' + service + '?', message: 'Active connections may be affected.', confirmLabel: 'Reload' }))) return;
			setBusy(button, true, 'Reloading…');
			try {
				const result = await api.veci('serviceAction', { service, action: 'reload' });
				if (!result.ok) throw Error(result.error || 'Service reload failed');
				toast('Reloaded ' + service, 'success');
			} catch (error) {
				toast(error.message || 'Reload failed', 'error');
			} finally { setBusy(button, false); }
		}));

		const passwordForm = root.querySelector('#native-password');
		passwordForm?.addEventListener('submit', async event => {
			event.preventDefault();
			const password = passwordForm.elements.namedItem('password').value;
			const repeated = passwordForm.elements.namedItem('confirm').value;
			if (password !== repeated || password.length < 8 || password.length > 72) {
				toast('Passwords do not match or length is invalid.', 'error');
				return;
			}
			if (!(await confirm({ title: 'Change administrator password?', message: 'All future router logins will use the new password.', confirmLabel: 'Change password' }))) return;
			const button = passwordForm.querySelector('button');
			setBusy(button, true, 'Changing…');
			try {
				const result = await api.veci('changeAdminPassword', { password });
				if (!result.ok) throw Error(result.error || 'Password change failed');
				toast('Password changed. Use it for your next login.', 'success');
			} catch (error) {
				toast(error.message || 'Password change failed.', 'error');
			} finally {
				passwordForm.reset();
				setBusy(button, false);
			}
		});

		const backup = root.querySelector('#native-backup');
		backup?.addEventListener('click', async () => {
			const status = root.querySelector('#native-backup-status');
			setBusy(backup, true, 'Preparing backup…');
			let id = '';
			try {
				const started = await api.veci('backupStart', {}, { timeout: 45000 });
				if (!started.ok || !/^[A-Za-z0-9]{8}$/.test(started.id) ||
					!Number.isInteger(started.size) || started.size < 1 || started.size > 2097152 ||
					started.chunk_size !== 12288) throw Error(started.error || 'Invalid backup response');
				id = started.id;
				const parts = [];
				const count = Math.ceil(started.size / started.chunk_size);
				let received = 0;
				for (let index = 0; index < count; index++) {
					const chunk = await api.veci('backupRead', { id, sequence: index }, { timeout: 20000 });
					if (!chunk.ok || chunk.sequence !== index || typeof chunk.data !== 'string') throw Error(chunk.error || 'Backup chunk failed');
					const raw = atob(chunk.data);
					const bytes = Uint8Array.from(raw, char => char.charCodeAt(0));
					received += bytes.length;
					parts.push(bytes);
				}
				if (received !== started.size) throw Error('Downloaded backup size differs from source');
				const blob = new Blob(parts, { type: 'application/gzip' });
				const url = URL.createObjectURL(blob);
				const link = document.createElement('a');
				link.href = url;
				link.download = 'veci-we5927-config-' + new Date().toISOString().slice(0, 10) + '.tar.gz';
				document.body.appendChild(link);
				link.click();
				link.remove();
				URL.revokeObjectURL(url);
				status.textContent = 'Backup downloaded. Keep it in a secure location.';
				toast('Backup downloaded.', 'success');
			} catch (error) {
				status.textContent = 'Backup was not downloaded.';
				toast(error.message || 'Backup failed.', 'error');
			} finally {
				if (id) await api.veci('backupClear', { id }).catch(() => {});
				setBusy(backup, false);
			}
		});
	}
};
