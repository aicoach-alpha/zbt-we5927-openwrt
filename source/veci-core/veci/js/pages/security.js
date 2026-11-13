import { badge, escapeHtml, setBusy } from '../lib/dom.js';

function sections(values = {}, type) {
	return Object.entries(values)
		.filter(([, value]) => value['.type'] === type)
		.map(([section, value]) => ({ section, ...value }));
}

function protocolLabel(value) {
	const list = Array.isArray(value) ? value : String(value || 'tcp udp').split(/\s+/);
	return list.map(item => item.toUpperCase()).join(' + ');
}

function safeName(value) {
	return String(value || '')
		.trim()
		.replace(/[^A-Za-z0-9 _.-]/g, '')
		.slice(0, 48);
}

function validPort(value) {
	const port = Number(value);
	return Number.isInteger(port) && port >= 1 && port <= 65535;
}

function validIpv4(value) {
	const parts = String(value).split('.');
	return (
		parts.length === 4 && parts.every(part => /^\d{1,3}$/.test(part) && Number(part) >= 0 && Number(part) <= 255)
	);
}

export default {
	id: 'security',
	title: 'Security',
	eyebrow: 'PROTECTION',
	icon: 'shield',

	async render({ api, root, toast, confirm }) {
		const firewall = await api.uciGet('firewall').catch(() => ({ values: {} }));
		const values = firewall.values || {};
		const zones = sections(values, 'zone');
		const rules = sections(values, 'rule');
		const redirects = sections(values, 'redirect');
		const lanZones = zones.filter(zone => {
			const networks = Array.isArray(zone.network) ? zone.network : String(zone.network || '').split(/\s+/);
			return networks.includes('lan') || zone.name === 'lan';
		});
		const defaultDestZone = lanZones[0]?.name || 'lan';

		root.innerHTML = `
			<div class="page-intro">
				<div><h2>Security center</h2><p>A simpler view of firewall protection, exposed services and traffic rules.</p></div>
				<a class="button button-secondary" href="/cgi-bin/luci/admin/network/firewall">Advanced firewall</a>
			</div>

			<div class="security-summary">
				<article class="security-score">
					<div class="security-shield">✓</div>
					<div>
						<p class="eyebrow">FIREWALL STATUS</p>
						<h3>${zones.length ? 'Configured' : 'Review configuration'}</h3>
						<p>${zones.length} zones · ${rules.length} traffic rules · ${redirects.length} port forwards</p>
					</div>
				</article>
				<article class="panel">
					<div class="panel-heading"><div><p class="eyebrow">EXPOSURE</p><h3>Port forwards</h3></div>${badge(String(redirects.length), redirects.length ? 'warning' : 'success')}</div>
					<p class="panel-copy">${redirects.length ? 'Only keep Internet-facing forwards that you still need.' : 'No configured firewall redirects were detected.'}</p>
				</article>
			</div>

			<section class="panel port-forward-panel">
				<div class="panel-heading">
					<div><p class="eyebrow">PORT FORWARDING</p><h3>Internet → local device</h3></div>
					<button id="new-port-forward" class="button button-primary" type="button">Add port forward</button>
				</div>

				<div class="table-scroll">
					<table class="veci-table">
						<thead><tr><th>Name</th><th>Protocol</th><th>Internet port</th><th>Destination</th><th></th></tr></thead>
						<tbody>
							${
								redirects.length
									? redirects
											.map(
												item => `
								<tr>
									<td><strong>${escapeHtml(item.name || item.section)}</strong></td>
									<td>${escapeHtml(protocolLabel(item.proto))}</td>
									<td class="mono">${escapeHtml(item.src_dport || '—')}</td>
									<td class="mono">${escapeHtml(item.dest_ip || '—')}:${escapeHtml(item.dest_port || item.src_dport || '—')}</td>
									<td class="table-actions"><button class="button button-compact button-danger" data-delete-forward="${escapeHtml(item.section)}" data-forward-name="${escapeHtml(item.name || item.section)}" type="button">Remove</button></td>
								</tr>
							`
											)
											.join('')
									: '<tr><td colspan="5" class="table-empty">No port forwards configured.</td></tr>'
							}
						</tbody>
					</table>
				</div>

				<form id="port-forward-editor" class="editor-panel hidden">
					<div class="editor-grid">
						<label class="field">
							<span>Name</span>
							<input id="forward-name" type="text" maxlength="48" value="Port forward" required />
						</label>
						<label class="field">
							<span>Protocol</span>
							<select id="forward-proto">
								<option value="tcp">TCP</option>
								<option value="udp">UDP</option>
								<option value="tcp udp">TCP + UDP</option>
							</select>
						</label>
						<label class="field">
							<span>Internet port</span>
							<input id="forward-src-port" type="number" min="1" max="65535" placeholder="443" required />
						</label>
						<label class="field">
							<span>Local IP address</span>
							<input id="forward-dest-ip" type="text" inputmode="decimal" placeholder="192.168.1.100" required />
						</label>
						<label class="field">
							<span>Local port</span>
							<input id="forward-dest-port" type="number" min="1" max="65535" placeholder="443" required />
						</label>
					</div>
					<div class="editor-warning">A port forward makes a service on your local network reachable from the Internet. Only expose services you understand and keep them patched.</div>
					<div class="editor-actions">
						<button id="cancel-port-forward" class="button button-secondary" type="button">Cancel</button>
						<button id="save-port-forward" class="button button-primary" type="submit">Create port forward</button>
					</div>
				</form>
			</section>

			<div class="content-grid content-grid-2">
				<article class="panel">
					<div class="panel-heading"><div><p class="eyebrow">ZONES</p><h3>Trust boundaries</h3></div></div>
					<div class="zone-list">
						${
							zones.length
								? zones
										.map(
											zone => `
							<div class="zone-row">
								<div><strong>${escapeHtml(zone.name || zone.section)}</strong><span>${escapeHtml(Array.isArray(zone.network) ? zone.network.join(', ') : zone.network || 'No network')}</span></div>
								<div class="zone-policy"><span>IN ${escapeHtml(zone.input || '—')}</span><span>FWD ${escapeHtml(zone.forward || '—')}</span><span>OUT ${escapeHtml(zone.output || '—')}</span></div>
							</div>
						`
										)
										.join('')
								: '<p class="panel-copy">No firewall zones found.</p>'
						}
					</div>
				</article>
				<article class="panel">
					<div class="panel-heading"><div><p class="eyebrow">GUIDANCE</p><h3>Keep the router safe</h3></div></div>
					<ul class="check-list">
						<li><span>✓</span> Keep the admin UI on trusted LAN/Wi-Fi only.</li>
						<li><span>✓</span> Remove unused port forwards.</li>
						<li><span>✓</span> Use WPA2/WPA3 with a strong Wi-Fi password.</li>
						<li><span>✓</span> Keep OpenWrt packages and firmware intentionally maintained.</li>
					</ul>
				</article>
			</div>
		`;

		const editor = root.querySelector('#port-forward-editor');
		root.querySelector('#new-port-forward')?.addEventListener('click', () => {
			editor.classList.remove('hidden');
			root.querySelector('#forward-src-port')?.focus();
		});
		root.querySelector('#cancel-port-forward')?.addEventListener('click', () => editor.classList.add('hidden'));

		editor?.addEventListener('submit', async event => {
			event.preventDefault();
			const name = safeName(root.querySelector('#forward-name').value) || 'Port forward';
			const proto = root.querySelector('#forward-proto').value;
			const srcPort = root.querySelector('#forward-src-port').value.trim();
			const destIp = root.querySelector('#forward-dest-ip').value.trim();
			const destPort = root.querySelector('#forward-dest-port').value.trim();
			const saveButton = root.querySelector('#save-port-forward');

			if (!validPort(srcPort) || !validPort(destPort)) {
				toast('Ports must be between 1 and 65535.', 'error');
				return;
			}
			if (!validIpv4(destIp)) {
				toast('Enter a valid local IPv4 address.', 'error');
				return;
			}

			const ok = await confirm({
				title: 'Create Internet port forward?',
				message: `${protocolLabel(proto)} port ${srcPort} will be forwarded to ${destIp}:${destPort}.`,
				confirmLabel: 'Create'
			});
			if (!ok) return;

			setBusy(saveButton, true, 'Creating…');
			try {
				await api.uciAdd('firewall', 'redirect', {
					name,
					src: 'wan',
					src_dport: srcPort,
					dest: defaultDestZone,
					dest_ip: destIp,
					dest_port: destPort,
					proto,
					target: 'DNAT',
					family: 'ipv4'
				});
				await api.uciCommit('firewall');
				await api.veci('serviceAction', { service: 'firewall', action: 'reload' });
				toast('Port forward created.', 'success');
				await this.render({ api, root, toast, confirm });
			} catch (error) {
				toast(error.message || 'Could not create port forward.', 'error');
			} finally {
				setBusy(saveButton, false);
			}
		});

		root.querySelectorAll('[data-delete-forward]').forEach(button => {
			button.addEventListener('click', async () => {
				const section = button.dataset.deleteForward;
				const name = button.dataset.forwardName || section;
				const ok = await confirm({
					title: 'Remove port forward?',
					message: `${name} will no longer accept new connections from the Internet.`,
					confirmLabel: 'Remove',
					tone: 'danger'
				});
				if (!ok) return;

				setBusy(button, true, 'Removing…');
				try {
					await api.uciDelete('firewall', section);
					await api.uciCommit('firewall');
					await api.veci('serviceAction', { service: 'firewall', action: 'reload' });
					toast('Port forward removed.', 'success');
					await this.render({ api, root, toast, confirm });
				} catch (error) {
					toast(error.message || 'Could not remove port forward.', 'error');
				} finally {
					setBusy(button, false);
				}
			});
		});
	}
};
