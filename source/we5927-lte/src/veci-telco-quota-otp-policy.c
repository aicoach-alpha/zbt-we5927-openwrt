/*
 * Default-deny policy gate for operator-app quota-login SMS ONLY.
 * SOURCE-ONLY. No filesystem, modem/AT, browser, HTTP, logging or OTP I/O.
 */
#include "veci-telco-quota-otp-policy.h"
#include <errno.h>
#include <stddef.h>
#include <stdint.h>

#define QUOTA_LOGIN_MAX_TTL_MS 120000u

static void wipe(void *v, size_t n)
{
    volatile unsigned char *p=(volatile unsigned char *)v;
    while(n--) *p++=0;
}
void veci_telco_quota_otp_clear(struct veci_telco_quota_otp_policy *p)
{
    if(p) wipe(p,sizeof(*p));
}
static int valid_provider(unsigned int x)
{
    return x >= VECI_TELCO_XL && x <= VECI_TELCO_SMARTFREN;
}
static int reject(struct veci_telco_quota_otp_policy *p)
{
    if(p){
        wipe(p,sizeof(*p));
        p->state=VECI_TELCO_REJECTED;
    }
    return -EACCES;
}
int veci_telco_quota_otp_begin(
    struct veci_telco_quota_otp_policy *p,
    unsigned int provider, unsigned int purpose,
    uint64_t login_id, uint64_t generation,
    uint64_t now, unsigned int ttl_ms,
    int verified_official_login, int user_enabled,
    int sim_verified, int integration_approved)
{
    if(!p) return -EINVAL;
    if(p->state!=VECI_TELCO_EMPTY) return -EBUSY;
    if(!valid_provider(provider) ||
       purpose!=VECI_TELCO_PURPOSE_QUOTA_APP_LOGIN ||
       !login_id || !generation || !now ||
       !ttl_ms || ttl_ms>QUOTA_LOGIN_MAX_TTL_MS ||
       now>UINT64_MAX-ttl_ms ||
       verified_official_login!=1 || user_enabled!=1 ||
       sim_verified!=1 || integration_approved!=1)
        return -EACCES;
    p->provider=provider;
    p->quota_login_id=login_id;
    p->modem_generation=generation;
    p->armed_ms=now;
    p->deadline_ms=now+ttl_ms;
    p->state=VECI_TELCO_ARMED;
    return 0;
}
int veci_telco_quota_otp_allow_candidate(
    struct veci_telco_quota_otp_policy *p,
    unsigned int provider, unsigned int purpose,
    unsigned int slot, uint64_t login_id,
    uint64_t generation, uint64_t now,
    int pre_read_provider_attested, int challenge_bound)
{
    int matches;
    if(!p) return -EINVAL;
    if(p->state!=VECI_TELCO_ARMED) return -EACCES;
    /* Regardless of match, consume the single candidate; NEVER iterate
     * unrelated inbox slots until a matching OTP is found.
     */
    matches=(provider==p->provider) &
            valid_provider(provider) &
            (purpose==VECI_TELCO_PURPOSE_QUOTA_APP_LOGIN) &
            (slot<=65535u) &
            (login_id==p->quota_login_id) &
            (generation==p->modem_generation) &
            (now>=p->armed_ms) &
            (now<p->deadline_ms) &
            (pre_read_provider_attested==1) &
            (challenge_bound==1);
    if(!matches) return reject(p);
    p->approved_slot=slot;
    p->quota_login_id=0;
    p->modem_generation=0;
    p->armed_ms=0;
    p->deadline_ms=0;
    p->state=VECI_TELCO_PERMITTED;
    return 0;
}
