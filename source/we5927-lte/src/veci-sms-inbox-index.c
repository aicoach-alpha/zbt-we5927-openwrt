/*
 * Bounded, ephemeral SMS inbox index framing (AT+CMGL=4).
 * No message text, sender, SMS PDU or OTP retained or returned.
 * Not compiled into router firmware. No modem I/O, network, logs,
 * persistence, authorization/session service, or retry capability.
 * GPL-2.0-only.
 */
#include "veci-sms-inbox-index.h"
#include <errno.h>
#include <stdint.h>
#include <string.h>

static void wipe(void *memory, size_t bytes)
{
    volatile unsigned char *p = (volatile unsigned char *)memory;
    while (bytes--) *p++ = 0;
}
void veci_sms_index_clear(struct veci_sms_index_session *s)
{
    if (s) wipe(s, sizeof(*s));
}
int veci_sms_index_init(struct veci_sms_index_session *s, int approved,
                        int unread_to_read_effect_acknowledged)
{
    if (!s) return -EINVAL;
    veci_sms_index_clear(s);
    /* SMS listing via AT+CMGL can mark unread messages as read.
     * It is not a side-effect-free operation. Refuse without both flags.
     */
    if (approved != 1 || unread_to_read_effect_acknowledged != 1)
        return -EACCES;
    s->approved = 1;
    veci_frame_init(&s->frame);
    return 0;
}
static void invalidate(struct veci_sms_index_session *s)
{
    wipe(s->entries, sizeof(s->entries));
    wipe(&s->pending, sizeof(s->pending));
    s->count = 0;
    s->completed = 0;
    s->failed = 1;
}
/* Parse strictly the PDU-mode CMGL index header:
 *   +CMGL: <index>,<stat>,,<tpdu_octets>
 * No text-mode, quoted sender, arbitrary string, ANSI, or AT injection.
 */
static int decimal(const char **cursor, unsigned int max, uint32_t *out)
{
    const char *p = *cursor;
    uint32_t value = 0;
    unsigned int digits = 0;
    while (*p >= '0' && *p <= '9') {
        if (++digits > 5u) return -1;
        value = value * 10u + (uint32_t)(*p++ - '0');
        if (value > max) return -1;
    }
    if (!digits) return -1;
    *out = value;
    *cursor = p;
    return 0;
}
static void blanks(const char **cursor)
{
    while (**cursor == ' ') ++*cursor;
}
static int header(const char *line, struct veci_sms_index_entry *entry)
{
    static const char prefix[] = "+CMGL:";
    uint32_t number, state, len;
    const char *p;
    if (strncmp(line, prefix, sizeof(prefix)-1u)) return -1;
    p = line + sizeof(prefix)-1u;
    blanks(&p);
    if (decimal(&p, 65535u, &number) || *p++ != ',') return -1;
    blanks(&p);
    if (decimal(&p, 4u, &state) || *p++ != ',') return -1;
    /* Alpha must be the EMPTY PDU field, not a quoted sender. */
    blanks(&p);
    if (*p++ != ',') return -1;
    blanks(&p);
    if (decimal(&p, 240u, &len) || *p) return -1;
    if (!len) return -1;
    entry->index = number;
    entry->state = state;
    entry->tpdu_octets = len;
    return 0;
}
static void on_frame(int event, const char *value, int meta, void *ctx)
{
    struct veci_sms_index_session *s = (struct veci_sms_index_session *)ctx;
    unsigned int i;
    if (s->failed) return;
    /* A complete response may carry no messages, but cannot carry
     * arbitrary lines before or after OK. An exact command echo is
     * allowed once, before any message header.
     */
    if (event == VECI_FRAME_OTHER && s->stage == 0 &&
        !s->echo_seen && !s->count && !strcmp(value, "AT+CMGL=4")) {
        s->echo_seen = 1;
        return;
    }
    if (event == VECI_FRAME_OTHER && s->stage == 0) {
        if (s->count == VECI_SMS_INDEX_MAX ||
            header(value, &s->pending) != 0) {
            invalidate(s);
            return;
        }
        for (i = 0; i < s->count; ++i) {
            if (s->entries[i].index == s->pending.index) {
                invalidate(s);
                return;
            }
        }
        s->stage = 1;
        return;
    }
    if (event == VECI_FRAME_SMS_PDU && s->stage == 1 &&
        meta > 0 && (uint32_t)meta == s->pending.tpdu_octets) {
        s->entries[s->count++] = s->pending;
        wipe(&s->pending, sizeof(s->pending));
        s->stage = 0;
        return;
    }
    if (event == VECI_FRAME_OK && s->stage == 0) {
        s->stage = 2;
        return;
    }
    /* Includes +CMTI, +CUSD, unsolicited +CMT, duplicate PDU,
     * nonmatching header, ERROR, false OK and all post-terminal data.
     */
    invalidate(s);
}
int veci_sms_index_feed(struct veci_sms_index_session *s,
                        const unsigned char *bytes, size_t n)
{
    int rc;
    if (!s || (!bytes && n)) return -EINVAL;
    if (!s->approved) return -EACCES;
    if (s->failed) return -EPROTO;
    if (s->completed) {
        /* Never retain previously approved metadata if late bytes arrive
         * after a caller already reported success. No partial replay.
         */
        if (n) invalidate(s);
        return -EPROTO;
    }
    if (s->stage == 2) {
        /* A CRLF terminal may arrive split at arbitrary transport reads.
         * Ignore ONLY CR/LF after OK, not a second command or response.
         * No bytes are committed until finish() confirms the frame.
         */
        size_t i;
        for (i = 0; i < n; ++i) {
            if (bytes[i] != '\r' && bytes[i] != '\n') {
                invalidate(s);
                wipe(&s->frame, sizeof(s->frame));
                return -EPROTO;
            }
        }
        return 0;
    }
    rc = veci_frame_feed(&s->frame, bytes, n, on_frame, s);
    if (!s->frame.line_len)
        wipe(s->frame.line, sizeof(s->frame.line));
    if (rc != 0 || s->failed) {
        invalidate(s);
        /* PDU input may contain personal SMS/OTP bytes. Wipe even if
         * framing failed midway through a partial sensitive PDU line.
         */
        wipe(&s->frame, sizeof(s->frame));
        return -EPROTO;
    }
    return 0;
}
int veci_sms_index_finish(struct veci_sms_index_session *s)
{
    if (!s) return -EINVAL;
    if (!s->approved) return -EACCES;
    if (s->failed || s->completed) return -EPROTO;
    if (veci_frame_finish(&s->frame, on_frame, s) ||
        s->failed || s->stage != 2) {
        invalidate(s);
        wipe(&s->frame, sizeof(s->frame));
        return -EPROTO;
    }
    /* Discard all raw partial/complete transport frame bytes. */
    wipe(&s->frame, sizeof(s->frame));
    wipe(&s->pending, sizeof(s->pending));
    s->completed = 1;
    return 0;
}
int veci_sms_index_count(const struct veci_sms_index_session *s)
{
    if (!s || !s->approved || !s->completed || s->failed)
        return -EACCES;
    return (int)s->count;
}
int veci_sms_index_get(const struct veci_sms_index_session *s,
                       unsigned int ordinal, struct veci_sms_index_entry *out)
{
    if (!s || !out) return -EINVAL;
    wipe(out, sizeof(*out));
    if (!s->approved || !s->completed || s->failed) return -EACCES;
    if (ordinal >= s->count) return -ENOENT;
    *out = s->entries[ordinal];
    return 0;
}
