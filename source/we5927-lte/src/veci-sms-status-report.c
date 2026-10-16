/*
 * Decode one 3GPP SMS-STATUS-REPORT PDU (TP-MTI=2), source-only.
 * Input: one uppercase hex PDU from authenticated backend, up to 255 octets.
 * Output: one fixed JSON object; does NOT touch modem, send SMS, or mutate storage.
 * Caller must correlate TP-MR + normalized TP-RA + recent submitted message
 * before changing delivery state. A standalone report is NOT proof of identity.
 */
#include <ctype.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define MAX_PDU 255
static void invalid(void){ puts("{\"ok\":false,\"reason\":\"invalid_status_report\"}"); }
static int decode_hex(uint8_t *b,size_t *n){
    char s[2*MAX_PDU+3];size_t i,len;
    if(!fgets(s,sizeof s,stdin))return 0;
    len=strcspn(s,"\n\r");
    if(len<30||len>2*MAX_PDU||len%2 || (s[len] && s[len]!='\n' && s[len]!='\r'))return 0;
    for(i=0;i<len;i++){
        if(!isxdigit((unsigned char)s[i]))return 0;
        if(s[i]>='a'&&s[i]<='f')return 0;
    }
    for(i=0;i<len;i+=2){
        unsigned a=(unsigned)(s[i]>='A'?s[i]-'A'+10:s[i]-'0');
        unsigned c=(unsigned)(s[i+1]>='A'?s[i+1]-'A'+10:s[i+1]-'0');
        b[i/2]=(uint8_t)(a*16+c);
    }
    memset(s,0,sizeof s);*n=len/2;return 1;
}
static int bcd(int b){
    const int low=b&15,high=(b>>4)&15;
    return (low<=9&&high<=9)?low*10+high:-1;
}
static int valid_scts(const uint8_t *p){
    int year=bcd(p[0]),mon=bcd(p[1]),day=bcd(p[2]);
    int hour=bcd(p[3]),minute=bcd(p[4]),second=bcd(p[5]);
    int tz=p[6]&0xF7;
    return year>=0 && mon>=1 && mon<=12 && day>=1 && day<=31 &&
        hour>=0 && hour<=23 && minute>=0 && minute<=59 &&
        second>=0 && second<=59 && bcd(tz)>=0;
}
/*
 * A serial-port owner can pass a single, already-framed unsolicited
 * notification here. This decoder never opens the modem or reads messages.
 * +CDS carries a status PDU; +CDSI carries ONLY a stored index.
 */
static int parse_cds_header(unsigned *octets){
    char line[48]={0};size_t n,i;unsigned value=0;
    if(!fgets(line,sizeof line,stdin))return 0;
    n=strcspn(line,"\r\n");
    if(line[n]=='\0' || n<7 || n>10 || strncmp(line,"+CDS: ",6))return 0;
    for(i=6;i<n;i++){
        if(line[i]<'0'||line[i]>'9')return 0;
        value=value*10+(unsigned)(line[i]-'0');
    }
    if(value<1||value>255)return 0;
    if(line[n]=='\r' && line[n+1]!='\n')return 0;
    *octets=value;return 1;
}
static int parse_stored_urc(void){
    char line[80]={0};size_t n,i;unsigned index=0;const char *p;
    if(!fgets(line,sizeof line,stdin))return 0;
    n=strcspn(line,"\r\n");
    if(line[n]=='\0' || n<13 || strncmp(line,"+CDSI: \"",8))return 0;
    p=line+8;
    if(!((p[0]=='S' && p[1]=='M')||(p[0]=='M' && p[1]=='E')) ||
        p[2]!='"'||p[3]!=',')return 0;
    for(i=12;i<n;i++){
        if(line[i]<'0'||line[i]>'9')return 0;
        index=index*10+(unsigned)(line[i]-'0');
        if(index>65535)return 0;
    }
    if(i==12 || (line[n]=='\r' && line[n+1]!='\n'))return 0;
    printf("{\"ok\":true,\"route\":\"stored_indication\",\"storage\":\"%c%c\",\"index\":%u}\n",
        p[0],p[1],index);
    return 1;
}
int main(int argc,char **argv){
    int direct=0;unsigned tpdu_length=0;
    if(argc==2 && strcmp(argv[1],"--stored-urc")==0){
        if(parse_stored_urc())return 0;
        goto bad;
    }
    if(argc==2 && strcmp(argv[1],"--direct-urc")==0)direct=1;
    else if(argc!=1)goto bad;
    if(direct && !parse_cds_header(&tpdu_length))goto bad;

    uint8_t b[MAX_PDU]={0};size_t n=0,at,alen,i;
    char recipient[19]={0};size_t k=0;
    unsigned mr,status,toa;
    if(!decode_hex(b,&n))goto bad;
    if(direct && (1u+(size_t)b[0]>n || n-1u-(size_t)b[0]!=tpdu_length))goto bad;
    at=1+(size_t)b[0]; /* SMSC length in OCTETS, no body data output */
    if(at+5>n || (b[at]&3)!=2)goto bad; /* STATUS-REPORT */
    at++;
    mr=b[at++];
    alen=b[at++];
    toa=b[at++];
    if(alen<3||alen>15 || (toa!=0x91 && toa!=0x81))goto bad;
    if(at+(alen+1)/2+15>n)goto bad; /* recipient + SCTS + DT + ST */
    if(toa==0x91)recipient[k++]='+';
    for(i=0;i<alen;i++){
        unsigned octet=b[at+i/2],v=i%2?octet>>4:octet&15;
        if(v>9)goto bad;
        recipient[k++]=(char)('0'+v);
    }
    if(alen&1){if((b[at+alen/2]>>4)!=0xF)goto bad;}
    recipient[k]='\0';at+=(alen+1)/2;
    if(!valid_scts(&b[at]) || !valid_scts(&b[at+7]))goto bad;
    at+=14;status=b[at++];
    /* Allow bounded optional TLVs, but do not expose or parse them. */
    if(n-at>140)goto bad;
    const char *state=status==0?"delivered":
        status>=0x20 && status<0x40?"pending":
        status>=0x40 && status<0x80?"failed":"unknown";
    if(direct)
        printf("{\"ok\":true,\"route\":\"direct_urc\",\"mr\":%u,\"recipient\":\"%s\",\"tp_st\":%u,\"state\":\"%s\"}\n",
            mr,recipient,status,state);
    else
        printf("{\"ok\":true,\"mr\":%u,\"recipient\":\"%s\",\"tp_st\":%u,\"state\":\"%s\"}\n",
            mr,recipient,status,state);
    memset(b,0,sizeof b);
    return 0;
bad:
    invalid();memset(b,0,sizeof b);return 1;
}
