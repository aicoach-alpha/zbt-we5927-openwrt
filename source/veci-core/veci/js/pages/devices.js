import { badge, escapeHtml, setBusy } from '../lib/dom.js';
import { relativeExpiry } from '../lib/format.js';

function normalizeMac(value = '') {
	return String(value).trim().toLowerCase();
}

function reservationsFrom(configResult) {
	const values = configResult?.values || {};
	const byMac = new Map();

	for (const [section, config] of Object.entries(values)) {
		if (config['.type'] !== 'host') continue;
		const macs = Array.isArray(config.mac) ? config.mac : [config.mac];
		for (const mac of macs.filter(Boolean)) {
			byMac.set(normalizeMac(mac), { section, config });
		}
	}

	return byMac;
}

function safeHostLabel(hostname, mac) {
	const clean = String(hostname || '')
		.trim()
		.replace(/[^A-Za-z0-9_-]/g, '-')
		.replace(/-+/g, '-')
		.replace(/^-|-$/g, '')
		.slice(0, 32);
	if (clean) return clean;
	return `device-${normalizeMac(mac).replace(/:/g, '').slice(-6)}`;
}

export default {
	id: 'devices',
	title: 'Devices',
	eyebrow: 'CLIENTS',
	icon: 'devices',

	async render({ api, root, toast, confirm }) {
		const [result, dhcpConfig] = await Promise.all([
			api.veci('clients').catch(() => ({ clients: [] })),
			api.uciGet('dhcp').catch(() => ({ values: {} }))
		]);
		const clients = result.clients || [];
		const reservations = reservationsFrom(dhcpConfig);

		root.innerHTML = `
			<div class="page-intro">
				<div>
					<h2>Connected devices</h2>
					<p>See active DHCP clients and reserve their current address without opening the expert interface.</p>
				</div>
				<a class="button button-secondary" href="/cgi-bin/luci/admin/network/dhcp">Advanced DHCP</a>
			</div>

			<div class="summary-strip">
				<div><span>Connected</span><strong>${clients.length}</strong></div>
				<div><span>Reserved</span><strong>${[...reservations.values()].length}</strong></div>
			</div>

			<div class="panel table-panel">
				<div class="panel-heading">
					<div><p class="eyebrow">CURRENT LEASES</p><h3>${clients.length} device${clients.length === 1 ? '' : 's'}</h3></div>
					${badge(clients.length ? 'Active' : 'No leases', clients.length ? 'success' : 'neutral')}
				</div>
				<div class="table-scroll">
					<table class="veci-table">
						<thead><tr><th>Device</th><th>IP address</th><th>MAC address</th><th>Lease</th><th>Address</th><th></th></tr></thead>
						<tbody>
							${
								clients.length
									? clients
											.map(client => {
												const mac = normalizeMac(client.macaddr);
												const reservation = reservations.get(mac);
												const reservedIp = reservation?.config?.ip || '';
												return `
								<tr>
									<td><strong>${escapeHtml(client.hostname || 'Unknown device')}</strong></td>
									<td>${escapeHtml(client.ipaddr || '—')}</td>
									<td class="mono">${escapeHtml(client.macaddr || '—')}</td>
									<td>${escapeHtml(relativeExpiry(client.expires))}</td>
									<td>${reservation ? badge(`Reserved · ${reservedIp || client.ipaddr}`, 'info') : badge('Dynamic', 'neutral')}</td>
									<td class="table-actions">
										${
											reservation
												? `<button class="button button-compact button-secondary" data-release-reservation="${escapeHtml(reservation.section)}" data-device="${escapeHtml(client.hostname || client.macaddr)}" type="button">Remove reservation</button>`
												: `<button class="button button-compact button-secondary" data-reserve-mac="${escapeHtml(client.macaddr || '')}" data-reserve-ip="${escapeHtml(client.ipaddr || '')}" data-reserve-host="${escapeHtml(client.hostname || '')}" type="button">Reserve IP</button>`
										}
									</td>
								</tr>
							`;
											})
											.join('')
									: '<tr><td colspan="6" class="table-empty">No DHCP leases are currently visible.</td></tr>'
							}
						</tbody>
					</table>
				</div>
			</div>

			<div class="notice-card">
				<strong>What “Reserve IP” does</strong>
				<p>VeCI creates a standard OpenWrt DHCP host reservation using this device's MAC address and current IPv4 address, commits the DHCP configuration, then reloads dnsmasq.</p>
			</div>
		`;

		root.querySelectorAll('[data-reserve-mac]').forEach(button => {
			button.addEventListener('click', async () => {
				const mac = button.dataset.reserveMac;
				const ip = button.dataset.reserveIp;
				const host = button.dataset.reserveHost;
				if (!mac || !ip) {
					toast('This lease does not have enough information to reserve.', 'error');
					return;
				}

				const ok = await confirm({
					title: 'Reserve this IP address?',
					message: `${host || mac} will be assigned ${ip} by DHCP whenever possible.`,
					confirmLabel: 'Reserve IP'
				});
				if (!ok) return;

				setBusy(button, true, 'Saving…');
				try {
					await api.uciAdd('dhcp', 'host', {
						name: safeHostLabel(host, mac),
						mac,
						ip
					});
					await api.uciCommit('dhcp');
					await api.veci('serviceAction', { service: 'dnsmasq', action: 'reload' });
					toast(`Reserved ${ip} for ${host || mac}.`, 'success');
					await this.render({ api, root, toast, confirm });
				} catch (error) {
					toast(error.message || 'Could not create reservation.', 'error');
				} finally {
					setBusy(button, false);
				}
			});
		});

		root.querySelectorAll('[data-release-reservation]').forEach(button => {
			button.addEventListener('click', async () => {
				const section = button.dataset.releaseReservation;
				const device = button.dataset.device || 'this device';
				const ok = await confirm({
					title: 'Remove DHCP reservation?',
					message: `${device} will return to normal dynamic DHCP addressing after its lease renews.`,
					confirmLabel: 'Remove',
					tone: 'danger'
				});
				if (!ok) return;

				setBusy(button, true, 'Removing…');
				try {
					await api.uciDelete('dhcp', section);
					await api.uciCommit('dhcp');
					await api.veci('serviceAction', { service: 'dnsmasq', action: 'reload' });
					toast('DHCP reservation removed.', 'success');
					await this.render({ api, root, toast, confirm });
				} catch (error) {
					toast(error.message || 'Could not remove reservation.', 'error');
				} finally {
					setBusy(button, false);
				}
			});
		});
	}
};
