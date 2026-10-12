/* Minimal serial AT transport shared by LTE diagnostics and future SMS/USSD.
 * Terminal-line parsing MUST survive arbitrary serial read boundaries.
 * No SMS or USSD transaction handlers are added by this source change.
 */
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#define AT_RESPONSE_MAX 8192
#define AT_LINE_MAX 1024

static int64_t ms_now(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return -1;
    return (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

static int valid_command(const char *cmd) {
    size_t i, length = strlen(cmd);
    if (length < 2 || length > 500 || cmd[0] != 'A' || cmd[1] != 'T') return 0;
    for (i = 0; i < length; ++i) {
        unsigned char c = (unsigned char)cmd[i];
        if (c < 32 || c > 126) return 0; /* Reject CR/LF AT injection. */
    }
    return 1;
}

/*  0: ordinary line; 1: success; -1: modem-reported error. */
static int terminal_line(const char *line) {
    if (strcmp(line, "OK") == 0) return 1;
    if (strcmp(line, "ERROR") == 0 ||
        strcmp(line, "NO CARRIER") == 0 ||
        strncmp(line, "+CME ERROR:", 11) == 0 ||
        strncmp(line, "+CMS ERROR:", 11) == 0 ||
        strcmp(line, "+CME ERROR") == 0 ||
        strcmp(line, "+CMS ERROR") == 0) return -1;
    return 0;
}

int main(int argc, char **argv) {
    const char *dev, *cmd;
    int timeout_ms = 2500, fd, rc = 1;
    struct termios tio;
    char tx[512], buf[512], line[AT_LINE_MAX];
    size_t total = 0, line_len = 0, sent, tx_len;
    int64_t deadline;

    if (argc < 3 || argc > 4) {
        fprintf(stderr, "usage: %s /dev/ttyUSB1 'AT+CMD' [timeout_ms]\n", argv[0]);
        return 2;
    }
    dev = argv[1]; cmd = argv[2];
    if (!valid_command(cmd)) {
        fputs("invalid AT command\n", stderr);
        return 2;
    }
    if (argc == 4) {
        char *end = NULL;
        long value = strtol(argv[3], &end, 10);
        if (!end || *end || value < 100 || value > 30000) {
            fputs("invalid timeout\n", stderr);
            return 2;
        }
        timeout_ms = (int)value;
    }
    fd = open(dev, O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) { perror(dev); return 3; }
    if (tcgetattr(fd, &tio) != 0) { perror("tcgetattr"); close(fd); return 3; }
    cfmakeraw(&tio);
    cfsetispeed(&tio, B115200);
    cfsetospeed(&tio, B115200);
    tio.c_cflag |= CLOCAL | CREAD;
    tio.c_cflag &= ~CRTSCTS;
    tio.c_cc[VMIN] = 0;
    tio.c_cc[VTIME] = 0;
    if (tcsetattr(fd, TCSANOW, &tio) != 0) { perror("tcsetattr"); close(fd); return 3; }
    tcflush(fd, TCIOFLUSH);

    if (snprintf(tx, sizeof(tx), "%s\r", cmd) >= (int)sizeof(tx)) {
        close(fd); return 2;
    }
    tx_len = strlen(tx);
    for (sent = 0; sent < tx_len;) {
        ssize_t n = write(fd, tx + sent, tx_len - sent);
        if (n > 0) { sent += (size_t)n; continue; }
        if (n < 0 && errno == EINTR) continue;
        if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
            struct pollfd wr = { .fd = fd, .events = POLLOUT };
            if (poll(&wr, 1, 500) > 0) continue;
        }
        close(fd); return 3;
    }

    deadline = ms_now() + timeout_ms;
    while (ms_now() >= 0 && ms_now() < deadline) {
        struct pollfd pfd = { .fd = fd, .events = POLLIN };
        int left = (int)(deadline - ms_now());
        int pr;
        if (left <= 0) break;
        pr = poll(&pfd, 1, left > 250 ? 250 : left);
        if (pr < 0 && errno != EINTR) break;
        if (pr <= 0) continue;
        if (pfd.revents & POLLIN) {
            ssize_t n = read(fd, buf, sizeof(buf));
            size_t i;
            int finished = 0;
            if (n < 0 && (errno == EINTR || errno == EAGAIN)) continue;
            if (n <= 0) break;
            if (total + (size_t)n > AT_RESPONSE_MAX) {
                fputs("AT response exceeded limit\n", stderr);
                rc = 1;
                break;
            }
            total += (size_t)n;
            if (fwrite(buf, 1, (size_t)n, stdout) != (size_t)n) {
                rc = 1;
                break;
            }
            fflush(stdout);
            for (i = 0; i < (size_t)n; ++i) {
                unsigned char ch = (unsigned char)buf[i];
                if (ch == '\r' || ch == '\n') {
                    if (line_len != 0) {
                        line[line_len] = '\0';
                        int state = terminal_line(line);
                        line_len = 0;
                        if (state != 0) {
                            rc = state > 0 ? 0 : 1;
                            finished = 1;
                            break;
                        }
                    }
                } else {
                    if (line_len + 1 >= sizeof(line)) {
                        fputs("AT line exceeded limit\n", stderr);
                        rc = 1;
                        finished = 1;
                        break;
                    }
                    line[line_len++] = (char)ch;
                }
            }
            if (finished) break;
        }
    }
    close(fd);
    return rc;
}
