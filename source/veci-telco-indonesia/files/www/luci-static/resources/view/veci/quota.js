'use strict';
'require view';
'require rpc';
'require ui';

var callQuotaStatus = rpc.declare({
	object: 'veci.quota',
	method: 'status',
	expect: { '': {} }
});

var callProviders = rpc.declare({
	object: 'veci.quota',
	method: 'providers',
	expect: { '': {} }
});

function numberBytes(v) {
	if (typeof v !== 'number' || !isFinite(v) || v < 0)
		return '-';
	var units = [ 'B', 'KB', 'MB', 'GB', 'TB' ];
	var u = 0;
	while (v >= 1024 && u < units.length - 1) {
		v /= 1024;
		u++;
	}
	return v.toFixed(u ? 2 : 0) + ' ' + units[u];
}

function stateLabel(state) {
	switch (state) {
	case 'ready': return _('Verified carrier quota');
	case 'stale': return _('Previously verified data is out of date');
	case 'not_connected': return _('XL account not connected');
	default: return _('Carrier quota unavailable');
	}
}

function row(name, value) {
	return E('tr', {}, [
		E('td', { 'style': 'width:40%;font-weight:600' }, [ name ]),
		E('td', {}, [ value ])
	]);
}

return view.extend({
	load: function() {
		return Promise.all([
			callQuotaStatus().catch(function() { return null; }),
			callProviders().catch(function() { return null; })
		]);
	},

	render: function(data) {
		var st = data[0] || {};
		var registry = data[1] || {};
		var valid = st.schema === 1 && st.provider === 'xl' &&
			st.state === 'ready' && st.source === 'carrier_authenticated' &&
			typeof st.total_bytes === 'number' && isFinite(st.total_bytes) &&
			typeof st.remaining_bytes === 'number' && isFinite(st.remaining_bytes) &&
			st.total_bytes > 0 && st.remaining_bytes >= 0 &&
			st.remaining_bytes <= st.total_bytes;
		var state = valid ? 'ready' : (st.state === 'stale' ? 'stale' :
			(st.state === 'not_connected' ? 'not_connected' : 'unavailable'));
		var quotaRows = [
			row(_('Operator'), 'XL'),
			row(_('Status'), stateLabel(state)),
			row(_('Total data'), valid ? numberBytes(st.total_bytes) : '-'),
			row(_('Remaining data'), valid ? numberBytes(st.remaining_bytes) : '-'),
			row(_('Last verified'), valid && st.fetched_at ? String(st.fetched_at) : '-')
		];

		var providers = Array.isArray(registry.providers) ? registry.providers : [];
		var seen = {};
		var providerRows = providers.filter(function(p) {
			if (!p || typeof p.id !== 'string' || p.id === 'xl' || seen[p.id])
				return false;
			seen[p.id] = true;
			return true;
		}).map(function(p) {
			// Provider registry explicitly declares research-only providers.
			// NEVER infer working integration from a family or existing package.
			return row(String(p.name || p.id), _('Integration not available'));
		});

		var refresh = E('button', {
			'class': 'btn cbi-button cbi-button-action',
			'click': ui.createHandlerFn(this, function() {
				return this.load().then(function(next) {
					var root = document.getElementById('veci-indonesia-quota-root');
					if (root)
						root.replaceWith(this.render(next));
				}.bind(this));
			})
		}, [ _('Refresh local status') ]);

		var root = E('div', { 'id': 'veci-indonesia-quota-root' }, [
			E('h2', {}, [ _('Operator Quota · Indonesia Edition') ]),
			E('div', { 'class': 'cbi-section' }, [
				E('h3', {}, [ _('XL package balance') ]),
				E('p', {}, [
					_('Quota is shown only after a verified, authorized carrier response.'),
					' ',
					_('The native XL runtime is installed separately and does not log in by itself.')
				]),
				E('table', { 'class': 'table' }, quotaRows),
				E('div', { 'style': 'margin-top:10px' }, [ refresh ])
			]),
			E('div', { 'class': 'cbi-section' }, [
				E('h3', {}, [ _('XL account authentication') ]),
				E('p', {}, [
					_('Not available: an operator-authorized myXL client/login method has not been verified.'),
					' ',
					_('No OTP is read automatically and no token is stored or transmitted by this page.')
				]),
				E('p', {}, [
					E('a', {
						'href': 'https://www.xl.co.id/bantuan/digital-services/our-apps/bagaimana-cara-login-ke-aplikasi-myxl-menggunakan-nomor-xl',
						'target': '_blank',
						'rel': 'noopener noreferrer'
					}, [ _('Official myXL login help') ])
				])
			]),
			E('div', { 'class': 'cbi-section' }, [
				E('h3', {}, [ _('Other Indonesian operators') ]),
				E('p', {}, [
					_('Provider names below are a research registry, not active carrier connections.')
				]),
				providerRows.length
					? E('table', { 'class': 'table' }, providerRows)
					: E('p', {}, [ _('Provider registry unavailable') ])
			])
		]);
		return root;
	},

	handleSaveApply: null,
	handleSave: null,
	handleReset: null
});
