'use strict';
'require view';
'require form';
'require fs';
'require uci';
'require ui';

function yesno(v) {
	return v ? _('Online') : _('Offline');
}

function statusTable(st) {
	var sig = '-';
	if (st.signal_percent != null)
		sig = st.signal_percent + '%' + (st.signal_dbm != null ? ' (' + st.signal_dbm + ' dBm)' : '');

	var rows = [
		[ _('Connection'), yesno(st.online) ],
		[ _('Active SIM'), st.sim ? 'SIM ' + st.sim : '-' ],
		[ _('IPv4'), st.ipv4 || '-' ],
		[ _('Gateway'), st.gateway || '-' ],
		[ _('Signal'), sig ],
		[ _('SIM status'), st.sim_status || '-' ],
		[ _('Operator'), st.operator || '-' ],
		[ _('Access technology'), st.access_tech || '-' ],
		[ _('Registration status'), st.registration_status || '-' ],
		[ _('Packet attach'), st.packet_status || st.packet_attach || '-' ],
		[ _('Registration denied'), st.registration_denied ? _('Yes') : _('No') ],
		[ _('Extended network error'), st.extended_error || '-' ],
		[ _('ICCID'), st.iccid || '-' ],
		[ _('Manufacturer'), st.manufacturer || '-' ],
		[ _('Modem'), st.model || '-' ],
		[ _('Revision'), st.revision || '-' ],
		[ _('IMEI'), st.imei || '-' ],
		[ _('Data interface'), st.data_interface || '-' ],
		[ _('AT port'), st.at_port || '-' ],
		[ _('Data mode'), st.mode || '-' ],
		[ _('Wi-Fi hardware'), st.wifi || '2.4 GHz single-band' ]
	];

	return E('table', { 'class': 'table' },
		rows.map(function(r) {
			return E('tr', {}, [
				E('td', { 'style': 'width:35%;font-weight:bold' }, [ r[0] ]),
				E('td', {}, [ String(r[1]) ])
			]);
		})
	);
}

return view.extend({
	load: function() {
		return Promise.all([
			uci.load('we5927_lte'),
			fs.exec('/usr/sbin/we5927-lte', [ 'status-fast' ]).catch(function(e) {
				return { stdout: '', stderr: String(e) };
			})
		]);
	},

	render: function(data) {
		var res = data[1] || {};
		var st = {};

		try {
			st = JSON.parse(res.stdout || '{}');
		}
		catch (e) {
			st = { error: res.stdout || res.stderr || String(e) };
		}

		var refresh = E('button', {
			'class': 'btn cbi-button cbi-button-action',
			'click': function() { window.location.reload(); }
		}, [ _('Refresh status') ]);

		var live = E('div', { 'class': 'cbi-section' }, [
			E('h3', {}, [ _('Live 4G status') ]),
			st.error ? E('div', { 'class': 'alert-message warning' }, [ st.error ]) : statusTable(st),
			E('div', { 'style': 'margin-top:10px' }, [ refresh ])
		]);

		var m = new form.Map('we5927_lte', _('4G / Dual SIM'),
			_('LTE automation for ZBT-WE5927 / WE2825-2SIM. This unit has 2.4 GHz Wi-Fi only. 4G data uses usb0/RNDIS and AT control uses the CX07E serial interface.'));

		var s = m.section(form.NamedSection, 'main', 'modem', _('LTE settings'));
		s.addremove = false;

		var o = s.option(form.Flag, 'enabled', _('Enable LTE automation'));
		o.default = o.enabled;

		o = s.option(form.Value, 'apn', _('APN'));
		o.placeholder = 'internet';
		o.rmempty = false;

		o = s.option(form.ListValue, 'sim', _('Preferred SIM'));
		o.value('1', _('SIM 1'));
		o.value('2', _('SIM 2'));

		o = s.option(form.Flag, 'auto_failover', _('Automatic SIM failover'));
		o.default = o.enabled;
		o.description = _('If repeated modem recovery fails, switch to the other SIM and power-cycle the modem.');

		o = s.option(form.Value, 'ping_host', _('Connectivity test host'));
		o.placeholder = '1.1.1.1';
		o.datatype = 'host';

		o = s.option(form.Value, 'ping_interval', _('Check interval (seconds)'));
		o.datatype = 'uinteger';

		o = s.option(form.Value, 'fail_threshold', _('Failures before reconnect'));
		o.datatype = 'uinteger';

		o = s.option(form.Value, 'hard_reset_after', _('Reconnect cycles before modem power-cycle'));
		o.datatype = 'uinteger';

		o = s.option(form.Value, 'sim_failover_after', _('Recovery cycles before switching SIM'));
		o.datatype = 'uinteger';

		function actionButton(label, args, style, confirmText) {
			return E('button', {
				'class': 'btn cbi-button cbi-button-' + (style || 'action'),
				'style': 'margin-right:8px;margin-bottom:8px',
				'click': function(ev) {
					ev.preventDefault();
					if (confirmText && !confirm(confirmText))
						return;

					ev.currentTarget.disabled = true;
					fs.exec('/usr/sbin/we5927-lte', args).then(function(out) {
						ui.addNotification(null, E('p', {}, [
							out.stdout || out.stderr || _('Command completed')
						]));
					}).catch(function(e) {
						ui.addNotification(null, E('p', {}, [ String(e) ]), 'error');
					}).finally(function() {
						ev.currentTarget.disabled = false;
					});
				}
			}, [ label ]);
		}

		var actions = E('div', { 'class': 'cbi-section' }, [
			E('h3', {}, [ _('Manual actions') ]),
			E('div', {}, [
				actionButton(_('Repair USB / RNDIS'), [ 'usb-repair' ], 'action'),
				actionButton(_('Reconnect 4G'), [ 'reconnect' ], 'apply'),
				actionButton(_('Power-cycle modem'), [ 'power-cycle' ], 'reset',
					_('Power-cycle the LTE modem now? Internet will be interrupted temporarily.')),
				actionButton(_('Switch to SIM 1'), [ 'sim', '1' ], 'apply',
					_('Switch to SIM 1 and restart the LTE modem?')),
				actionButton(_('Switch to SIM 2'), [ 'sim', '2' ], 'apply',
					_('Switch to SIM 2 and restart the LTE modem?'))
			])
		]);

		return m.render().then(function(node) {
			return E([], [ live, node, actions ]);
		});
	}
});
