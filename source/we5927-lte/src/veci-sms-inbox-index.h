/*
 * VeCI: SMS inbox index-only session over inert AT+CMGL PDU framing.
 * SOURCE-ONLY, not linked to firmware, no AT/modem/ubus/daemon I/O.
 * Requires separately authenticated one-time permission and a future
 * privileged transport that holds the physical modem lock throughout.
 * GPL-2.0-only.
 */
#ifndef VECI_SMS_INBOX_INDEX_H
#define VECI_SMS_INBOX_INDEX_H
#include "veci-at-framing.h"
#include <stddef.h>
#include <stdint.h>
#define VECI_SMS_INDEX_MAX 16u

struct veci_sms_index_entry {
    uint32_t index;
    uint32_t state;          /* Modem 3GPP PDU status: 0..4, not text. */
    uint32_t tpdu_octets;
};

struct veci_sms_index_session {
    struct veci_at_frame frame;
    struct veci_sms_index_entry entries[VECI_SMS_INDEX_MAX];
    struct veci_sms_index_entry pending;
    unsigned int count;
    int approved;
    int stage;               /* 0 headers, 1 awaiting PDU, 2 terminal OK */
    int failed;
    int completed;
    int echo_seen;
};

/* approved=1 is a necessary input from trusted backend, NOT an ACL check.
 * Returns -EACCES unless 1. All previous state is wiped on init. */
int veci_sms_index_init(struct veci_sms_index_session *s, int approved);
/* Caller must supply bytes for ONE exact AT+CMGL=4 query while holding
 * shared full-session lock. No transport and no auto-retry in this library.
 */
int veci_sms_index_feed(struct veci_sms_index_session *s,
                        const unsigned char *bytes, size_t n);
/* Only succeeds once after a complete final OK; fails on truncation. */
int veci_sms_index_finish(struct veci_sms_index_session *s);
/* Metadata becomes visible ONLY after successfully finishing. */
int veci_sms_index_count(const struct veci_sms_index_session *s);
int veci_sms_index_get(const struct veci_sms_index_session *s,
                       unsigned int ordinal, struct veci_sms_index_entry *out);
/* Mandatory when session is done; removes all session data. */
void veci_sms_index_clear(struct veci_sms_index_session *s);
#endif
