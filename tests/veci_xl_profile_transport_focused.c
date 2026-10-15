/* Only the new read-only XL profile transport variant. No operator traffic. */
#define VECI_XL_PROFILE_VARIANT 1
#define main veci_xl_profile_original_main
#include "../source/veci-telco-indonesia/veci-xl-quota-http.c"
#undef main
#include <assert.h>
int main(void){
 assert(strcmp(ROUTE,"/api/v8/profile")==0);
 assert(strcmp(PRIVATE,"/tmp/veci-telco-private/pending-profile")==0);
 assert(strstr(ROUTE,"quota-details")==NULL);
 const char *json="{\"xdata\":\"AAAAAA==\",\"xtime\":1791987600000}";
 assert(valid_quota_envelope((const unsigned char*)json,strlen(json),(const unsigned char*)"1791987600"));
 const char *bad="{\"xdata\":\"AAAAAA==\",\"xtime\":1791987600000,\"action\":\"purchase\"}";
 assert(!valid_quota_envelope((const unsigned char*)bad,strlen(bad),(const unsigned char*)"1791987600"));
 const char *ok="HTTP/1.1 200 OK\r\nContent-Length: 7\r\nContent-Type: application/json\r\n\r\n{\"a\":1}";
 size_t bytes=strlen(ok),count=0;
 memcpy(wire,ok,bytes);
 assert(parse_response(bytes,&count)==0);
 assert(count==7);
 const char *bad_status="HTTP/1.1 302 Found\r\nContent-Length: 7\r\nContent-Type: application/json\r\n\r\n{\"a\":1}";
 bytes=strlen(bad_status);
 memcpy(wire,bad_status,bytes);
 assert(parse_response(bytes,&count)!=0);
 puts("VECI_XL_PROFILE_TRANSPORT_FOCUSED=pass");
 return 0;
}
