/* VeCI ephemeral SMS multipart API — DEVELOPMENT/INACTIVE only.
 * GPL-2.0-only. No transport I/O. Caller owns permission and SIM context.
 */
#ifndef VECI_SMS_MULTIPART_H
#define VECI_SMS_MULTIPART_H

#include <stddef.h>
#include <stdint.h>

#define VECI_MP_GROUPS 2u
#define VECI_MP_PARTS 8u
#define VECI_MP_PART_MAX 512u
#define VECI_MP_TOTAL_MAX 2048u
#define VECI_MP_TTL_MAX 600000
#define VECI_MP_SENDER_MAX 24u

struct veci_mp_part {
    uint64_t scope_id;          /* trusted nonzero SIM/ingress scope */
    const char *sender;         /* verified SMS-DELIVER sender */
    unsigned int alphabet;      /* 0 GSM7 or 2 UCS2 */
    unsigned int concat_ref;
    unsigned int concat_total;
    unsigned int concat_part;
    unsigned int concat_is_16bit;
    const char *text;           /* verified UTF-8 from PDU decoder */
    size_t text_len;
};

struct veci_mp_group {
    uint64_t scope_id;
    int64_t opened_ms;
    unsigned int ref, total, alphabet, ref_16bit, received;
    unsigned int occupied;
    unsigned int completed;
    char sender[VECI_MP_SENDER_MAX];
    unsigned int mask;
    uint16_t len[VECI_MP_PARTS];
    char chunks[VECI_MP_PARTS][VECI_MP_PART_MAX + 1u];
};

struct veci_mp_state {
    struct veci_mp_group groups[VECI_MP_GROUPS];
    int64_t last_now_ms;
    int clock_valid;
    int poisoned;
};

struct veci_mp_result {
    char text[VECI_MP_TOTAL_MAX + 1u];
    size_t text_len;
    uint64_t scope_id;
    unsigned int total_parts;
};

/* Caller MUST wipe after handling secrets, OTP or any user text. */
void veci_mp_clear_result(struct veci_mp_result *out);
void veci_mp_reset(struct veci_mp_state *state);
/* 0 means okay, negative errno on clock regression or expired partial. */
int veci_mp_expire(struct veci_mp_state *state, int64_t now_ms);
/* 0 incomplete, 1 assembled, negative errno on failure. */
int veci_mp_add(struct veci_mp_state *state,
                const struct veci_mp_part *part, int64_t now_ms,
                struct veci_mp_result *out);

#endif
