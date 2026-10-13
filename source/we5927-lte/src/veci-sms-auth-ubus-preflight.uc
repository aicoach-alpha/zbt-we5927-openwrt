'use strict';

/*
 * SOURCE-ONLY rpcd ucode method. Does not read, send, list or delete SMS.
 *
 * uhttpd /ubus overwrites ubus_rpc_session on the RPC it forwards and
 * checks the permission before invoking this method. In contrast, a
 * direct local ubus call can supply a claimed SID. Restrict the native
 * peer ACL to root, i.e. trusted privileged local code or uhttpd running
 * as root. req.info.acl.user is NOT the browser account name.
 *
 * This is a diagnostic ACL preflight, NOT a production authentication
 * proof for separate armRead/readSlot requests; do not chain it to AT.
 */
let ubus = require('ubus').connect();

function denied() {
    return { ok: false, reason: 'not_authorized', diagnostic_only: true };
}

function valid_sid(s) {
    return typeof s == 'string' &&
        /^[0-9a-f]{32}$/.test(s) &&
        s != '00000000000000000000000000000000';
}

return {
    'veci.sms.auth.audit': {
        probe: {
            args: { slot: 32, scope: '' },
            call: function(request) {
                let args = request && request.args;
                let info = request && request.info;
                let acl = info && info.acl;
                if (!args || !acl ||
                    acl.user != 'root' ||
                    info.method != 'probe' ||
                    !info.object || info.object.name != 'veci.sms.auth.audit' ||
                    !valid_sid(args.ubus_rpc_session) ||
                    !Number.isInteger(args.slot) ||
                    args.slot < 0 || args.slot > 65535 ||
                    args.scope != 'authorization_preflight_only')
                    return denied();

                /* session.access is an additional server-side ACL check,
                 * not an attestation that this invocation came from HTTP.
                 * Actual HTTP/native entry provenance needs physical UAT.
                 * Return only a boolean; NEVER return/log a session ID.
                 */
                return ubus.defer('session', 'access', {
                    ubus_rpc_session: args.ubus_rpc_session,
                    scope: 'ubus',
                    object: 'veci.sms.private',
                    function: 'readSlot'
                }, function(code, response) {
                    request.reply({
                        ok: code === 0 && response != null &&
                            response.access === true,
                        diagnostic_only: true
                    }, 0);
                });
            }
        }
    }
};
