/*
 * VeCI SMS one-use capability store, source-only. NOT a session verifier.
 * A privileged caller MUST establish authenticated principal + restricted
 * ACL + CSRF + fresh consent independently (NEVER from browser booleans).
 *
 * Private dirfd: open on a root-owned 0700 tmpfs directory, separately in
 * each rpcd process. Only one pending capability exists per router.
 * Caller must NOT use a directory fd inherited by forked workers.
 * No modem I/O; consume occurs before any caller sends AT+CMGR.
 */
#ifndef VECI_SMS_READ_CAP_STORE_H
#define VECI_SMS_READ_CAP_STORE_H
#include <stdint.h>
#include "veci-sms-read-capability.h"

int veci_sms_store_arm(int private_dirfd,
                       const unsigned char trusted_session[VECI_SMS_SESSION_BYTES],
                       const unsigned char random_nonce[VECI_SMS_CAP_BYTES],
                       unsigned int slot, uint64_t modem_generation,
                       uint64_t now_monotonic_ms, unsigned int ttl_ms,
                       int authenticated_acl, int csrf_verified,
                       int fresh_per_slot_consent);

/*
 * Preferred future server-side entry point: generate 128-bit capability from
 * the Linux kernel CSPRNG. Never accept a nonce supplied by the browser.
 * On failure nonce_out is cleared, including when the store is busy.
 * AUTH / CSRF / per-slot consent flags MUST be derived by a trusted caller.
 */
int veci_sms_store_arm_generated(
    int private_dirfd,
    const unsigned char trusted_session[VECI_SMS_SESSION_BYTES],
    unsigned int slot, uint64_t modem_generation,
    uint64_t now_monotonic_ms, unsigned int ttl_ms,
    int authenticated_acl, int csrf_verified, int fresh_per_slot_consent,
    unsigned char nonce_out[VECI_SMS_CAP_BYTES]);

int veci_sms_store_consume(int private_dirfd,
                           const unsigned char trusted_session[VECI_SMS_SESSION_BYTES],
                           const unsigned char nonce[VECI_SMS_CAP_BYTES],
                           unsigned int slot, uint64_t modem_generation,
                           uint64_t now_monotonic_ms);
#endif
