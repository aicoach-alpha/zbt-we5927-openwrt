/*
 * VeCI WE5927 generic user-initiated USSD dial transaction.
 * Only callable by a separately authenticated/allowlisted wrapper.
 * One AT+CUSD request; waits for async +CUSD, not merely final OK.
 * No daemon, no SMS, no token logging, no modem configuration changes.
 * Caller owns /var/lock/we5927-at.lock for the full operation.
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

#define MAX_LINE 1120
#define MAX_TEXT 768
static int64_t ticks(void) {
 struct timespec t; if(clock_gettime(CLOCK_MONOTONIC,&t))return -1;
 return (int64_t)t.tv_sec*1000+t.tv_nsec/1000000;
}
static int fail(const char *s) {
 printf("{\"ok\":false,\"reason\":\"%s\"}\n",s);return 1;
}
static int write_all(int fd,const char *s,size_t n,int64_t end){
 size_t done=0;
 while(done<n && ticks()>=0 && ticks()<end){
  struct pollfd p={.fd=fd,.events=POLLOUT};int t=(int)(end-ticks());
  if(t>250)t=250;
  int rc=poll(&p,1,t);
  if(rc<0 && errno==EINTR)continue;
  if(rc<0 || (p.revents&(POLLERR|POLLHUP|POLLNVAL)))return -1;
  if(rc==0)continue;
  ssize_t m=write(fd,s+done,n-done);
  if(m<0 && (errno==EINTR||errno==EAGAIN))continue;
  if(m<=0)return -1;
  done+=(size_t)m;
 }
 return done==n?0:-1;
}
static int hexval(char c){
 if(c>='0'&&c<='9')return c-'0';
 if(c>='A'&&c<='F')return c-'A'+10;
 if(c>='a'&&c<='f')return c-'a'+10;
 return -1;
}
static int append_cp(char *out,size_t *used,unsigned cp){
 unsigned char a[4];size_t n;
 if(cp<0x20 || cp==0x7f || cp>0x10ffff || (cp>=0xd800&&cp<=0xdfff))return -1;
 if(cp<0x80){a[0]=(unsigned char)cp;n=1;}
 else if(cp<0x800){a[0]=0xc0|(cp>>6);a[1]=0x80|(cp&63);n=2;}
 else if(cp<0x10000){a[0]=0xe0|(cp>>12);a[1]=0x80|((cp>>6)&63);a[2]=0x80|(cp&63);n=3;}
 else {a[0]=0xf0|(cp>>18);a[1]=0x80|((cp>>12)&63);a[2]=0x80|((cp>>6)&63);a[3]=0x80|(cp&63);n=4;}
 if(*used+n>=MAX_TEXT)return -1;
 memcpy(out+*used,a,n);*used+=n;out[*used]=0;return 0;
}
static int parse_urc(const char *s,int *mode,int *dcs,char out[MAX_TEXT],int *supported){
 const char *p=s,*q;int v=0,seen=0;
 if(strncmp(p,"+CUSD:",6))return -1;
 p+=6;while(*p==' ')p++;
 if(*p<'0'||*p>'5')return -1;
 *mode=*p++-'0';while(*p==' ')p++;
 *dcs=-1;*supported=0;out[0]=0;
 if(!*p){*supported=1;return 0;}
 if(*p++!=',')return -1;
 while(*p==' ')p++;
 if(*p++!='"')return -1;
 q=p;while(*q && *q!='"'){if((unsigned char)*q<32||q-p>MAX_TEXT) return -1;q++;}
 if(*q!='"')return -1;
 size_t len=(size_t)(q-p);p=q+1;
 while(*p==' ')p++;
 if(*p++!=',')return -1;
 while(*p==' ')p++;
 if(*p<'0'||*p>'9')return -1;
 while(*p>='0'&&*p<='9'){if(++seen>3)return -1;v=v*10+(*p++-'0');}
 while(*p==' ')p++;
 if(*p || v>255)return -1;
 *dcs=v;size_t used=0;
 if(v==15 || v==0){
  /* Modem-provided printable GSM text, NOT arbitrary hex-decoding. */
  if(len>=MAX_TEXT)return -1;
  for(size_t i=0;i<len;i++){
   unsigned char ch=(unsigned char)q[-(int)(len-i)];
   if(ch<32||ch>126)return -1;
  }
  memcpy(out,q-len,len);out[len]=0;*supported=1;return 0;
 }
 if(v!=72 && v!=8)return 0;
 if(len%4!=0)return -1;
 const char *h=q-len;
 for(size_t i=0;i<len;i+=4){
  int a=hexval(h[i]),b=hexval(h[i+1]),c=hexval(h[i+2]),d=hexval(h[i+3]);
  if(a<0||b<0||c<0||d<0)return -1;
  unsigned cp=(unsigned)((a<<12)|(b<<8)|(c<<4)|d);
  if(cp>=0xd800&&cp<=0xdbff){
   if(i+7>=len)return -1;
   a=hexval(h[i+4]);b=hexval(h[i+5]);c=hexval(h[i+6]);d=hexval(h[i+7]);
   if(a<0||b<0||c<0||d<0)return -1;
   unsigned lo=(unsigned)((a<<12)|(b<<8)|(c<<4)|d);
   if(lo<0xdc00||lo>0xdfff)return -1;
   cp=0x10000+((cp-0xd800)<<10)+(lo-0xdc00);i+=4;
  }
  if(append_cp(out,&used,cp))return -1;
 }
 *supported=1;return 0;
}
static void print_json(const char *s){
 putchar('"');
 for(const unsigned char *p=(const unsigned char *)s;*p;p++){
  if(*p=='"'||*p=='\\'){putchar('\\');putchar(*p);}
  else if(*p=='\n')fputs("\\n",stdout);
  else if(*p<32)printf("\\u%04X",*p);
  else putchar(*p);
 }
 putchar('"');
}
int main(int argc,char **argv){
 int fd=-1,rc=1,ack=0,has=0,mode=0,dcs=-1,supported=0;
 struct termios old,now;int tty_set=0;
 char command[96],line[MAX_LINE]={0},body[MAX_TEXT]={0};
 size_t used=0;int64_t end;int count=0;
 if(argc!=3)return fail("invalid_request");
 if(strcmp(argv[1],"/dev/ttyUSB2") && strncmp(argv[1],"/dev/pts/",9))
   return fail("invalid_device");
 /* Only USSD short codes or numeric menu replies, never raw AT syntax.
  * Allow user-entered *123#, #21#, *808*7*3# but not shell/AT quotes,
  * CR/LF, unicode, spaces, semicolons, or uncontrolled string lengths. */
 size_t dial_len=strlen(argv[2]);
 int is_code=(argv[2][0]=='*'||argv[2][0]=='#');
 if(is_code){
  if(dial_len<3||dial_len>32||argv[2][dial_len-1]!='#')
   return fail("invalid_dial");
  for(size_t i=1;i<dial_len;i++)
   if(!isdigit((unsigned char)argv[2][i])&&argv[2][i]!='*'&&argv[2][i]!='#')
    return fail("invalid_dial");
 }else{
  if(dial_len<1||dial_len>2||(dial_len==2&&argv[2][0]=='0'))
   return fail("invalid_choice");
  for(size_t i=0;i<dial_len;i++)
   if(!isdigit((unsigned char)argv[2][i]))return fail("invalid_choice");
 }
 if(snprintf(command,sizeof command,"AT+CUSD=1,\"%s\",15\r",argv[2]) >= (int)sizeof command)
  return fail("invalid_request");
 fd=open(argv[1],O_RDWR|O_NOCTTY|O_NONBLOCK|O_CLOEXEC);
 if(fd<0||tcgetattr(fd,&old)){rc=fail("serial_unavailable");goto done;}
 now=old;cfmakeraw(&now);cfsetispeed(&now,B115200);cfsetospeed(&now,B115200);
 now.c_cflag|=CLOCAL|CREAD;now.c_cflag&=~CRTSCTS;
 now.c_cc[VMIN]=0;now.c_cc[VTIME]=0;
 if(tcsetattr(fd,TCSANOW,&now)){rc=fail("serial_unavailable");goto done;}
 tty_set=1;
 /* Existing transaction boundary: do not flush after sending command. */
 if(write_all(fd,command,strlen(command),ticks()+5000)){
  rc=fail("outcome_unknown");goto done;
 }
 end=ticks()+30000;
 while(ticks()>=0 && ticks()<end){
  struct pollfd p={.fd=fd,.events=POLLIN};int wait=(int)(end-ticks());
  if(wait>300)wait=300;
  int polled=poll(&p,1,wait);
  if(polled<0&&errno==EINTR)continue;
  if(polled<0||(p.revents&(POLLERR|POLLHUP|POLLNVAL)))break;
  if(polled<=0)continue;
  unsigned char buf[128];ssize_t n=read(fd,buf,sizeof buf);
  if(n<0&&(errno==EAGAIN||errno==EINTR))continue;
  if(n<=0)break;
  for(ssize_t i=0;i<n;i++){
   unsigned char c=buf[i];
   if(++count>4096)goto outcome_unknown;
   if(c=='\r'||c=='\n'){
    if(!used)continue;
    line[used]=0;used=0;
    if(!strcmp(line,"OK"))ack=1;
    else if(!strcmp(line,"ERROR")||!strncmp(line,"+CME ERROR:",11)||
            !strncmp(line,"+CMS ERROR:",11)){rc=fail("network_rejected");goto done;}
    else if(!strncmp(line,"+CUSD:",6)){
      if(has||parse_urc(line,&mode,&dcs,body,&supported)){
       rc=fail("invalid_response");goto done;
      }
      has=1;
    }
    else if(!strncmp(line,"AT+CUSD=",8)){} /* modem echo */
    else {} /* unrelated URC ignored; never logged */
    if(has&&ack){
      printf("{\"ok\":true,\"source\":\"operator_ussd\",\"mode\":%d,\"dcs\":%d,\"text_supported\":%s,\"interactive\":%s,\"text\":",
       mode,dcs,supported?"true":"false",mode==1?"true":"false");
      print_json(supported?body:"");puts("}");
      rc=0;goto done;
    }
   }else{
    if(c<32||c>126||used+1>=sizeof line){rc=fail("invalid_response");goto done;}
    line[used++]=(char)c;
   }
  }
 }
outcome_unknown:
 rc=fail("outcome_unknown");
done:
 memset(body,0,sizeof body);memset(line,0,sizeof line);memset(command,0,sizeof command);
 if(fd>=0){if(tty_set)tcsetattr(fd,TCSANOW,&old);close(fd);}
 return rc;
}
