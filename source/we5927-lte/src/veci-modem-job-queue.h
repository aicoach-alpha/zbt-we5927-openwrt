/* VeCI bounded, opt-in SMS/USSD job FIFO. Inactive/offline. GPL-2.0-only. */
#ifndef VECI_MODEM_JOB_QUEUE_H
#define VECI_MODEM_JOB_QUEUE_H
#include <stdint.h>
#define VECI_JOBS_MAX 4
#define VECI_JOB_TIMEOUT_MIN_MS 100
#define VECI_JOB_TIMEOUT_MAX_MS 30000
enum veci_job_kind {
    VECI_JOB_SMS_LIST=1, VECI_JOB_SMS_READ=2, VECI_JOB_USSD=3
};
enum veci_event_kind {
    VECI_OTHER=0, VECI_OK=1, VECI_ERROR=2,
    VECI_SMS_PDU=3, VECI_SMS_NOTICE=4,
    VECI_USSD=5, VECI_PROTOCOL_ERROR=6
};
enum veci_job_result {
    VECI_WAITING=0, VECI_COMPLETE=1, VECI_INPUT_REQUIRED=2
};
struct veci_job {
    uint32_t id;
    int kind;
};
struct veci_job_queue {
    struct veci_job pending[VECI_JOBS_MAX], active;
    unsigned int head, count;
    int active_valid, poisoned;
    int64_t deadline_ms, started_ms;
    int acked, ussd_received, ussd_mode, expected_pdu;
    unsigned int pdu_count;
    int result;
};
void veci_jobs_init(struct veci_job_queue *q);
int veci_jobs_submit(struct veci_job_queue *q, uint32_t id,
                     int kind, int approved);
int veci_jobs_begin(struct veci_job_queue *q, int64_t now_ms,
                    int timeout_ms, uint32_t *id, int *kind);
int veci_jobs_expire(struct veci_job_queue *q, int64_t now_ms);
int veci_jobs_consume(struct veci_job_queue *q, uint32_t id,
                      int event, const char *line, int meta, int64_t now_ms);
int veci_jobs_finish(struct veci_job_queue *q, uint32_t id);
int veci_jobs_abort(struct veci_job_queue *q, uint32_t id);
void veci_jobs_reset(struct veci_job_queue *q);
#endif
