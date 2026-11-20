#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

static int64_t ms_now(void) {
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (int64_t)ts.tv_sec * 1000 + ts.tv_nsec / 1000000L;
}

/* Read credentials from a pipe, never argv; disallow all AT syntax in input. */
static int pin_command(const char *mode, char *tx, size_t capacity) {
	char input[20];
	size_t length = fread(input, 1, sizeof(input), stdin);
	if (ferror(stdin) || !length || length >= sizeof(input) || input[length - 1] != '\n')
		return -1;
	input[--length] = '\0';
	int puk = !strcmp(mode, "--sim-puk-stdin");
	for (size_t i = 0; i < length; i++) {
		if (puk && i == 8 && input[i] == ' ') continue;
		if (input[i] < '0' || input[i] > '9') return -1;
	}
	if (puk) {
		if (length < 13 || length > 17 || input[8] != ' ') return -1;
		input[8] = '\0';
		return snprintf(tx, capacity, "AT+CPIN=\"%s\",\"%s\"\r", input, input + 9);
	}
	if (length < 4 || length > 8) return -1;
	return snprintf(tx, capacity, "AT+CPIN=\"%s\"\r", input);
}

int main(int argc, char **argv) {
	const char *dev, *cmd;
	int timeout_ms = 2500, fd, rc = 1;
	struct termios tio;
	char tx[512], buf[512];
	int64_t deadline;
	char line[768], response[768] = "";
	int acknowledged = 0, overflow = 0;
	size_t used = 0;

	if (argc < 3 || argc > 4) {
		fprintf(stderr, "usage: %s /dev/ttyUSB1 'AT+CMD' [timeout_ms]\n", argv[0]);
		return 2;
	}
	dev = argv[1]; cmd = argv[2];
	if (argc == 4) timeout_ms = atoi(argv[3]);
	if (timeout_ms < 100) timeout_ms = 100;
	if (timeout_ms > 30000) timeout_ms = 30000;

	int private_cmd = !strcmp(cmd, "--sim-pin-stdin") || !strcmp(cmd, "--sim-puk-stdin");
	int ussd = !strcmp(cmd, "--ussd-stdin");
	int tx_length;
	if (ussd) {
		char input[40];
		size_t length = fread(input, 1, sizeof(input), stdin);
		if (ferror(stdin) || length < 4 || length > 33 || input[length-1] != '\n' ||
		    (input[0] != '*' && input[0] != '#') || input[length-2] != '#') return 2;
		input[--length] = '\0';
		if (strspn(input, "*#0123456789") != length || !strpbrk(input,"0123456789")) return 2;
		tx_length = snprintf(tx, sizeof(tx), "AT+CUSD=1,\"%s\",15\r", input);
	} else tx_length = private_cmd ? pin_command(cmd, tx, sizeof(tx)) :
		snprintf(tx, sizeof(tx), "%s\r", cmd);
	if (tx_length < 0 || (size_t)tx_length >= sizeof(tx)) return 2;

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

	if (write(fd, tx, (size_t)tx_length) != tx_length) { perror("write"); close(fd); return 3; }

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
				if (!private_cmd && !ussd) { fputs(buf, stdout); fflush(stdout); }
				for (ssize_t i = 0; i < n; i++) {
					if (buf[i] != '\r' && buf[i] != '\n') {
						if (used < sizeof(line) - 1)
							line[used++] = buf[i];
						else overflow = 1;
						continue;
					}
					line[used] = '\0';
					if (ussd && !strncmp(line, "+CUSD:", 6)) {
						if (overflow || response[0]) goto done;
						memcpy(response, line, used + 1);
					}
					if (!strcmp(line, "OK")) acknowledged = 1;
					if (acknowledged && (!ussd || response[0])) {
						if (ussd) puts(response);
						rc = 0;
						goto done;
					}
					if (!strcmp(line, "ERROR") || !strncmp(line, "+CME ERROR:", 11) ||
					    !strncmp(line, "+CMS ERROR:", 11))
						goto done;
					used = 0;
					overflow = 0;
				}
			}
		}
	}
done:
	close(fd);
	return rc;
}
