/*
 * OFFLINE TEST HARNESS ONLY: one verified-FD +CMGR read using a synthetic PTY.
 * Never compile into firmware, open a physical modem port or expose a production RPC.
 * Caller supplies trusted already-open noncanonical PTY and a TEST lock path.
 * Security inputs must be proven by privileged caller in any future runtime.
 */
#ifndef VECI_ENABLE_OFFLINE_PTY_HARNESS
#error "OFFLINE PTY ONLY: forbid linking into production firmware"
#endif
#define _POSIX_C_SOURCE 200809L
#include "veci-sms-cmgr-frame.h"
#include "veci-modem-identity.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
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

static void wipe(void *data, size_t size)
{
    volatile unsigned char *p = (volatile unsigned char *)data;
    while (size--) *p++ = 0;
}
static int64_t clock_ms(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) return -1;
    if (t.tv_sec < 0 || t.tv_sec > (INT64_MAX-999)/1000) return -1;
    return (int64_t)t.tv_sec*1000 + t.tv_nsec/1000000;
}
static int poll_ready(int fd, short events, int64_t deadline)
{
    struct pollfd p = { .fd=fd, .events=events };
    for (;;) {
        int64_t now = clock_ms();
        int n;
        if (now < 0) return -EIO;
        if (now >= deadline) return -ETIMEDOUT;
        n = poll(&p, 1, (int)(deadline-now));
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) return -errno;
        if (!n) return -ETIMEDOUT;
        if ((p.revents & (POLLHUP|POLLERR|POLLNVAL)) ||
            !(p.revents & events)) return -EIO;
        return 0;
    }
}
/* no arbitrary command parameter; exact decimal slot, plus CR */
static int command_for(unsigned int slot, char out[24])
{
    int n;
    if (slot > 65535u) return -EINVAL;
    n = snprintf(out, 24u, "AT+CMGR=%u\r", slot);
    return n >= 0 && n < 24 ? n : -EINVAL;
}

/* Metadata-free returned status; decoded text is in caller-owned output
 * only on SUCCESS, to be wiped immediately after foreground display.
 * Never log it; do not put it in diagnostic JSON.
 */
int veci_serial_cmgr_pty_once(
    int tty_fd, const char *trusted_fake_sysfs, const char *tty_name,
    const char *test_lock_path, struct veci_sms_read_policy *approval,
    int timeout_ms, struct veci_sms_deliver *output)
{
    struct veci_sms_cmgr_frame parser;
    struct veci_modem_identity identity;
    struct termios tio;
    char cmd[24] = {0};
    unsigned char rx[256] = {0};
    int lock = -1, orig = -1, rc = -EINVAL, command_len, terminal_lf = 0;
    int64_t deadline;
    size_t sent = 0;
    if (!output) return -EINVAL;
    wipe(output, sizeof(*output));
    memset(&parser, 0, sizeof(parser));
    memset(&identity, 0, sizeof(identity));
    if (!approval || approval->state != VECI_SMS_READ_ARMED ||
        !test_lock_path || !*test_lock_path ||
        !trusted_fake_sysfs || !tty_name || tty_fd < 0 ||
        timeout_ms < 100 || timeout_ms > 30000) {
        rc = -EACCES; goto done;
    }
    command_len = command_for(approval->slot, cmd);
    if (command_len < 0) { rc=command_len; goto done; }
    lock = veci_at_session_lock_path(test_lock_path, 0);
    if (lock < 0) { rc=lock; lock=-1; goto done; }
    rc = veci_modem_verify_identity(trusted_fake_sysfs, tty_name, tty_fd,
                                    &identity);
    if (rc) goto done;
    if (!isatty(tty_fd) || tcgetattr(tty_fd, &tio) ||
        (tio.c_lflag & ICANON)) { rc=-ENOTTY; goto done; }
    orig = fcntl(tty_fd, F_GETFL);
    if (orig < 0) { rc=-EBADF; goto done; }
    if (fcntl(tty_fd, F_SETFL, orig | O_NONBLOCK) != 0) {
        rc=-errno; goto done;
    }
    /* Never flush stale input; reject rather than attributing URC to
     * the freshly approved command. Late URCs require production lifecycle.
     */
    {
        struct pollfd pending = { .fd=tty_fd, .events=POLLIN };
        int n = poll(&pending, 1, 0);
        if (n < 0) { rc=-errno; goto done; }
        if (n) { rc=-EAGAIN; goto done; }
    }
    deadline = clock_ms();
    if (deadline < 0 || deadline > INT64_MAX - timeout_ms) {
        rc=-EIO; goto done;
    }
    deadline += timeout_ms;
    rc = veci_sms_read_issued(approval, approval->session_binding,
                              approval->request_nonce, approval->modem_generation,
                              approval->slot);
    if (rc) goto done;
    rc = veci_sms_cmgr_init(&parser, approval);
    if (rc) goto done;
    /* Exactly one command. Poll retries handle only partial write/EAGAIN
     * of that SAME command, never retransmit a completed request.
     */
    while (sent < (size_t)command_len) {
        ssize_t n;
        rc=poll_ready(tty_fd, POLLOUT, deadline);
        if (rc) goto done;
        n=write(tty_fd, cmd+sent, (size_t)command_len-sent);
        if (n > 0) { sent+=(size_t)n; continue; }
        if (n < 0 && (errno==EAGAIN || errno==EINTR)) continue;
        rc=n==0 ? -EIO : -errno;
        goto done;
    }
    for (;;) {
        ssize_t n;
        rc=poll_ready(tty_fd, POLLIN, deadline);
        if (rc) goto done;
        n=read(tty_fd, rx, sizeof(rx));
        if (n < 0 && (errno==EAGAIN || errno==EINTR)) continue;
        if (n <= 0) { rc=-EIO; goto done; }
        rc=veci_sms_cmgr_feed(&parser, rx, (size_t)n);
        terminal_lf = rx[n-1]=='\n';
        wipe(rx, sizeof(rx));
        if (rc) goto done;
        /* Terminal must include final LF. Do not release on a split CR,
         * which would leave a stray delimiter in subsequent transaction.
         */
        if (parser.stage == 3u && terminal_lf) break;
    }
    rc=veci_sms_cmgr_finish(&parser);
    if (rc) goto done;
    rc=veci_sms_read_complete(approval, approval->session_binding,
                             approval->request_nonce, approval->modem_generation,
                             approval->slot, 1);
    if (rc) goto done;
    rc=veci_sms_cmgr_take(&parser, approval, output);
done:
    if (rc) {
        wipe(output, sizeof(*output));
        if (approval) veci_sms_read_abort(approval);
    }
    veci_sms_cmgr_clear(&parser);
    wipe(&identity, sizeof(identity));
    wipe(rx, sizeof(rx));
    wipe(cmd, sizeof(cmd));
    if (orig >= 0) (void)fcntl(tty_fd, F_SETFL, orig);
    if (lock >= 0) veci_at_session_unlock(lock);
    return rc;
}
