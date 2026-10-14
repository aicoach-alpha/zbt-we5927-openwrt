/*
 * VeCI Indonesia: read-only operator HTTPS identity probe.
 *
 * Verifies real DNS/TCP/TLS and the certificate hostname for ONE
 * explicitly selected carrier endpoint, without tokens, OTP, SMS or API
 * authentication. Returns no response body and never writes to disk.
 *
 * This is deliberately NOT a quota client. The service endpoints are
 * community-discovered candidates and may change without notice.
 */
#define _POSIX_C_SOURCE 200809L
#include <mbedtls/ssl.h>
#include <mbedtls/net_sockets.h>
#include <mbedtls/x509_crt.h>
#include <mbedtls/entropy.h>
#include <mbedtls/ctr_drbg.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <unistd.h>

#define CA_FILE "/etc/ssl/certs/ca-certificates.crt"
#define DEADLINE_SECONDS 25
#define MAX_RESPONSE_LINE 512
#define REQUEST_LIMIT 256

struct carrier {
    const char *id;
    const char *host;
};
static const struct carrier approved[] = {
    { "api", "api.myxl.xlaxiata.co.id" },
    { "ciam", "gede.ciam.xlaxiata.co.id" }
};

static int response_code(const char *line)
{
    if (strncmp(line, "HTTP/1.1 ", 9) != 0 &&
        strncmp(line, "HTTP/1.0 ", 9) != 0) return -1;
    if (!isdigit((unsigned char)line[9]) ||
        !isdigit((unsigned char)line[10]) ||
        !isdigit((unsigned char)line[11]) ||
        (line[12] != ' ' && line[12] != '\r' && line[12] != '\n')) return -1;
    int status = (line[9]-'0')*100+(line[10]-'0')*10+(line[11]-'0');
    return status >= 100 && status <= 599 ? status : -1;
}
static int probe(const struct carrier *carrier)
{
    int ret=-1, status=-1, success=0;
    char request[REQUEST_LIMIT], response[MAX_RESPONSE_LINE+1];
    size_t used=0;
    mbedtls_net_context net;
    mbedtls_ssl_context ssl;
    mbedtls_ssl_config config;
    mbedtls_x509_crt ca;
    mbedtls_entropy_context entropy;
    mbedtls_ctr_drbg_context rng;
    mbedtls_net_init(&net);
    mbedtls_ssl_init(&ssl);
    mbedtls_ssl_config_init(&config);
    mbedtls_x509_crt_init(&ca);
    mbedtls_entropy_init(&entropy);
    mbedtls_ctr_drbg_init(&rng);
    const unsigned char personalization[]="veci-xl-readonly-identity-probe";
    if (mbedtls_ctr_drbg_seed(&rng,mbedtls_entropy_func,&entropy,
                             personalization,sizeof(personalization)-1)!=0) goto cleanup;
    if (mbedtls_x509_crt_parse_file(&ca,CA_FILE)!=0) goto cleanup;
    if (mbedtls_ssl_config_defaults(&config,MBEDTLS_SSL_IS_CLIENT,
                                    MBEDTLS_SSL_TRANSPORT_STREAM,
                                    MBEDTLS_SSL_PRESET_DEFAULT)!=0) goto cleanup;
    mbedtls_ssl_conf_authmode(&config,MBEDTLS_SSL_VERIFY_REQUIRED);
    mbedtls_ssl_conf_ca_chain(&config,&ca,NULL);
    mbedtls_ssl_conf_rng(&config,mbedtls_ctr_drbg_random,&rng);
    mbedtls_ssl_conf_read_timeout(&config,6000);
    if (mbedtls_ssl_setup(&ssl,&config)!=0) goto cleanup;
    /* This checks SAN/CN AND sends SNI, not just the CA signature. */
    if (mbedtls_ssl_set_hostname(&ssl,carrier->host)!=0) goto cleanup;
    if (mbedtls_net_connect(&net,carrier->host,"443",MBEDTLS_NET_PROTO_TCP)!=0) goto cleanup;
    mbedtls_ssl_set_bio(&ssl,&net,mbedtls_net_send,mbedtls_net_recv,
                        mbedtls_net_recv_timeout);
    do {
        ret=mbedtls_ssl_handshake(&ssl);
    } while (ret==MBEDTLS_ERR_SSL_WANT_READ || ret==MBEDTLS_ERR_SSL_WANT_WRITE);
    if (ret!=0 || mbedtls_ssl_get_verify_result(&ssl)!=0) goto cleanup;
    int n=snprintf(request,sizeof(request),
                   "HEAD / HTTP/1.1\r\nHost: %s\r\n"
                   "User-Agent: VeCI-ReadOnly-Probe/1\r\n"
                   "Connection: close\r\nCache-Control: no-store\r\n\r\n",
                   carrier->host);
    if (n<=0 || n>=(int)sizeof(request)) goto cleanup;
    for (int sent=0;sent<n;) {
        ret=mbedtls_ssl_write(&ssl,(const unsigned char *)request+sent,(size_t)(n-sent));
        if (ret==MBEDTLS_ERR_SSL_WANT_READ || ret==MBEDTLS_ERR_SSL_WANT_WRITE) continue;
        if (ret<=0) goto cleanup;
        sent+=ret;
    }
    /* Read ONLY the first status line: never expose payloads or headers. */
    while (used<MAX_RESPONSE_LINE) {
        unsigned char ch;
        ret=mbedtls_ssl_read(&ssl,&ch,1);
        if (ret==MBEDTLS_ERR_SSL_WANT_READ || ret==MBEDTLS_ERR_SSL_WANT_WRITE) continue;
        if (ret<=0) goto cleanup;
        response[used++]=(char)ch;
        if (ch=='\n') break;
    }
    if (!used || response[used-1]!='\n') goto cleanup;
    response[used]=0;
    status=response_code(response);
    if (status<0) goto cleanup;
    printf("VECI_XL_DIRECT_TLS=verified\n");
    printf("VECI_XL_HTTP_STATUS=%d\n",status);
    printf("VECI_REAL_OPERATOR_LOGIN=not_attempted\n");
    printf("VECI_OPERATOR_QUOTA=not_verified\n");
    printf("VECI_MODEM_AND_SMS_UNCHANGED=true\n");
    printf("VECI_FLASH_WRITES=none\n");
    success=1;
cleanup:
    mbedtls_ssl_free(&ssl);
    mbedtls_ssl_config_free(&config);
    mbedtls_x509_crt_free(&ca);
    mbedtls_ctr_drbg_free(&rng);
    mbedtls_entropy_free(&entropy);
    mbedtls_net_free(&net);
    if (!success) {
        fputs("VECI_XL_DIRECT_TLS=failed\n",stderr);
        return 1;
    }
    return 0;
}
int main(int argc,char **argv)
{
    const struct carrier *selected=NULL;
    if (argc!=2) goto usage;
    for (size_t i=0;i<sizeof(approved)/sizeof(approved[0]);i++) {
        if (strcmp(argv[1],approved[i].id)==0) selected=&approved[i];
    }
    if (selected==NULL) goto usage;
    signal(SIGPIPE,SIG_IGN);
    /* Bound DNS, TCP and handshake together; no retry loop. */
    alarm(DEADLINE_SECONDS);
    int ret=probe(selected);
    alarm(0);
    return ret;
usage:
    fputs("usage: veci-xl-tls-probe api|ciam\n",stderr);
    return 2;
}
