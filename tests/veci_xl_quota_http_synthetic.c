/* Offline synthetic HTTP framing checks; no network, account or secrets. */
#define main veci_xl_http_original_main
#include "../source/veci-telco-indonesia/veci-xl-quota-http.c"
#undef main
static int check(const char *raw,int expected){
 size_t n=strlen(raw),out=0;
 if(n>=sizeof(wire))return 2;
 memset(wire,0,sizeof(wire));
 memcpy(wire,raw,n);
 int valid=parse_response(n,&out)==0;
 if(valid!=expected)return 1;
 if(valid && (out<2||normalized[0]!='{'))return 1;
 return 0;
}
int main(void){
 const char *ok="HTTP/1.1 200 OK\r\nContent-Length: 7\r\nContent-Type: application/json\r\n\r\n{\"a\":1}";
 const char *chunk="HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nContent-Type: application/json\r\n\r\n7\r\n{\"a\":1}\r\n0\r\n\r\n";
 const char *invalid_cl="HTTP/1.1 200 OK\r\nContent-Length: 8\r\n\r\n{\"a\":1}";
 const char *invalid_double="HTTP/1.1 200 OK\r\nContent-Length: 7\r\nContent-Length: 7\r\n\r\n{\"a\":1}";
 const char *invalid_gzip="HTTP/1.1 200 OK\r\nContent-Encoding: gzip\r\n\r\n{\"a\":1}";
 const char *invalid_redirect="HTTP/1.1 302 Found\r\nContent-Length: 7\r\n\r\n{\"a\":1}";
 const char *invalid_chunk="HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n6\r\n{\"a\":1}\r\n0\r\n\r\n";
 const char *invalid_html="HTTP/1.1 200 OK\r\nContent-Length: 13\r\n\r\n<html></html>";
 if(check(ok,1)||check(chunk,1)||check(invalid_cl,0)||
    check(invalid_double,0)||check(invalid_gzip,0)||
    check(invalid_redirect,0)||check(invalid_chunk,0)||
    check(invalid_html,0)){
  fputs("VECI_XL_HTTP_OFFLINE_SYNTHETIC=failed\n",stderr);
  return 1;
 }
 puts("VECI_XL_HTTP_OFFLINE_SYNTHETIC=pass");
 return 0;
}
