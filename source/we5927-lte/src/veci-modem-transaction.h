/* VeCI SMS/USSD offline-only AT transaction coordinator.
 * GPL-2.0-only. Source-only, not linked into production.
 * The caller owns a real flock across arm -> feed -> finish/abort; this
 * pure coordinator cannot attest which tty or modem produced the bytes.
 */
#ifndef VECI_MODEM_TRANSACTION_H
#define VECI_MODEM_TRANSACTION_H
#include <stddef.h>
#include <stdint.h>

#define VECI_TXN_LINE 1024
#define VECI_TXN_QUEUE 4
enum veci_txn_state {
    VECI_TXN_IDLE = 0,
    VECI_TXN_ARMED = 1,
    VECI_TXN_INFLIGHT = 2,
    VECI_TXN_COMPLETE = 3,
    VECI_TXN_INTERACTIVE = 4,
    VECI_TXN_QUARANTINED = 5
};
struct veci_txn_frame {
    char line[VECI_TXN_LINE];
    size_t line_len, total;
    int pdu_expected, failed;
};
struct veci_txn_job {
    uint32_t id;
    int kind;
};
struct veci_txn_queue {
    struct veci_txn_job pending[VECI_TXN_QUEUE], active;
    unsigned int head, count;
    int active_valid, poisoned;
    int64_t deadline_ms, started_ms;
    int acked, ussd_received, ussd_mode, expected_pdu;
    unsigned int pdu_count;
    int result;
};
struct veci_modem_transaction {
    struct veci_txn_frame frame;
    struct veci_txn_queue queue;
    uint64_t epoch;
    int lock_fd;       /* borrowed; never closed by coordinator */
    uint32_t job_id;
    int kind;
    int state;
    int first_error;
};

/* 0 if queued. Caller is responsible for actual UI consent/ACL check. */
void veci_txn_init(struct veci_modem_transaction *tx);
int veci_txn_submit(struct veci_modem_transaction *tx, uint32_t id,
                    int kind, int exact_approval);
/* epoch must be a strictly increasing unique ingress generation; caller
 * must own flock descriptor already and must hold it until finalize.
 * No I/O is performed. All operations are single-threaded.
 */
int veci_txn_arm(struct veci_modem_transaction *tx, uint64_t epoch,
                 int borrowed_lock_fd, int64_t now_ms, int timeout_ms,
                 uint32_t *id, int *kind);
/* Caller must first send an explicitly approved AT command using a
 * separately audited transport. This merely records TX phase. */
int veci_txn_issued(struct veci_modem_transaction *tx,
                    uint64_t epoch, uint32_t id);
/* Feed only bytes scoped by trusted transport to this same epoch. Returns:
 * 0 waiting, 1 complete, 2 interactive, negative errno on failure. */
int veci_txn_feed(struct veci_modem_transaction *tx,
                  uint64_t epoch, uint32_t id,
                  const unsigned char *bytes, size_t size, int64_t now_ms);
/* 0 pending; -ETIMEDOUT/EPROTO on failure; requires explicit recovery. */
int veci_txn_tick(struct veci_modem_transaction *tx, int64_t now_ms);
/* Flush pending parser state, complete the job, then caller may release lock. */
int veci_txn_finish(struct veci_modem_transaction *tx,
                    uint64_t epoch, uint32_t id);
/* Abort poisons queue. Caller must drain/reset modem before recovery. */
int veci_txn_abort(struct veci_modem_transaction *tx,
                   uint64_t epoch, uint32_t id);
/* External verified resync + new lock + fresh ACL required before calling.
 * Cannot be used to silently recover/retry an active session. */
int veci_txn_resync(struct veci_modem_transaction *tx, uint64_t new_epoch,
                    int authorized_external_resync);

#endif
