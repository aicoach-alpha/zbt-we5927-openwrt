import { VeciApi } from './lib/api.js';
import { escapeHtml, qs, qsa, setBusy } from './lib/dom.js';
import { hydrateIcons, icon } from './lib/icons.js';

import homePage from './pages/home.js';
import internetPage from './pages/internet.js';
import wifiPage from './pages/wifi.js';
import devicesPage from './pages/devices.js';
import securityPage from './pages/security.js';
import networkPage from './pages/network.js';
import systemPage from './pages/system.js';
import cellularPage from './pages/cellular.js';
import appsPage from './pages/apps.js';

const pages = [
	homePage,
	internetPage,
	wifiPage,
	devicesPage,
	cellularPage,
	securityPage,
	networkPage,
	systemPage,
	appsPage
];
const pageMap = new Map(pages.map(page => [page.id, page]));

class VeciApp {
	constructor() {
		this.api = new VeciApi();
		this.state = { board: null, system: null, capabilities: {}, interfaces: [], wireless: {} };
		this.activeCleanup = null;
		this.pageRequest = 0;
	}

	async start() {
		this.bindChrome();
		hydrateIcons();
		if (await this.api.validateSession()) await this.enterApp();
		else this.showLogin();
	}

	bindChrome() {
		qs('#login-form')?.addEventListener('submit', event => this.handleLogin(event));
		qs('#logout-button')?.addEventListener('click', () => this.handleLogout());
		qs('#mobile-menu-button')?.addEventListener('click', () => document.body.classList.toggle('menu-open'));
		window.addEventListener('hashchange', () => this.route());
		document.addEventListener('click', event => {
			const target = event.target.closest('[data-route]');
			if (!target) return;
			event.preventDefault();
			this.navigate(target.dataset.route);
		});
	}

	async handleLogin(event) {
		event.preventDefault();
		const button = qs('#login-submit');
		const error = qs('#login-error');
		error.textContent = '';
		setBusy(button, true, 'Signing in…');
		try {
			await this.api.login(qs('#username').value.trim(), qs('#password').value);
			qs('#password').value = '';
			await this.enterApp();
		} catch (loginError) {
			error.textContent = loginError.message || 'Unable to sign in';
		} finally {
			setBusy(button, false);
		}
	}

	async handleLogout() {
		await this.api.logout();
		if (this.activeCleanup) this.activeCleanup();
		this.activeCleanup = null;
		this.showLogin();
	}

	showLogin() {
		qs('#login-view').classList.remove('hidden');
		qs('#app-view').classList.add('hidden');
		document.body.classList.remove('menu-open');
		qs('#password')?.focus();
	}

	async enterApp() {
		qs('#login-view').classList.add('hidden');
		qs('#app-view').classList.remove('hidden');
		await this.refreshIdentity();
		this.renderNavigation();
		await this.detectExpertUi();
		if (!window.location.hash || window.location.hash === '#/') {
			this.navigate('home');
			return;
		}
		await this.route();
	}

	async refreshIdentity() {
		const [board, system, capabilities] = await Promise.all([
			this.api.board().catch(() => ({})),
			this.api.systemInfo().catch(() => ({})),
			this.api.veci('capabilities').catch(() => ({}))
		]);
		this.state.board = board;
		this.state.system = system;
		this.state.capabilities = capabilities;

		const model = board.model || board.board_name || 'OpenWrt Router';
		const release = board.release || {};
		const firmware = release.description || release.pretty_name || release.version || 'OpenWrt';
		qs('#sidebar-model').textContent = model;
		qs('#topbar-model').textContent = model;
		qs('#topbar-firmware').textContent = firmware;
		qs('#connection-dot').classList.add('online');
	}

	renderNavigation() {
		const nav = qs('#primary-nav');
		nav.innerHTML = pages
			.filter(page => !page.capability || this.state.capabilities?.[page.capability] !== false)
			.map(
				page => `
				<a class="nav-link" href="#/${page.id}" data-route="${page.id}">
					<span class="nav-icon">${icon(page.icon, 'svg-icon')}</span>
					<span>${escapeHtml(page.navLabel || page.title)}</span>
				</a>
			`
			)
			.join('');
	}

	async detectExpertUi() {
		const link = qs('#expert-link');
		if (!link) return;
		try {
			const response = await fetch('/cgi-bin/luci/', { method: 'HEAD', cache: 'no-store', redirect: 'manual' });
			link.classList.toggle('hidden', response.status === 404);
		} catch {
			link.classList.add('hidden');
		}
	}

	navigate(pageId) {
		window.location.hash = `#/${pageId}`;
	}

	async route() {
		if (!this.api.sessionId) return;
		const requestId = ++this.pageRequest;
		const pageId = (window.location.hash.replace(/^#\//, '').split('/')[0] || 'home').toLowerCase();
		const page = pageMap.get(pageId) || homePage;

		if (this.activeCleanup) {
			this.activeCleanup();
			this.activeCleanup = null;
		}

		qsa('.nav-link[data-route]').forEach(link => link.classList.toggle('active', link.dataset.route === page.id));
		qs('#page-eyebrow').textContent = page.eyebrow || 'ROUTER';
		qs('#page-title').textContent = page.title;
		document.body.classList.remove('menu-open');

		const root = qs('#page-content');
		root.innerHTML = `
			<div class="page-loading">
				<span class="spinner"></span>
				<span>Loading ${escapeHtml(page.title)}…</span>
			</div>
		`;

		const context = {
			api: this.api,
			state: this.state,
			root,
			app: this,
			navigate: id => this.navigate(id),
			toast: (message, tone) => this.toast(message, tone),
			confirm: options => this.confirm(options)
		};

		try {
			const cleanup = await page.render(context);
			if (requestId !== this.pageRequest) {
				if (typeof cleanup === 'function') cleanup();
				return;
			}
			this.activeCleanup = typeof cleanup === 'function' ? cleanup : null;
			hydrateIcons(root);
			root.focus({ preventScroll: true });
		} catch (error) {
			console.error(error);
			root.innerHTML = `
				<div class="error-panel">
					<div class="error-panel-icon">!</div>
					<div>
						<h2>Could not load this page</h2>
						<p>${escapeHtml(error.message || 'Unknown error')}</p>
					</div>
					<button class="button button-secondary" id="retry-page">Retry</button>
				</div>
			`;
			qs('#retry-page', root)?.addEventListener('click', () => this.route());
		}
	}

	toast(message, tone = 'info') {
		const root = qs('#toast-root');
		const toast = document.createElement('div');
		toast.className = `toast toast-${tone}`;
		toast.textContent = message;
		root.appendChild(toast);
		requestAnimationFrame(() => toast.classList.add('show'));
		setTimeout(() => {
			toast.classList.remove('show');
			setTimeout(() => toast.remove(), 220);
		}, 3200);
	}

	confirm({ title, message, confirmLabel = 'Continue', tone = 'primary' }) {
		return new Promise(resolve => {
			const root = qs('#modal-root');
			root.innerHTML = `
				<div class="modal-backdrop" data-modal-close>
					<div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
						<p class="eyebrow">CONFIRM ACTION</p>
						<h2 id="confirm-title">${escapeHtml(title)}</h2>
						<p>${escapeHtml(message)}</p>
						<div class="modal-actions">
							<button class="button button-secondary" data-modal-cancel type="button">Cancel</button>
							<button class="button button-${tone}" data-modal-confirm type="button">${escapeHtml(confirmLabel)}</button>
						</div>
					</div>
				</div>
			`;
			const finish = value => {
				root.innerHTML = '';
				resolve(value);
			};
			qs('[data-modal-confirm]', root).addEventListener('click', () => finish(true));
			qs('[data-modal-cancel]', root).addEventListener('click', () => finish(false));
			qs('[data-modal-close]', root).addEventListener('click', event => {
				if (event.target === event.currentTarget) finish(false);
			});
		});
	}
}

const app = new VeciApp();
app.start().catch(error => console.error('VeCI startup failed', error));
