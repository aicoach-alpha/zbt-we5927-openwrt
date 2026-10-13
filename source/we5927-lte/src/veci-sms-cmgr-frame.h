/*
 * Sensitive single-slot SMS +CMGR parser. SOURCE-ONLY, never linked to
 * firmware/rpcd. NO modem I/O, logging, storage or spontaneous SMS fetch.
 */
#ifndef VECI_SMS_CMGR_FRAME_H
#define VECI_SMS_CMGR_FRAME_H
#include "veci-at-framing.h"
#include "veci-sms-read-slot-policy.h"
#include <stddef.h>
#include <stdint.h>

/* Must match veci-sms-pdu-decode.c ABI; shared public declaration lives here
 * until a future standalone codec header is introduced.
 */
#define VECI_SMS_BODY_MAX 1024u
#define VECI_SMS_SENDER_MAX 24u
struct veci_sms_deliver {
    char sender[VECI_SMS_SENDER_MAX];
    char text[VECI_SMS_BODY_MAX + 1u];
    size_t text_len;
    unsigned int alphabet, concat_ref, concat_total, concat_part;
    unsigned int concat_is_16bit, udhi;
};

struct veci_sms_cmgr_frame {
    struct veci_at_frame framing;
    char pdu[VECI_FRAME_PDU_MAX + 1u];
    uint64_t binding, nonce, generation;
    unsigned int slot, status, tpdu;
    unsigned int stage, echo_seen, completed, failed;
};

int veci_sms_cmgr_init(struct veci_sms_cmgr_frame *s,
                       const struct veci_sms_read_policy *approval);
int veci_sms_cmgr_feed(struct veci_sms_cmgr_frame *s,
                       const unsigned char *bytes, size_t size);
int veci_sms_cmgr_finish(struct veci_sms_cmgr_frame *s);
/* Take once only; requires policy COMPLETED after full terminal frame.
 * Returned decoded SMS is PRIVATE: caller must wipe with veci_sms_clear.
 * Ownership must never cross diagnostic RPCs or logs.
 */
int veci_sms_cmgr_take(struct veci_sms_cmgr_frame *s,
                       const struct veci_sms_read_policy *approval,
                       struct veci_sms_deliver *out);
void veci_sms_cmgr_clear(struct veci_sms_cmgr_frame *s);
void veci_sms_clear(struct veci_sms_deliver *out);
#endif
