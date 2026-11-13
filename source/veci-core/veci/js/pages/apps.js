import { badge, escapeHtml, setBusy } from '../lib/dom.js';

const fallbackApps = {
	guest: ['Guest portal', 'Captive portal engine'],
	sqm: ['Smart Queue', 'Queue management'],
	ddns: ['Dynamic DNS', 'Hostname updates'],
	wireguard: ['WireGuard', 'VPN capability'],
	voucher: ['Voucher', 'Time-limited guest access']
};

function fallbackCatalog(capabilities) {
	return Object.entries(fallbackApps).map(([id, [name, description]]) => ({
		id,
		name,
		description,
		tier: '',
		installed: Boolean(capabilities[id]),
		installable: false,
		removable: false,
		packages: []
	}));
}

export default {
	id: 'apps',
	title: 'Apps',
	eyebrow: 'EXTENSIONS',
	icon: 'apps',

	async render({ api, root, toast, confirm }) {
		const load = async () => {
			const [capabilities, catalog, updateStatus, deviceApps] = await Promise.all([
				api.veci('capabilities').catch(() => ({})),
				api.veci('apps', {}, { timeout: 10000 }).catch(() => ({ apps: [] })),
				api.veci('updateStatus', {}, { timeout: 10000 }).catch(() => ({})),
				api.call('veci.apps', 'status', {}, { timeout: 10000 }).catch(() => null)
			]);
			return {
				capabilities,
				catalog,
				updateStatus,
				deviceApps,
				apps: Array.isArray(catalog.apps) && catalog.apps.length ? catalog.apps : fallbackCatalog(capabilities)
			};
		};

		let state = await load();
		let activeModuleCleanup = null;

		const draw = () => {
			// A missing provider is not proof of a verified signed package index.
			const feedEnabled =
				state.catalog.feed_enabled === true &&
				state.deviceApps?.feed_ready === true &&
				state.deviceApps?.feed_verified === true;
			const manager = state.catalog.package_manager || 'unknown';
			const feedBlockReason =
				state.deviceApps === null
					? 'Signed-feed verification provider veci.apps is not installed. A Core hot-update does not install optional APKs.'
					: state.deviceApps.feed_configured !== true
						? 'No device-matched signed app repository is configured. Guest, Voucher, SQM, DDNS and WireGuard installation stays blocked.'
						: state.deviceApps.feed_verified !== true
							? 'This router has not verified the signed app feed for its running firmware. Never use packages from a different kernel build.'
							: state.deviceApps.feed_ready !== true
								? 'The signed feed is not ready or does not match this firmware; check exact build ID, signatures and dependencies.'
								: null;
			const kernelFeedMismatch = Boolean(state.updateStatus.kernel_feed_mismatch);
			const resources = Number.isFinite(state.deviceApps?.overlay_free_kb) ? state.deviceApps : state.catalog;
			const overlayInsufficient =
				Number.isFinite(resources?.overlay_free_kb) &&
				Number.isFinite(resources?.minimum_overlay_kb) &&
				resources.overlay_free_kb < resources.minimum_overlay_kb;

			root.innerHTML = `
				<div class="page-intro">
					<div>
						<h2>Router apps</h2>
						<p>Optional capabilities stay outside VeCI Core. Only catalogued packages from the router's compatible package source can be managed here.</p>
					</div>
				</div>
				<div class="app-grid">
					${state.apps
						.map(app => {
							const enabled = app.enabled !== false;
							const installed = Boolean(app.installed);
							const installable = Boolean(app.installable) && feedEnabled;
							const removable = Boolean(app.removable);
							const status = installed
								? badge('Installed', 'success')
								: !enabled
									? badge('Not ready', 'warning')
									: installable
										? badge('Ready to install', 'info')
										: badge('Not installed', 'neutral');
							const actions = [];
							if (installed && app.module) {
								actions.push(
									`<button class="button button-primary" data-app-module="${escapeHtml(app.module)}" data-app-id="${escapeHtml(app.id)}" type="button">Configure</button>`
								);
							}
							if (installed && removable) {
								actions.push(
									`<button class="button button-secondary" data-app-action="remove" data-app-id="${escapeHtml(app.id)}" type="button">Remove</button>`
								);
							} else if (!installed && installable) {
								actions.push(
									`<button class="button button-primary" data-app-action="install" data-app-id="${escapeHtml(app.id)}" type="button">Install</button>`
								);
							}
							return `
								<article class="app-card">
									<div class="app-card-icon">${escapeHtml((app.name || app.id || '?').slice(0, 1))}</div>
									<div class="app-card-copy">
										<div class="app-card-title"><h3>${escapeHtml(app.name || app.id || 'App')}</h3>${status}</div>
										<p>${escapeHtml(app.description || '')}</p>
										${app.tier ? `<p class="muted">Resource tier ${escapeHtml(app.tier)}</p>` : ''}
										${actions.length ? `<div class="app-card-actions">${actions.join('')}</div>` : ''}
									</div>
								</article>
							`;
						})
						.join('')}
				</div>
				<div class="notice-card">
					<strong>${feedEnabled ? 'VeCI signed app feed is verified and ready.' : 'VeCI signed app installation is blocked.'}</strong>
					<p>${
						overlayInsufficient
							? `Only ${resources.overlay_free_kb} KB overlay available; minimum ${resources.minimum_overlay_kb} KB required for even attempting optional-app installation. Use a verified firmware image bundling required apps or supported extroot; never force APKs.`
							: kernelFeedMismatch
								? 'Kernel ABI mismatch detected. Kernel-dependent apps remain blocked until the exact VeCI-matched feed is configured.'
								: feedEnabled
									? `Package manager: ${escapeHtml(manager)}. Install actions are restricted to root-owned app manifests on this router.`
									: escapeHtml(
											feedBlockReason ||
												'Install actions stay locked until a compatible signed feed is configured by the firmware profile.'
										)
					}</p>
					${state.deviceApps?.feed_configured === true && state.deviceApps?.feed_verified !== true ? '<button id="verify-app-feed" class="button button-secondary" type="button">Verify signed App Store feed</button>' : ''}
				</div>
			`;

			const verifyFeed = root.querySelector('#verify-app-feed');
			verifyFeed?.addEventListener('click', async () => {
				setBusy(verifyFeed, true, 'Verifying repository…');
				try {
					const result = await api.call('veci.apps', 'verifyFeed', {}, { timeout: 120000 });
					if (result?.ok !== true || result?.verified !== true) {
						throw new Error(result?.reason || 'Repository signature verification failed');
					}
					state = await load();
					draw();
					toast('The matched signed app repository has been verified.', 'success');
				} catch (error) {
					toast(error.message || 'Could not verify signed repository.', 'error');
					setBusy(verifyFeed, false);
				}
			});

			root.querySelectorAll('[data-app-module]').forEach(button => {
				button.addEventListener('click', async () => {
					const id = button.dataset.appId;
					const modulePath = button.dataset.appModule;
					const app = state.apps.find(item => item.id === id);
					if (!app || !/^\/veci-apps\/[A-Za-z0-9._/-]+\.js$/.test(modulePath || '')) {
						toast('This router app module is not valid.', 'error');
						return;
					}

					setBusy(button, true, 'Opening…');
					try {
						const imported = await import(modulePath);
						if (!imported.default || typeof imported.default.render !== 'function') {
							throw new Error('Router app module does not expose a render function');
						}
						if (activeModuleCleanup) activeModuleCleanup();
						activeModuleCleanup = null;
						root.innerHTML = '';
						const cleanup = await imported.default.render({
							api,
							root,
							toast,
							confirm,
							app,
							back: () => {
								if (activeModuleCleanup) activeModuleCleanup();
								activeModuleCleanup = null;
								draw();
							}
						});
						activeModuleCleanup = typeof cleanup === 'function' ? cleanup : null;
					} catch (error) {
						toast(error.message || 'Could not open router app.', 'error');
						draw();
					}
				});
			});

			root.querySelectorAll('[data-app-action]').forEach(button => {
				button.addEventListener('click', async () => {
					const id = button.dataset.appId;
					const action = button.dataset.appAction;
					const app = state.apps.find(item => item.id === id);
					if (!app) return;

					const allowed = await confirm({
						title: action === 'install' ? `Install ${app.name}?` : `Remove ${app.name}?`,
						message:
							action === 'install'
								? 'VeCI will install only the packages declared by the router app manifest.'
								: 'The selected app packages will be removed. Core firmware packages are not part of this action.',
						confirmLabel: action === 'install' ? 'Install app' : 'Remove app',
						tone: action === 'install' ? 'primary' : 'danger'
					});
					if (!allowed) return;

					setBusy(button, true, action === 'install' ? 'Installing…' : 'Removing…');
					try {
						const result = await api.veci('appAction', { id, action }, { timeout: 120000 });
						if (!result.ok) throw new Error(result.error || 'App action failed');
						state = await load();
						draw();
						toast(action === 'install' ? `${app.name} installed.` : `${app.name} removed.`, 'success');
					} catch (error) {
						toast(error.message || 'Could not change router app state.', 'error');
						setBusy(button, false);
					}
				});
			});
		};

		draw();
		return () => {
			if (activeModuleCleanup) activeModuleCleanup();
		};
	}
};
