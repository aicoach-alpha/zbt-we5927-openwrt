/*
 * VeCI AT message framing - pure parser, NO modem I/O and NO AT commands.
 *
 * Incremental, bounded decoder of PDU-mode SMS frames and asynchronous USSD
 * notifications. This file is not wired to the production modem transport.
 * Integration must retain the single we5927-at.lock for the ENTIRE session.
 *
 * Payload pointers passed to callbacks are temporary, never logged here.
 * License: GPL-2.0-only
 */
#include <ctype.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define VECI_FRAME_LINE_MAX 1024
#define VECI_FRAME_STREAM_MAX 8192
#define VECI_FRAME_PDU_MAX 512

enum veci_frame_event {
    VECI_FRAME_OTHER = 0,
    VECI_FRAME_OK = 1,
    VECI_FRAME_ERROR = 2,
    VECI_FRAME_SMS_PDU = 3,
    VECI_FRAME_SMS_NOTICE = 4,
    VECI_FRAME_USSD = 5,
    VECI_FRAME_PROTOCOL_ERROR = 6
};

struct veci_at_frame {
    char line[VECI_FRAME_LINE_MAX];
    size_t line_len;
    size_t total;
    int pdu_expected;        /* -1 when no SMS PDU header is pending */
    int failed;
};

typedef void (*veci_frame_callback)(int event, const char *value, int metadata, void *ctx);

void veci_frame_init(struct veci_at_frame *f)
{
    memset(f, 0, sizeof(*f));
    f->pdu_expected = -1;
}

static int hex_digit(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

/* PDU length is SMSC-length octet + SMSC bytes + TPDU bytes.
 * Unlike text mode, PDU mode is safely framed even when decoded SMS says OK.
 */
static int pdu_valid(const char *line, int expected_tpdu)
{
    size_t i, n = strlen(line);
    int smsc_len;
    if (!n || n % 2 || n > VECI_FRAME_PDU_MAX || n < 4) return 0;
    for (i = 0; i < n; ++i)
        if (hex_digit(line[i]) < 0) return 0;
    smsc_len = hex_digit(line[0]) * 16 + hex_digit(line[1]);
    if (smsc_len > 12 || (size_t)(1 + smsc_len) >= n / 2) return 0;
    return (int)(n / 2 - 1 - (size_t)smsc_len) == expected_tpdu;
}

/* The last header field in 3GPP SMS PDU mode is TPDU length.
 * Reject text-mode records with timestamps rather than guessing a length.
 */
static int pdu_header_length(const char *line)
{
    const char *comma = strrchr(line, ',');
    char *end;
    long len;
    if (!comma) return -1;
    ++comma;
    while (*comma == ' ') ++comma;
    if (!*comma || !isdigit((unsigned char)*comma)) return -1;
    len = strtol(comma, &end, 10);
    while (*end == ' ') ++end;
    if (*end || len < 1 || len > 240) return -1;
    return (int)len;
}

static int starts(const char *line, const char *prefix)
{
    return strncmp(line, prefix, strlen(prefix)) == 0;
}

/* Parse only the USSD mode here. UCS2 and GSM-7 decoding belongs in the
 * eventual privileged consumer; content remains an opaque ephemeral string.
 */
static int ussd_mode(const char *line)
{
    const char *p = line + strlen("+CUSD:");
    while (*p == ' ') ++p;
    if (*p >= '0' && *p <= '5' && (p[1] == ',' || p[1] == '\0'))
        return *p - '0';
    return -1;
}

static void emit_failure(struct veci_at_frame *f,
                         veci_frame_callback callback, void *ctx)
{
    f->failed = 1;
    f->line_len = 0;
    f->pdu_expected = -1;
    if (callback) callback(VECI_FRAME_PROTOCOL_ERROR, "", 0, ctx);
}

static void complete_line(struct veci_at_frame *f,
                          veci_frame_callback callback, void *ctx)
{
    int event = VECI_FRAME_OTHER, meta = 0;
    if (!f->line_len) return;
    f->line[f->line_len] = '\0';

    if (f->pdu_expected >= 0) {
        if (!pdu_valid(f->line, f->pdu_expected)) {
            emit_failure(f, callback, ctx);
            return;
        }
        event = VECI_FRAME_SMS_PDU;
        meta = f->pdu_expected;
        f->pdu_expected = -1;
    } else if (starts(f->line, "+CMGL:") ||
               starts(f->line, "+CMGR:") ||
               starts(f->line, "+CMT:") ||
               starts(f->line, "+CDS:")) {
        meta = pdu_header_length(f->line);
        if (meta < 0) {
            emit_failure(f, callback, ctx);
            return;
        }
        f->pdu_expected = meta;
    } else if (starts(f->line, "+CMTI:")) {
        event = VECI_FRAME_SMS_NOTICE;
    } else if (starts(f->line, "+CUSD:")) {
        meta = ussd_mode(f->line);
        if (meta < 0) {
            emit_failure(f, callback, ctx);
            return;
        }
        event = VECI_FRAME_USSD;
    } else if (!strcmp(f->line, "OK")) {
        event = VECI_FRAME_OK;
    } else if (!strcmp(f->line, "ERROR") ||
               !strcmp(f->line, "NO CARRIER") ||
               starts(f->line, "+CMS ERROR:") ||
               starts(f->line, "+CME ERROR:") ||
               !strcmp(f->line, "+CMS ERROR") ||
               !strcmp(f->line, "+CME ERROR")) {
        event = VECI_FRAME_ERROR;
    }

    if (callback) callback(event, f->line, meta, ctx);
    f->line_len = 0;
}

/* No output from the library other than caller callbacks.
 * A partial line remains buffered until a CR or LF arrives.
 * On protocol error, parser must be explicitly reset by its owner.
 */
int veci_frame_feed(struct veci_at_frame *f, const unsigned char *buf,
                    size_t n, veci_frame_callback callback, void *ctx)
{
    size_t i;
    if (!f || (!buf && n) || f->failed) return -1;
    if (n > VECI_FRAME_STREAM_MAX - f->total) {
        emit_failure(f, callback, ctx);
        return -1;
    }
    f->total += n;
    for (i = 0; i < n; ++i) {
        unsigned char ch = buf[i];
        if (ch == '\r' || ch == '\n') {
            complete_line(f, callback, ctx);
            if (f->failed) return -1;
        } else if (ch < 32 || ch > 126 ||
                   f->line_len + 1 >= sizeof(f->line)) {
            emit_failure(f, callback, ctx);
            return -1;
        } else {
            f->line[f->line_len++] = (char)ch;
        }
    }
    return 0;
}

/* Called at end of a bounded transaction: a truncated PDU or pending line
 * MUST fail instead of being interpreted as an empty SMS inbox.
 */
int veci_frame_finish(struct veci_at_frame *f,
                      veci_frame_callback callback, void *ctx)
{
    if (!f || f->failed) return -1;
    if (f->line_len || f->pdu_expected >= 0) {
        emit_failure(f, callback, ctx);
        return -1;
    }
    return 0;
}

/* A USSD request is not complete on its initial AT OK. +CUSD is an
 * asynchronous URC and may arrive either before or after that OK.
 * This state tracker has no retry, timeout, AT transmitter or persistence.
 */
enum veci_ussd_state {
    VECI_USSD_WAITING = 0,
    VECI_USSD_RESPONSE = 1,
    VECI_USSD_INTERACTIVE = 2,
    VECI_USSD_TERMINATED = 3,
    VECI_USSD_FAILED = 4
};
struct veci_ussd_session {
    int acked;
    int seen_urc;
    int mode;
    int failed;
};

void veci_ussd_init(struct veci_ussd_session *s)
{
    memset(s, 0, sizeof(*s));
    s->mode = -1;
}

int veci_ussd_consume(struct veci_ussd_session *s, int event, int meta)
{
    if (!s) return VECI_USSD_FAILED;
    if (event == VECI_FRAME_PROTOCOL_ERROR || event == VECI_FRAME_ERROR)
        s->failed = 1;
    else if (event == VECI_FRAME_OK)
        s->acked = 1;
    else if (event == VECI_FRAME_USSD) {
        s->seen_urc = 1;
        s->mode = meta;
    }
    if (s->failed) return VECI_USSD_FAILED;
    if (!s->acked || !s->seen_urc) return VECI_USSD_WAITING;
    if (s->mode == 0) return VECI_USSD_RESPONSE;
    if (s->mode == 1) return VECI_USSD_INTERACTIVE;
    return VECI_USSD_TERMINATED;
}

/* Caller must own a monotonic deadline and invoke this if a response has
 * not completed in time. No automatic resend or USSD cancellation here.
 */
int veci_ussd_expire(struct veci_ussd_session *s)
{
    if (!s) return VECI_USSD_FAILED;
    s->failed = 1;
    return VECI_USSD_FAILED;
}
