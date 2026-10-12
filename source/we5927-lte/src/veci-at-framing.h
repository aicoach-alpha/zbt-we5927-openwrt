/* VeCI inert AT SMS PDU / USSD framing API. GPL-2.0-only. */
#ifndef VECI_AT_FRAMING_H
#define VECI_AT_FRAMING_H
#include <stddef.h>
#define VECI_FRAME_LINE_MAX 1024
#define VECI_FRAME_STREAM_MAX 8192
#define VECI_FRAME_PDU_MAX 512
enum veci_frame_event {
    VECI_FRAME_OTHER = 0,
    VECI_FRAME_OK = 1,
    VECI_FRAME_ERROR = 2,
    VECI_FRAME_SMS_PDU = 3,
    VECI_FRAME_SMS_NOTICE = 4,
    VECI_FRAME_USSD = 5,
    VECI_FRAME_PROTOCOL_ERROR = 6
};
struct veci_at_frame {
    char line[VECI_FRAME_LINE_MAX];
    size_t line_len, total;
    int pdu_expected, failed;
};
typedef void (*veci_frame_callback)(int event, const char *value,
                                    int metadata, void *ctx);
void veci_frame_init(struct veci_at_frame *f);
int veci_frame_feed(struct veci_at_frame *f, const unsigned char *buf,
                    size_t n, veci_frame_callback callback, void *ctx);
int veci_frame_finish(struct veci_at_frame *f,
                      veci_frame_callback callback, void *ctx);
enum veci_ussd_state {
    VECI_USSD_WAITING = 0, VECI_USSD_RESPONSE = 1,
    VECI_USSD_INTERACTIVE = 2, VECI_USSD_TERMINATED = 3,
    VECI_USSD_FAILED = 4
};
struct veci_ussd_session {
    int acked, seen_urc, mode, failed;
};
void veci_ussd_init(struct veci_ussd_session *s);
int veci_ussd_consume(struct veci_ussd_session *s, int event, int meta);
int veci_ussd_expire(struct veci_ussd_session *s);
#endif
