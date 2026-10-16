/*
 * Inert XL *808# USSD action guard. No transport or AT command execution.
 * The caller MUST authenticate owner, verify SIM belongs to XL, attest
 * physical modem identity, display the actual modem response and obtain
 * a fresh explicit approval for every menu reply.
 * GPL-2.0-only.
 */
#include "veci-xl-ussd-consent.h"
#include <errno.h>
#include <stddef.h>
#include <string.h>

void veci_xl_ussd_clear(struct veci_xl_ussd_session *session)
{
    volatile unsigned char *p;
    size_t n;
    if (!session) return;
    p = (volatile unsigned char *)session;
    n = sizeof(*session);
    while (n--) *p++ = 0;
}

int veci_xl_ussd_begin(struct veci_xl_ussd_session *session,
                       uint64_t generation, int is_verified_xl,
                       const char *dial, int one_time_approval)
{
    if (!session || !dial || !generation) return -EINVAL;
    if (session->state != VECI_XL_USSD_IDLE) return -EBUSY;
    /* Avoid executing purchases, recharge, caller-provided AT sequences,
     * legacy dial codes, or arbitrary SMS/USSD input.
     */
    if (is_verified_xl != 1 || one_time_approval != 1) return -EACCES;
    if (strcmp(dial, "*808#")) return -EPERM;
    session->generation = generation;
    session->steps = 0;
    session->state = VECI_XL_USSD_AWAITING_RESPONSE;
    return 0;
}

int veci_xl_ussd_result(struct veci_xl_ussd_session *session,
                        uint64_t generation, unsigned int mode)
{
    if (!session || !generation) return -EINVAL;
    if (!session->generation || session->generation != generation)
        return -EACCES;
    if (session->state != VECI_XL_USSD_AWAITING_RESPONSE)
        return -EPROTO;
    if (mode > 5u) {
        session->state = VECI_XL_USSD_FAILED;
        return -EPROTO;
    }
    if (mode == 1u)
        session->state = VECI_XL_USSD_INTERACTIVE;
    else
        session->state = VECI_XL_USSD_CLOSED;
    return 0;
}

int veci_xl_ussd_reply(struct veci_xl_ussd_session *session,
                       uint64_t generation, const char *menu_entry,
                       int fresh_approval)
{
    size_t len, i;
    if (!session || !menu_entry || !generation) return -EINVAL;
    if (!session->generation || session->generation != generation)
        return -EACCES;
    if (session->state != VECI_XL_USSD_INTERACTIVE) return -EPROTO;
    if (fresh_approval != 1) return -EACCES;
    /* Every network menu and purchase possibility is dynamic.
     * Permit only user-selected one/two decimal digits, one click per
     * response, never auto-follow a menu tree or submit USSD codes.
     */
    len = strlen(menu_entry);
    if (!len || len > 2u || (len > 1 && menu_entry[0] == '0'))
        return -EINVAL;
    for (i = 0; i < len; ++i)
        if (menu_entry[i] < '0' || menu_entry[i] > '9')
            return -EINVAL;
    if (session->steps >= VECI_XL_USSD_MAX_STEPS) {
        session->state = VECI_XL_USSD_FAILED;
        return -E2BIG;
    }
    session->steps++;
    session->state = VECI_XL_USSD_AWAITING_RESPONSE;
    return 0;
}
