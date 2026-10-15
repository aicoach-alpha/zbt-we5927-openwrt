/*
 * VeCI XL CIAM: narrowly scoped interactive OTP transport (stage 1).
 * Ported only the two account-owner initiated BITS-XL CIAM operations.
 *
 * This is NOT a quota producer and never claims a carrier-authenticated
 * session until a subsequent profile validation confirms account identity.
 * No automatic SMS reading, API purchases, subscriptions or USSD.
 * All input is local in root-owned 0700 directory with regular 0600 files.
 * No phone/OTP/auth secrets in argv, environment, shell history or logs.
 */
#define _POSIX_C_SOURCE 200809L
#include <mbedtls/ssl.h>
#include <mbedtls/net_sockets.h>
#include <mbedtls/x509_crt.h>
#include <mbedtls/entropy.h>
#include <mbedtls/ctr_drbg.h>
#include <mbedtls/md.h>
#include <mbedtls/base64.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#ifndef O_NOFOLLOW
#error O_NOFOLLOW required
#endif
#define HOST "gede.ciam.xlaxiata.co.id"
#define CA "/etc/ssl/certs/ca-certificates.crt"
#define DIR "/tmp/veci-xl-ciam"
#define MAX_HTTP 24576
#define DEADLINE 25

static char request[8192], body[512], response[MAX_HTTP+1];
static char auth[512], ua[256], fingerprint[2048], device[80];
static char sigkey[128], number[24], otp[16], hsignature[128];

static void wipe(void *p,size_t n) {
 volatile unsigned char *b=p; while(n--)*b++=0;
}
static int private_dir(void){
 struct stat st;
 return lstat(DIR,&st)==0 && S_ISDIR(st.st_mode) &&
        st.st_uid==0 && (st.st_mode&0777)==0700;
}
static int read_local(const char *name,char *out,size_t capacity){
 char path[160];struct stat st;
 if(!private_dir())return -1;
 int n=snprintf(path,sizeof(path),DIR "/%s",name);
 if(n<1||(size_t)n>=sizeof(path))return -1;
 int fd=open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
 if(fd<0)return -1;
 if(fstat(fd,&st)!=0 || !S_ISREG(st.st_mode) || st.st_uid!=0 ||
    (st.st_mode&0777)!=0600 || st.st_nlink!=1 ||
    st.st_size<1 || st.st_size>=(off_t)capacity){close(fd);return -1;}
 size_t used=0;
 while(used<(size_t)st.st_size) {
  ssize_t k=read(fd,out+used,(size_t)st.st_size-used);
  if(k<=0){close(fd);return -1;}
  used+=(size_t)k;
 }
 close(fd);
 if(used && out[used-1]=='\n') used--;
 if(!used)return -1;
 for(size_t i=0;i<used;i++){
  if(out[i]=='\r'||out[i]=='\n'||out[i]==0)return -1;
 }
 out[used]=0;return (int)used;
}
static int visible_ascii(const char *p) {
 for(;*p;p++)if((unsigned char)*p<33||(unsigned char)*p>126)return 0;
 return 1;
}
static int digits(const char *p,size_t lo,size_t hi) {
 size_t n=strlen(p);
 if(n<lo||n>hi)return 0;
 for(size_t i=0;i<n;i++)if(!isdigit((unsigned char)p[i]))return 0;
 return 1;
}
static int valid_number(const char *p){
 size_t n=strlen(p);
 return n>=10&&n<=15 && p[0]=='6'&&p[1]=='2'&&digits(p,10,15);
}
static int date_gmt7(time_t when,int millis,char *dest,size_t cap){
 struct tm t;
 when+=7*3600;
 if(!gmtime_r(&when,&t))return -1;
 size_t n=strftime(dest,cap,"%Y-%m-%dT%H:%M:%S",&t);
 if(n==0 || n+9>=cap)return -1;
 return snprintf(dest+n,cap-n,".%03d+0700",millis)<0?-1:0;
}
static int signature(const char *stamp,const char *contact,const char *code) {
 char payload[220];int n=snprintf(payload,sizeof(payload),
      "%spasswordSMS%s%sopenid",stamp,contact,code);
 if(n<0 || (size_t)n>=sizeof(payload))return -1;
 const mbedtls_md_info_t *info=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
 if(!info)return -1;
 unsigned char digest[32];size_t used=0;int rc=-1;
 if(mbedtls_md_hmac(info,(const unsigned char*)sigkey,strlen(sigkey),
      (const unsigned char*)payload,(size_t)n,digest)!=0)goto done;
 if(mbedtls_base64_encode((unsigned char*)hsignature,sizeof(hsignature),
      &used,digest,sizeof(digest))!=0 || used>=sizeof(hsignature))goto done;
 hsignature[used]=0;rc=0;
done:
 wipe(payload,sizeof(payload));wipe(digest,sizeof(digest));
 return rc;
}
static int local_config(int submit){
 if(read_local("basic_auth",auth,sizeof(auth))<0 ||
    read_local("user_agent",ua,sizeof(ua))<0 ||
    read_local("fingerprint",fingerprint,sizeof(fingerprint))<0 ||
    read_local("device_id",device,sizeof(device))<0 ||
    read_local("number",number,sizeof(number))<0)return -1;
 if(!visible_ascii(auth)||!visible_ascii(ua)||!visible_ascii(fingerprint)||
    !visible_ascii(device)||!valid_number(number))return -1;
 if(submit) {
  if(read_local("ax_api_sig_key",sigkey,sizeof(sigkey))<0 ||
     read_local("otp",otp,sizeof(otp))<0)return -1;
  if(!visible_ascii(sigkey)||!digits(otp,4,8))return -1;
 }
 return 0;
}
static int make_request(int submit){
 struct timespec ts;
 if(clock_gettime(CLOCK_REALTIME,&ts)!=0)return -1;
 char signed_at[48], requested_at[48];
 if(date_gmt7(ts.tv_sec,ts.tv_nsec/1000000,signed_at,sizeof(signed_at))!=0 ||
    date_gmt7(ts.tv_sec-(submit?300:0),ts.tv_nsec/1000000,requested_at,sizeof(requested_at))!=0)
  return -1;
 char path[224];
 if(submit){
  if(signature(signed_at,number,otp)!=0)return -1;
  int bn=snprintf(body,sizeof(body),
    "contactType=SMS&code=%s&grant_type=password&contact=%s&scope=openid",
    otp,number);
  if(bn<=0||(size_t)bn>=sizeof(body))return -1;
  snprintf(path,sizeof(path),"/realms/xl-ciam/protocol/openid-connect/token");
 }else{
  int pn=snprintf(path,sizeof(path),
    "/realms/xl-ciam/auth/otp?contact=%s&contactType=SMS&alternateContact=false",number);
  if(pn<=0||(size_t)pn>=sizeof(path))return -1;
 }
 char optional[300]={0};
 if(submit){
  int hn=snprintf(optional,sizeof(optional),
    "Ax-Api-Signature: %s\r\nContent-Length: %zu\r\n",
    hsignature,strlen(body));
  if(hn<=0||(size_t)hn>=sizeof(optional))return -1;
 }
 int n=snprintf(request,sizeof(request),
  "%s %s HTTP/1.1\r\n"
  "Host: " HOST "\r\n"
  "Accept: application/json\r\n"
  "Accept-Encoding: identity\r\n"
  "Authorization: Basic %s\r\n"
  "Ax-Fingerprint: %s\r\n"
  "Ax-Device-Id: %s\r\n"
  "Ax-Request-At: %s\r\n"
  "Ax-Request-Device: samsung\r\n"
  "Ax-Request-Device-Model: SM-N935F\r\n"
  "Ax-Substype: PREPAID\r\n"
  "User-Agent: %s\r\n"
  "Content-Type: %s\r\n"
  "%s"
  "Connection: close\r\n"
  "Cache-Control: no-store\r\n\r\n"
  "%s",
  submit?"POST":"GET",path,auth,fingerprint,device,requested_at,ua,
  submit?"application/x-www-form-urlencoded":"application/json",
  optional,submit?body:"");
 if(n<0||(size_t)n>=sizeof(request))return -1;

 wipe(hsignature,sizeof(hsignature));wipe(body,sizeof(body));
 return 0;
}
static int status_code(const char *p){
 if(strncmp(p,"HTTP/1.1 ",9)&&strncmp(p,"HTTP/1.0 ",9))return -1;
 for(int i=9;i<12;i++)if(!isdigit((unsigned char)p[i]))return -1;
 if(p[12]!=' ')return -1;
 return (p[9]-'0')*100+(p[10]-'0')*10+p[11]-'0';
}
static int parse_reply(int submit,size_t n){
 response[n]=0;
 int code=status_code(response);
 if(code<200||code>=300)return -1;
 char *headers=strstr(response,"\r\n\r\n");
 if(!headers)return -1;
 size_t hdr_end=(size_t)(headers-response)+4;
 if(hdr_end>8192||hdr_end>=n)return -1;
 /* Header scan is bounded to actual headers. Never match body substrings. */
 int has_json=0, has_cl=0;size_t declared=0;
 char *line=strstr(response,"\r\n");
 if(!line || line>=headers)return -1;
 line+=2;
 while(line<headers){
  char *end=strstr(line,"\r\n");
  if(!end || end>headers)return -1;
  if(end==line)break;
  size_t m=(size_t)(end-line);
  if(m>256)return -1;
  if(m>=13 && !strncasecmp(line,"Content-Type:",13)){
   if(has_json)return -1;
   const char *v=line+13;
   while(v<end&&(*v==' '||*v=='\t'))v++;
   if((size_t)(end-v)<16||strncasecmp(v,"application/json",16))return -1;
   has_json=1;
  }
  if(m>=15 && !strncasecmp(line,"Content-Length:",15)){
   if(has_cl)return -1;
   char tmp[18];size_t k=0;
   const char *v=line+15;
   while(v<end&&(*v==' '||*v=='\t'))v++;
   while(v<end&&k<sizeof(tmp)-1&&isdigit((unsigned char)*v))
    tmp[k++]=*v++;
   if(!k||v!=end)return -1;
   tmp[k]=0;declared=(size_t)strtoul(tmp,NULL,10);
   has_cl=1;
  }
  if(m>=18 && !strncasecmp(line,"Transfer-Encoding:",18))return -1;
  if(m>=17 && !strncasecmp(line,"Content-Encoding:",17))return -1;
  line=end+2;
 }
 if(!has_json || !has_cl || declared!=n-hdr_end)return -1;
 const char *payload=response+hdr_end;
 if(payload[0]!='{'||payload[declared-1]!='}')return -1;
 if(submit){
  /* Token JSON never leaves the root-owned volatile directory. */
  char path[160],temp[168];struct stat st;
  snprintf(path,sizeof(path),DIR "/token-candidate.json");
  snprintf(temp,sizeof(temp),DIR "/.token.%ld",(long)getpid());
  int fd=open(temp,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
  if(fd<0)return -1;
  size_t off=0;
  while(off<declared){
   ssize_t k=write(fd,payload+off,declared-off);
   if(k<=0){close(fd);unlink(temp);return -1;}
   off+=(size_t)k;
  }
  if(fsync(fd)!=0){close(fd);unlink(temp);return -1;}
  close(fd);
  if(lstat(path,&st)==0 && (!S_ISREG(st.st_mode)||st.st_uid!=0 ||
       st.st_nlink!=1 || (st.st_mode&0777)!=0600)){unlink(temp);return -1;}
  if(rename(temp,path)!=0){unlink(temp);return -1;}
  /* Successful HTTP != validated identity/session; downstream must validate. */
  puts("VECI_XL_CIAM=token_candidate_received");
 }else puts("VECI_XL_CIAM=otp_request_accepted");
 return 0;
}

static int transport(int submit){
 mbedtls_net_context net;mbedtls_ssl_context ssl;mbedtls_ssl_config cfg;
 mbedtls_x509_crt ca;mbedtls_entropy_context entropy;mbedtls_ctr_drbg_context rng;
 int rc=-1,err;size_t got=0;const unsigned char p[]="veci-xl-ciam-otp-v1";
 mbedtls_net_init(&net);mbedtls_ssl_init(&ssl);mbedtls_ssl_config_init(&cfg);
 mbedtls_x509_crt_init(&ca);mbedtls_entropy_init(&entropy);mbedtls_ctr_drbg_init(&rng);
 if(mbedtls_ctr_drbg_seed(&rng,mbedtls_entropy_func,&entropy,p,sizeof(p)-1))goto finish;
 if(mbedtls_x509_crt_parse_file(&ca,CA))goto finish;
 if(mbedtls_ssl_config_defaults(&cfg,MBEDTLS_SSL_IS_CLIENT,
    MBEDTLS_SSL_TRANSPORT_STREAM,MBEDTLS_SSL_PRESET_DEFAULT))goto finish;
 mbedtls_ssl_conf_authmode(&cfg,MBEDTLS_SSL_VERIFY_REQUIRED);
 mbedtls_ssl_conf_ca_chain(&cfg,&ca,NULL);
 mbedtls_ssl_conf_rng(&cfg,mbedtls_ctr_drbg_random,&rng);
 mbedtls_ssl_conf_read_timeout(&cfg,5000);
 if(mbedtls_ssl_setup(&ssl,&cfg) ||
    mbedtls_ssl_set_hostname(&ssl,HOST) ||
    mbedtls_net_connect(&net,HOST,"443",MBEDTLS_NET_PROTO_TCP))goto finish;
 mbedtls_ssl_set_bio(&ssl,&net,mbedtls_net_send,mbedtls_net_recv,mbedtls_net_recv_timeout);
 do{err=mbedtls_ssl_handshake(&ssl);}
 while(err==MBEDTLS_ERR_SSL_WANT_READ||err==MBEDTLS_ERR_SSL_WANT_WRITE);
 if(err||mbedtls_ssl_get_verify_result(&ssl))goto finish;
 for(size_t sent=0,reqn=strlen(request);sent<reqn;){
  err=mbedtls_ssl_write(&ssl,(unsigned char*)request+sent,reqn-sent);
  if(err==MBEDTLS_ERR_SSL_WANT_READ||err==MBEDTLS_ERR_SSL_WANT_WRITE)continue;
  if(err<=0)goto finish;
  sent+=(size_t)err;
 }
 while(got<MAX_HTTP){
  err=mbedtls_ssl_read(&ssl,(unsigned char*)response+got,MAX_HTTP-got);
  if(err==MBEDTLS_ERR_SSL_WANT_READ||err==MBEDTLS_ERR_SSL_WANT_WRITE)continue;
  if(err==0||err==MBEDTLS_ERR_SSL_PEER_CLOSE_NOTIFY)break;
  if(err<0)goto finish;
  got+=(size_t)err;
 }
 if(got==MAX_HTTP||parse_reply(submit,got)!=0)goto finish;
 rc=0;
finish:
 mbedtls_ssl_free(&ssl);mbedtls_ssl_config_free(&cfg);
 mbedtls_x509_crt_free(&ca);mbedtls_ctr_drbg_free(&rng);
 mbedtls_entropy_free(&entropy);mbedtls_net_free(&net);
 return rc;
}
int main(int argc,char **argv){
 if(argc!=2 || (strcmp(argv[1],"request-otp") &&
                strcmp(argv[1],"submit-otp")))return 2;
 if(geteuid()!=0||isatty(STDOUT_FILENO))return 1;
 int submit=!strcmp(argv[1],"submit-otp"),rc=1;
 signal(SIGPIPE,SIG_IGN);
 if(local_config(submit)!=0){
  puts("VECI_XL_CIAM=not_configured");goto done;
 }
 if(make_request(submit)!=0){
  puts("VECI_XL_CIAM=invalid_request");goto done;
 }
 alarm(DEADLINE);
 if(transport(submit)==0)rc=0;
 else puts("VECI_XL_CIAM=operator_response_unavailable");
 alarm(0);
 /* Never retain a submitted OTP after an attempt. Other session files stay
    inside the owner's 0700 directory for the next explicit step. */
 if(submit) {
  char secret[160];
  if(snprintf(secret,sizeof(secret),DIR "/otp")<(int)sizeof(secret))
   unlink(secret);
 }
done:
 wipe(auth,sizeof(auth));wipe(ua,sizeof(ua));
 wipe(fingerprint,sizeof(fingerprint));wipe(device,sizeof(device));
 wipe(sigkey,sizeof(sigkey));wipe(number,sizeof(number));wipe(otp,sizeof(otp));
 wipe(hsignature,sizeof(hsignature));wipe(request,sizeof(request));
 wipe(body,sizeof(body));wipe(response,sizeof(response));
 return rc;
}
