/*
 * One-shot SMS read authorization and replay guard, NO modem access.
 * GPL-2.0-only. Source-only and not production-installed.
 * Does NOT by itself enforce user authentication or session/CSRF binding.
 */
#include "veci-sms-read-slot-policy.h"
#include <errno.h>
#include <stddef.h>

static void wipe(void *p, size_t n)
{
    volatile unsigned char *q = (volatile unsigned char *)p;
    while (n--) *q++ = 0;
}

void veci_sms_read_clear(struct veci_sms_read_policy *p)
{
    if (p) wipe(p, sizeof(*p));
}

void veci_sms_read_abort(struct veci_sms_read_policy *p)
{
    if (!p) return;
    wipe(p, sizeof(*p));
    p->state = VECI_SMS_READ_QUARANTINED;
}

int veci_sms_read_arm(struct veci_sms_read_policy *p,
                      unsigned int slot,
                      uint64_t session_binding,
                      uint64_t request_nonce,
                      uint64_t modem_generation,
                      int acl_authorized, int csrf_verified,
                      int fresh_per_slot_consent,
                      int serial_lock_held, int opened_fd_verified)
{
    if (!p || p->state != VECI_SMS_READ_IDLE)
        return -EBUSY;
    if (slot > 65535u || !session_binding || !request_nonce ||
        !modem_generation || acl_authorized != 1 || csrf_verified != 1 ||
        fresh_per_slot_consent != 1 || serial_lock_held != 1 ||
        opened_fd_verified != 1)
        return -EPERM;
    p->session_binding = session_binding;
    p->request_nonce = request_nonce;
    p->modem_generation = modem_generation;
    p->slot = slot;
    p->state = VECI_SMS_READ_ARMED;
    return 0;
}

static int match(const struct veci_sms_read_policy *p,
                 uint64_t session_binding, uint64_t request_nonce,
                 uint64_t modem_generation, unsigned int slot)
{
    return p && p->session_binding == session_binding &&
           p->request_nonce == request_nonce &&
           p->modem_generation == modem_generation &&
           p->slot == slot;
}

int veci_sms_read_issued(struct veci_sms_read_policy *p,
                         uint64_t session_binding,
                         uint64_t request_nonce,
                         uint64_t modem_generation,
                         unsigned int slot)
{
    if (!p || p->state != VECI_SMS_READ_ARMED) return -EPERM;
    if (!match(p, session_binding, request_nonce, modem_generation, slot)) {
        veci_sms_read_abort(p);
        return -ESTALE;
    }
    p->state = VECI_SMS_READ_ISSUED;
    return 0;
}

int veci_sms_read_complete(struct veci_sms_read_policy *p,
                           uint64_t session_binding,
                           uint64_t request_nonce,
                           uint64_t modem_generation,
                           unsigned int slot,
                           int complete_frame_valid)
{
    if (!p || p->state != VECI_SMS_READ_ISSUED) return -EPERM;
    if (!match(p, session_binding, request_nonce, modem_generation, slot) ||
        complete_frame_valid != 1) {
        veci_sms_read_abort(p);
        return -ESTALE;
    }
    p->state = VECI_SMS_READ_COMPLETED;
    return 0;
}
