/*
 * VeCI WE5927 SMS-SUBMIT one-shot AT+CMGS transport.
 *
 * SOURCE-ONLY until cross-compiled and explicitly installed. Input is ONE
 * bounded GSM7 or UCS2 SMS-SUBMIT PDU hexadecimal line on stdin. The CLI
 * NEVER prints the PDU/recipient/text (including on error).
 *
 * Output is one fixed schema JSON status. If the modem's final response
 * is lost after Ctrl-Z, the result is outcome_unknown; never auto-retry.
 * Serial device is protected by the existing WE5927 modem lock at caller.
 */
#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <ctype.h>
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

#define MAX_BYTES 192
#define MAX_HEX (MAX_BYTES * 2)
#define REPLY_MAX 2048

static long long monotonic_ms(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts)) return -1;
    return (long long)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

static int parse_hex(unsigned char b[MAX_BYTES], size_t *total) {
    char hex[MAX_HEX+3]={0};
    size_t i, n;
    if (!fgets(hex, sizeof hex, stdin)) return -1;
    n=strcspn(hex,"\r\n");
    if (n<22 || n>MAX_HEX || n%2) return -1;
    if (hex[n]!='\n' && hex[n]!='\r' && hex[n]!='\0') return -1;
    for (i=0; i<n; i+=2) {
        int hi,lo;
        char a=hex[i],c=hex[i+1];
        if (!isxdigit((unsigned char)a)||!isxdigit((unsigned char)c))return -1;
        hi=(a>='0'&&a<='9')?a-'0':(a>='A'&&a<='F')?a-'A'+10:a-'a'+10;
        lo=(c>='0'&&c<='9')?c-'0':(c>='A'&&c<='F')?c-'A'+10:c-'a'+10;
        b[i/2]=(unsigned char)((hi<<4)|lo);
    }
    *total=n/2;
    memset(hex,0,sizeof hex);
    return 0;
}

/* TPDU is SMS-SUBMIT without user data headers or validity period. */
static int valid_submit(const unsigned char *b, size_t n, int *tpdu_len) {
    size_t i,addr_count,ud_start,payload;
    unsigned char dcs,udl,toa;
    if(n<12 || n>MAX_BYTES || b[0]!=0x00 || b[1]!=0x01 || b[2]!=0x00)
        return 0;
    addr_count=b[3];
    toa=b[4];
    if(addr_count<3 || addr_count>15 || (toa!=0x81 && toa!=0x91))return 0;
    ud_start=5+(addr_count+1)/2;
    if(ud_start+3>n)return 0;
    for(i=0;i<(addr_count+1)/2;i++){
        unsigned x=b[5+i],low=x&15,high=x>>4;
        if(low>9) return 0;
        if(i*2+1<addr_count){if(high>9)return 0;}
        else if(high!=0x0f)return 0;
    }
    if(b[ud_start]!=0x00)return 0; /* PID */
    dcs=b[ud_start+1];
    udl=b[ud_start+2];
    payload=n-(ud_start+3);
    if(dcs==0x00){
        if(udl<1||udl>160||payload!=(udl*7+7)/8) return 0;
    }else if(dcs==0x08){
        if(udl<2||udl>140||udl%2||payload!=udl)return 0;
    }else return 0;
    if(n-1>190)return 0;
    *tpdu_len=(int)n-1;
    return 1;
}
static int put_all(int fd,const void *buf,size_t n,long long deadline) {
    size_t done=0;const unsigned char *p=buf;
    while(done<n){
        long long now=monotonic_ms();
        if(now<0||now>=deadline)return -1;
        struct pollfd item={.fd=fd,.events=POLLOUT};
        int timeout=(int)(deadline-now);
        if(timeout>300)timeout=300;
        int polled=poll(&item,1,timeout);
        if(polled<=0){if(polled<0&&errno!=EINTR)return -1;continue;}
        if(item.revents&(POLLERR|POLLHUP|POLLNVAL))return -1;
        ssize_t m=write(fd,p+done,n-done);
        if(m>0){done+=(size_t)m;continue;}
        if(m<0&&(errno==EINTR||errno==EAGAIN))continue;
        return -1;
    }
    return 0;
}
static int read_phase(int fd,int prompt_phase,long long deadline){
    char line[256];size_t linelen=0;
    int mr=0;unsigned bytes=0;
    for(;;){
        long long now=monotonic_ms();
        if(now<0||now>=deadline)return -1;
        struct pollfd item={.fd=fd,.events=POLLIN};
        int timeout=(int)(deadline-now);
        if(timeout>350)timeout=350;
        int polled=poll(&item,1,timeout);
        if(polled<=0){if(polled<0&&errno!=EINTR)return -1;continue;}
        if(item.revents&(POLLERR|POLLHUP|POLLNVAL))return -1;
        unsigned char buf[128];
        ssize_t n=read(fd,buf,sizeof buf);
        if(n<0&&(errno==EINTR||errno==EAGAIN))continue;
        if(n<=0)return -1;
        for(ssize_t i=0;i<n;i++){
            unsigned char c=buf[i];
            if(++bytes>REPLY_MAX)return -1;
            if(prompt_phase && c=='>')return 1;
            if(c=='\r'||c=='\n'){
                if(linelen){
                    line[linelen]='\0';
                    if(!strcmp(line,"ERROR") || !strncmp(line,"+CMS ERROR:",11) ||
                       !strncmp(line,"+CME ERROR:",11))return 0;
                    if(!prompt_phase){
                        if(!strncmp(line,"+CMGS:",6)){
                            char *p=line+6,*end;
                            long v;
                            while(*p==' ')p++;
                            errno=0;v=strtol(p,&end,10);
                            if(!errno&&p!=end&&v>=0&&v<=255){
                                while(*end==' ')end++;
                                if(!*end)mr=1;
                            }
                        }
                        if(!strcmp(line,"OK") && mr)return 1;
                        if(!strcmp(line,"OK") && !mr)return 0;
                    }
                    linelen=0;
                }
            }else{
                if(c<32 || c>126){if(c!='\t')continue;}
                if(linelen+1>=sizeof line)return -1;
                line[linelen++]=(char)c;
            }
        }
    }
}
int main(int argc,char **argv){
    unsigned char data[MAX_BYTES]={0};
    size_t n=0;int len=0,fd=-1,rc=1,phase;
    struct termios tty,old;
    char command[32],hex[MAX_HEX+1];
    long long deadline;
    if(argc!=2 || parse_hex(data,&n) || !valid_submit(data,n,&len)){
        puts("{\"ok\":false,\"reason\":\"invalid_submit\"}");
        goto done;
    }
    if(strcmp(argv[1],"/dev/ttyUSB2") && strncmp(argv[1],"/dev/pts/",9)){
        puts("{\"ok\":false,\"reason\":\"invalid_device\"}");
        goto done;
    }
    fd=open(argv[1],O_RDWR|O_NOCTTY|O_NONBLOCK|O_CLOEXEC);
    if(fd<0 || tcgetattr(fd,&old)){
        puts("{\"ok\":false,\"reason\":\"serial_unavailable\"}");
        goto done;
    }
    tty=old;
    cfmakeraw(&tty);cfsetispeed(&tty,B115200);cfsetospeed(&tty,B115200);
    tty.c_cflag|=CLOCAL|CREAD;tty.c_cflag&=~CRTSCTS;
    tty.c_cc[VMIN]=0;tty.c_cc[VTIME]=0;
    if(tcsetattr(fd,TCSANOW,&tty)){
        puts("{\"ok\":false,\"reason\":\"serial_unavailable\"}");
        goto done;
    }
    /* No modem state change except one explicit message transaction. */
    tcflush(fd,TCIFLUSH);
    snprintf(command,sizeof command,"AT+CMGS=%d\r",len);
    deadline=monotonic_ms()+5000;
    if(put_all(fd,command,strlen(command),deadline) ||
       (phase=read_phase(fd,1,deadline))!=1){
        puts("{\"ok\":false,\"reason\":\"prompt_unavailable\"}");
        goto done;
    }
    for(size_t i=0;i<n;i++)snprintf(hex+i*2,3,"%02X",data[i]);
    hex[n*2]='\032';  /* Ctrl-Z starts GSM network transmission. */
    deadline=monotonic_ms()+5000;
    if(put_all(fd,hex,n*2+1,deadline)){
        puts("{\"ok\":false,\"reason\":\"outcome_unknown\"}");
        goto done;
    }
    deadline=monotonic_ms()+35000;
    phase=read_phase(fd,0,deadline);
    if(phase==1){puts("{\"ok\":true,\"status\":\"accepted_by_modem\"}");rc=0;}
    else if(phase==0)puts("{\"ok\":false,\"reason\":\"network_rejected\"}");
    else puts("{\"ok\":false,\"reason\":\"outcome_unknown\"}");
done:
    memset(data,0,sizeof data);
    memset(hex,0,sizeof hex);
    if(fd>=0){tcsetattr(fd,TCSANOW,&old);close(fd);}
    return rc;
}
