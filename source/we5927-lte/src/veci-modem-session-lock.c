/*
 * VeCI shared per-modem session lock (inactive library, GPL-2.0-only).
 * Holds the SAME lock path used by we5927-lte and the capability probe.
 *
 * No serial I/O, AT commands, subprocess, daemon or network access here.
 * A future privileged caller must hold returned fd across command, prompt,
 * PDU, and late unsolicited +CUSD response, then explicitly release it.
 *
 * Bounded lock admission is NOT a fairness-guaranteed FIFO work queue.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define VECI_AT_LOCK_PATH "/var/lock/we5927-at.lock"
#define VECI_LOCK_WAIT_MAX_MS 2000

static int64_t mono_ms(void)
{
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return -1;
    return (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

/* Internal test seam. Never pass a path originating from RPC/browser input.
 * Returns owned descriptor >= 0 or negative errno.
 */
int veci_at_session_lock_path(const char *path, int wait_ms)
{
    struct stat st;
    int fd, saved;
    int64_t deadline;
    if (!path || !*path || wait_ms < 0 || wait_ms > VECI_LOCK_WAIT_MAX_MS)
        return -EINVAL;
    fd = open(path, O_CREAT | O_RDWR | O_CLOEXEC | O_NOFOLLOW, 0600);
    if (fd < 0) return -errno;
    if (fstat(fd, &st) != 0) {
        saved = errno;
        close(fd);
        return -saved;
    }
    /* A lock must be a regular file, not a device/FIFO or a hardlink. */
    if (!S_ISREG(st.st_mode) || st.st_nlink != 1 ||
        st.st_uid != geteuid()) {
        close(fd);
        return -EPERM;
    }
    deadline = mono_ms();
    if (deadline < 0) {
        close(fd);
        return -EIO;
    }
    deadline += wait_ms;

    for (;;) {
        if (flock(fd, LOCK_EX | LOCK_NB) == 0)
            return fd; /* Owned until caller closes it. */
        saved = errno;
        if (saved != EWOULDBLOCK && saved != EAGAIN && saved != EINTR) {
            close(fd);
            return -saved;
        }
        if (wait_ms == 0) {
            close(fd);
            return -EBUSY;
        }
        if (mono_ms() >= deadline) {
            close(fd);
            return -ETIMEDOUT;
        }
        {
            struct timespec nap = { .tv_sec = 0, .tv_nsec = 25000000L };
            while (nanosleep(&nap, &nap) != 0 && errno == EINTR) { }
        }
    }
}

/* The only production entrance: all modem consumers must use one lock. */
int veci_at_session_lock(int wait_ms)
{
    return veci_at_session_lock_path(VECI_AT_LOCK_PATH, wait_ms);
}

void veci_at_session_unlock(int fd)
{
    if (fd >= 0) close(fd);
}
