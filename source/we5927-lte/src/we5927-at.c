#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

static long ms_now(void) {
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec * 1000L + ts.tv_nsec / 1000000L;
}

int main(int argc, char **argv) {
	const char *dev, *cmd;
	int timeout_ms = 2500, fd, rc = 1;
	struct termios tio;
	char tx[512], buf[512];
	long deadline;

	if (argc < 3 || argc > 4) {
		fprintf(stderr, "usage: %s /dev/ttyUSB1 'AT+CMD' [timeout_ms]\n", argv[0]);
		return 2;
	}
	dev = argv[1]; cmd = argv[2];
	if (argc == 4) timeout_ms = atoi(argv[3]);
	if (timeout_ms < 100) timeout_ms = 100;
	if (timeout_ms > 30000) timeout_ms = 30000;

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

	if (snprintf(tx, sizeof(tx), "%s\r", cmd) >= (int)sizeof(tx)) { close(fd); return 2; }
	if (write(fd, tx, strlen(tx)) < 0) { perror("write"); close(fd); return 3; }

	deadline = ms_now() + timeout_ms;
	while (ms_now() < deadline) {
		struct pollfd pfd = { .fd = fd, .events = POLLIN };
		int left = (int)(deadline - ms_now());
		int pr = poll(&pfd, 1, left > 250 ? 250 : left);
		if (pr < 0 && errno != EINTR) break;
		if (pr <= 0) continue;
		if (pfd.revents & POLLIN) {
			ssize_t n = read(fd, buf, sizeof(buf)-1);
			if (n > 0) {
				buf[n] = '\0';
				fputs(buf, stdout);
				fflush(stdout);
				if (strstr(buf, "\r\nOK\r\n") || strstr(buf, "\nOK\r") || strstr(buf, "\nOK\n")) rc = 0;
				if (strstr(buf, "\r\nERROR\r\n") || strstr(buf, "+CME ERROR") || strstr(buf, "+CMS ERROR")) rc = 1;
				if (rc == 0 || strstr(buf, "ERROR")) break;
			}
		}
	}
	close(fd);
	return rc;
}
