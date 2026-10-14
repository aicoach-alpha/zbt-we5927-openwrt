/*
 * VeCI Indonesia Edition — myXL read-only protocol crypto primitives.
 * Ported from public descriptions and independent implementation research.
 * No embedded operator app keys, tokens, contacts or authentication secrets.
 * This binary NEVER makes network calls; caller performs verified direct TLS
 * only to explicit operator hosts. No purchase/payment methods provided.
 *
 * Native OpenWrt footprint: mbedTLS crypto only (libmbedcrypto).
 * Usage:
 *  veci-xl-crypto xdata <13-digit-xtime-ms> <root-only-32-byte-keyfile>
 *     [plaintext <=4096 bytes on stdin] -> base64url ciphertext
 *  veci-xl-crypto signature <10-digit-unix-time> <secretfile> <tokenfile>
 *     -> lowercase HMAC-SHA512 over myXL read-only quota path
 */
#include <mbedtls/aes.h>
#include <mbedtls/md.h>
#include <mbedtls/base64.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define MAX_INPUT 4096
#define MAX_SECRET 512
#define MAX_TOKEN 3072
#define QUOTA_PATH "api/v8/packages/quota-details"

static void wipe(void *ptr, size_t n) {
 volatile unsigned char *p=(volatile unsigned char *)ptr;
 while(n--) *p++=0;
}
static int bad(void){
 fputs("VECI_XL_CRYPTO_UNAVAILABLE\n",stderr);
 return 1;
}
static int numeric(const char *s, size_t n){
 if(strlen(s)!=n)return 0;
 for(size_t i=0;i<n;i++)if(s[i]<'0'||s[i]>'9')return 0;
 return 1;
}
static int load(const char *path,unsigned char *buf,size_t cap,size_t *len){
 struct stat st;
 if(!path||path[0]!='/'||lstat(path,&st)||!S_ISREG(st.st_mode)||
    (st.st_mode&077)!=0 || st.st_size<=0||st.st_size>(off_t)cap ||
    st.st_nlink!=1)return -1;
 FILE *f=fopen(path,"rb");if(!f)return -1;
 *len=fread(buf,1,cap+1,f);
 int eof=feof(f);
 fclose(f);
 if(*len>cap||(!eof&&*len==0))return -1;
 if(*len&&buf[*len-1]=='\n')(*len)--;
 for(size_t i=0;i<*len;i++)
   if(buf[i]==0||buf[i]=='\r'||buf[i]=='\n')return -1;
 return *len?0:-1;
}
static int digest(const unsigned char *src,size_t n,unsigned char out[32]){
 const mbedtls_md_info_t *inf=mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
 return inf?mbedtls_md(inf,src,n,out):-1;
}
static int encryption(const char *time,const char *file){
 unsigned char key[MAX_SECRET+2]={0},plain[MAX_INPUT+32]={0};
 unsigned char hashed[32],iv[16],encrypted[MAX_INPUT+32]={0},encoded[(MAX_INPUT+64)*2]={0};
 size_t klen=0,n=0,olen=0;int rc=1;
 if(!numeric(time,13)||load(file,key,MAX_SECRET,&klen)||klen!=32)goto done;
 n=fread(plain,1,MAX_INPUT+1,stdin);
 if(n==0||n>MAX_INPUT||ferror(stdin))goto done;
 if(digest((const unsigned char *)time,strlen(time),hashed))goto done;
 const char hex[]="0123456789abcdef";char ivhex[65];
 for(size_t i=0;i<32;i++){ivhex[i*2]=hex[hashed[i]>>4];ivhex[i*2+1]=hex[hashed[i]&15];}
 memcpy(iv,ivhex,16);
 unsigned char pad=(unsigned char)(16-(n%16));
 for(size_t i=0;i<pad;i++)plain[n+i]=pad;
 n+=pad;
 mbedtls_aes_context aes;mbedtls_aes_init(&aes);
 int ok=mbedtls_aes_setkey_enc(&aes,key,256);
 if(!ok)ok=mbedtls_aes_crypt_cbc(&aes,MBEDTLS_AES_ENCRYPT,n,iv,plain,encrypted);
 mbedtls_aes_free(&aes);if(ok)goto done;
 if(mbedtls_base64_encode(encoded,sizeof(encoded),&olen,encrypted,n)||olen>=sizeof(encoded))goto done;
 /* URL-safe base64 with optional trailing '=' stripped (as source reference). */
 for(size_t i=0;i<olen;i++){
   if(encoded[i]=='+')encoded[i]='-';
   if(encoded[i]=='/')encoded[i]='_';
 }
 /* BITS reference encodes urlsafe b64 retaining padding: do not strip '='. */
 fwrite(encoded,1,olen,stdout);putchar('\n');rc=0;
done:
 wipe(key,sizeof key);wipe(plain,sizeof plain);wipe(encrypted,sizeof encrypted);
 wipe(iv,sizeof iv);wipe(hashed,sizeof hashed);wipe(encoded,sizeof encoded);
 return rc;
}
static int signature(const char *ts,const char *keyfile,const char *tokenfile){
 unsigned char secret[MAX_SECRET+2]={0},token[MAX_TOKEN+2]={0},mac[64]={0};
 char key[MAX_SECRET+MAX_TOKEN+96]={0},msg[MAX_TOKEN+32]={0};
 size_t slen=0,tlen=0;
 int rc=1;
 if(!numeric(ts,10)||load(keyfile,secret,MAX_SECRET,&slen)||
    load(tokenfile,token,MAX_TOKEN,&tlen))goto done;
 int k=snprintf(key,sizeof(key),"%.*s;%.*s;POST;%s;%s",
        (int)slen,secret,(int)tlen,token,QUOTA_PATH,ts);
 int m=snprintf(msg,sizeof(msg),"%.*s;%s;",(int)tlen,token,ts);
 if(k<=0||m<=0||(size_t)k>=sizeof(key)||(size_t)m>=sizeof(msg))goto done;
 const mbedtls_md_info_t *inf=mbedtls_md_info_from_type(MBEDTLS_MD_SHA512);
 if(!inf||mbedtls_md_hmac(inf,(const unsigned char*)key,(size_t)k,
          (const unsigned char*)msg,(size_t)m,mac))goto done;
 for(size_t i=0;i<64;i++)printf("%02x",mac[i]);
 putchar('\n');rc=0;
done:
 wipe(secret,sizeof secret);wipe(token,sizeof token);wipe(key,sizeof key);
 wipe(msg,sizeof msg);wipe(mac,sizeof mac);
 return rc;
}
int main(int argc,char **argv){
 int result=1;
 if(argc==4&&!strcmp(argv[1],"xdata"))result=encryption(argv[2],argv[3]);
 else if(argc==5&&!strcmp(argv[1],"signature"))result=signature(argv[2],argv[3],argv[4]);
 else return bad();
 if(result)return bad();
 return 0;
}
