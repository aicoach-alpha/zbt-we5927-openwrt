/*
 * XL Indonesia USSD user-action guard (source-only, no modem I/O).
 * Initial check is official *808#. Every menu continuation needs new
 * authorization; never guess menu paths, purchase services or retry.
 * No phone number, USSD response text, credentials or OTP stored.
 * GPL-2.0-only.
 */
#ifndef VECI_XL_USSD_CONSENT_H
#define VECI_XL_USSD_CONSENT_H
#include <stdint.h>
#define VECI_XL_USSD_MAX_STEPS 6u
enum veci_xl_ussd_state {
    VECI_XL_USSD_IDLE = 0,
    VECI_XL_USSD_AWAITING_RESPONSE = 1,
    VECI_XL_USSD_INTERACTIVE = 2,
    VECI_XL_USSD_CLOSED = 3,
    VECI_XL_USSD_FAILED = 4
};
struct veci_xl_ussd_session {
    uint64_t generation;  /* nonzero, trusted backend allocated */
    unsigned int steps;
    int state;
};
/* Caller must attest confirmed operator identity and exact user action,
 * after authentication/CSRF checks. This library cannot do those checks.
 * dial is validated as EXACTLY *808# (not arbitrary USSD).
 */
int veci_xl_ussd_begin(struct veci_xl_ussd_session *session,
                       uint64_t generation, int is_verified_xl,
                       const char *dial, int one_time_approval);
/* Consume a completed, authenticated response state from the separate
 * session-aware framing coordinator (0=response, 1=interactive,
 * 2=terminal). Never consume a naked AT OK as a USSD result.
 */
int veci_xl_ussd_result(struct veci_xl_ussd_session *session,
                        uint64_t generation, unsigned int mode);
/* A new user click for EACH menu entry is mandatory. Only numeric
 * choices, never a script-provided guessed sequence or auto-reply.
 * The menu text must have been shown locally by the trusted UI.
 */
int veci_xl_ussd_reply(struct veci_xl_ussd_session *session,
                       uint64_t generation, const char *menu_entry,
                       int fresh_approval);
/* Wipe session state on user cancellation, timeout, port loss or SIM change.
 * Future transport must quarantine delayed URCs after this call.
 */
void veci_xl_ussd_clear(struct veci_xl_ussd_session *session);
#endif
