import { escapeHtml, setBusy } from '/veci/js/lib/dom.js';

const providerHelp = {
	'cloudflare.com-v4':
		'Cloudflare: username = Bearer for API Token; password = API Token; domain example host@example.com; lookup host example host.example.com.',
	'duckdns.org':
		'DuckDNS: password = token; domain example myhome; lookup host example myhome.duckdns.org. Username may be blank.',
	'no-ip.com': 'No-IP: use your account username/password; domain and lookup host are normally the same hostname.'
};

export default {
	async render({ api, root, toast, back, app }) {
		let status = await api.call('veci.app.ddns', 'status', {});

		const draw = () => {
			root.innerHTML = `
				<div class="page-intro">
					<div>
						<p class="eyebrow">ROUTER APP</p>
						<h2>${escapeHtml(app.name || 'Dynamic DNS')}</h2>
						<p>Keep a DNS hostname pointed at this router's current public IPv4 address.</p>
					</div>
					<button id="app-back" class="button button-secondary" type="button">Back to Apps</button>
				</div>

				<article class="panel">
					<form id="ddns-form">
						<label class="field">
							<span>Enable Dynamic DNS</span>
							<input id="ddns-enabled" type="checkbox" ${status.enabled ? 'checked' : ''} />
						</label>
						<label class="field">
							<span>Provider</span>
							<select id="ddns-service">
								<option value="cloudflare.com-v4" ${status.service === 'cloudflare.com-v4' ? 'selected' : ''}>Cloudflare API v4</option>
								<option value="duckdns.org" ${status.service === 'duckdns.org' ? 'selected' : ''}>DuckDNS</option>
								<option value="no-ip.com" ${status.service === 'no-ip.com' ? 'selected' : ''}>No-IP</option>
							</select>
						</label>
						<p id="ddns-provider-help" class="panel-copy"></p>
						<label class="field">
							<span>Lookup hostname</span>
							<input id="ddns-lookup" value="${escapeHtml(status.lookup_host || '')}" autocomplete="off" />
						</label>
						<label class="field">
							<span>Provider domain parameter</span>
							<input id="ddns-domain" value="${escapeHtml(status.domain || '')}" autocomplete="off" />
						</label>
						<label class="field">
							<span>Username</span>
							<input id="ddns-username" value="${escapeHtml(status.username || '')}" autocomplete="username" />
						</label>
						<label class="field">
							<span>Password / API token</span>
							<input id="ddns-password" type="password" value="" autocomplete="new-password" placeholder="${status.password_set ? 'Configured — leave blank to keep' : 'Required by provider'}" />
						</label>
						<label class="field">
							<span>OpenWrt network</span>
							<input id="ddns-network" value="${escapeHtml(status.network || 'lte')}" autocomplete="off" />
						</label>
						<button id="ddns-save" class="button button-primary" type="submit">Save Dynamic DNS</button>
					</form>
				</article>
			`;

			root.querySelector('#app-back')?.addEventListener('click', back);
			const service = root.querySelector('#ddns-service');
			const help = root.querySelector('#ddns-provider-help');
			const refreshHelp = () => {
				help.textContent = providerHelp[service.value] || '';
			};
			service.addEventListener('change', refreshHelp);
			refreshHelp();

			root.querySelector('#ddns-form')?.addEventListener('submit', async event => {
				event.preventDefault();
				const button = root.querySelector('#ddns-save');
				setBusy(button, true, 'Saving…');
				try {
					const result = await api.call(
						'veci.app.ddns',
						'save',
						{
							enabled: root.querySelector('#ddns-enabled').checked,
							service: service.value,
							lookup_host: root.querySelector('#ddns-lookup').value.trim(),
							domain: root.querySelector('#ddns-domain').value.trim(),
							username: root.querySelector('#ddns-username').value.trim(),
							password: root.querySelector('#ddns-password').value,
							network: root.querySelector('#ddns-network').value.trim()
						},
						{ timeout: 30000 }
					);
					if (!result.ok) throw new Error(result.error || 'Could not save Dynamic DNS');
					status = await api.call('veci.app.ddns', 'status', {});
					draw();
					toast('Dynamic DNS settings saved.', 'success');
				} catch (error) {
					toast(error.message || 'Could not save Dynamic DNS settings.', 'error');
					setBusy(button, false);
				}
			});
		};

		draw();
	}
};
