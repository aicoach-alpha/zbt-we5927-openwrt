/*
 * VeCI SMS-DELIVER PDU decoder (3GPP TS 23.040 / TS 23.038).
 * GPL-2.0-only. INACTIVE/offline library, NOT installed into router image.
 * Never reads the modem, opens a port, transmits, logs, or persists a message.
 *
 * Deliberately fail closed for unsupported PDU types, compressed/8-bit DCS,
 * alphanumeric originators and malformed UDH. Multipart metadata is returned
 * but NO reassembly across messages occurs in this library.
 */
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define VECI_SMS_PDU_HEX_MAX 512
#define VECI_SMS_BODY_MAX 1024
#define VECI_SMS_SENDER_MAX 24

struct veci_sms_deliver {
    char sender[VECI_SMS_SENDER_MAX];
    char text[VECI_SMS_BODY_MAX + 1];
    size_t text_len;
    unsigned int alphabet;        /* 0: GSM7, 2: UCS2 */
    unsigned int concat_ref;
    unsigned int concat_total;
    unsigned int concat_part;
    unsigned int concat_is_16bit;
    unsigned int udhi;
};

/* No dependence on libc explicit_bzero (not on every OpenWrt libc). */
static void secure_wipe(void *p, size_t n)
{
    volatile unsigned char *v = (volatile unsigned char *)p;
    while (n--) *v++ = 0;
}

static int nibble(char ch)
{
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    return -1;
}

static int append_utf8(struct veci_sms_deliver *dst, uint32_t cp)
{
    unsigned char bytes[4];
    size_t n = 0;
    if (!cp || cp > 0x10ffffu || (cp >= 0xd800u && cp <= 0xdfffu))
        return -1;  /* no NUL byte, surrogate or invalid scalar */
    if (cp < 0x80u) {
        bytes[n++] = (unsigned char)cp;
    } else if (cp < 0x800u) {
        bytes[n++] = (unsigned char)(0xc0u | (cp >> 6));
        bytes[n++] = (unsigned char)(0x80u | (cp & 0x3fu));
    } else if (cp < 0x10000u) {
        bytes[n++] = (unsigned char)(0xe0u | (cp >> 12));
        bytes[n++] = (unsigned char)(0x80u | ((cp >> 6) & 0x3fu));
        bytes[n++] = (unsigned char)(0x80u | (cp & 0x3fu));
    } else {
        bytes[n++] = (unsigned char)(0xf0u | (cp >> 18));
        bytes[n++] = (unsigned char)(0x80u | ((cp >> 12) & 0x3fu));
        bytes[n++] = (unsigned char)(0x80u | ((cp >> 6) & 0x3fu));
        bytes[n++] = (unsigned char)(0x80u | (cp & 0x3fu));
    }
    if (n > VECI_SMS_BODY_MAX - dst->text_len) return -1;
    memcpy(dst->text + dst->text_len, bytes, n);
    dst->text_len += n;
    dst->text[dst->text_len] = '\0';
    return 0;
}

/* GSM 03.38 default alphabet: all ordinary septets (0x1B is ESC). */
static const uint16_t gsm7_table[128] = {
    0x0040,0x00a3,0x0024,0x00a5,0x00e8,0x00e9,0x00f9,0x00ec,
    0x00f2,0x00c7,0x000a,0x00d8,0x00f8,0x000d,0x00c5,0x00e5,
    0x0394,0x005f,0x03a6,0x0393,0x039b,0x03a9,0x03a0,0x03a8,
    0x03a3,0x0398,0x039e,0x0000,0x00c6,0x00e6,0x00df,0x00c9,
    0x0020,0x0021,0x0022,0x0023,0x00a4,0x0025,0x0026,0x0027,
    0x0028,0x0029,0x002a,0x002b,0x002c,0x002d,0x002e,0x002f,
    0x0030,0x0031,0x0032,0x0033,0x0034,0x0035,0x0036,0x0037,
    0x0038,0x0039,0x003a,0x003b,0x003c,0x003d,0x003e,0x003f,
    0x00a1,0x0041,0x0042,0x0043,0x0044,0x0045,0x0046,0x0047,
    0x0048,0x0049,0x004a,0x004b,0x004c,0x004d,0x004e,0x004f,
    0x0050,0x0051,0x0052,0x0053,0x0054,0x0055,0x0056,0x0057,
    0x0058,0x0059,0x005a,0x00c4,0x00d6,0x00d1,0x00dc,0x00a7,
    0x00bf,0x0061,0x0062,0x0063,0x0064,0x0065,0x0066,0x0067,
    0x0068,0x0069,0x006a,0x006b,0x006c,0x006d,0x006e,0x006f,
    0x0070,0x0071,0x0072,0x0073,0x0074,0x0075,0x0076,0x0077,
    0x0078,0x0079,0x007a,0x00e4,0x00f6,0x00f1,0x00fc,0x00e0
};

static uint32_t gsm7_extension(unsigned char v)
{
    switch (v) {
    case 0x0a: return 0x000c;
    case 0x14: return '^';
    case 0x28: return '{';
    case 0x29: return '}';
    case 0x2f: return '\\';
    case 0x3c: return '[';
    case 0x3d: return '~';
    case 0x3e: return ']';
    case 0x40: return '|';
    case 0x65: return 0x20ac;
    default: return 0;
    }
}

static int decode_septets(const unsigned char *ud, size_t bytes,
                          unsigned int count, unsigned int offset,
                          struct veci_sms_deliver *out)
{
    unsigned int i;
    int esc = 0;
    for (i = 0; i < count; ++i) {
        size_t bit = (size_t)offset + (size_t)i * 7u;
        size_t b = bit / 8u;
        unsigned int shift = (unsigned int)(bit % 8u);
        unsigned int v;
        uint32_t cp;
        if (b >= bytes) return -1;
        v = (unsigned int)(ud[b] >> shift);
        if (shift > 1u) {
            if (b + 1u >= bytes) return -1;
            v |= (unsigned int)ud[b + 1u] << (8u - shift);
        }
        v &= 0x7fu;
        if (esc) {
            cp = gsm7_extension((unsigned char)v);
            esc = 0;
        } else if (v == 0x1bu) {
            esc = 1;
            continue;
        } else {
            cp = gsm7_table[v];
        }
        if (!cp || append_utf8(out, cp) != 0) return -1;
    }
    return esc ? -1 : 0;
}

static int decode_ucs2(const unsigned char *data, size_t n,
                       struct veci_sms_deliver *out)
{
    size_t i;
    if (n & 1u) return -1;
    for (i = 0; i < n; i += 2) {
        uint32_t cp = ((uint32_t)data[i] << 8) | data[i + 1];
        if (cp >= 0xd800u && cp <= 0xdbffu) {
            uint32_t low;
            if (i + 3 >= n) return -1;
            low = ((uint32_t)data[i + 2] << 8) | data[i + 3];
            if (low < 0xdc00u || low > 0xdfffu) return -1;
            cp = 0x10000u + ((cp - 0xd800u) << 10) + (low - 0xdc00u);
            i += 2;
        }
        if (append_utf8(out, cp) != 0) return -1;
    }
    return 0;
}

static int parse_udh(const unsigned char *ud, size_t length,
                     size_t *header_bytes, struct veci_sms_deliver *out)
{
    size_t cursor, end;
    if (!length) return -1;
    end = (size_t)ud[0] + 1u;
    if (end > length || end < 3u) return -1;
    cursor = 1u;
    while (cursor < end) {
        unsigned int id, n;
        if (end - cursor < 2u) return -1;
        id = ud[cursor++];
        n = ud[cursor++];
        if (n > end - cursor) return -1;
        if (id == 0x00u || id == 0x08u) {
            unsigned int total, part, ref;
            if (out->concat_total) return -1;
            if (id == 0x00u && n != 3u) return -1;
            if (id == 0x08u && n != 4u) return -1;
            if (id == 0x00u) {
                ref = ud[cursor]; total = ud[cursor + 1]; part = ud[cursor + 2];
            } else {
                ref = ((unsigned int)ud[cursor] << 8) | ud[cursor + 1];
                total = ud[cursor + 2]; part = ud[cursor + 3];
                out->concat_is_16bit = 1;
            }
            if (total < 2u || total > 16u || part < 1u || part > total)
                return -1;
            out->concat_ref = ref;
            out->concat_total = total;
            out->concat_part = part;
        }
        cursor += n;
    }
    *header_bytes = end;
    return 0;
}

int veci_sms_decode_deliver(const char *hex, struct veci_sms_deliver *out)
{
    unsigned char raw[VECI_SMS_PDU_HEX_MAX / 2];
    size_t hex_len, n = 0, i, p, oa_bytes, header = 0;
    unsigned int oa_digits, udl, alphabet, dcs, fo;
    int rc = -1;
    if (!out) return -1;
    memset(out, 0, sizeof(*out));
    if (!hex) return -1;
    hex_len = strlen(hex);
    if (hex_len < 4u || hex_len > VECI_SMS_PDU_HEX_MAX ||
        (hex_len & 1u)) return -1;
    for (i = 0; i < hex_len; i += 2) {
        int hi = nibble(hex[i]), lo = nibble(hex[i+1]);
        if (hi < 0 || lo < 0) goto done;
        raw[n++] = (unsigned char)((hi << 4) | lo);
    }
    if ((size_t)raw[0] > 12u || (size_t)raw[0] + 2u >= n) goto done;
    p = 1u + raw[0];
    fo = raw[p++];
    if ((fo & 3u) != 0u || (fo & 0x80u)) goto done;
    out->udhi = !!(fo & 0x40u);
    if (p + 2u > n) goto done;
    oa_digits = raw[p++];
    if (!oa_digits || oa_digits > 20u) goto done;
    {
        unsigned int toa = raw[p++];
        if (!(toa & 0x80u) || (toa & 0x70u) == 0x50u) goto done;
        if ((toa & 0x70u) == 0x10u)
            out->sender[0] = '+';
    }
    oa_bytes = (oa_digits + 1u) / 2u;
    if (oa_bytes > n - p) goto done;
    {
        size_t j, prefix = (out->sender[0] == '+') ? 1u : 0u;
        for (j = 0; j < oa_digits; ++j) {
            unsigned int v = (j & 1u) ? raw[p + j / 2u] >> 4
                                       : raw[p + j / 2u] & 0x0fu;
            if (v > 9u) goto done;
            out->sender[prefix + j] = (char)('0' + v);
        }
        if ((oa_digits & 1u) && (raw[p + oa_bytes - 1u] >> 4) != 0x0fu)
            goto done;
    }
    p += oa_bytes;
    if (n - p < 10u) goto done; /* PID + DCS + seven SCTS + UDL */
    p++; /* PID is an uninterpreted byte */
    dcs = raw[p++];
    if ((dcs & 0xc0u) != 0u || (dcs & 0x20u) != 0u) goto done;
    alphabet = (dcs >> 2) & 3u;
    if (alphabet != 0u && alphabet != 2u) goto done;
    out->alphabet = alphabet;
    p += 7u; /* SCTS retained nowhere: no time assumptions */
    udl = raw[p++];
    if (p > n) goto done;
    {
        const unsigned char *ud = raw + p;
        size_t ud_bytes = n - p;
        if (alphabet == 2u) {
            if (udl > 140u || ud_bytes != udl) goto done;
            if (out->udhi && parse_udh(ud, ud_bytes, &header, out) != 0)
                goto done;
            if (decode_ucs2(ud + header, ud_bytes - header, out) != 0)
                goto done;
        } else {
            unsigned int header_septets = 0, count, offset;
            if (udl > 160u || ud_bytes != ((size_t)udl * 7u + 7u) / 8u)
                goto done;
            if (out->udhi) {
                if (parse_udh(ud, ud_bytes, &header, out) != 0) goto done;
                header_septets = (unsigned int)((header * 8u + 6u) / 7u);
            }
            if (header_septets > udl) goto done;
            count = udl - header_septets;
            offset = header_septets * 7u;
            if (decode_septets(ud, ud_bytes, count, offset, out) != 0)
                goto done;
        }
    }
    rc = 0;
done:
    secure_wipe(raw, sizeof(raw));
    if (rc != 0) secure_wipe(out, sizeof(*out));
    return rc;
}

void veci_sms_clear(struct veci_sms_deliver *out)
{
    if (out) secure_wipe(out, sizeof(*out));
}
