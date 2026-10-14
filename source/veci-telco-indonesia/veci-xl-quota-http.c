/*
 * VeCI Indonesia — candidate myXL read-only quota HTTPS transport.
 *
 * Designed only for credentials that a user is independently authorized to
 * provision. This code DOES NOT log in, request OTP, forge app identities,
 * harvest SMS, or claim quota data is authenticated.
 *
 * To avoid argv/env/history disclosure, every request credential is loaded
 * from a 0700 root-owned directory of 0600 regular files in volatile /tmp.
 * Output is permitted only into a pipe/file, never an interactive terminal.
 * Network destination and method/path are compile-time fixed.
 *
 * Do not install into production before real operator authorization and
 * response format have been validated on hardware. Missing credential files
 * means fail-closed and NO network request.
 */
#define _POSIX_C_SOURCE 200809L
#include <mbedtls/ssl.h>
#include <mbedtls/net_sockets.h>
#include <mbedtls/x509_crt.h>
#include <mbedtls/entropy.h>
#include <mbedtls/ctr_drbg.h>
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
#error "O_NOFOLLOW is required to safely read private session files"
#endif

#define HOST "api.myxl.xlaxiata.co.id"
#define ROUTE "/api/v8/packages/quota-details"
#define CA "/etc/ssl/certs/ca-certificates.crt"
#define PRIVATE "/tmp/veci-telco-private"
#define MAX_BODY 4096
#define MAX_WIRE 73728
#define MAX_OUT 65536
#define TIMEOUT_SEC 30

static unsigned char token[3074], api_key[258], signature[130], sig_time[12];
static unsigned char request_body[MAX_BODY+2], headers[8192];
static unsigned char wire[MAX_WIRE+1], normalized[MAX_OUT+1];

static void wipe(void *p,size_t n){
 volatile unsigned char *q=(volatile unsigned char*)p;
 while(n--)*q++=0;
}
static void failure(const char *reason){
 fprintf(stderr,"VECI_XL_HTTP_ERROR=%s\n",reason);
}
static int private_directory(void){
 struct stat st;
 if(lstat(PRIVATE,&st)!=0 || !S_ISDIR(st.st_mode))return -1;
 if(st.st_uid!=0 || (st.st_mode&0777)!=0700)return -1;
 return 0;
}
static int private_file(const char *name,unsigned char *buf,size_t cap,size_t *used){
 char path[160];
 if(private_directory()!=0)return -1;
 int n=snprintf(path,sizeof(path),"%s/%s",PRIVATE,name);
 if(n<=0||(size_t)n>=sizeof(path))return -1;
 int fd=open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
 if(fd<0)return -1;
 struct stat st;
 if(fstat(fd,&st)!=0||!S_ISREG(st.st_mode)||st.st_uid!=0||
    (st.st_mode&0777)!=0600||st.st_nlink!=1||
    st.st_size<=0||st.st_size>(off_t)cap){close(fd);return -1;}
 size_t off=0;
 while(off<(size_t)st.st_size){
  ssize_t k=read(fd,buf+off,(size_t)st.st_size-off);
  if(k<=0){close(fd);return -1;}
  off+=(size_t)k;
 }
 close(fd);
 /* One trailing shell-created newline is permitted for TEXT files. */
 if(strcmp(name,"body.json")!=0&&off&&buf[off-1]=='\n')off--;
 if(!off)return -1;
 buf[off]=0;*used=off;
 return 0;
}
static int header_value(const unsigned char *s,size_t n){
 if(!n)return 0;
 for(size_t i=0;i<n;i++)if(s[i]<33||s[i]>126)return 0;
 return 1;
}
static int numeric(const unsigned char *s,size_t n){
 if(n!=10)return 0;
 for(size_t i=0;i<n;i++)if(!isdigit(s[i]))return 0;
 return 1;
}
static int load_request(size_t *bodylen){
 size_t a,b,c,d;
 if(private_file("id_token",token,sizeof(token)-2,&a) ||
    private_file("api_key",api_key,sizeof(api_key)-2,&b) ||
    private_file("signature",signature,sizeof(signature)-2,&c) ||
    private_file("signature_time",sig_time,sizeof(sig_time)-2,&d) ||
    private_file("body.json",request_body,MAX_BODY,bodylen))return -1;
 if(!header_value(token,a)||!header_value(api_key,b)||
    !header_value(signature,c)||c!=128||!numeric(sig_time,d))return -1;
 for(size_t i=0;i<c;i++)if(!isxdigit(signature[i]))return -1;
 /* Signature must be fresh; require synchronized clock. */
 unsigned long long timestamp=strtoull((const char *)sig_time,NULL,10);
 time_t now=time(NULL);
 if(now<0||timestamp>(unsigned long long)now+120 ||
    (unsigned long long)now>timestamp+120)return -1;
 /* Local encrypted xdata request: reject arbitrary commands/paths. */
 if(*bodylen<20||request_body[0]!='{'||
    !strstr((const char *)request_body,"\"xdata\"")||
    !strstr((const char *)request_body,"\"xtime\""))return -1;
 for(size_t i=0;i<*bodylen;i++)if(request_body[i]==0)return -1;
 int n=snprintf((char *)headers,sizeof(headers),
   "POST " ROUTE " HTTP/1.1\r\n"
   "Host: " HOST "\r\n"
   "User-Agent: VeCI-Indonesia/0.1\r\n"
   "Content-Type: application/json; charset=utf-8\r\n"
   "Accept: application/json\r\n"
   "Accept-Encoding: identity\r\n"
   "Authorization: Bearer %s\r\n"
   "x-api-key: %s\r\n"
   "x-signature-time: %s\r\n"
   "x-signature: %s\r\n"
   "x-hv: v3\r\n"
   "Content-Length: %zu\r\n"
   "Connection: close\r\n\r\n",
   token,api_key,sig_time,signature,*bodylen);
 return n>0&&(size_t)n<sizeof(headers)?n:-1;
}
static int read_http_status(const unsigned char *s,size_t n){
 if(n<13 || (memcmp(s,"HTTP/1.1 ",9)!=0&&memcmp(s,"HTTP/1.0 ",9)!=0))return -1;
 if(!isdigit(s[9])||!isdigit(s[10])||!isdigit(s[11])||s[12]!=' ')return -1;
 return (s[9]-'0')*100+(s[10]-'0')*10+s[11]-'0';
}
static int digit_hex(unsigned char c){
 if(c>='0'&&c<='9')return c-'0';
 if(c>='a'&&c<='f')return c-'a'+10;
 if(c>='A'&&c<='F')return c-'A'+10;
 return -1;
}
static int unpack_chunked(const unsigned char *s,size_t n,size_t *out){
 size_t at=0,used=0;
 for(;;){
  size_t start=at;
  while(at+1<n && !(s[at]=='\r'&&s[at+1]=='\n')&&at-start<16)at++;
  if(at+1>=n||at-start==0||at-start>8||s[at]!='\r'||s[at+1]!='\n')return -1;
  size_t chunk=0;
  for(size_t i=start;i<at;i++){
   int hex=digit_hex(s[i]);
   if(hex<0)return -1;
   chunk=chunk*16+(size_t)hex;
  }
  at+=2;
  if(chunk>MAX_OUT-used||chunk>n-at)return -1;
  if(chunk){memcpy(normalized+used,s+at,chunk);used+=chunk;}
  at+=chunk;
  if(at+1>=n||s[at]!='\r'||s[at+1]!='\n')return -1;
  at+=2;
  if(chunk==0){
   /* No trailers except one mandatory terminating CRLF. */
   if(at!=n)return -1;
   *out=used;
   return 0;
  }
 }
}
static int parse_response(size_t size,size_t *result){
 size_t sep=0;
 while(sep+3<size&&!(wire[sep]=='\r'&&wire[sep+1]=='\n'&&
                     wire[sep+2]=='\r'&&wire[sep+3]=='\n'))sep++;
 if(sep+3>=size||sep>8192)return -1;
 int status=read_http_status(wire,size);
 if(status<200||status>=300){
  fprintf(stderr,"VECI_XL_HTTP_STATUS=%d\n",status);
  return -1;
 }
 size_t headerlen=sep+4,bodylen=size-headerlen;
 int chunked=0,has_cl=0;
 size_t content_length=0;
 /* Parse complete HTTP headers without ever logging their values. */
 size_t at=0;
 while(at+1<sep&&!(wire[at]=='\r'&&wire[at+1]=='\n'))at++;
 if(at+1>=sep)return -1;
 at+=2;
 while(at<sep){
  size_t end=at;
  while(end+1<sep&&!(wire[end]=='\r'&&wire[end+1]=='\n'))end++;
  if(end+1>=sep)return -1;
  size_t colon=at;
  while(colon<end&&wire[colon]!=':')colon++;
  if(colon==end)return -1;
  const unsigned char *v=wire+colon+1;
  size_t vlen=end-colon-1;
  while(vlen && (*v==' '||*v=='\t')){v++;vlen--;}
  size_t klen=colon-at;
  if(klen==14&&!strncasecmp((const char*)wire+at,"content-length",14)){
   if(has_cl||vlen==0||vlen>6)return -1;
   for(size_t i=0;i<vlen;i++){
    if(!isdigit(v[i]))return -1;
    content_length=content_length*10+(size_t)(v[i]-'0');
   }
   has_cl=1;
  }else if(klen==17&&!strncasecmp((const char*)wire+at,"transfer-encoding",17)){
   if(chunked||vlen!=7||strncasecmp((const char*)v,"chunked",7))return -1;
   chunked=1;
  }else if(klen==16&&!strncasecmp((const char*)wire+at,"content-encoding",16)){
   if(vlen!=8||strncasecmp((const char*)v,"identity",8))return -1;
  }
  at=end+2;
 }
 if(chunked&&has_cl)return -1;
 if(chunked){
  if(unpack_chunked(wire+headerlen,bodylen,result)!=0)return -1;
 }else{
  if(has_cl&&content_length!=bodylen)return -1;
  if(bodylen>MAX_OUT)return -1;
  memcpy(normalized,wire+headerlen,bodylen);
  *result=bodylen;
 }
 /* A successful HTTP status alone does NOT prove quota information. */
 if(*result<2||normalized[0]!='{'||normalized[*result-1]!='}')return -1;
 return 0;
}
static int request_network(int n,size_t bodylen){
 mbedtls_net_context net;mbedtls_ssl_context ssl;mbedtls_ssl_config cfg;
 mbedtls_x509_crt ca;mbedtls_entropy_context entropy;mbedtls_ctr_drbg_context rng;
 int success=0,rc=0;size_t received=0,result=0;
 mbedtls_net_init(&net);mbedtls_ssl_init(&ssl);mbedtls_ssl_config_init(&cfg);
 mbedtls_x509_crt_init(&ca);mbedtls_entropy_init(&entropy);mbedtls_ctr_drbg_init(&rng);
 const unsigned char p[]="veci-xl-quota-readonly";
 if(mbedtls_ctr_drbg_seed(&rng,mbedtls_entropy_func,&entropy,p,sizeof(p)-1)!=0)goto finish;
 if(mbedtls_x509_crt_parse_file(&ca,CA)!=0)goto finish;
 if(mbedtls_ssl_config_defaults(&cfg,MBEDTLS_SSL_IS_CLIENT,
       MBEDTLS_SSL_TRANSPORT_STREAM,MBEDTLS_SSL_PRESET_DEFAULT)!=0)goto finish;
 mbedtls_ssl_conf_authmode(&cfg,MBEDTLS_SSL_VERIFY_REQUIRED);
 mbedtls_ssl_conf_ca_chain(&cfg,&ca,NULL);
 mbedtls_ssl_conf_rng(&cfg,mbedtls_ctr_drbg_random,&rng);
 mbedtls_ssl_conf_read_timeout(&cfg,7000);
 if(mbedtls_ssl_setup(&ssl,&cfg)!=0)goto finish;
 if(mbedtls_ssl_set_hostname(&ssl,HOST)!=0)goto finish;
 if(mbedtls_net_connect(&net,HOST,"443",MBEDTLS_NET_PROTO_TCP)!=0)goto finish;
 mbedtls_ssl_set_bio(&ssl,&net,mbedtls_net_send,mbedtls_net_recv,mbedtls_net_recv_timeout);
 do{rc=mbedtls_ssl_handshake(&ssl);}
 while(rc==MBEDTLS_ERR_SSL_WANT_READ||rc==MBEDTLS_ERR_SSL_WANT_WRITE);
 if(rc!=0||mbedtls_ssl_get_verify_result(&ssl)!=0)goto finish;
 const unsigned char *parts[]={headers,request_body};
 size_t sizes[]={(size_t)n,bodylen};
 for(int part=0;part<2;part++){
  for(size_t off=0;off<sizes[part];){
   rc=mbedtls_ssl_write(&ssl,parts[part]+off,sizes[part]-off);
   if(rc==MBEDTLS_ERR_SSL_WANT_READ||rc==MBEDTLS_ERR_SSL_WANT_WRITE)continue;
   if(rc<=0)goto finish;
   off+=(size_t)rc;
  }
 }
 while(received<MAX_WIRE){
  rc=mbedtls_ssl_read(&ssl,wire+received,MAX_WIRE-received);
  if(rc==MBEDTLS_ERR_SSL_WANT_READ||rc==MBEDTLS_ERR_SSL_WANT_WRITE)continue;
  if(rc==0||rc==MBEDTLS_ERR_SSL_PEER_CLOSE_NOTIFY)break;
  if(rc<0)goto finish;
  received+=(size_t)rc;
 }
 if(received==MAX_WIRE)goto finish;
 if(parse_response(received,&result)!=0)goto finish;
 if(fwrite(normalized,1,result,stdout)!=result)goto finish;
 success=1;
finish:
 mbedtls_ssl_free(&ssl);mbedtls_ssl_config_free(&cfg);mbedtls_x509_crt_free(&ca);
 mbedtls_ctr_drbg_free(&rng);mbedtls_entropy_free(&entropy);mbedtls_net_free(&net);
 if(!success)failure("verified_operator_response_unavailable");
 return success?0:1;
}
int main(int argc,char **argv){
 if(argc!=2||strcmp(argv[1],"quota")!=0){
  fputs("usage: veci-xl-quota-http quota\n",stderr);return 2;
 }
 if(geteuid()!=0){failure("root_required");return 1;}
 if(isatty(STDOUT_FILENO)){failure("pipe_required");return 1;}
 signal(SIGPIPE,SIG_IGN);
 size_t bodylen=0;
 int n=load_request(&bodylen);
 if(n<=0){failure("authorized_session_not_configured");return 1;}
 alarm(TIMEOUT_SEC);
 int rc=request_network(n,bodylen);
 alarm(0);
 wipe(token,sizeof(token));wipe(api_key,sizeof(api_key));
 wipe(signature,sizeof(signature));wipe(sig_time,sizeof(sig_time));
 wipe(request_body,sizeof(request_body));wipe(headers,sizeof(headers));
 wipe(wire,sizeof(wire));wipe(normalized,sizeof(normalized));
 return rc;
}
