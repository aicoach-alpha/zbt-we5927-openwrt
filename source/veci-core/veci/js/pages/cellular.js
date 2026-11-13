import { badge, escapeHtml, setBusy } from '../lib/dom.js';

function metric(label, value, suffix = '') {
	const display = value === undefined || value === null || value === '' ? '—' : `${value}${suffix}`;
	return `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(display)}</strong></div>`;
}

export default {
	id: 'cellular',
	title: 'Cellular',
	navLabel: 'Cellular',
	eyebrow: 'MOBILE NETWORK',
	icon: 'signal',
	capability: 'cellular',

	async render({ api, root, toast, confirm }) {
		const [status, quota] = await Promise.all([
			api.cellularStatus(),
			api.call('veci.quota', 'status', {}).catch(() => null)
		]);

		const signalPercent = Number.isFinite(Number(status.signal_percent)) ? Number(status.signal_percent) : null;
		const signalDbm = Number.isFinite(Number(status.signal_dbm)) ? Number(status.signal_dbm) : null;
		const online = status.online === true || status.online === 1 || status.online === '1';
		const sim = status.sim || '—';
		const model = status.model || status.manufacturer || 'Cellular modem';
		const operator = status.operator || 'No operator';
		const technology = status.access_tech || status.registration_status || 'Unknown';

		// A native carrier-authenticated snapshot is the only source of numeric
		// quota. Other states (including uninstalled quota service) fail closed.
		const quotaReady = quota?.schema === 1 && quota?.provider === 'xl' &&
			quota?.state === 'ready' && quota?.source === 'carrier_authenticated' &&
			typeof quota?.total_bytes === 'number' && Number.isFinite(quota.total_bytes) &&
			typeof quota?.remaining_bytes === 'number' && Number.isFinite(quota.remaining_bytes) &&
			quota.total_bytes > 0 && quota.remaining_bytes >= 0 &&
			quota.remaining_bytes <= quota.total_bytes;
		const quotaState = quotaReady ? 'Verified balance' :
			quota?.state === 'not_connected' ? 'XL account not connected' :
			quota?.state === 'stale' ? 'Balance expired' : 'Balance unavailable';
		const quotaSize = n => (n / 1073741824).toFixed(2) + ' GB';

		root.innerHTML = `
			<div class="page-intro">
				<div>
					<h2>Mobile connection</h2>
					<p>Signal, SIM and modem health from the cellular integration installed on this router.</p>
				</div>
				${badge(online ? 'Online' : 'Offline', online ? 'success' : 'danger')}
			</div>

			<div class="cellular-hero">
				<section class="panel">
					<div class="panel-heading">
						<div>
							<p class="eyebrow">MODEM</p>
							<h3>${escapeHtml(model)}</h3>
						</div>
						<strong class="cellular-operator">${escapeHtml(operator)}</strong>
					</div>
					<div class="signal-block">
						<div>
							<span class="signal-number">${signalPercent === null ? '—' : escapeHtml(String(signalPercent))}<small>${signalPercent === null ? '' : '%'}</small></span>
							<span class="signal-label">Signal strength</span>
						</div>
						<div class="signal-bars" aria-label="Signal strength">
							${[20, 40, 60, 80, 100]
								.map(
									limit =>
										`<span class="${signalPercent !== null && signalPercent >= limit ? 'active' : ''}"></span>`
								)
								.join('')}
						</div>
					</div>
					<div class="detail-list">
						${metric('Technology', technology)}
						${metric('Signal', signalDbm, signalDbm === null ? '' : ' dBm')}
						${metric('Registration', status.registration_status || status.registration)}
						${metric('Packet service', status.packet_status || status.packet_attach)}
					</div>
				</section>

				<section class="panel">
					<div class="panel-heading">
						<div><p class="eyebrow">CONNECTION</p><h3>SIM & data</h3></div>
					</div>
					<div class="detail-list">
						${metric('Active SIM', sim)}
						${metric('SIM status', status.sim_status)}
						${metric('IPv4', status.ipv4)}
						${metric('Gateway', status.gateway)}
						${metric('Data interface', status.data_interface)}
						${metric('Mode', status.mode)}
					</div>
					<div class="cellular-actions">
						<button class="button button-secondary" id="cellular-reconnect" type="button">Reconnect data</button>
						${status.sim !== undefined ? '<button class="button button-secondary" id="cellular-switch-sim" type="button">Switch SIM</button>' : ''}
					</div>
				</section>
			</div>

			<section class="panel" id="veci-operator-quota">
				<div class="panel-heading">
					<div><p class="eyebrow">INDONESIA EDITION</p><h3>Operator data quota</h3></div>
					${badge(quotaReady ? 'Verified' : 'Unavailable', quotaReady ? 'success' : 'neutral')}
				</div>
				<div class="detail-list">
					${metric('Operator', 'XL')}
					${metric('Status', quotaState)}
					${metric('Total quota', quotaReady ? quotaSize(quota.total_bytes) : '—')}
					${metric('Remaining quota', quotaReady ? quotaSize(quota.remaining_bytes) : '—')}
				</div>
				<p class="panel-copy">Balance is displayed only after a verified carrier response. Account login is not yet supported.</p>
				<button class="button button-secondary" id="cellular-quota-refresh" type="button">Refresh quota status</button>
			</section>

			<div class="notice-card">
				<strong>Hardware-aware integration</strong>
				<p>VeCI Core does not assume a specific modem or router. This page appears only when the firmware exposes the standard <code>veci.cellular</code> provider.</p>
			</div>
		`;

		root.querySelector('#cellular-quota-refresh')?.addEventListener('click', () =>
			this.render({ api, root, toast, confirm })
		);

		const reconnect = root.querySelector('#cellular-reconnect');
		reconnect?.addEventListener('click', async () => {
			const ok = await confirm({
				title: 'Reconnect mobile data?',
				message: 'The cellular data session will be restarted. Internet access may drop briefly.',
				confirmLabel: 'Reconnect'
			});
			if (!ok) return;
			setBusy(reconnect, true, 'Reconnecting…');
			try {
				await api.cellularAction('reconnect');
				toast('Cellular reconnect requested.', 'success');
				setTimeout(() => this.render({ api, root, toast, confirm }), 1800);
			} catch (error) {
				toast(error.message || 'Reconnect failed.', 'error');
			} finally {
				setBusy(reconnect, false);
			}
		});

		const switchButton = root.querySelector('#cellular-switch-sim');
		switchButton?.addEventListener('click', async () => {
			const current = Number(status.sim) === 2 ? 2 : 1;
			const next = current === 1 ? 2 : 1;
			const ok = await confirm({
				title: `Switch to SIM ${next}?`,
				message:
					'The modem will change SIM and reconnect. This can interrupt Internet access for a short period.',
				confirmLabel: `Use SIM ${next}`
			});
			if (!ok) return;
			setBusy(switchButton, true, 'Switching…');
			try {
				await api.cellularAction('switchSim', { sim: next });
				toast(`Switch to SIM ${next} requested.`, 'success');
				setTimeout(() => this.render({ api, root, toast, confirm }), 2500);
			} catch (error) {
				toast(error.message || 'SIM switch failed.', 'error');
			} finally {
				setBusy(switchButton, false);
			}
		});
	}
};
