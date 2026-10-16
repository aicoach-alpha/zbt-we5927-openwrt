/*
 * VeCI bounded multipart SMS-DELIVER reassembler (offline/inert).
 * GPL-2.0-only.
 *
 * No modem, network, AT or file operations. The caller MUST:
 * - decode every SMS-DELIVER PDU first (no raw text-mode SMS),
 * - supply a nonzero trusted SIM/ingress scope_id (not guessed from sender),
 * - use monotonic milliseconds; never store this state across processes,
 * - clear completed messages and session state when access ends/SIM changes.
 *
 * Limits: 2 concurrent groups; <=8 parts; <=512 UTF-8 bytes/part;
 * <=2048 bytes total; maximum 600000 ms per incomplete group. A duplicate
 * with identical part bytes is harmless; conflicting metadata or duplicates
 * poison and erase all pending groups, without automatic retries. Completed
 * group metadata remains as a tombstone until explicit reset/expiry to avoid
 * treating a delayed duplicate as a fresh message.
 *
 * NOTE: reference reuse and forged SMS sender identity are not authenticatable
 * from the GSM protocol alone. Requires device-level integration tests.
 */
#include "veci-sms-multipart.h"
#include <errno.h>
#include <string.h>

static void wipe(void *ptr, size_t length)
{
    volatile unsigned char *v = (volatile unsigned char *)ptr;
    while (length--) *v++ = 0;
}

void veci_mp_clear_result(struct veci_mp_result *out)
{
    if (out) wipe(out, sizeof(*out));
}

void veci_mp_reset(struct veci_mp_state *state)
{
    if (state) wipe(state, sizeof(*state));
}

static int invalid(struct veci_mp_state *state, int err)
{
    if (state) {
        wipe(state->groups, sizeof(state->groups));
        state->poisoned = 1;
    }
    return -err;
}

static size_t limited_length(const char *s, size_t max)
{
    size_t i;
    if (!s) return max;
    for (i = 0; i < max; i++) {
        if (!s[i]) return i;
    }
    return max;
}

/* Strict UTF-8: no embedded NUL, overlong encoding, surrogate or out-of-range
 * scalars. Every SMS part must be independently valid UTF-8 (PDU decoder rule).
 */
static int utf8_ok(const char *text, size_t size)
{
    size_t i = 0, k;
    if (!text || !size || size > VECI_MP_PART_MAX) return 0;
    while (i < size) {
        unsigned char c = (unsigned char)text[i];
        uint32_t cp;
        unsigned int n;
        if (c >= 0x20u && c <= 0x7eu) { i++; continue; }
        if (c == '\n' || c == '\r' || c == '\t') { i++; continue; }
        if (c >= 0xc2u && c <= 0xdfu) {
            cp = c & 31u; n = 2u;
        } else if (c >= 0xe0u && c <= 0xefu) {
            cp = c & 15u; n = 3u;
        } else if (c >= 0xf0u && c <= 0xf4u) {
            cp = c & 7u; n = 4u;
        } else {
            return 0;
        }
        if (n > size - i) return 0;
        for (k = 1u; k < n; ++k) {
            unsigned char x = (unsigned char)text[i+k];
            if (x < 0x80u || x > 0xbfu) return 0;
            cp = (cp << 6) | (x & 63u);
        }
        if ((n == 2u && cp < 0x80u) ||
            (n == 3u && cp < 0x800u) ||
            (n == 4u && cp < 0x10000u) ||
            cp > 0x10ffffu ||
            (cp >= 0xd800u && cp <= 0xdfffu)) return 0;
        i += n;
    }
    return 1;
}

static int valid(const struct veci_mp_part *part)
{
    size_t slen, i;
    const char *s;
    if (!part || !part->scope_id || !part->sender || !part->text ||
        (part->alphabet != 0u && part->alphabet != 2u) ||
        part->concat_total < 2u || part->concat_total > VECI_MP_PARTS ||
        part->concat_part < 1u || part->concat_part > part->concat_total ||
        part->concat_is_16bit > 1u ||
        (!part->concat_is_16bit && part->concat_ref > 255u) ||
        (part->concat_is_16bit && part->concat_ref > 65535u) ||
        !utf8_ok(part->text, part->text_len)) return 0;
    slen = limited_length(part->sender, VECI_MP_SENDER_MAX);
    if (!slen || slen >= VECI_MP_SENDER_MAX) return 0;
    s = part->sender;
    if (s[0] == '+') {
        s++; slen--;
        if (!slen) return 0;
    }
    for (i = 0; i < slen; i++) {
        if (s[i] < '0' || s[i] > '9') return 0;
    }
    return 1;
}

static int matches(const struct veci_mp_group *g,
                   const struct veci_mp_part *p)
{
    return g->scope_id == p->scope_id &&
           strcmp(g->sender, p->sender) == 0 &&
           g->ref == p->concat_ref &&
           g->ref_16bit == p->concat_is_16bit;
}

static int expire_groups(struct veci_mp_state *state, int64_t now_ms)
{
    unsigned int i;
    for (i = 0; i < VECI_MP_GROUPS; ++i) {
        struct veci_mp_group *g = &state->groups[i];
        if (!g->occupied) continue;
        if (now_ms < g->opened_ms) return invalid(state, EPROTO);
        if (now_ms - g->opened_ms >= VECI_MP_TTL_MAX) {
            if (!g->completed) return invalid(state, ETIMEDOUT);
            wipe(g, sizeof(*g)); /* expire completed tombstone */
        }
    }
    return 0;
}

/* Explicit expiry check may be called from the owner process's scheduler.
 * Returns 0 or a negative errno. It never automatically starts new work.
 */
int veci_mp_expire(struct veci_mp_state *state, int64_t now_ms)
{
    if (!state || now_ms < 0) return -EINVAL;
    if (state->poisoned) return -EIO;
    if (state->clock_valid && now_ms < state->last_now_ms)
        return invalid(state, EPROTO);
    state->last_now_ms = now_ms;
    state->clock_valid = 1;
    return expire_groups(state, now_ms);
}

/* Return 0 while incomplete, 1 when text was assembled, negative errno if
 * rejected. Output is wiped on every call. Access/ACL check belongs upstream.
 */
int veci_mp_add(struct veci_mp_state *state,
                const struct veci_mp_part *part, int64_t now_ms,
                struct veci_mp_result *out)
{
    struct veci_mp_group *g = NULL;
    unsigned int i, idx, mask, slot = VECI_MP_GROUPS;
    size_t len = 0;
    int r;
    if (!state || !out) return -EINVAL;
    veci_mp_clear_result(out);
    if (state->poisoned) return -EIO;
    if (now_ms < 0 || !valid(part)) return -EINVAL;
    r = veci_mp_expire(state, now_ms);
    if (r != 0) return r;
    for (i = 0; i < VECI_MP_GROUPS; ++i) {
        if (state->groups[i].occupied) {
            if (matches(&state->groups[i], part)) {
                g = &state->groups[i];
                break;
            }
        } else if (slot == VECI_MP_GROUPS) {
            slot = i;
        }
    }
    if (g) {
        if (g->total != part->concat_total ||
            g->alphabet != part->alphabet ||
            g->ref_16bit != part->concat_is_16bit)
            return invalid(state, EPROTO);
        if (g->completed) return -EALREADY;
    } else {
        if (slot == VECI_MP_GROUPS) return -ENOSPC;
        g = &state->groups[slot];
        /* Fresh allocation. Stale content always cleared at finalization. */
        wipe(g, sizeof(*g));
        g->occupied = 1;
        g->opened_ms = now_ms;
        g->scope_id = part->scope_id;
        g->ref = part->concat_ref;
        g->ref_16bit = part->concat_is_16bit;
        g->total = part->concat_total;
        g->alphabet = part->alphabet;
        memcpy(g->sender, part->sender, strlen(part->sender)+1u);
    }
    idx = part->concat_part - 1u;
    mask = 1u << idx;
    if (g->mask & mask) {
        if (g->len[idx] != part->text_len ||
            memcmp(g->chunks[idx], part->text, part->text_len) != 0)
            return invalid(state, EPROTO);
        return 0; /* exact duplicate, no second output */
    }
    memcpy(g->chunks[idx], part->text, part->text_len);
    g->chunks[idx][part->text_len] = '\0';
    g->len[idx] = (uint16_t)part->text_len;
    g->mask |= mask;
    g->received++;
    if (g->received != g->total) return 0;
    /* Size-validate ALL segments before exposing any sensitive text. */
    for (i = 0; i < g->total; ++i) {
        if (!(g->mask & (1u << i)) ||
            g->len[i] > VECI_MP_TOTAL_MAX - len)
            return invalid(state, EOVERFLOW);
        len += g->len[i];
    }
    len = 0;
    for (i = 0; i < g->total; ++i) {
        memcpy(out->text + len, g->chunks[i], g->len[i]);
        len += g->len[i];
    }
    out->text[len] = '\0';
    out->text_len = len;
    out->scope_id = g->scope_id;
    out->total_parts = g->total;
    for (i = 0; i < VECI_MP_PARTS; ++i) {
        wipe(g->chunks[i], sizeof(g->chunks[i]));
        g->len[i] = 0u;
    }
    g->mask = 0u;
    g->completed = 1;
    return 1;
}
