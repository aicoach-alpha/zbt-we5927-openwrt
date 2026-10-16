/*
 * VeCI bounded single-SMS read authorization state machine.
 * SOURCE-ONLY (not linked into OpenWrt firmware).
 *
 * This module is NOT an authentication system, CSRF service or modem I/O.
 * Caller MUST independently verify session ACL/CSRF/one-time UI consent,
 * and live opened-fd W907 identity under the shared serial lock.
 * Never expose SMS/OTP, PDU, sender or AT responses here.
 */
#ifndef VECI_SMS_READ_SLOT_POLICY_H
#define VECI_SMS_READ_SLOT_POLICY_H
#include <stdint.h>

enum veci_sms_read_state {
    VECI_SMS_READ_IDLE = 0,
    VECI_SMS_READ_ARMED = 1,
    VECI_SMS_READ_ISSUED = 2,
    VECI_SMS_READ_COMPLETED = 3,
    VECI_SMS_READ_QUARANTINED = 4
};

struct veci_sms_read_policy {
    uint64_t session_binding;
    uint64_t request_nonce;
    uint64_t modem_generation;
    unsigned int slot;
    enum veci_sms_read_state state;
};

/* All gate arguments must be exactly 1. request_nonce is a random,
 * one-use token verified against trusted server state by the caller.
 * session_binding must derive from an authenticated session securely;
 * it is NOT a public browser-supplied number. modem_generation is
 * trustworthy only if tied to actual open serial file descriptor.
 */
int veci_sms_read_arm(struct veci_sms_read_policy *p,
                      unsigned int slot,
                      uint64_t session_binding,
                      uint64_t request_nonce,
                      uint64_t modem_generation,
                      int acl_authorized, int csrf_verified,
                      int fresh_per_slot_consent,
                      int serial_lock_held, int opened_fd_verified);

/* Exactly one AT+CMGR attempt per approval. Never retry a command that
 * might already have changed unread state or exposed sensitive content.
 */
int veci_sms_read_issued(struct veci_sms_read_policy *p,
                         uint64_t session_binding,
                         uint64_t request_nonce,
                         uint64_t modem_generation,
                         unsigned int slot);

/* Caller must ensure final OK / entire PDU verified separately.
 * This state machine never holds SMS data or returns any raw content.
 */
int veci_sms_read_complete(struct veci_sms_read_policy *p,
                           uint64_t session_binding,
                           uint64_t request_nonce,
                           uint64_t modem_generation,
                           unsigned int slot,
                           int complete_frame_valid);

void veci_sms_read_abort(struct veci_sms_read_policy *p);
void veci_sms_read_clear(struct veci_sms_read_policy *p);
#endif
