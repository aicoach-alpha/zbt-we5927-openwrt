/* Single-scope host UAT: CIAM OTP formatting, trust boundaries and framing.
 * No real operator access, no browser, no modem/SMS tests. */
#define main veci_ciam_program_main
#include "../source/veci-telco-indonesia/veci-xl-ciam.c"
#undef main
#include <assert.h>

int main(void){
 assert(valid_number("6281234567890"));
 assert(!valid_number("081234567890"));
 assert(!valid_number("6281234;echo"));
 assert(!valid_number("628123456789012345"));
 char timebuf[48];
 assert(date_gmt7((time_t)0,123,timebuf,sizeof(timebuf))==0);
 assert(strcmp(timebuf,"1970-01-01T07:00:00.123+0700")==0);

 strcpy(auth,"test_authorization");
 strcpy(ua,"VeCI-TEST");
 strcpy(fingerprint,"test_fingerprint");
 strcpy(device,"test_device_id");
 strcpy(number,"6281234567890");
 strcpy(sigkey,"test-signing-key");
 strcpy(otp,"123456");
 assert(make_request(0)==0);
 assert(strstr(request,"GET /realms/xl-ciam/auth/otp?contact=6281234567890&contactType=SMS&alternateContact=false HTTP/1.1\r\n"));
 assert(strstr(request,"Host: gede.ciam.xlaxiata.co.id\r\n"));
 assert(!strstr(request,"Ax-Api-Signature:"));
 assert(!strstr(request,"/payments"));
 assert(make_request(1)==0);
 assert(strstr(request,"POST /realms/xl-ciam/protocol/openid-connect/token HTTP/1.1\r\n"));
 assert(strstr(request,"Ax-Api-Signature: "));
 assert(strstr(request,"Content-Length: "));
 assert(strstr(request,"contactType=SMS&code=123456&grant_type=password&contact=6281234567890&scope=openid"));
 assert(!strstr(request,"/payments"));
 assert(!strstr(request,"/unsubscribe"));

 /* Parse response status, JSON Content-Type and exact framing. Never trust HTTP
    2xx alone as verified account ownership or quota. */
 const char *body_json="{\"ok\":true}";
 int n=snprintf(response,sizeof(response),
     "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %zu\r\n\r\n%s",
     strlen(body_json),body_json);
 assert(n>0 && (size_t)n<sizeof(response));
 assert(parse_reply(0,(size_t)n)==0);
 n=snprintf(response,sizeof(response),
     "HTTP/1.1 302 Found\r\nContent-Type: application/json\r\nContent-Length: %zu\r\n\r\n%s",
     strlen(body_json),body_json);
 assert(parse_reply(0,(size_t)n)!=0);
 n=snprintf(response,sizeof(response),
     "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: %zu\r\n\r\n%s",
     strlen(body_json),body_json);
 assert(parse_reply(0,(size_t)n)!=0);
 n=snprintf(response,sizeof(response),
     "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n%s",body_json);
 assert(parse_reply(0,(size_t)n)!=0);
 n=snprintf(response,sizeof(response),
     "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 33\r\n\r\n%s",body_json);
 assert(parse_reply(0,(size_t)n)!=0);
 puts("VECI_XL_CIAM_FOCUSED_HOST=pass");
 return 0;
}
