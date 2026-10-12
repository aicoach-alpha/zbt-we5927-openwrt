/*
 * Deterministic negative-input harness for OFFLINE VeCI PDU and USSD decoders.
 * No AT port, network, SIM access or private data. Compiler ASAN+UBSAN in CI.
 */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

#define SMS_BODY_MAX 1024
#define USSD_BODY_MAX 1024

struct veci_sms_deliver {
    char sender[24];
    char text[SMS_BODY_MAX + 1];
    size_t text_len;
    unsigned int alphabet, concat_ref, concat_total, concat_part,
                 concat_is_16bit, udhi;
};
struct veci_ussd_reply {
    unsigned int mode, dcs, decoded;
    char text[USSD_BODY_MAX + 1];
    size_t text_len;
};

int veci_sms_decode_deliver(const char *, struct veci_sms_deliver *);
void veci_sms_clear(struct veci_sms_deliver *);
int veci_ussd_decode_urc(const char *, struct veci_ussd_reply *);
void veci_ussd_clear(struct veci_ussd_reply *);

static uint32_t seed = 0x9e3779b9u;
static uint32_t next_random(void)
{
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    return seed;
}

int main(void)
{
    static const char alphabet[] = "0123456789ABCDEFabcdef!@\"\\,:\r\n+ ";
    unsigned int i;
    for (i = 0; i < 5000u; ++i) {
        char pdu[514];
        char ussd[1100];
        struct veci_sms_deliver sms;
        struct veci_ussd_reply reply;
        size_t j, len = (size_t)(next_random() % 515u);
        int rc;

        /* Vary length, bad hex, malformed TPDU and random embedded NUL. */
        for (j = 0; j < len; ++j)
            pdu[j] = alphabet[next_random() % (sizeof(alphabet) - 1u)];
        pdu[len] = 0;
        rc = veci_sms_decode_deliver(pdu, &sms);
        if ((rc != -1 && rc != 0) || sms.text_len > SMS_BODY_MAX ||
            sms.text[sms.text_len] != '\0' ||
            (rc != 0 && (sms.text_len || sms.sender[0])))
            return 2;
        veci_sms_clear(&sms);

        /* NUL-terminated arbitrary +CUSD byte string with bounded length. */
        len = (size_t)(next_random() % (sizeof(ussd) - 1u));
        if (len > 0u && (next_random() & 1u)) {
            static const char prefix[] = "+CUSD: 0,\"";
            size_t prefix_len = sizeof(prefix) - 1u;
            for (j = 0; j < prefix_len && j < len; ++j) ussd[j] = prefix[j];
        } else {
            j = 0;
        }
        for (; j < len; ++j)
            ussd[j] = alphabet[next_random() % (sizeof(alphabet) - 1u)];
        ussd[len] = 0;
        rc = veci_ussd_decode_urc(ussd, &reply);
        if ((rc != -1 && rc != 0 && rc != 1) ||
            reply.text_len > USSD_BODY_MAX ||
            reply.text[reply.text_len] != '\0' ||
            (rc != 0 && reply.text_len))
            return 3;
        veci_ussd_clear(&reply);
    }
    puts("OFFLINE_CODEC_NEGATIVE_CORPUS_PASS 5000 PDU + 5000 CUSD");
    return 0;
}
