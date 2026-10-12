/*
 * VeCI OFFLINE ONLY PTY serial transaction smoke harness, GPL-2.0-only.
 *
 * IMPORTANT: compile is forbidden unless VECI_ENABLE_OFFLINE_PTY_HARNESS
 * is intentionally defined by host CI. This is NOT a router executable,
 * NOT production modem transport and NOT a verified protocol layer.
 * Test accepts an already-open, externally configured mock PTY FD.
 *
 * SMS READ/LIST only (no send, delete, USSD, arbitrary AT or OTP output).
 * Caller/CI supplies an isolated test lock path, never an RPC/browser path.
 * A production transport must instead pin its hardcoded lock path and
 * validate physical modem/sysfs identity, ACL/CSRF, session provenance,
 * AT URC correlation, SIM change, and device lifecycle on real hardware.
 */
#ifndef VECI_ENABLE_OFFLINE_PTY_HARNESS
#error "Disabled: offline PTY harness must never be linked into firmware"
#endif
#define _GNU_SOURCE
#include "veci-modem-transaction.h"
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

extern int veci_at_session_lock_path(const char *path, int wait_ms);
extern void veci_at_session_unlock(int fd);

struct veci_serial_smoke_result {
    unsigned int records;       /* ONLY a count, no SMS message data */
    int status;                 /* 0 success or negative errno */
};

static void secure_wipe(void *p, size_t n)
{
    volatile unsigned char *v = (volatile unsigned char *)p;
    while (n--) *v++ = 0;
}

static int64_t now_ms(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) return -1;
    if (t.tv_sec < 0 || t.tv_sec > INT64_MAX / 1000 - 1) return -1;
    return (int64_t)t.tv_sec * 1000 + t.tv_nsec / 1000000;
}
static int time_remaining(int64_t deadline)
{
    int64_t now = now_ms();
    if (now < 0) return -EIO;
    if (now >= deadline) return -ETIMEDOUT;
    return (int)(deadline - now);
}
/* No user text/command parameters: only allow fixed read-only SMS AT
 * commands in a mock PTY. Reading SMS is sensitive and requires approval.
 */
static int command_for(int kind, unsigned int index,
                       char *command, size_t cap)
{
    int n;
    if (kind == VECI_JOB_SMS_LIST && index == 0)
        n = snprintf(command, cap, "AT+CMGL=4\r");
    else if (kind == VECI_JOB_SMS_READ && index >= 1 && index <= 255)
        n = snprintf(command, cap, "AT+CMGR=%u\r", index);
    else
        return -EINVAL; /* SMS send/delete, USSD, arbitrary AT denied */
    if (n <= 0 || (size_t)n >= cap) return -EINVAL;
    return n;
}

/* A smoke operation locks the SAME lock file as the LTE manager.
 * PTY FD must be noncanonical, raw and configured by the trusted caller.
 * Result contains only count/status, never raw bytes or decoded OTP.
 */
int veci_serial_sms_smoke_fd(int tty_fd, const char *isolated_test_lock,
                             int kind, unsigned int index, int approved,
                             int timeout_ms,
                             struct veci_serial_smoke_result *out)
{
    struct veci_modem_transaction tx;
    struct termios tio;
    int lock_fd=-1, old_flags=-1, rc=-EINVAL, k, remaining;
    int64_t deadline;
    uint32_t id=0;
    char command[32];
    unsigned char buffer[256];
    size_t to_write, written=0;
    uint64_t epoch=1u;
    if (!out) return -EINVAL;
    memset(out, 0, sizeof(*out));
    out->status = -EINVAL;
    if (approved != 1 || !isolated_test_lock || !*isolated_test_lock ||
        tty_fd < 0 || timeout_ms < 100 || timeout_ms > 30000) {
        rc = approved != 1 ? -EACCES : -EINVAL;
        goto done;
    }
    k = command_for(kind, index, command, sizeof(command));
    if (k < 0) { rc = k; goto done; }
    if (!isatty(tty_fd) || tcgetattr(tty_fd, &tio) != 0 ||
        (tio.c_lflag & ICANON) != 0) {
        rc = -ENOTTY;
        goto done;
    }
    old_flags = fcntl(tty_fd, F_GETFL);
    if (old_flags < 0) { rc = -EBADF; goto done; }
    lock_fd = veci_at_session_lock_path(isolated_test_lock, 0);
    if (lock_fd < 0) { rc = lock_fd; goto done; }
    if (fcntl(tty_fd, F_SETFL, old_flags | O_NONBLOCK) != 0) {
        rc = -errno; goto done;
    }
    {
        struct pollfd pending = { .fd=tty_fd, .events=POLLIN };
        int pr = poll(&pending, 1, 0);
        /* Fail closed rather than flushing stale responses or consuming
         * a leftover USSD URC as the response to a fresh SMS command.
         * This check alone cannot prevent an URC arriving later. */
        if (pr < 0) { rc = -errno; goto done; }
        if (pr > 0) { rc = -EAGAIN; goto done; }
    }
    deadline = now_ms();
    if (deadline < 0 || deadline > INT64_MAX - timeout_ms) {
        rc = -EIO; goto done;
    }
    veci_txn_init(&tx);
    rc = veci_txn_submit(&tx, 1u, kind, approved);
    if (rc) goto done;
    rc = veci_txn_arm(&tx, epoch, lock_fd, deadline, timeout_ms, &id, &k);
    if (rc) goto done;
    if (id != 1u || k != kind) { rc = -EPROTO; goto done; }
    rc = veci_txn_issued(&tx, epoch, id);
    if (rc) goto done;
    deadline += timeout_ms;
    to_write = strlen(command);
    while (written < to_write) {
        struct pollfd pfd = { .fd=tty_fd, .events=POLLOUT };
        ssize_t n;
        remaining = time_remaining(deadline);
        if (remaining < 0) { rc = remaining; goto done; }
        k = poll(&pfd, 1, remaining);
        if (k < 0 && errno == EINTR) continue;
        if (k <= 0) { rc = k == 0 ? -ETIMEDOUT : -errno; goto done; }
        if ((pfd.revents & (POLLERR|POLLNVAL|POLLHUP)) ||
            !(pfd.revents & POLLOUT)) { rc = -EIO; goto done; }
        n = write(tty_fd, command + written, to_write - written);
        if (n > 0) { written += (size_t)n; continue; }
        if (n < 0 && (errno == EAGAIN || errno == EINTR)) continue;
        rc = n == 0 ? -EIO : -errno;
        goto done;
    }
    /* Return only metadata, never echo message to logs/stdout.
     * No auto retry or automatic AT commands; all error paths discard.
     */
    for (;;) {
        struct pollfd pfd = { .fd=tty_fd, .events=POLLIN };
        ssize_t n;
        remaining = time_remaining(deadline);
        if (remaining < 0) { rc = remaining; goto done; }
        k = poll(&pfd, 1, remaining);
        if (k < 0 && errno == EINTR) continue;
        if (k <= 0) { rc = k == 0 ? -ETIMEDOUT : -errno; goto done; }
        if ((pfd.revents & (POLLERR|POLLNVAL|POLLHUP)) ||
            !(pfd.revents & POLLIN)) { rc = -EIO; goto done; }
        n = read(tty_fd, buffer, sizeof(buffer));
        if (n < 0 && (errno == EAGAIN || errno == EINTR)) continue;
        if (n <= 0) { rc = -EIO; goto done; }
        rc = veci_txn_feed(&tx, epoch, id, buffer, (size_t)n, now_ms());
        if (rc < 0) goto done;
        if (rc == VECI_COMPLETE) {
            /* All events in the chunk were parsed; no raw content copied
             * to result. Caller still must quiesce/drain physical modem. */
            unsigned int count = tx.queue.pdu_count;
            rc = veci_txn_finish(&tx, epoch, id);
            if (rc) goto done;
            out->records = count;
            rc = 0;
            goto done;
        }
        if (rc == VECI_INPUT_REQUIRED) {
            rc = -EOPNOTSUPP; /* No interactive USSD through this harness. */
            goto done;
        }
    }
done:
    /* Command and serial RX bytes are never logged or exposed.
     * Most failures occurred with transport ambiguity; do not retry.
     */
    secure_wipe(buffer, sizeof(buffer));
    secure_wipe(command, sizeof(command));
    if (old_flags >= 0)
        (void)fcntl(tty_fd, F_SETFL, old_flags);
    if (lock_fd >= 0)
        veci_at_session_unlock(lock_fd);
    out->status = rc;
    if (rc != 0) out->records = 0;
    return rc;
}
