import { badge, escapeHtml, setBusy } from '../lib/dom.js?v=162';
import { formatBytes, formatDuration, formatMemory, firstAddress } from '../lib/format.js?v=162';
import { icon } from '../lib/icons.js?v=162';

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

function configuredWireless(configResult, type) {
	return Object.values(configResult?.values || {}).filter(section => section['.type'] === type);
}

function wifiInventory(status, configResult) {
	const runtimeRadios = Object.values(status || {});
	const runtimeNetworks = wifiNetworks(status);
	return {
		radios: runtimeRadios.length ? runtimeRadios : configuredWireless(configResult, 'wifi-device'),
		networks: runtimeNetworks.length ? runtimeNetworks : configuredWireless(configResult, 'wifi-iface')
	};
}

export default {
	id: 'home',
	title: 'Home',
	navLabel: 'Home',
	eyebrow: 'OVERVIEW',
	icon: 'home',

	async render({ api, state, root, navigate, toast }) {
		const [system, interfacesResult, wireless, wirelessConfig, clients, security, performance] = await Promise.all([
			api.systemInfo(),
			api.interfaces(),
			api.wirelessStatus().catch(() => ({})),
			api.uciGet('wireless').catch(() => ({ values: {} })),
			api.veci('clients').catch(() => ({ clients: [] })),
			api.veci('securityStatus').catch(() => ({ root_password_set: true })),
			api.call('veci.cellular', 'performanceStatus', {}, { timeout: 2500 }).catch(() => ({ ok: false }))
		]);

		const interfaces = interfacesResult.interface || [];
		state.system = system;
		state.interfaces = interfaces;
		state.wireless = wireless;

		const uplink = defaultRouteInterface(interfaces);
		const memory = formatMemory(system.memory || {});
		const memoryPercent = Math.min(Math.max(memory.percent, 0), 100);
		const { radios, networks } = wifiInventory(wireless, wirelessConfig);
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
						<span id="home-connectivity-dot" class="status-dot"></span>
						<div>
							<strong id="home-connectivity-title">${uplink ? 'Checking Internet…' : 'Uplink unavailable'}</strong>
							<span id="home-connectivity-detail">${uplink ? `${escapeHtml(uplink.interface)} · ${escapeHtml(firstAddress(uplink))} · uplink active` : 'Check the WAN or mobile data link'}</span>
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

            <section class="content-grid content-grid-2" aria-label="Connection stability">
                <article class="panel">
                    <div class="panel-heading"><div><p class="eyebrow">CELLULAR RELIABILITY</p><h3>LTE Recovery</h3></div></div>
                    <p id="perf-lte-stage">Not monitored</p>
                    <div class="detail-list compact">
                        <div><span>Monitor interval</span><strong id="perf-lte-poll">Not available</strong></div>
                        <div><span>Consecutive failures</span><strong id="perf-lte-fail">—</strong></div>
                        <div><span>Strategy</span><strong>DHCP first · modem reset last</strong></div>
                    </div>
                    <button class="text-link" data-go="cellular" type="button">Mobile connection</button>
                </article>
                <article class="panel">
                    <div class="panel-heading"><div><p class="eyebrow">WI-FI RELIABILITY</p><h3>Wi-Fi Guardian</h3></div></div>
                    <p id="perf-wifi-stage">Not monitored</p>
                    <div class="detail-list compact">
                        <div><span>Monitor interval</span><strong id="perf-wifi-poll">Not available</strong></div>
                        <div><span>Consecutive failures</span><strong id="perf-wifi-fail">—</strong></div>
                        <div><span>Strategy</span><strong>Stable channel · guarded AP recovery</strong></div>
                    </div>
                    <button class="text-link" data-go="wifi" type="button">Wi-Fi stability</button>
                </article>
            </section>
			<section class="metric-grid">
				<button class="metric-card metric-link" data-go="internet" type="button">
					<span class="metric-icon">${icon('globe', 'svg-icon')}</span>
					<div><span>Internet</span><strong id="home-internet-metric">${uplink ? 'Checking…' : 'No uplink'}</strong><small id="home-internet-metric-detail">${uplink ? `${escapeHtml(uplink?.proto?.toUpperCase() || 'UPLINK')} · uplink active` : 'No active uplink'}</small></div>
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
						<div><p class="eyebrow">UPLINK</p><h3>Connection</h3></div>
						<span id="home-uplink-badge">${uplink ? badge('Checking', 'neutral') : badge('Link down', 'danger')}</span>
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
						<progress class="memory-progress" max="100" value="${memoryPercent}" aria-label="Memory used"></progress>
					</div>
					<div class="detail-list compact">
						<div><span>Firmware</span><strong>${escapeHtml(firmware)}</strong></div>
						<div><span>Kernel</span><strong>${escapeHtml(state.board?.kernel || '—')}</strong></div>
					</div>
					<button class="text-link" data-go="system" type="button">System details <span>→</span></button>
				</article>
			</section>
		`;

		// Read-only statuses; never claim the connection is healthy when
		// the tiny /tmp monitor has not actually run.
		if (performance?.ok === true && performance?.source === 'local_tmpfs_monitors') {
			const label = {
				healthy: 'Healthy · monitoring',
				stale: 'Monitor data stale · state unverified',
				dhcp_renew: 'Restoring DHCP',
				recovered_dhcp: 'Restored · DHCP',
				interface_recovery: 'Repairing LTE interface',
				recovered_interface: 'Restored · LTE interface',
				modem_soft_reconnect: 'Recovering modem registration',
				recovered_soft: 'Restored · cellular modem',
				upstream_degraded: 'Gateway reachable · Internet degraded',
				power_cycle_cooldown: 'Reset cooldown active',
				last_resort_power_cycle: 'Last-resort modem reset',
				ready: 'Access point operational',
				radio_recovery: 'Recovering missing access point',
				ap_not_ready: 'Access point not ready',
				intentionally_disabled: 'Wi-Fi intentionally disabled',
				hold_associated_or_unknown: 'Conservative hold · clients may be connected',
				cooldown_or_observe: 'Monitoring · cooldown'
			};
			const updateText = (id, value) => {
				const element = root.querySelector(id);
				if (element) element.textContent = String(value);
			};
			const lte = performance.lte || {};
			const wifi = performance.wifi || {};
			updateText('#perf-lte-stage', label[lte.stage] || 'Not monitored');
			updateText('#perf-wifi-stage', label[wifi.stage] || 'Not monitored');
			if (Number.isInteger(lte.check_interval_seconds) && lte.check_interval_seconds > 0)
				updateText('#perf-lte-poll', String(lte.check_interval_seconds) + ' sec');
			if (Number.isInteger(wifi.check_interval_seconds) && wifi.check_interval_seconds > 0)
				updateText('#perf-wifi-poll', String(wifi.check_interval_seconds) + ' sec');
			if (Number.isInteger(lte.failures) && lte.failures >= 0) updateText('#perf-lte-fail', lte.failures);
			if (Number.isInteger(wifi.failures) && wifi.failures >= 0) updateText('#perf-wifi-fail', wifi.failures);
		}

		if (uplink) {
			api.veci('internetStatus', {}, { timeout: 3000 })
				.then(status => {
					const title = root.querySelector('#home-connectivity-title');
					const detail = root.querySelector('#home-connectivity-detail');
					const metric = root.querySelector('#home-internet-metric');
					const metricDetail = root.querySelector('#home-internet-metric-detail');
					const dot = root.querySelector('#home-connectivity-dot');
					const badgeHost = root.querySelector('#home-uplink-badge');
					if (!title || !detail || !metric || !metricDetail || !dot || !badgeHost) return;

					if (status.status === 'reachable' && status.reachable === true) {
						title.textContent = 'Internet reachable';
						detail.textContent = `${uplink.interface} · ${firstAddress(uplink)} · verified`;
						metric.textContent = 'Internet reachable';
						metricDetail.textContent = `${uplink.proto?.toUpperCase() || 'UPLINK'} · verified`;
						dot.classList.add('online');
						badgeHost.innerHTML = badge('Internet reachable', 'success');
					} else if (status.status === 'unreachable' && status.reachable === false) {
						title.textContent = 'Internet unavailable';
						detail.textContent = `${uplink.interface} · ${firstAddress(uplink)} · uplink active`;
						metric.textContent = 'Internet unavailable';
						metricDetail.textContent = `${uplink.proto?.toUpperCase() || 'UPLINK'} · uplink active`;
						dot.classList.remove('online');
						badgeHost.innerHTML = badge('No Internet', 'danger');
					} else {
						title.textContent = 'Uplink active';
						detail.textContent = `${uplink.interface} · ${firstAddress(uplink)} · Internet not verified`;
						metric.textContent = 'Uplink active';
						metricDetail.textContent = `${uplink.proto?.toUpperCase() || 'UPLINK'} · reachability not verified`;
						dot.classList.remove('online');
						badgeHost.innerHTML = badge('Link up', 'neutral');
					}
				})
				.catch(() => {
					const title = root.querySelector('#home-connectivity-title');
					const detail = root.querySelector('#home-connectivity-detail');
					const metric = root.querySelector('#home-internet-metric');
					const metricDetail = root.querySelector('#home-internet-metric-detail');
					const badgeHost = root.querySelector('#home-uplink-badge');
					if (title) title.textContent = 'Uplink active';
					if (detail)
						detail.textContent = `${uplink.interface} · ${firstAddress(uplink)} · Internet not verified`;
					if (metric) metric.textContent = 'Uplink active';
					if (metricDetail)
						metricDetail.textContent = `${uplink.proto?.toUpperCase() || 'UPLINK'} · reachability not verified`;
					if (badgeHost) badgeHost.innerHTML = badge('Link up', 'neutral');
				});
		}

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
					toast('Administrator password is already configured. Manage settings in VeCI System.', 'info');
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
