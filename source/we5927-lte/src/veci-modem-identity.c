/*
 * VeCI read-only WE5927 / W907-EC modem sysfs identity verification.
 * GPL-2.0-only. DEVELOPMENT SOURCE ONLY, not compiled by router Makefile.
 *
 * No write, modem AT command, usb probe, tty open, syslog or IOCTL.
 * A future privileged owner must hardcode /sys, obtain the *already
 * opened* serial fd under the shared flock and recheck on USB/SIM changes.
 * Linux sysfs topology MUST be validated against the actual router before
 * activating this code on a device (and never try alternate AT tty ports).
 */
#define _GNU_SOURCE
#include "veci-modem-identity.h"
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>

#ifndef PATH_MAX
#define PATH_MAX 4096
#endif
#define VID 0x05c6u
#define PID 0x902eu

static int fmt(char *dst, size_t cap, const char *base,
               const char *suffix)
{
    int n = snprintf(dst, cap, "%s/%s", base, suffix);
    return n < 0 || (size_t)n >= cap ? -ENAMETOOLONG : 0;
}
static int addpath(char *dst, size_t cap, const char *suffix)
{
    size_t len = strlen(dst), extra = strlen(suffix);
    if (len >= cap || extra > cap - len - 2u) return -ENAMETOOLONG;
    dst[len++] = '/';
    memcpy(dst + len, suffix, extra + 1u);
    return 0;
}
static int under(const char *root, const char *path)
{
    size_t n = strlen(root);
    return !strncmp(root, path, n) && path[n] == '/';
}
static int name_ok(const char *s)
{
    unsigned int digits = 0;
    if (!s || strncmp(s, "ttyUSB", 6) != 0 ||
        strcmp(s, "ttyUSB3") == 0) return 0;
    s += 6;
    while (*s) {
        if (*s < '0' || *s > '9' || ++digits > 5u) return 0;
        ++s;
    }
    return digits > 0u;
}
static int attr(const char *dir, const char *name,
                char *buf, size_t capacity)
{
    char path[PATH_MAX];
    int fd;
    ssize_t n;
    struct stat st;
    size_t len;
    if (fmt(path, sizeof(path), dir, name) != 0) return -ENAMETOOLONG;
    fd = open(path, O_RDONLY|O_CLOEXEC|O_NOFOLLOW|O_NONBLOCK);
    if (fd < 0) return -errno;
    if (fstat(fd, &st) != 0 || !S_ISREG(st.st_mode)) {
        close(fd); return -EINVAL;
    }
    n = read(fd, buf, capacity);
    close(fd);
    if (n <= 0 || (size_t)n >= capacity) return -EINVAL;
    len = (size_t)n;
    while (len && (buf[len - 1] == '\n' ||
                   buf[len - 1] == '\r' ||
                   buf[len - 1] == ' ')) len--;
    buf[len] = '\0';
    return len ? 0 : -EINVAL;
}
static int hex4(const char *str, unsigned int *out)
{
    unsigned int i, v = 0;
    if (strlen(str) != 4) return -EINVAL;
    for (i = 0; i < 4u; ++i) {
        char c = str[i];
        unsigned int d;
        if (c >= '0' && c <= '9') d = (unsigned int)(c - '0');
        else if (c >= 'a' && c <= 'f') d = (unsigned int)(c-'a')+10u;
        else if (c >= 'A' && c <= 'F') d = (unsigned int)(c-'A')+10u;
        else return -EINVAL;
        v = (v << 4) | d;
    }
    *out = v;
    return 0;
}
static int decimal_uint(const char *s, unsigned int *value,
                        const char **after)
{
    unsigned int v = 0, digits = 0;
    while (*s >= '0' && *s <= '9') {
        unsigned int d = (unsigned int)(*s++-'0');
        if (++digits > 10u || v > (UINT32_MAX-d)/10u) return -EINVAL;
        v = v*10u + d;
    }
    if (!digits) return -EINVAL;
    *value = v;
    *after = s;
    return 0;
}
static int devpair(const char *s, unsigned int *major_no,
                   unsigned int *minor_no)
{
    const char *p = s;
    if (decimal_uint(p, major_no, &p) != 0 || *p != ':')
        return -EINVAL;
    ++p;
    if (decimal_uint(p, minor_no, &p) != 0 || *p)
        return -EINVAL;
    return 0;
}
static int interface_path(const char *root, const char *resolved,
                          const char *name, char *ifdir, size_t cap)
{
    size_t n = strlen(resolved), slen = strlen(name);
    const char *suffix;
    char parent[PATH_MAX], *last;
    if (!under(root, resolved) || n <= slen ||
        strcmp(resolved + n - slen, name) != 0 ||
        resolved[n - slen - 1] != '/') return -EPERM;
    if (n - slen - 1 >= sizeof(parent)) return -ENAMETOOLONG;
    memcpy(parent, resolved, n-slen-1);
    parent[n-slen-1] = '\0';
    /* Some kernels have /interface/ttyUSBn/tty/ttyUSBn; do not
     * infer arbitrary nested paths or accept trailing '..' components.
     */
    last = strrchr(parent, '/');
    if (!last) return -EPERM;
    if (!strcmp(last+1, "tty")) {
        *last = '\0';
        last = strrchr(parent, '/');
        if (!last || strcmp(last+1, name) != 0) return -EPERM;
        *last = '\0';
    }
    last = strrchr(parent, '/');
    if (!last) return -EPERM;
    suffix = strrchr(last+1, ':');
    if (!suffix || strcmp(suffix, ":1.4") != 0 ||
        suffix == last+1 || !under(root, parent)) return -EPERM;
    if (strlen(parent) >= cap) return -ENAMETOOLONG;
    memcpy(ifdir, parent, strlen(parent)+1);
    return 0;
}
int veci_modem_verify_identity(const char *trusted_sysfs_root,
                               const char *tty_name, int serial_fd,
                               struct veci_modem_identity *out)
{
    char root[PATH_MAX], classpath[PATH_MAX], resolved[PATH_MAX];
    char ifdir[PATH_MAX], usbdev[PATH_MAX], driver_path[PATH_MAX];
    char driver_real[PATH_MAX], buf[32];
    struct stat st;
    unsigned int vid=0, pid=0, mj=0, mn=0;
    char *slash, *tail;
    int rc;
    if (!out) return -EINVAL;
    memset(out, 0, sizeof(*out));
    if (!trusted_sysfs_root || !name_ok(tty_name)) return -EINVAL;
    if (serial_fd < 0 || fstat(serial_fd, &st) != 0 ||
        !S_ISCHR(st.st_mode)) return -ENOTTY;
    if (!realpath(trusted_sysfs_root, root)) return -errno;
    if (fmt(classpath, sizeof(classpath), root, "class/tty") != 0)
        return -ENAMETOOLONG;
    if (addpath(classpath, sizeof(classpath), tty_name) != 0)
        return -ENAMETOOLONG;
    if (addpath(classpath, sizeof(classpath), "device") != 0)
        return -ENAMETOOLONG;
    if (!realpath(classpath, resolved)) return -errno;
    rc = interface_path(root, resolved, tty_name, ifdir, sizeof(ifdir));
    if (rc != 0) return rc;
    if (fmt(driver_path, sizeof(driver_path), ifdir, "driver") != 0)
        return -ENAMETOOLONG;
    if (!realpath(driver_path, driver_real) ||
        !under(root, driver_real)) return -EPERM;
    tail = strrchr(driver_real, '/');
    if (!tail || (strcmp(tail+1, "option") && strcmp(tail+1,"option1")))
        return -EPERM;
    strcpy(usbdev, ifdir);
    slash = strrchr(usbdev, '/');
    if (!slash || slash == usbdev) return -EPERM;
    *slash = '\0';
    if (!under(root, usbdev)) return -EPERM;
    if (attr(usbdev, "idVendor", buf, sizeof(buf)) ||
        hex4(buf, &vid) != 0 || vid != VID) return -ENODEV;
    if (attr(usbdev, "idProduct", buf, sizeof(buf)) ||
        hex4(buf, &pid) != 0 || pid != PID) return -ENODEV;
    /* Never trust just ttyUSB ordinal: tie its sysfs major/minor to fd. */
    if (fmt(classpath, sizeof(classpath), root, "class/tty") != 0)
        return -ENAMETOOLONG;
    if (fmt(classpath, sizeof(classpath), classpath, tty_name) != 0)
        return -ENAMETOOLONG;
    if (attr(classpath, "dev", buf, sizeof(buf)) ||
        devpair(buf, &mj, &mn) != 0) return -ENODEV;
    if (mj != (unsigned int)major(st.st_rdev) ||
        mn != (unsigned int)minor(st.st_rdev)) return -ENODEV;
    out->vendor_id = vid;
    out->product_id = pid;
    out->interface_number = 4u;
    out->tty_major = mj;
    out->tty_minor = mn;
    return 0;
}
