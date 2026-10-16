/*
 * VeCI read-only modem identity check (GPL-2.0-only).
 * SOURCE-ONLY: no firmware link, no modem commands, no device writes.
 * Root must be hardcoded by future privileged production caller, NEVER
 * taken from a user, browser or RPC. Testing uses isolated fake sysfs.
 */
#ifndef VECI_MODEM_IDENTITY_H
#define VECI_MODEM_IDENTITY_H
#include <stdint.h>
struct veci_modem_identity {
    unsigned int vendor_id;
    unsigned int product_id;
    unsigned int interface_number;
    unsigned int tty_major;
    unsigned int tty_minor;
};
/* Returns 0 only when tty name, resolved sysfs interface, VID/PID, driver,
 * and opened character device major:minor all match. Negative errno otherwise.
 * fd is a BORROWED read-only-inspected descriptor; never opened/closed here.
 */
int veci_modem_verify_identity(const char *trusted_sysfs_root,
                               const char *tty_name, int serial_fd,
                               struct veci_modem_identity *out);
#endif
