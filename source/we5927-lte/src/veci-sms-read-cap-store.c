/*
 * VeCI locked private tmpfs one-use SMS capability. NOT INSTALLED.
 * GPL-2.0-only. No serial, modem, networking, logger or UI operations.
 * The same trusted principal must be supplied by authenticated callers
 * across requests; this library does NOT derive it from rpcd stdin.
 */
#define _GNU_SOURCE
#include "veci-sms-read-cap-store.h"
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/types.h>
#include <unistd.h>

#ifndef TMPFS_MAGIC
#define TMPFS_MAGIC 0x01021994
#endif
#define VECI_STORE_TAG 0x56454349u
#define VECI_STORE_REV 1u
#define VECI_STORE_NAME "pending"
struct veci_store_record {
    uint32_t tag;
    uint32_t revision;
    struct veci_sms_read_capability cap;
};

static void erase(void *buf, size_t n)
{
    volatile unsigned char *p = (volatile unsigned char *)buf;
    while (n--) *p++ = 0;
}

static int private_tmpfs(int fd)
{
    struct stat st;
    struct statfs fs;
    if (fd < 0 || fstat(fd, &st) != 0 || !S_ISDIR(st.st_mode) ||
        (st.st_mode & 07777u) != 0700u || st.st_uid != geteuid() ||
        fstatfs(fd, &fs) != 0 || (unsigned long)fs.f_type != TMPFS_MAGIC)
        return -EPERM;
    return 0;
}

static int take_lock(int fd)
{
    int ret;
    do { ret = flock(fd, LOCK_EX | LOCK_NB); } while (ret < 0 && errno == EINTR);
    return ret == 0 ? 0 : -EBUSY;
}

static int file_ok(int fd)
{
    struct stat st;
    return fstat(fd, &st) == 0 && S_ISREG(st.st_mode) &&
           st.st_nlink == 1 && st.st_uid == geteuid() &&
           (st.st_mode & 07777u) == 0600u ? 0 : -EPERM;
}

static int full_write(int fd, const void *buf, size_t n)
{
    const unsigned char *p = (const unsigned char *)buf;
    while (n) {
        ssize_t sent = write(fd, p, n);
        if (sent < 0 && errno == EINTR) continue;
        if (sent <= 0) return -EIO;
        p += (size_t)sent; n -= (size_t)sent;
    }
    return 0;
}

static int full_read(int fd, void *buf, size_t n)
{
    unsigned char *p = (unsigned char *)buf;
    while (n) {
        ssize_t got = read(fd, p, n);
        if (got < 0 && errno == EINTR) continue;
        if (got <= 0) return -EIO;
        p += (size_t)got; n -= (size_t)got;
    }
    unsigned char extra;
    ssize_t got;
    do { got = read(fd, &extra, 1); } while (got < 0 && errno == EINTR);
    return got == 0 ? 0 : -EIO;
}

int veci_sms_store_arm(int dirfd,
                       const unsigned char session[VECI_SMS_SESSION_BYTES],
                       const unsigned char token[VECI_SMS_CAP_BYTES],
                       unsigned int slot, uint64_t generation,
                       uint64_t now, unsigned int ttl,
                       int acl, int csrf, int consent)
{
    struct veci_store_record rec = {0};
    int fd = -1, ret, created = 0;
    ret = veci_sms_cap_arm(&rec.cap, session, token, slot, generation,
                           now, ttl, acl, csrf, consent);
    if (ret) goto done;
    rec.tag = VECI_STORE_TAG;
    rec.revision = VECI_STORE_REV;
    ret = private_tmpfs(dirfd);
    if (ret) goto done;
    ret = take_lock(dirfd);
    if (ret) goto done;
    fd = openat(dirfd, VECI_STORE_NAME,
                O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC |
                O_NONBLOCK, 0600);
    if (fd < 0) { ret = errno == EEXIST ? -EBUSY : -EIO; goto unlock; }
    created = 1;
    ret = file_ok(fd);
    if (!ret) ret = full_write(fd, &rec, sizeof(rec));
    if (close(fd) != 0 && !ret) ret = -EIO;
    fd = -1;
    if (ret && created) (void)unlinkat(dirfd, VECI_STORE_NAME, 0);
unlock:
    (void)flock(dirfd, LOCK_UN);
done:
    erase(&rec, sizeof(rec));
    return ret;
}

int veci_sms_store_consume(int dirfd,
                           const unsigned char session[VECI_SMS_SESSION_BYTES],
                           const unsigned char token[VECI_SMS_CAP_BYTES],
                           unsigned int slot, uint64_t generation,
                           uint64_t now)
{
    struct veci_store_record rec = {0};
    int ret, fd = -1;
    ret = private_tmpfs(dirfd);
    if (ret) goto done;
    ret = take_lock(dirfd);
    if (ret) goto done;
    fd = openat(dirfd, VECI_STORE_NAME, O_RDONLY | O_NOFOLLOW |
                O_CLOEXEC | O_NONBLOCK);
    if (fd < 0) { ret = -EACCES; goto unlock; }
    ret = file_ok(fd);
    if (!ret) ret = full_read(fd, &rec, sizeof(rec));
    (void)close(fd);
    fd = -1;
    /* Unlink under the exclusive directory lock BEFORE token checks.
     * Even a malformed token or bad CRC/layout burns the pending record.
     */
    if (unlinkat(dirfd, VECI_STORE_NAME, 0) != 0) {
        ret = -EACCES;
        goto unlock;
    }
    if (!ret && (rec.tag != VECI_STORE_TAG ||
                 rec.revision != VECI_STORE_REV ||
                 rec.cap.state != VECI_SMS_CAP_READY)) ret = -EACCES;
    if (!ret) ret = veci_sms_cap_consume(&rec.cap, session, token,
                                        slot, generation, now);
unlock:
    (void)flock(dirfd, LOCK_UN);
done:
    erase(&rec, sizeof(rec));
    return ret;
}
