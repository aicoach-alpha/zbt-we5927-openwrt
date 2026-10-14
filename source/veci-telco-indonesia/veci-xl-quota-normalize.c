/*
 * VeCI XL native quota-details response normalizer.
 * NO network, auth, certificates, modem or cache writes.
 * Caller MUST authenticate and decrypt the XL HTTPS response first.
 *
 * Supported community-described shape:
 * { "data": { "quotas": [
 *    { "benefits": [ {"data_type":"DATA","remaining":bytes,"total":bytes} ]}
 * ]}}
 * Also accepts quotas at root, or inside root.quota.data.
 *
 * Prints only finite DATA benefit totals; never prints raw JSON or secrets.
 * Does NOT assert an authenticated source; that belongs to the caller.
 */
#define _POSIX_C_SOURCE 200809L
#include <ctype.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#define MAX_RESPONSE 65536
#define MAX_TOKENS 4096
#define MAX_DEPTH 24
#define MAX_BENEFITS 256
#define MAX_NUM 9999999999999ULL

enum kind { OBJECT, ARRAY, STRING, ATOM };
struct token { int start,end,after,kind; };
static char input[MAX_RESPONSE+2];
static struct token tokens[MAX_TOKENS];
static int len,pos,count,failed;
static void ws(void){while(pos<len && (input[pos]==' '||input[pos]=='\n'||input[pos]=='\r'||input[pos]=='\t'))pos++;}
static int make(int kind,int at){
 if(count>=MAX_TOKENS){failed=1;return -1;}
 int n=count++;tokens[n].kind=kind;tokens[n].start=at;return n;
}
static int quoted(void){
 if(pos>=len||input[pos]!='"'){failed=1;return -1;}
 int t=make(STRING,pos++);if(t<0)return -1;
 while(pos<len){
  unsigned char c=(unsigned char)input[pos++];
  if(c=='"'){tokens[t].end=pos;tokens[t].after=count;return t;}
  if(c<32){failed=1;return -1;}
  if(c!='\\')continue;
  if(pos>=len){failed=1;return -1;}
  c=(unsigned char)input[pos++];
  if(c=='u'){
   for(int j=0;j<4;j++){
    if(pos>=len||!isxdigit((unsigned char)input[pos++])){failed=1;return -1;}
   }
  }else if(c!='"'&&c!='\\'&&c!='/'&&c!='b'&&c!='f'&&c!='n'&&c!='r'&&c!='t'){
   failed=1;return -1;
  }
 }
 failed=1;return -1;
}
static int parse(int depth){
 ws();if(failed||depth>MAX_DEPTH||pos>=len){failed=1;return -1;}
 if(input[pos]=='"')return quoted();
 if(input[pos]=='{' || input[pos]=='['){
  const int object=input[pos]=='{';
  int t=make(object?OBJECT:ARRAY,pos++);
  if(t<0)return -1;
  ws();const char close=object?'}':']';
  if(pos<len&&input[pos]==close){pos++;tokens[t].end=pos;tokens[t].after=count;return t;}
  for(;;){
   if(object){
    if(quoted()<0)return -1;
    ws();if(pos>=len||input[pos++]!=':'){failed=1;return -1;}
   }
   if(parse(depth+1)<0)return -1;
   ws();
   if(pos>=len){failed=1;return -1;}
   if(input[pos]==close){pos++;tokens[t].end=pos;tokens[t].after=count;return t;}
   if(input[pos++]!=','){failed=1;return -1;}
   ws();
  }
 }
 int t=make(ATOM,pos);
 if(t<0)return -1;
 while(pos<len&&input[pos]!=','&&input[pos]!=']'&&input[pos]!='}'&&
       input[pos]!=' '&&input[pos]!='\r'&&input[pos]!='\n'&&input[pos]!='\t')pos++;
 if(pos<=tokens[t].start){failed=1;return -1;}
 tokens[t].end=pos;tokens[t].after=count;return t;
}
static int eq(int t,const char *wanted){
 if(t<0||t>=count||tokens[t].kind!=STRING)return 0;
 size_t n=strlen(wanted);
 return (size_t)(tokens[t].end-tokens[t].start-2)==n &&
        !strncmp(input+tokens[t].start+1,wanted,n);
}
static int ieq(int t,const char *wanted){
 if(t<0||t>=count||tokens[t].kind!=STRING)return 0;
 size_t n=strlen(wanted);
 return (size_t)(tokens[t].end-tokens[t].start-2)==n &&
        !strncasecmp(input+tokens[t].start+1,wanted,n);
}
static int field(int obj,const char *key){
 if(obj<0||obj>=count||tokens[obj].kind!=OBJECT)return -1;
 int result=-1;
 for(int i=obj+1;i<tokens[obj].after;){
  int v=tokens[i].after;
  if(v>=tokens[obj].after||v>=count){failed=1;return -1;}
  if(eq(i,key)){
   if(result>=0){failed=1;return -1;}
   result=v;
  }
  i=tokens[v].after;
 }
 return result;
}
static int number(int t,uint64_t *v){
 if(t<0||t>=count)return 0;
 int a=tokens[t].start,b=tokens[t].end;
 if(tokens[t].kind==STRING){a++;b--;}
 else if(tokens[t].kind!=ATOM)return 0;
 if(a>=b||b-a>13)return 0;
 if(b-a>1&&input[a]=='0')return 0;
 uint64_t result=0;
 for(int i=a;i<b;i++){
  if(input[i]<'0'||input[i]>'9')return 0;
  result=result*10+(unsigned)(input[i]-'0');
  if(result>MAX_NUM)return 0;
 }
 *v=result;return 1;
}
static int is_true(int t){
 return t>=0&&tokens[t].kind==ATOM&&tokens[t].end-tokens[t].start==4 &&
 !strncmp(input+tokens[t].start,"true",4);
}
static int good_status(int obj){
 int s=field(obj,"status");
 return !failed&&(s<0||ieq(s,"SUCCESS")||ieq(s,"OK")||ieq(s,"SUCCEEDED"));
}
static int main_parse(void){
 if(input[0]=='\0'||parse(0)<0||failed)return 1;
 ws();if(pos!=len||tokens[0].kind!=OBJECT||!good_status(0))return 1;
 int root=field(0,"data");
 if(failed)return 1;
 if(root<0)root=0;
 if(tokens[root].kind!=OBJECT)return 1;
 int quota=field(root,"quotas");
 if(failed)return 1;
 if(quota<0){
  int wrapper=field(root,"quota");
  if(wrapper>=0){
   int nested=field(wrapper,"data");
   if(nested>=0)wrapper=nested;
   quota=field(wrapper,"quotas");
  }
 }
 if(failed||quota<0||tokens[quota].kind!=ARRAY)return 1;
 uint64_t remaining=0,total=0;
 int data_benefits=0,benefit_rows=0,rows=0;
 for(int q=quota+1;q<tokens[quota].after;q=tokens[q].after){
  if(tokens[q].kind!=OBJECT||++rows>256)return 1;
  int benefits=field(q,"benefits");
  if(failed)return 1;
  if(benefits<0)continue;
  if(tokens[benefits].kind!=ARRAY)return 1;
  for(int i=benefits+1;i<tokens[benefits].after;i=tokens[i].after){
   if(tokens[i].kind!=OBJECT||++benefit_rows>MAX_BENEFITS)return 1;
   int kind=field(i,"data_type");
   if(failed)return 1;
   if(!ieq(kind,"DATA"))continue;
   if(is_true(field(i,"is_unlimited")))continue;
   int r=field(i,"remaining"),t=field(i,"total");
   uint64_t rv=0,tv=0;
   if(failed||!number(r,&rv)||!number(t,&tv)||rv>tv)return 1;
   if(remaining>MAX_NUM-rv||total>MAX_NUM-tv)return 1;
   remaining+=rv;total+=tv;
   data_benefits++;
  }
 }
 if(failed||data_benefits==0||total==0)return 1;
 printf("{\"ok\":true,\"parsed_only\":true,\"provider\":\"xl\",\"remaining_bytes\":%llu,"
  "\"total_bytes\":%llu}\n",(unsigned long long)remaining,(unsigned long long)total);
 return 0;
}
int main(void){
 len=(int)fread(input,1,MAX_RESPONSE+1,stdin);
 if(len<=0||len>MAX_RESPONSE||ferror(stdin))return 2;
 input[len]=0;
 if(main_parse()){
  fputs("{\"ok\":false,\"reason\":\"invalid_quota_payload\"}\n",stdout);
  return 1;
 }
 return 0;
}
