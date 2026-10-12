/*
 * VeCI inert AT transaction coordinator (GPL-2.0-only).
 * Pure state and RAM-bound framing, NO serial access, AT command transmit,
 * network, filesystem, logging, SMS/OTP persistence, threading or retry.
 * The real privileged transport MUST independently enforce the shared flock
 * and attribute each byte stream to the current modem/port generation.
 * Logical epochs alone CANNOT correlate a delayed URC on a physical modem.
 */
#include "veci-modem-transaction.h"
#include <errno.h>
#include <fcntl.h>
#include <string.h>

static void wipe(void *p, size_t n)
{
    volatile unsigned char *q = (volatile unsigned char *)p;
    while (n--) *q++ = 0;
}

static int live_fd(const struct veci_modem_transaction *tx)
{
    return tx->lock_fd >= 0 && fcntl(tx->lock_fd, F_GETFD) != -1;
}

static int reject(struct veci_modem_transaction *tx, int error)
{
    if (!tx) return -EINVAL;
    if (error >= 0) error = -EPROTO;
    if (tx->queue.active_valid && !tx->queue.poisoned)
        (void)veci_jobs_abort(&tx->queue, tx->job_id);
    else if (!tx->queue.poisoned)
        veci_jobs_reset(&tx->queue);
    /* Prevent queued work from silently being replayed after reset. */
    tx->queue.poisoned = 1;
    wipe(&tx->frame, sizeof(tx->frame));
    tx->state = VECI_TXN_QUARANTINED;
    tx->first_error = error;
    return error;
}

void veci_txn_init(struct veci_modem_transaction *tx)
{
    if (!tx) return;
    memset(tx, 0, sizeof(*tx));
    veci_jobs_init(&tx->queue);
    veci_frame_init(&tx->frame);
    tx->lock_fd = -1;
}

int veci_txn_submit(struct veci_modem_transaction *tx, uint32_t id,
                    int kind, int exact_approval)
{
    if (!tx) return -EINVAL;
    if (tx->state == VECI_TXN_QUARANTINED) return -EIO;
    return veci_jobs_submit(&tx->queue, id, kind, exact_approval);
}

int veci_txn_arm(struct veci_modem_transaction *tx, uint64_t epoch,
                 int borrowed_lock_fd, int64_t now_ms, int timeout_ms,
                 uint32_t *id, int *kind)
{
    int rc;
    if (!tx || !id || !kind || epoch == 0 || epoch <= tx->epoch)
        return -EINVAL;
    if (tx->state == VECI_TXN_QUARANTINED) return -EIO;
    if (tx->state != VECI_TXN_IDLE) return -EBUSY;
    if (borrowed_lock_fd < 0 || fcntl(borrowed_lock_fd, F_GETFD) == -1)
        return -EBADF;
    rc = veci_jobs_begin(&tx->queue, now_ms, timeout_ms, id, kind);
    if (rc != 0) return rc;
    tx->epoch = epoch;
    tx->job_id = *id;
    tx->kind = *kind;
    tx->lock_fd = borrowed_lock_fd;
    tx->state = VECI_TXN_ARMED;
    tx->first_error = 0;
    veci_frame_init(&tx->frame);
    return 0;
}

static int check_owner(struct veci_modem_transaction *tx,
                       uint64_t epoch, uint32_t id)
{
    if (!tx || !id || !epoch) return -EINVAL;
    if (tx->state == VECI_TXN_QUARANTINED) return -EIO;
    if (epoch != tx->epoch || id != tx->job_id) return -ESTALE;
    if (!live_fd(tx)) return reject(tx, -EBADF);
    return 0;
}

int veci_txn_issued(struct veci_modem_transaction *tx,
                    uint64_t epoch, uint32_t id)
{
    int rc = check_owner(tx, epoch, id);
    if (rc != 0) return rc;
    if (tx->state != VECI_TXN_ARMED) return -EPERM;
    tx->state = VECI_TXN_INFLIGHT;
    return 0;
}

struct veci_event_ctx {
    struct veci_modem_transaction *tx;
    int64_t now_ms;
};

static int starts(const char *s, const char *prefix)
{
    return s && strncmp(s, prefix, strlen(prefix)) == 0;
}

static void on_event(int event, const char *line, int metadata, void *arg)
{
    struct veci_event_ctx *ctx = (struct veci_event_ctx *)arg;
    struct veci_modem_transaction *tx = ctx->tx;
    int rc;
    if (tx->state == VECI_TXN_QUARANTINED) return;
    if (tx->state != VECI_TXN_INFLIGHT) {
        (void)reject(tx, -EPROTO);
        return;
    }
    /* +CUSD observed during SMS is ambiguous and may be an old USSD
     * response. Do not count it as the next transaction's response. */
    if ((event == VECI_FRAME_USSD && tx->kind != VECI_JOB_USSD) ||
        (tx->kind == VECI_JOB_USSD && event == VECI_FRAME_OTHER &&
         (starts(line, "+CMGL:") || starts(line, "+CMGR:")))) {
        (void)reject(tx, -EPROTO);
        return;
    }
    rc = veci_jobs_consume(&tx->queue, tx->job_id,
                           event, line, metadata, ctx->now_ms);
    if (rc < 0) {
        (void)reject(tx, rc);
    } else if (rc == VECI_COMPLETE) {
        tx->state = VECI_TXN_COMPLETE;
    } else if (rc == VECI_INPUT_REQUIRED) {
        /* UI must explicitly abort/resync, never auto-answer USSD menus. */
        tx->state = VECI_TXN_INTERACTIVE;
    }
}

int veci_txn_tick(struct veci_modem_transaction *tx, int64_t now_ms)
{
    int rc;
    if (!tx || now_ms < 0) return -EINVAL;
    if (tx->state == VECI_TXN_QUARANTINED) return -EIO;
    if (tx->state == VECI_TXN_IDLE) return -ENOENT;
    if (!live_fd(tx)) return reject(tx, -EBADF);
    rc = veci_jobs_expire(&tx->queue, now_ms);
    if (rc < 0) return reject(tx, rc);
    return 0;
}

int veci_txn_feed(struct veci_modem_transaction *tx,
                  uint64_t epoch, uint32_t id,
                  const unsigned char *bytes, size_t size, int64_t now_ms)
{
    struct veci_event_ctx ctx;
    int rc = check_owner(tx, epoch, id);
    if (rc != 0) return rc;
    if (tx->state != VECI_TXN_INFLIGHT) return -EPERM;
    if (!bytes && size) return -EINVAL;
    if (!size) return 0;
    rc = veci_txn_tick(tx, now_ms);
    if (rc < 0) return rc;
    ctx.tx = tx;
    ctx.now_ms = now_ms;
    rc = veci_frame_feed(&tx->frame, bytes, size, on_event, &ctx);
    if (tx->state == VECI_TXN_QUARANTINED)
        return tx->first_error;
    if (rc != 0) return reject(tx, -EPROTO);
    if (tx->state == VECI_TXN_COMPLETE) return VECI_COMPLETE;
    if (tx->state == VECI_TXN_INTERACTIVE) return VECI_INPUT_REQUIRED;
    return VECI_WAITING;
}

int veci_txn_finish(struct veci_modem_transaction *tx,
                    uint64_t epoch, uint32_t id)
{
    int rc = check_owner(tx, epoch, id);
    if (rc != 0) return rc;
    if (tx->state != VECI_TXN_COMPLETE) return -EBUSY;
    /* An incomplete trailing PDU/line must invalidate success. */
    rc = veci_frame_finish(&tx->frame, NULL, NULL);
    if (rc != 0) return reject(tx, -EPROTO);
    rc = veci_jobs_finish(&tx->queue, id);
    if (rc != 0) return reject(tx, rc);
    wipe(&tx->frame, sizeof(tx->frame));
    tx->job_id = 0;
    tx->kind = 0;
    tx->lock_fd = -1;
    tx->state = VECI_TXN_IDLE;
    return 0;
}

int veci_txn_abort(struct veci_modem_transaction *tx,
                   uint64_t epoch, uint32_t id)
{
    int rc = check_owner(tx, epoch, id);
    if (rc != 0) return rc;
    if (tx->state == VECI_TXN_IDLE) return -ENOENT;
    return reject(tx, -ECANCELED);
}

int veci_txn_resync(struct veci_modem_transaction *tx, uint64_t new_epoch,
                    int authorized_external_resync)
{
    if (!tx || !new_epoch || new_epoch <= tx->epoch) return -EINVAL;
    if (authorized_external_resync != 1) return -EACCES;
    if (tx->state != VECI_TXN_QUARANTINED) return -EPERM;
    /* This function does NOT actually reset the port/modem. Privileged
     * owner must first verify resynchronization on the real device. */
    wipe(&tx->frame, sizeof(tx->frame));
    veci_jobs_reset(&tx->queue);
    tx->epoch = new_epoch;
    tx->job_id = 0;
    tx->kind = 0;
    tx->lock_fd = -1;
    tx->state = VECI_TXN_IDLE;
    tx->first_error = 0;
    veci_frame_init(&tx->frame);
    return 0;
}
