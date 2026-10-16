/*
 * Strict single AT+CMGR response parser, source-only, GPL-2.0-only.
 * Rejects unsolicited SMS/USSD, extra frames, malformed/partial PDU,
 * different command echoes and text-mode output. Buffer wiped after take.
 * Caller must hold lock & opened-FD identity across complete modem exchange.
 */
#include "veci-sms-cmgr-frame.h"
#include <errno.h>
#include <string.h>

extern int veci_sms_decode_deliver(const char *, struct veci_sms_deliver *);

static void wipe(void *ptr, size_t n)
{
    volatile unsigned char *p = (volatile unsigned char *)ptr;
    while (n--) *p++ = 0;
}
void veci_sms_cmgr_clear(struct veci_sms_cmgr_frame *s)
{
    if (s) wipe(s, sizeof(*s));
}
static int reject(struct veci_sms_cmgr_frame *s)
{
    wipe(s->pdu, sizeof(s->pdu));
    wipe(&s->framing, sizeof(s->framing));
    s->completed = 0;
    s->failed = 1;
    return -EPROTO;
}
static int decimal(const char **ptr, unsigned int max, unsigned int *out)
{
    unsigned int n = 0, count = 0;
    const char *p = *ptr;
    while (*p >= '0' && *p <= '9') {
        if (++count > 5u) return -1;
        n = n * 10u + (unsigned int)(*p++ - '0');
        if (n > max) return -1;
    }
    if (!count) return -1;
    *out = n;
    *ptr = p;
    return 0;
}
/* PDU-only form of +CMGR: <stat>,,<length>, no sender or text-mode. */
static int cmgr_header(const char *line, unsigned int *status,
                       unsigned int *length)
{
    const char *p = line;
    if (strncmp(p, "+CMGR:", 6u)) return -1;
    p += 6;
    while (*p == ' ') p++;
    if (decimal(&p, 4u, status)) return -1;
    if (*p != ',') return -1;
    ++p;
    while (*p == ' ') p++;
    if (*p != ',') return -1;
    ++p;
    while (*p == ' ') p++;
    if (decimal(&p, 240u, length) || !*length || *p) return -1;
    return 0;
}
static void on_line(int event, const char *line, int meta, void *ctx)
{
    struct veci_sms_cmgr_frame *s = ctx;
    unsigned int status = 0, tpdu = 0;
    if (s->failed) return;
    if (event == VECI_FRAME_OTHER && !s->stage &&
        !s->echo_seen && !strncmp(line, "AT+CMGR=", 8u)) {
        char want[24];
        /* Do not accept a different slot's echo or arbitrary AT line. */
        size_t n = 0;
        unsigned int v = s->slot;
        char reversed[6];
        do {
            reversed[n++] = (char)('0' + v % 10u);
            v /= 10u;
        } while (v && n < sizeof(reversed));
        memcpy(want, "AT+CMGR=", 8u);
        for (size_t i = 0; i < n; ++i)
            want[8u+i] = reversed[n-1u-i];
        want[8u+n] = 0;
        wipe(reversed, sizeof(reversed));
        if (strcmp(want, line)) { (void)reject(s); return; }
        s->echo_seen = 1;
        return;
    }
    if (event == VECI_FRAME_OTHER && s->stage == 0 &&
        !cmgr_header(line, &status, &tpdu)) {
        s->status = status;
        s->tpdu = tpdu;
        s->stage = 1;
        return;
    }
    if (event == VECI_FRAME_SMS_PDU && s->stage == 1 &&
        meta == (int)s->tpdu) {
        size_t len = strlen(line);
        if (!len || len > VECI_FRAME_PDU_MAX) {
            (void)reject(s); return;
        }
        memcpy(s->pdu, line, len + 1u);
        s->stage = 2;
        return;
    }
    if (event == VECI_FRAME_OK && s->stage == 2) {
        s->stage = 3;
        return;
    }
    /* Reject error, extra CMGL/CMGR, URCs, repeated OK, arbitrary line. */
    (void)reject(s);
}
int veci_sms_cmgr_init(struct veci_sms_cmgr_frame *s,
                       const struct veci_sms_read_policy *p)
{
    if (!s) return -EINVAL;
    veci_sms_cmgr_clear(s);
    if (!p || p->state != VECI_SMS_READ_ISSUED ||
        !p->session_binding || !p->request_nonce || !p->modem_generation ||
        p->slot > 65535u) return -EACCES;
    s->slot = p->slot;
    s->binding = p->session_binding;
    s->nonce = p->request_nonce;
    s->generation = p->modem_generation;
    veci_frame_init(&s->framing);
    return 0;
}
int veci_sms_cmgr_feed(struct veci_sms_cmgr_frame *s,
                       const unsigned char *bytes, size_t size)
{
    int rc;
    if (!s || (!bytes && size)) return -EINVAL;
    if (!s->nonce) return -EACCES;
    if (s->failed) return -EPROTO;
    if (s->completed) return reject(s);
    if (s->stage == 3u) {
        if (size > VECI_FRAME_STREAM_MAX - s->framing.total)
            return reject(s);
        for (size_t i = 0; i < size; ++i)
            if (bytes[i] != '\r' && bytes[i] != '\n') return reject(s);
        s->framing.total += size;
        return 0;
    }
    rc = veci_frame_feed(&s->framing, bytes, size, on_line, s);
    if (!s->framing.line_len)
        wipe(s->framing.line, sizeof(s->framing.line));
    if (rc || s->failed) return reject(s);
    return 0;
}
int veci_sms_cmgr_finish(struct veci_sms_cmgr_frame *s)
{
    if (!s || !s->nonce) return -EACCES;
    if (s->failed || s->completed || s->stage != 3u)
        return reject(s);
    if (veci_frame_finish(&s->framing, on_line, s) || s->failed)
        return reject(s);
    wipe(&s->framing, sizeof(s->framing));
    s->completed = 1;
    return 0;
}
int veci_sms_cmgr_take(struct veci_sms_cmgr_frame *s,
                       const struct veci_sms_read_policy *p,
                       struct veci_sms_deliver *out)
{
    int rc;
    if (!s || !out) return -EINVAL;
    wipe(out, sizeof(*out));
    if (!p || !s->completed || s->failed ||
        p->state != VECI_SMS_READ_COMPLETED ||
        p->slot != s->slot || p->session_binding != s->binding ||
        p->request_nonce != s->nonce || p->modem_generation != s->generation) {
        veci_sms_cmgr_clear(s);
        return -EACCES;
    }
    rc = veci_sms_decode_deliver(s->pdu, out);
    veci_sms_cmgr_clear(s);
    if (rc) {
        wipe(out, sizeof(*out));
        return -EPROTO;
    }
    return 0;
}
