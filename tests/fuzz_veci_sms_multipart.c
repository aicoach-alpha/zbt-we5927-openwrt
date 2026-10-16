/* Offline-only deterministic ASAN/UBSAN multipart parser stress.
 * Does NOT touch the modem, network, files or user SMS content.
 */
#include "veci-sms-multipart.h"
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint32_t seed = 0x5384a709u;
static uint32_t random32(void)
{
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    return seed;
}

int main(void)
{
    struct veci_mp_state state;
    struct veci_mp_result out;
    char text[521];
    unsigned int i;
    for (i = 0; i < 8000u; ++i) {
        struct veci_mp_part p;
        size_t j, size = random32() % 521u;
        int rc;
        veci_mp_reset(&state);
        memset(text, 0, sizeof(text));
        for (j = 0; j < size; j++)
            text[j] = (char)(random32() & 0xffu);
        text[size] = 0;
        memset(&p, 0, sizeof(p));
        p.scope_id = (random32() % 6u) ? 1u : 0u;
        p.sender = (random32() % 9u) ? "+62812" : "+62BAD";
        p.alphabet = (random32() % 2u) ? 0u : 2u;
        p.concat_ref = random32() % 1024u;
        p.concat_total = random32() % 12u;
        p.concat_part = random32() % 12u;
        p.concat_is_16bit = random32() % 2u;
        p.text = text;
        p.text_len = size;
        memset(&out, 0x5a, sizeof(out));
        rc = veci_mp_add(&state, &p, 1000 + (int64_t)i, &out);
        if (!(rc == 0 || rc == 1 || rc == -EINVAL ||
              rc == -EIO || rc == -ENOSPC || rc == -EALREADY ||
              rc == -ETIMEDOUT || rc == -EPROTO || rc == -EOVERFLOW))
            return 2;
        if (out.text_len > VECI_MP_TOTAL_MAX ||
            out.text[out.text_len] != '\0')
            return 3;
        if (rc != 1 && (out.text_len != 0 || out.scope_id != 0))
            return 4;
        veci_mp_clear_result(&out);
        if (out.text_len != 0 || out.text[0] != '\0')
            return 5;
    }
    for (i = 0; i < 1000u; ++i) {
        struct veci_mp_part p;
        int rc;
        veci_mp_reset(&state);
        memset(&p, 0, sizeof(p));
        p.scope_id = 17;
        p.sender = "+62812";
        p.alphabet = 2;
        p.concat_ref = 42;
        p.concat_total = 2;
        p.concat_is_16bit = 0;
        p.text = "partA";
        p.text_len = 5;
        p.concat_part = 1;
        rc = veci_mp_add(&state, &p, i, &out);
        if (rc != 0) return 6;
        p.text = "partB";
        p.concat_part = 2;
        rc = veci_mp_add(&state, &p, i + 1, &out);
        if (rc != 1 || out.text_len != 10 ||
            strcmp(out.text, "partApartB") != 0)
            return 7;
        veci_mp_clear_result(&out);
    }
    veci_mp_reset(&state);
    puts("OFFLINE_MULTIPART_SANITIZER_PASS 8000 malformed + 1000 complete groups");
    return 0;
}
