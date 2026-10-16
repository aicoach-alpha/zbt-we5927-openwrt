/*
 * VeCI bounded +CUSD notification payload interpreter.
 * GPL-2.0-only. INACTIVE/offline: NO modem I/O, AT TX, SMS, log or storage.
 * Only UCS2 DCS 0x48/0x08 hex is decoded. Other DCS encodings remain
 * 'unsupported' until confirmed on the actual W907 modem. Never guess GSM7.
 */
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define VECI_USSD_BODY_MAX 1024
#define VECI_USSD_HEX_MAX 512

struct veci_ussd_reply {
    unsigned int mode;      /* +CUSD n=0..5 */
    unsigned int dcs;       /* UINT32_MAX if not present */
    unsigned int decoded;   /* 1 only for verified UCS2 / empty payload */
    char text[VECI_USSD_BODY_MAX + 1];
    size_t text_len;
};

static void wipe(void *p, size_t n)
{
    volatile unsigned char *b = (volatile unsigned char *)p;
    while (n--) *b++ = 0;
}

static int nibble(char ch)
{
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    return -1;
}

static int append(struct veci_ussd_reply *r, uint32_t cp)
{
    unsigned char bytes[4];
    size_t n = 0;
    if (!cp || cp > 0x10ffffu || (cp >= 0xd800u && cp <= 0xdfffu))
        return -1;
    if (cp < 0x80u) {
        bytes[n++] = (unsigned char)cp;
    } else if (cp < 0x800u) {
        bytes[n++] = (unsigned char)(0xc0u | (cp >> 6));
        bytes[n++] = (unsigned char)(0x80u | (cp & 63u));
    } else if (cp < 0x10000u) {
        bytes[n++] = (unsigned char)(0xe0u | (cp >> 12));
        bytes[n++] = (unsigned char)(0x80u | ((cp >> 6) & 63u));
        bytes[n++] = (unsigned char)(0x80u | (cp & 63u));
    } else {
        bytes[n++] = (unsigned char)(0xf0u | (cp >> 18));
        bytes[n++] = (unsigned char)(0x80u | ((cp >> 12) & 63u));
        bytes[n++] = (unsigned char)(0x80u | ((cp >> 6) & 63u));
        bytes[n++] = (unsigned char)(0x80u | (cp & 63u));
    }
    if (n > VECI_USSD_BODY_MAX - r->text_len) return -1;
    memcpy(r->text + r->text_len, bytes, n);
    r->text_len += n;
    r->text[r->text_len] = 0;
    return 0;
}

/* Return 0 if decoded, 1 if supported framing but unknown DCS,
 * -1 for malformed/spoofed notification. This function is PURE.
 */
int veci_ussd_decode_urc(const char *line, struct veci_ussd_reply *out)
{
    static const char prefix[] = "+CUSD:";
    char payload[VECI_USSD_HEX_MAX + 1];
    size_t len = 0, i;
    const char *p;
    unsigned int dcs = 0, digits = 0;
    int rc = -1;
    if (!out) return -1;
    memset(out, 0, sizeof(*out));
    out->dcs = UINT32_MAX;
    if (!line || strncmp(line, prefix, sizeof(prefix) - 1u)) return -1;
    p = line + sizeof(prefix) - 1u;
    while (*p == ' ') ++p;
    if (*p < '0' || *p > '5') return -1;
    out->mode = (unsigned int)(*p++ - '0');
    while (*p == ' ') ++p;
    if (!*p) {
        out->decoded = 1;
        return 0;
    }
    if (*p++ != ',') goto done;
    while (*p == ' ') ++p;
    if (*p++ != '"') goto done;
    while (*p && *p != '"') {
        unsigned char ch = (unsigned char)*p++;
        if (ch < 32u || ch > 126u || len >= VECI_USSD_HEX_MAX)
            goto done;
        payload[len++] = (char)ch;
    }
    if (*p++ != '"') goto done;
    payload[len] = '\0';
    while (*p == ' ') ++p;
    if (*p++ != ',') goto done;
    while (*p == ' ') ++p;
    if (*p < '0' || *p > '9') goto done;
    while (*p >= '0' && *p <= '9') {
        if (++digits > 3u) goto done;
        dcs = dcs * 10u + (unsigned int)(*p++ - '0');
        if (dcs > 255u) goto done;
    }
    while (*p == ' ') ++p;
    if (*p) goto done;
    out->dcs = dcs;
    if (dcs != 72u && dcs != 8u) {
        rc = 1; /* valid +CUSD framing, unknown DCS; NO text disclosure */
        goto done;
    }
    if (len % 4u) goto done;  /* each UCS2 unit is 4 hex digits */
    for (i = 0; i < len; i += 4) {
        int a = nibble(payload[i]), b = nibble(payload[i+1]),
            c = nibble(payload[i+2]), d = nibble(payload[i+3]);
        uint32_t cp;
        if (a < 0 || b < 0 || c < 0 || d < 0) goto done;
        cp = ((uint32_t)a << 12) | ((uint32_t)b << 8) |
             ((uint32_t)c << 4) | (uint32_t)d;
        if (cp >= 0xd800u && cp <= 0xdbffu) {
            uint32_t lo;
            if (i + 7u >= len) goto done;
            a = nibble(payload[i+4]); b = nibble(payload[i+5]);
            c = nibble(payload[i+6]); d = nibble(payload[i+7]);
            if (a < 0 || b < 0 || c < 0 || d < 0) goto done;
            lo = ((uint32_t)a << 12) | ((uint32_t)b << 8) |
                 ((uint32_t)c << 4) | (uint32_t)d;
            if (lo < 0xdc00u || lo > 0xdfffu) goto done;
            cp = 0x10000u + ((cp - 0xd800u) << 10) + (lo - 0xdc00u);
            i += 4u;
        }
        if (append(out, cp) != 0) goto done;
    }
    out->decoded = 1;
    rc = 0;
done:
    wipe(payload, sizeof(payload));
    if (rc < 0) wipe(out, sizeof(*out));
    return rc;
}

void veci_ussd_clear(struct veci_ussd_reply *out)
{
    if (out) wipe(out, sizeof(*out));
}
