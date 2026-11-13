import { badge, escapeHtml } from '../lib/dom.js';

const appLabels = {
	opennds: ['Guest portal', 'Captive portal engine'],
	sqm: ['Smart Queue', 'Queue management'],
	ddns: ['Dynamic DNS', 'Hostname updates'],
	wireguard: ['WireGuard', 'VPN capability'],
	voucher: ['Voucher', 'Time-limited guest access']
};

export default {
	id: 'apps',
	title: 'Apps',
	eyebrow: 'EXTENSIONS',
	icon: 'apps',

	async render({ api, root }) {
		const capabilities = await api.veci('capabilities').catch(() => ({}));
		root.innerHTML = `
			<div class="page-intro">
				<div><h2>Router apps</h2><p>Optional capabilities stay outside VeCI Core so small routers do not pay the RAM and flash cost for features they never use.</p></div>
			</div>
			<div class="app-grid">
				${Object.entries(appLabels)
					.map(([key, [title, description]]) => {
						const installed = Boolean(capabilities[key]);
						return `
						<article class="app-card">
							<div class="app-card-icon">${title.slice(0, 1)}</div>
							<div class="app-card-copy">
								<div class="app-card-title"><h3>${escapeHtml(title)}</h3>${badge(installed ? 'Available' : 'Not installed', installed ? 'success' : 'neutral')}</div>
								<p>${escapeHtml(description)}</p>
							</div>
						</article>
					`;
					})
					.join('')}
			</div>
			<div class="notice-card">
				<strong>VeCI app feed is intentionally disabled.</strong>
				<p>Public extensions will be enabled only after VeCI has its own signing key, reproducible package pipeline and compatibility metadata.</p>
			</div>
		`;
	}
};
