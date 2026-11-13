const EMPTY_SESSION = '00000000000000000000000000000000';

export class VeciApi {
	constructor() {
		this.sessionId = sessionStorage.getItem('veci.ubus_session') || '';
	}

	async request(sessionId, object, method, params = {}, options = {}) {
		const timeout = options.timeout ?? 10000;
		const controller = new AbortController();
		const timer = setTimeout(() => controller.abort(), timeout);

		try {
			const response = await fetch('/ubus', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				cache: 'no-store',
				signal: controller.signal,
				body: JSON.stringify({
					jsonrpc: '2.0',
					id: Date.now(),
					method: 'call',
					params: [sessionId || EMPTY_SESSION, object, method, params]
				})
			});

			if (!response.ok) throw new Error(`HTTP ${response.status}`);

			const payload = await response.json();
			if (payload.error) throw new Error(payload.error.message || `${object}.${method} failed`);
			if (!Array.isArray(payload.result)) throw new Error(`Invalid ubus response for ${object}.${method}`);
			return payload.result;
		} catch (error) {
			if (error.name === 'AbortError') throw new Error(`${object}.${method} timed out`);
			throw error;
		} finally {
			clearTimeout(timer);
		}
	}

	async login(username, password) {
		const result = await this.request(EMPTY_SESSION, 'session', 'login', { username, password });
		const session = result?.[1]?.ubus_rpc_session;
		if (result?.[0] !== 0 || !session) throw new Error('Invalid username or password');
		this.sessionId = session;
		sessionStorage.setItem('veci.ubus_session', session);
		return session;
	}

	async call(object, method, params = {}, options = {}) {
		if (!this.sessionId) throw new Error('Not authenticated');
		const result = await this.request(this.sessionId, object, method, params, options);
		const status = result?.[0];
		if (status !== 0) {
			const error = new Error(`${object}.${method} returned ubus status ${status}`);
			error.ubusStatus = status;
			throw error;
		}
		return result?.[1] ?? {};
	}

	async validateSession() {
		if (!this.sessionId) return false;
		try {
			await this.call('session', 'access', {});
			return true;
		} catch {
			this.clearSession();
			return false;
		}
	}

	async logout() {
		if (this.sessionId) {
			try {
				await this.call('session', 'destroy', {});
			} catch {}
		}
		this.clearSession();
	}

	clearSession() {
		this.sessionId = '';
		sessionStorage.removeItem('veci.ubus_session');
	}

	board() {
		return this.call('system', 'board', {});
	}
	systemInfo() {
		return this.call('system', 'info', {});
	}
	interfaces() {
		return this.call('network.interface', 'dump', {});
	}
	wirelessStatus() {
		return this.call('network.wireless', 'status', {});
	}
	interfaceStatus(name) {
		return this.call(`network.interface.${name}`, 'status', {});
	}

	interfaceAction(name, action) {
		if (!['up', 'down'].includes(action)) throw new Error('Unsupported interface action');
		return this.call(`network.interface.${name}`, action, {});
	}

	uciGet(config, section = null) {
		const params = { config };
		if (section) params.section = section;
		return this.call('uci', 'get', params);
	}

	uciSet(config, section, values) {
		return this.call('uci', 'set', { config, section, values });
	}

	uciAdd(config, type, values = {}, name = null) {
		const params = { config, type, values };
		if (name) params.name = name;
		return this.call('uci', 'add', params);
	}

	uciDelete(config, section, option = null) {
		const params = { config, section };
		if (option) params.option = option;
		return this.call('uci', 'delete', params);
	}

	uciCommit(config) {
		return this.call('uci', 'commit', { config });
	}

	cellularStatus() {
		return this.call('veci.cellular', 'status', {});
	}

	cellularAction(method, params = {}) {
		if (!['reconnect', 'switchSim'].includes(method)) throw new Error('Unsupported cellular action');
		return this.call('veci.cellular', method, params);
	}

	veci(method, params = {}) {
		return this.call('veci', method, params);
	}
}
