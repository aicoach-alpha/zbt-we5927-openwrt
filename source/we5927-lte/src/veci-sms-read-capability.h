/*
 * VeCI ephemeral one-use per-slot SMS read capability (source-only).
 * GPL-2.0-only. Not registered with rpcd, not linked into firmware.
 *
 * Caller MUST supply an AUTHENTICATED, SERVER-VERIFIED session identifier
 * from a trusted security boundary, not a browser-provided claimed ID.
 * Caller must also verify ACL, CSRF and explicit per-slot foreground consent.
 * Tokens MUST originate from a cryptographically strong random source.
 * Caller serializes operations on this capability under a process lock.
 */
#ifndef VECI_SMS_READ_CAPABILITY_H
#define VECI_SMS_READ_CAPABILITY_H
#include <stddef.h>
#include <stdint.h>

#define VECI_SMS_CAP_BYTES 16u
#define VECI_SMS_SESSION_BYTES 16u
#define VECI_SMS_CAP_MAX_TTL_MS 30000u

enum veci_sms_cap_status {
    VECI_SMS_CAP_EMPTY = 0,
    VECI_SMS_CAP_READY = 1,
    VECI_SMS_CAP_USED = 2
};
struct veci_sms_read_capability {
    unsigned char trusted_session[VECI_SMS_SESSION_BYTES];
    unsigned char nonce[VECI_SMS_CAP_BYTES];
    uint64_t generation;
    uint64_t armed_ms;
    uint64_t expires_ms;
    uint32_t slot;
    uint32_t state;
};

/* Security boundary inputs are trusted iff independent caller verified
 * real rpcd session + restricted ACL + fresh CSRF+UI action.
 * Distinct trusted_session and random_nonce must be nonzero. All
 * failure states leave the capability unchanged and return generic errno.
 */
int veci_sms_cap_arm(struct veci_sms_read_capability *c,
                     const unsigned char trusted_session[VECI_SMS_SESSION_BYTES],
                     const unsigned char random_nonce[VECI_SMS_CAP_BYTES],
                     unsigned int slot, uint64_t modem_generation,
                     uint64_t now_monotonic_ms, unsigned int ttl_ms,
                     int authenticated_acl, int csrf_verified,
                     int per_slot_consent);

/* Atomically consume in trusted caller BEFORE sending any AT bytes.
 * Even if transport fails, replay is denied; no automatic resends.
 * No generic browser caller may reset a USED capability to READY.
 */
int veci_sms_cap_consume(struct veci_sms_read_capability *c,
                         const unsigned char trusted_session[VECI_SMS_SESSION_BYTES],
                         const unsigned char nonce[VECI_SMS_CAP_BYTES],
                         unsigned int slot, uint64_t modem_generation,
                         uint64_t now_monotonic_ms);
void veci_sms_cap_clear(struct veci_sms_read_capability *c);
#endif
