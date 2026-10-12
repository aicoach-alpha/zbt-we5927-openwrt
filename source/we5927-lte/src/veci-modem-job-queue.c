/*
 * VeCI opt-in SMS / USSD job queue & response classification.
 * INERT C library: no tty/modem I/O, no AT transmission, no ubus, no daemon.
 * No message text, phone number, PIN, token or OTP is ever retained.
 * GPL-2.0-only.
 *
 * Integration contract:
 *   1. Privileged caller validates ACL and fresh user action/approval.
 *   2. Submit only opaque IDs; no sensitive parameters in this queue.
 *   3. Begin under a held veci_at_session_lock across entire command/URC.
 *   4. Feed events from veci-at-framing.c; complete before unlocking.
 *   5. Fail/timeout/port reset POISONS queue to prevent stale replay.
 *
 * The fixed FIFO has maximum four pending jobs and NO automatic retries.
 */
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

#define VECI_JOBS_MAX 4
#define VECI_JOB_TIMEOUT_MIN_MS 100
#define VECI_JOB_TIMEOUT_MAX_MS 30000

enum veci_job_kind { VECI_JOB_SMS_LIST=1, VECI_JOB_SMS_READ=2,
                     VECI_JOB_USSD=3 };
enum veci_event_kind { VECI_OTHER=0, VECI_OK=1, VECI_ERROR=2,
                       VECI_SMS_PDU=3, VECI_SMS_NOTICE=4,
                       VECI_USSD=5, VECI_PROTOCOL_ERROR=6 };
enum veci_job_result { VECI_WAITING=0, VECI_COMPLETE=1,
                       VECI_INPUT_REQUIRED=2 };

struct veci_job {
    uint32_t id;
    int kind;
};

struct veci_job_queue {
    struct veci_job pending[VECI_JOBS_MAX];
    struct veci_job active;
    unsigned int head;
    unsigned int count;
    int active_valid;
    int poisoned;
    int64_t deadline_ms;
    int64_t started_ms;
    int acked;
    int ussd_received;
    int ussd_mode;
    int expected_pdu;
    unsigned int pdu_count;
    int result;
};

void veci_jobs_init(struct veci_job_queue *q)
{
    if (!q) return;
    memset(q, 0, sizeof(*q));
}

static int good_kind(int kind)
{
    return kind == VECI_JOB_SMS_LIST ||
           kind == VECI_JOB_SMS_READ || kind == VECI_JOB_USSD;
}

static int has_id(const struct veci_job_queue *q, uint32_t id)
{
    unsigned int i;
    if (q->active_valid && q->active.id == id) return 1;
    for (i = 0; i < q->count; ++i) {
        if (q->pending[(q->head + i) % VECI_JOBS_MAX].id == id) return 1;
    }
    return 0;
}

int veci_jobs_submit(struct veci_job_queue *q, uint32_t id,
                     int kind, int approved)
{
    unsigned int tail;
    if (!q || !id || !good_kind(kind)) return -EINVAL;
    if (approved != 1) return -EACCES;
    if (q->poisoned) return -EIO;
    if (has_id(q, id)) return -EEXIST;
    if (q->count == VECI_JOBS_MAX) return -ENOSPC;
    tail = (q->head + q->count) % VECI_JOBS_MAX;
    q->pending[tail].id = id;
    q->pending[tail].kind = kind;
    q->count++;
    return 0;
}

int veci_jobs_begin(struct veci_job_queue *q, int64_t now_ms,
                    int timeout_ms, uint32_t *id, int *kind)
{
    if (!q || !id || !kind || now_ms < 0 ||
        now_ms > INT64_MAX - VECI_JOB_TIMEOUT_MAX_MS ||
        timeout_ms < VECI_JOB_TIMEOUT_MIN_MS ||
        timeout_ms > VECI_JOB_TIMEOUT_MAX_MS) return -EINVAL;
    if (q->poisoned) return -EIO;
    if (q->active_valid) return -EBUSY;
    if (!q->count) return -ENOENT;
    q->active = q->pending[q->head];
    memset(&q->pending[q->head], 0, sizeof(q->pending[q->head]));
    q->head = (q->head + 1) % VECI_JOBS_MAX;
    q->count--;
    q->active_valid = 1;
    q->started_ms = now_ms;
    q->deadline_ms = now_ms + timeout_ms;
    q->acked = q->ussd_received = q->expected_pdu = 0;
    q->pdu_count = 0;
    q->ussd_mode = -1;
    q->result = VECI_WAITING;
    *id = q->active.id;
    *kind = q->active.kind;
    return 0;
}

static int poison(struct veci_job_queue *q, int error)
{
    /* No automatic replay after unexpected modem state or timeout. */
    memset(q->pending, 0, sizeof(q->pending));
    q->head = q->count = 0;
    q->poisoned = 1;
    q->result = error;
    return error;
}

int veci_jobs_expire(struct veci_job_queue *q, int64_t now_ms)
{
    if (!q || now_ms < 0) return -EINVAL;
    if (q->poisoned) return -EIO;
    if (!q->active_valid) return -ENOENT;
    if (now_ms < q->started_ms) return poison(q, -EPROTO);
    if (now_ms >= q->deadline_ms) return poison(q, -ETIMEDOUT);
    return VECI_WAITING;
}

static int prefix(const char *line, const char *name)
{
    if (!line) return 0;
    while (*name) {
        if (*line++ != *name++) return 0;
    }
    return 1;
}

/* One event emitted by the inert AT frame parser. No payload storage.
 * A +CMT or +CDS unsolicited PDU must NOT count as an SMS inbox entry.
 * This only tracks expected response headers +CMGL / +CMGR; it is not
 * an SMS decoder, network transaction correlator or privacy layer.
 */
int veci_jobs_consume(struct veci_job_queue *q, uint32_t id,
                      int event, const char *line, int meta, int64_t now_ms)
{
    if (!q || !id || now_ms < 0) return -EINVAL;
    if (q->poisoned) return -EIO;
    if (!q->active_valid || q->active.id != id) return -ENOENT;
    if (now_ms < q->started_ms || event < VECI_OTHER ||
        event > VECI_PROTOCOL_ERROR) return poison(q, -EPROTO);
    if (now_ms >= q->deadline_ms) return poison(q, -ETIMEDOUT);
    if (q->result != VECI_WAITING) return -EALREADY;
    if (event == VECI_PROTOCOL_ERROR || event == VECI_ERROR)
        return poison(q, -EPROTO);
    if (event == VECI_OK) {
        q->acked = 1;
    } else if (event == VECI_OTHER &&
               q->active.kind == VECI_JOB_SMS_LIST &&
               prefix(line, "+CMGL:")) {
        if (q->expected_pdu) return poison(q, -EPROTO);
        q->expected_pdu = 1;
    } else if (event == VECI_OTHER &&
               q->active.kind == VECI_JOB_SMS_READ &&
               prefix(line, "+CMGR:")) {
        if (q->expected_pdu || q->pdu_count) return poison(q, -EPROTO);
        q->expected_pdu = 1;
    } else if (event == VECI_SMS_PDU && q->expected_pdu) {
        q->expected_pdu = 0;
        q->pdu_count++;
        /* Bound visible SMS metadata and reject oversized response. */
        if (q->pdu_count > 50) return poison(q, -EOVERFLOW);
    } else if (event == VECI_USSD && q->active.kind == VECI_JOB_USSD) {
        if (q->ussd_received || meta < 0 || meta > 5)
            return poison(q, -EPROTO);
        q->ussd_received = 1;
        q->ussd_mode = meta;
    }
    if (q->active.kind == VECI_JOB_USSD) {
        if (!q->acked || !q->ussd_received) return VECI_WAITING;
        q->result = q->ussd_mode == 1 ? VECI_INPUT_REQUIRED : VECI_COMPLETE;
        return q->result;
    }
    if (!q->acked) return VECI_WAITING;
    if (q->expected_pdu) return poison(q, -EPROTO);
    if (q->active.kind == VECI_JOB_SMS_READ && q->pdu_count != 1)
        return poison(q, -EPROTO);
    q->result = VECI_COMPLETE;
    return VECI_COMPLETE;
}

/* Explicit application acknowledgement; no dequeue of next task here.
 * For interactive USSD, do not auto-close or auto-answer the session;
 * the privileged UI must handle it separately. Abort poisons the queue.
 */
int veci_jobs_finish(struct veci_job_queue *q, uint32_t id)
{
    if (!q || !id) return -EINVAL;
    if (q->poisoned) return -EIO;
    if (!q->active_valid || q->active.id != id) return -ENOENT;
    if (q->result != VECI_COMPLETE) return -EBUSY;
    memset(&q->active, 0, sizeof(q->active));
    q->active_valid = 0;
    q->result = VECI_WAITING;
    return 0;
}

int veci_jobs_abort(struct veci_job_queue *q, uint32_t id)
{
    if (!q || !id) return -EINVAL;
    if (!q->active_valid || q->active.id != id) return -ENOENT;
    return poison(q, -ECANCELED);
}

/* A new safe operator action can reset the queue after a modem reset.
 * This NEVER resurrects queued jobs or sends any AT command.
 */
void veci_jobs_reset(struct veci_job_queue *q)
{
    veci_jobs_init(q);
}
