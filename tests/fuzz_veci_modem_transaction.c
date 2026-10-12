/*
 * Deterministic native-C sanitizer corpus for source-only AT coordinator.
 * All input bytes synthetic, no serial/modem/SIM/USSD transmission.
 * A duplicated CI stdout FD is used only to satisfy mock lease validation.
 */
#include "veci-modem-transaction.h"
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>

static uint32_t seed = 0x231b4acbu;
static uint32_t next_u32(void)
{
    seed ^= seed << 13;
    seed ^= seed >> 17;
    seed ^= seed << 5;
    return seed;
}

int main(void)
{
    int fd = dup(STDOUT_FILENO);
    unsigned int i;
    if (fd < 0) return 10;
    for (i = 0; i < 5000u; i++) {
        struct veci_modem_transaction tx;
        unsigned char input[160];
        unsigned int chunk, n = next_u32() % 160u;
        uint32_t id = i + 1u, started = 0;
        uint32_t claimed_id = 0;
        int kind = next_u32() & 1u ? VECI_JOB_USSD : VECI_JOB_SMS_LIST;
        int claimed_kind = 0;
        int rc;
        int64_t now = (int64_t)i * 40000;
        veci_txn_init(&tx);
        if (veci_txn_submit(&tx, id, kind, 1) != 0) return 11;
        if (veci_txn_arm(&tx, (uint64_t)i + 1u, fd, now, 500,
                         &claimed_id, &claimed_kind) != 0 ||
            claimed_id != id || claimed_kind != kind) return 12;
        if (veci_txn_issued(&tx, (uint64_t)i + 1u, id) != 0) return 13;

        /* Mostly printable ASCII/CRLF, with a few invalid control bytes. */
        for (chunk = 0; chunk < n; chunk++) {
            uint32_t v = next_u32() % 100u;
            input[chunk] = (unsigned char)(v < 75u ? 32u + v % 95u :
                                v < 88u ? '\r' :
                                v < 99u ? '\n' : 0x01u);
        }
        for (chunk = 0; chunk < n;) {
            size_t take = (size_t)(1u + next_u32() % 21u);
            if (take > n - chunk) take = n - chunk;
            rc = veci_txn_feed(&tx, (uint64_t)i + 1u, id,
                               input + chunk, take, now + 1);
            if (rc != 0 && rc != VECI_COMPLETE &&
                rc != VECI_INPUT_REQUIRED &&
                rc != -EPROTO && rc != -EIO && rc != -EPERM &&
                rc != -EOVERFLOW && rc != -ETIMEDOUT) return 14;
            if (rc < 0 || rc == VECI_INPUT_REQUIRED) break;
            chunk += (unsigned int)take;
            started++;
        }
        if (tx.state == VECI_TXN_COMPLETE)
            (void)veci_txn_finish(&tx, (uint64_t)i + 1u, id);
        if (tx.state == VECI_TXN_INFLIGHT ||
            tx.state == VECI_TXN_ARMED ||
            tx.state == VECI_TXN_INTERACTIVE)
            (void)veci_txn_tick(&tx, now + 600);
        if (tx.state == VECI_TXN_QUARANTINED) {
            rc = veci_txn_resync(&tx, (uint64_t)i + 2u, 1);
            if (rc != 0) return 15;
            if (tx.queue.count || tx.queue.active_valid) return 16;
        }
        if (tx.state != VECI_TXN_IDLE ||
            tx.frame.line_len >= VECI_FRAME_LINE_MAX ||
            tx.frame.total > VECI_FRAME_STREAM_MAX ||
            tx.queue.count > VECI_JOBS_MAX ||
            started > n + 1u) return 17;
    }
    close(fd);
    puts("OFFLINE_TXN_SANITIZER_PASS 5000 fragmented/mock AT sessions");
    return 0;
}
