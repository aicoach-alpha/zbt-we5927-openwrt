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
static int check_body_restrictions(void){
 const char *ts="1791987600";
 const char *good="{\"xdata\":\"AAAAAA==\",\"xtime\":1791987600000}";
 const char *bad_extra="{\"xdata\":\"AAAAAA==\",\"xtime\":1791987600000,\"action\":\"purchase\"}";
 const char *bad_time="{\"xdata\":\"AAAAAA==\",\"xtime\":1791987601000}";
 const char *bad_injection="{\"xdata\":\"AAAA\nAA==\",\"xtime\":1791987600000}";
 const char *bad_alt="{\"xdata\":\"AAAAAA==\",\"xtime\":\"1791987600000\"}";
 if(!valid_quota_envelope((const unsigned char *)good,strlen(good),(const unsigned char *)ts))return 1;
 for(int i=0;i<4;i++){
  const char *bad=i==0?bad_extra:i==1?bad_time:i==2?bad_injection:bad_alt;
  if(valid_quota_envelope((const unsigned char *)bad,strlen(bad),(const unsigned char *)ts))return 1;
 }
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
 const char *invalid_missing_type="HTTP/1.1 200 OK\r\nContent-Length: 7\r\n\r\n{\"a\":1}";
 const char *invalid_html_type="HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 7\r\n\r\n{\"a\":1}";
 const char *invalid_no_framing="HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"a\":1}";
 const char *valid_json_charset="HTTP/1.1 200 OK\r\nContent-Length: 7\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{\"a\":1}";
 const char *invalid_conflict="HTTP/1.1 200 OK\r\nContent-Length: 7\r\nContent-Type: application/json\r\nTransfer-Encoding: chunked\r\n\r\n{\"a\":1}";

 if(check_body_restrictions()||check(ok,1)||check(chunk,1)||check(invalid_cl,0)||
    check(invalid_double,0)||check(invalid_gzip,0)||
    check(invalid_redirect,0)||check(invalid_chunk,0)||
    check(invalid_html,0)||check(invalid_missing_type,0)||
    check(invalid_html_type,0)||check(invalid_no_framing,0)||
    check(valid_json_charset,1)||check(invalid_conflict,0)){
  fputs("VECI_XL_HTTP_OFFLINE_SYNTHETIC=failed\n",stderr);
  return 1;
 }
 puts("VECI_XL_HTTP_OFFLINE_SYNTHETIC=pass");
 return 0;
}
