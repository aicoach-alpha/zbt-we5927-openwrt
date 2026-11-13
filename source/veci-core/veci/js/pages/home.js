import { badge, escapeHtml, setBusy } from '../lib/dom.js';
import { formatBytes, formatDuration, formatMemory, firstAddress } from '../lib/format.js';
import { icon } from '../lib/icons.js';

function defaultRouteInterface(interfaces) {
	return (
		interfaces.find(
			iface => iface.up && iface.route?.some(route => route.target === '0.0.0.0' || route.target === '::')
		) ||
		interfaces.find(iface => iface.up && /^(wan|lte|wwan|cellular)/i.test(iface.interface)) ||
		interfaces.find(iface => iface.up && iface.interface !== 'loopback')
	);
}

function wifiNetworks(status) {
	return Object.values(status || {}).flatMap(radio => radio.interfaces || []);
}

export default {
	id: 'home',
	title: 'Home',
	navLabel: 'Home',
	eyebrow: 'OVERVIEW',
	icon: 'home',

	async render({ api, state, root, navigate, toast }) {
		const [system, interfacesResult, wireless, clients, security] = await Promise.all([
			api.systemInfo(),
			api.interfaces(),
			api.wirelessStatus().catch(() => ({})),
			api.veci('clients').catch(() => ({ clients: [] })),
			api.veci('securityStatus').catch(() => ({ root_password_set: true }))
		]);

		const interfaces = interfacesResult.interface || [];
		state.system = system;
		state.interfaces = interfaces;
		state.wireless = wireless;

		const uplink = defaultRouteInterface(interfaces);
		const memory = formatMemory(system.memory || {});
		const radios = Object.values(wireless || {});
		const networks = wifiNetworks(wireless);
		const clientCount = clients.clients?.length || 0;
		const model = state.board?.model || state.board?.board_name || 'OpenWrt Router';
		const boardName = state.board?.board_name || '';
		const firmware = state.board?.release?.description || state.board?.release?.version || 'OpenWrt';

		root.innerHTML = `
			${
				security.root_password_set === false
					? `
						<section class="setup-alert" id="admin-password-setup">
							<div class="setup-alert-icon">!</div>
							<div class="setup-alert-copy">
								<p class="eyebrow">SECURITY SETUP</p>
								<h2>Set an administrator password</h2>
								<p>This router currently accepts the root account without a password. Create one before using the router beyond initial setup.</p>
								<form id="admin-password-form" class="setup-password-form">
									<label class="field"><span>New password</span><input id="admin-password" type="password" minlength="8" maxlength="72" autocomplete="new-password" required /></label>
									<label class="field"><span>Confirm password</span><input id="admin-password-confirm" type="password" minlength="8" maxlength="72" autocomplete="new-password" required /></label>
									<button id="admin-password-save" class="button button-primary" type="submit">Set admin password</button>
								</form>
							</div>
						</section>
					`
					: ''
			}
			<section class="hero-grid">
				<article class="hero-card hero-primary">
					<div class="hero-copy">
						<p class="eyebrow">YOUR ROUTER</p>
						<h2>${escapeHtml(model)}</h2>
						<p>${escapeHtml(boardName || firmware)}</p>
					</div>
					<div class="hero-state">
						<span class="status-dot ${uplink ? 'online' : ''}"></span>
						<div>
							<strong>${uplink ? 'Internet connected' : 'Internet unavailable'}</strong>
							<span>${uplink ? `${escapeHtml(uplink.interface)} · ${escapeHtml(firstAddress(uplink))}` : 'Check the Internet connection'}</span>
						</div>
					</div>
				</article>

				<article class="hero-card hero-health">
					<div>
						<p class="eyebrow">ROUTER HEALTH</p>
						<h3>${memory.percent < 85 ? 'Healthy' : 'Memory pressure'}</h3>
						<p>Uptime ${escapeHtml(formatDuration(system.uptime || 0))}</p>
					</div>
					<div class="health-ring" style="--value:${Math.min(memory.percent, 100)}">
						<strong>${memory.percent}%</strong><span>RAM</span>
					</div>
				</article>
			</section>

			<section class="metric-grid">
				<button class="metric-card metric-link" data-go="internet" type="button">
					<span class="metric-icon">${icon('globe', 'svg-icon')}</span>
					<div><span>Internet</span><strong>${uplink ? 'Online' : 'Offline'}</strong><small>${escapeHtml(uplink?.proto?.toUpperCase() || 'No uplink')}</small></div>
				</button>
				<button class="metric-card metric-link" data-go="wifi" type="button">
					<span class="metric-icon">${icon('wifi', 'svg-icon')}</span>
					<div><span>Wi-Fi</span><strong>${networks.length} network${networks.length === 1 ? '' : 's'}</strong><small>${radios.length} radio${radios.length === 1 ? '' : 's'} detected</small></div>
				</button>
				<button class="metric-card metric-link" data-go="devices" type="button">
					<span class="metric-icon">${icon('devices', 'svg-icon')}</span>
					<div><span>Devices</span><strong>${clientCount}</strong><small>DHCP clients</small></div>
				</button>
				<button class="metric-card metric-link" data-go="security" type="button">
					<span class="metric-icon">${icon('shield', 'svg-icon')}</span>
					<div><span>Security</span><strong>Firewall</strong><small>Review protection</small></div>
				</button>
			</section>

			<section class="content-grid content-grid-2">
				<article class="panel">
					<div class="panel-heading">
						<div><p class="eyebrow">INTERNET</p><h3>Connection</h3></div>
						${uplink ? badge('Online', 'success') : badge('Offline', 'danger')}
					</div>
					<div class="detail-list">
						<div><span>Interface</span><strong>${escapeHtml(uplink?.interface || '—')}</strong></div>
						<div><span>Address</span><strong>${escapeHtml(uplink ? firstAddress(uplink) : '—')}</strong></div>
						<div><span>Device</span><strong>${escapeHtml(uplink?.l3_device || uplink?.device || '—')}</strong></div>
					</div>
					<button class="text-link" data-go="internet" type="button">Manage Internet <span>→</span></button>
				</article>

				<article class="panel">
					<div class="panel-heading">
						<div><p class="eyebrow">SYSTEM</p><h3>Resources</h3></div>
						${badge(memory.percent < 85 ? 'Normal' : 'High', memory.percent < 85 ? 'success' : 'warning')}
					</div>
					<div class="resource-row">
						<div><span>Memory</span><strong>${formatBytes(memory.used)} / ${formatBytes(memory.total)}</strong></div>
						<div class="progress-track"><span style="width:${memory.percent}%"></span></div>
					</div>
					<div class="detail-list compact">
						<div><span>Firmware</span><strong>${escapeHtml(firmware)}</strong></div>
						<div><span>Kernel</span><strong>${escapeHtml(state.board?.kernel || '—')}</strong></div>
					</div>
					<button class="text-link" data-go="system" type="button">System details <span>→</span></button>
				</article>
			</section>
		`;

		const passwordForm = root.querySelector('#admin-password-form');
		passwordForm?.addEventListener('submit', async event => {
			event.preventDefault();
			const password = root.querySelector('#admin-password').value;
			const confirmation = root.querySelector('#admin-password-confirm').value;
			const button = root.querySelector('#admin-password-save');

			if (password.length < 8 || password.length > 72) {
				toast('Administrator password must be 8–72 characters.', 'error');
				return;
			}
			if (password !== confirmation) {
				toast('Password confirmation does not match.', 'error');
				return;
			}

			setBusy(button, true, 'Saving…');
			try {
				const result = await api.veci('setAdminPassword', { password });
				if (result.ok === false && result.error === 'password_already_set') {
					root.querySelector('#admin-password-setup')?.remove();
					toast('Administrator password is already configured. Use Expert / LuCI to change it.', 'info');
					return;
				}
				if (result.ok === false) throw new Error(result.error || 'Password change failed');
				root.querySelector('#admin-password').value = '';
				root.querySelector('#admin-password-confirm').value = '';
				root.querySelector('#admin-password-setup')?.remove();
				toast('Administrator password set.', 'success');
			} catch (error) {
				toast(error.message || 'Could not set administrator password.', 'error');
			} finally {
				setBusy(button, false);
			}
		});

		root.querySelectorAll('[data-go]').forEach(button =>
			button.addEventListener('click', () => navigate(button.dataset.go))
		);
	}
};
