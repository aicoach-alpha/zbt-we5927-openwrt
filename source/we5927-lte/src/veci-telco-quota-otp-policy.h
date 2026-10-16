/*
 * VE5927: telco QUOTA-LOGIN-only automatic SMS OTP authorization policy.
 * SOURCE ONLY: not built into firmware or installed on device.
 *
 * IMPORTANT: +CMTI contains memory+index, not sender. Do not auto-CMGR
 * arbitrary slots to determine whether an OTP belongs to an operator.
 * A trusted independent pre-read classification/provenance bridge MUST
 * exist before auto-read is possible. SMS sender text alone is SPOOFABLE
 * and NEVER sufficient attestation. Otherwise FAIL CLOSED.
 */
#ifndef VECI_TELCO_QUOTA_OTP_POLICY_H
#define VECI_TELCO_QUOTA_OTP_POLICY_H
#include <stdint.h>

enum veci_telco_provider {
    VECI_TELCO_NONE=0,
    VECI_TELCO_XL=1,
    VECI_TELCO_AXIS=2,
    VECI_TELCO_TELKOMSEL=3,
    VECI_TELCO_BYU=4,
    VECI_TELCO_INDOSAT=5,
    VECI_TELCO_TRI=6,
    VECI_TELCO_SMARTFREN=7
};
enum veci_telco_purpose {
    VECI_TELCO_PURPOSE_NONE=0,
    VECI_TELCO_PURPOSE_QUOTA_APP_LOGIN=1,
    VECI_TELCO_PURPOSE_BANK=2,
    VECI_TELCO_PURPOSE_EWALLET=3,
    VECI_TELCO_PURPOSE_EMAIL=4,
    VECI_TELCO_PURPOSE_OTHER=5
};
enum veci_telco_state {
    VECI_TELCO_EMPTY=0,
    VECI_TELCO_ARMED=1,
    VECI_TELCO_PERMITTED=2,
    VECI_TELCO_REJECTED=3
};
struct veci_telco_quota_otp_policy {
    uint64_t quota_login_id;
    uint64_t modem_generation;
    uint64_t armed_ms;
    uint64_t deadline_ms;
    unsigned int provider;
    unsigned int approved_slot;
    enum veci_telco_state state;
};

/* Trusted flags must be computed by a privileged verifier, NOT forwarded
 * verbatim from browser JSON. quota_login_id is unique to one official
 * operator-app quota-login transaction, NOT any account login.
 * No general inbox polling, +CMGL, +CMT auto-forwarding or content logging.
 */
int veci_telco_quota_otp_begin(
    struct veci_telco_quota_otp_policy *p,
    unsigned int provider, unsigned int purpose,
    uint64_t quota_login_id, uint64_t modem_generation,
    uint64_t now_monotonic_ms, unsigned int ttl_ms,
    int official_operator_login_verified,
    int authenticated_user_enabled_quota_sync,
    int carrier_matches_active_sim,
    int provider_integration_approved);

/* Called ONCE per live login; only if provider identity and OTP
 * classification have been securely established BEFORE any SMS PDU/body
 * is read. Bare +CMTI, spoofable originating address or content sniffing
 * MUST NOT be used to set either attestation flag.
 *
 * Positive return (0) does NOT authenticate a user, validate an OTP or
 * send SMS; a real provider-trust bridge and protected modem read pipeline
 * are additionally mandatory. All invalid candidates consume the gate.
 */
int veci_telco_quota_otp_allow_candidate(
    struct veci_telco_quota_otp_policy *p,
    unsigned int candidate_provider, unsigned int candidate_purpose,
    unsigned int slot, uint64_t quota_login_id,
    uint64_t modem_generation, uint64_t now_monotonic_ms,
    int independent_pre_read_provider_identity_attested,
    int operator_challenge_bound_to_active_login);

void veci_telco_quota_otp_clear(struct veci_telco_quota_otp_policy *p);
#endif
