'use strict';

/*
 * VeCI private SMS capability endpoint - STAGED SOURCE ONLY / NOT DEPLOYED.
 * This object owns two-step consent entirely in the existing rpcd ucode VM.
 * Live worker is invoked only after authenticated, one-use consent.
 * No serial command, no SMS contents or sender, no additional daemon.
 *
 * HTTP /ubus authenticates SID and appends ubus_rpc_session to the request;
 * request.info.acl is ubusd's UNIX peer ACL, NOT the browser username.
 * Only root-owned uhttpd is trusted to forward SIDs. Direct root ubus
 * callers are also within the device root trust boundary, NOT HTTP proof.
 */
let fs = require('fs');
let ubus = require('ubus').connect();
let pending = null;

/* One pending approval per device; RPC VM persists between calls. */
function denied() {
    return { ok: false, reason: 'not_authorized' };
}
function sid_ok(sid) {
    return type(sid) == 'string' &&
        match(sid, /^[0-9a-f]{32}$/) != null &&
        sid != '00000000000000000000000000000000';
}
function slot_ok(slot) {
    return type(slot) == 'int' && slot >= 0 && slot <= 65535;
}
function now_ms() {
    let stamp = clock(true);
    if (!stamp || type(stamp) != 'array' ||
        type(stamp[0]) != 'int' || type(stamp[1]) != 'int' ||
        stamp[0] < 0 || stamp[1] < 0 || stamp[1] >= 1000000000)
        return null;
    return stamp[0] * 1000 + int(stamp[1] / 1000000);
}
function valid_call(req, action) {
    let info = req && req.info;
    let args = req && req.args;
    return info && args && info.acl && info.acl.user == 'root' &&
        info.object && info.object.name == 'veci.sms.private' &&
        info.method == action && sid_ok(args.ubus_rpc_session) &&
        slot_ok(args.slot);
}
function checked_access(req, cb) {
    /* uhttpd ACL check is mandatory; the secondary session.access closes
     * the gap when armRead has a distinct ACL from sensitive readSlot.
     * SID from a privileged *local* root client is not HTTP-origin proof.
     */
    return ubus.defer('session', 'access', {
        ubus_rpc_session: req.args.ubus_rpc_session,
        scope: 'ubus',
        object: 'veci.sms.private',
        function: 'readSlot'
    }, function(status, result) {
        let authorized = status == 0 && result != null &&
            type(result.access) == 'bool' && result.access == true;
        cb(authorized);
    });
}
function fresh_record(now) {
    if (!pending)
        return false;
    /* Clock rollback also revokes approval, do not silently renew. */
    if (now == null || now < pending.armed_ms ||
        now >= pending.armed_ms + 30000) {
        pending = null;
        return false;
    }
    return true;
}
function arm_request(req) {
    if (!valid_call(req, 'armRead') ||
        req.args.scope != 'single_sms_private_read' ||
        req.args.consent != 'I_CONFIRM_READ_THIS_ONE_SMS')
        return denied();

    return checked_access(req, function(authorized) {
        if (!authorized) {
            req.reply(denied(), 0);
            return;
        }
        let now = now_ms();
        if (now == null) {
            req.reply({ok:false, reason:'unavailable'}, 0);
            return;
        }
        if (fresh_record(now)) {
            req.reply({ok:false, reason:'approval_pending'}, 0);
            return;
        }
        /* Generate ONLY after real ACL check. Never take from browser.
         * fs.readfile() must return exactly 16 cryptographic random bytes.
         */
        let random = fs.readfile('/dev/urandom', 16);
        if (type(random) != 'string' || length(random) != 16) {
            req.reply({ok:false, reason:'unavailable'}, 0);
            return;
        }
        let token = hexenc(random);
        if (length(token) != 32) {
            req.reply({ok:false, reason:'unavailable'}, 0);
            return;
        }
        pending = {
            sid: req.args.ubus_rpc_session,
            slot: req.args.slot,
            armed_ms: now,
            token: token
        };
        /* Ephemeral token in method reply only. Client must keep in JS
         * memory and never URL, storage, logs, generic support bundles.
         */
        req.reply({ok:true, token:token, expires_in_seconds:30}, 0);
    });
}
function read_request(req) {
    if (!valid_call(req, 'readSlot') ||
        type(req.args.token) != 'string' ||
        length(req.args.token) != 32 ||
        match(req.args.token, /^[0-9a-f]{32}$/) == null)
        return denied();

    return checked_access(req, function(authorized) {
        if (!authorized) {
            req.reply(denied(), 0);
            return;
        }
        let now = now_ms();
        if (!fresh_record(now)) {
            req.reply({ok:false, reason:'approval_missing_or_expired'}, 0);
            return;
        }
        let record = pending;
        /* Consume before checking token, slot and SID. Even a wrong
         * authorized call burns approval, never automatic retry.
         */
        pending = null;
        if (record.sid != req.args.ubus_rpc_session ||
            record.slot != req.args.slot || record.token != req.args.token) {
            req.reply(denied(), 0);
            return;
        }
        /* Explicit one-shot modem request AFTER successful readSlot ACL,
         * consumed token and exact SID+slot match. No arbitrary command;
         * sanitized decimal slot only. No shell or background job.
         */
        let proc = fs.popen(['/usr/libexec/veci-sms-private-read',
                              '' + req.args.slot], 'r');
        if (!proc) {
            req.reply({ok:false, reason:'sms_unavailable'}, 0);
            return;
        }
        let raw = proc.read(1400);
        let overflow = proc.read(1);
        let status = proc.close();
        if (status != 0 || type(raw) != 'string' ||
            length(raw) > 1400 || (overflow != null && length(overflow)) > 0) {
            req.reply({ok:false, reason:'sms_unavailable'}, 0);
            return;
        }
        let result;
        try { result = json(raw); } catch (e) { result = null; }
        raw = null;
        if (!result || result.ok != true ||
            result.index != req.args.slot ||
            type(result.pdu) != 'string' ||
            length(result.pdu) < 4 || length(result.pdu) > 512 ||
            length(result.pdu) % 2 != 0 ||
            match(result.pdu, /^[0-9A-F]+$/) == null) {
            req.reply({ok:false, reason:'sms_unavailable'}, 0);
            return;
        }
        /* Private RPC ONLY. No PDU in metadata, logs, generic dumps or
         * persistent storage. Frontend decodes in ephemeral foreground.
         */
        req.reply({ok:true, index:req.args.slot, pdu:result.pdu}, 0);

    });
}

return {
    'veci.sms.private': {
        armRead: {
            args: { slot:32, scope:'', consent:'' },
            call:arm_request
        },
        readSlot: {
            args: { slot:32, token:'' },
            call:read_request
        }
    }
};
