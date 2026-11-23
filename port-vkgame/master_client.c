/* MotorStorm: Pacific Rift master server client. See master_client.h. */
#include "master_client.h"

#include <stdio.h>
#include <string.h>

#define MS_LINE_MAX 512
#define MS_FIELDS 8

int ms_announce_url(char* buf, size_t cap, const char* base, int port, int max)
{
    int n = snprintf(buf, cap, "%s?a=announce&game=%s&port=%d&max=%d&v=%s",
                     base, MS_GAME_ID, port, max, MS_VERSION_TAG);
    return (n < 0 || (size_t)n >= cap) ? 1 : 0;
}

int ms_remove_url(char* buf, size_t cap, const char* base, int port)
{
    int n = snprintf(buf, cap, "%s?a=remove&game=%s&port=%d", base, MS_GAME_ID, port);
    return (n < 0 || (size_t)n >= cap) ? 1 : 0;
}

int ms_list_url(char* buf, size_t cap, const char* base)
{
    int n = snprintf(buf, cap, "%s?a=list&game=%s&format=lines", base, MS_GAME_ID);
    return (n < 0 || (size_t)n >= cap) ? 1 : 0;
}

/* One GET; the body is discarded for announce and remove. */
static int send_get(ms_transport t, const char* url, int* status)
{
    char body[1024];
    int st = -1;
    if (!t.get) return 1;
    if (t.get(t.ctx, url, body, sizeof body, &st) != 0) {
        *status = -1;
        return 1;
    }
    *status = st;
    return 0;
}

void ms_publisher_start(ms_publisher* p, const char* base, ms_transport t, int port, int max, long long now_ms)
{
    p->base_url = base;
    p->transport = t;
    p->port = port;
    p->max = max;
    p->active = 1;
    p->next_announce_ms = now_ms;  /* due at once */
    p->last_status = -1;
    p->announces = 0;
    p->removes = 0;
}

void ms_publisher_tick(ms_publisher* p, long long now_ms)
{
    char url[256];
    if (!p->active || now_ms < p->next_announce_ms) return;
    p->next_announce_ms = now_ms + MS_ANNOUNCE_PERIOD_MS;  /* a failed announce also waits the full period */
    if (ms_announce_url(url, sizeof url, p->base_url, p->port, p->max) != 0) {
        p->last_status = -1;
        return;
    }
    p->announces++;
    send_get(p->transport, url, &p->last_status);
}

void ms_publisher_stop(ms_publisher* p)
{
    char url[256];
    if (!p->active) return;
    p->active = 0;  /* no announce after this */
    if (ms_remove_url(url, sizeof url, p->base_url, p->port) != 0) {
        p->last_status = -1;
        return;
    }
    p->removes++;
    send_get(p->transport, url, &p->last_status);
}

/* Splits s in place at tabs. Fills f[0..max-1]; returns the total field count. */
static int split_tabs(char* s, char** f, int max)
{
    int n = 1;
    f[0] = s;
    for (char* q = s; *q; q++) {
        if (*q == '\t') {
            if (n < max) f[n] = q + 1;
            *q = '\0';
            n++;
        }
    }
    return n;
}

/* A dotted IPv4 address: four parts of 1 to 3 digits, each at most 255. */
static int parse_ipv4(const char* s, char* out, size_t cap)
{
    int parts = 0;
    const char* p = s;
    if (strlen(s) >= cap) return 0;
    while (1) {
        int digits = 0, v = 0;
        while (*p >= '0' && *p <= '9') {
            v = v * 10 + (*p - '0');
            p++;
            digits++;
        }
        if (digits < 1 || digits > 3 || v > 255) return 0;
        parts++;
        if (*p == '\0') break;
        if (*p != '.') return 0;
        p++;
    }
    if (parts != 4) return 0;
    memcpy(out, s, strlen(s) + 1);
    return 1;
}

/* A decimal number of 1 to 5 digits, at most maxval. */
static int parse_uint(const char* s, int maxval, int* out)
{
    long v = 0;
    size_t n = strlen(s);
    if (n < 1 || n > 5) return 0;
    for (size_t i = 0; i < n; i++) {
        if (s[i] < '0' || s[i] > '9') return 0;
        v = v * 10 + (s[i] - '0');
    }
    if (v > maxval) return 0;
    *out = (int)v;
    return 1;
}

static int copy_text(char* dst, size_t cap, const char* src)
{
    if (strlen(src) >= cap) return 0;
    memcpy(dst, src, strlen(src) + 1);
    return 1;
}

/* One line, already without its line break. Returns 1 when it is a valid server. */
static int parse_line(char* line, ms_server* sv)
{
    char* f[MS_FIELDS];
    int n = split_tabs(line, f, MS_FIELDS);
    if (n != MS_FIELDS) return 0;
    if (!parse_ipv4(f[0], sv->address, sizeof sv->address)) return 0;
    if (!parse_uint(f[1], 65535, &sv->port) || sv->port < 1) return 0;
    if (!copy_text(sv->name, sizeof sv->name, f[2])) return 0;
    if (!copy_text(sv->map, sizeof sv->map, f[3])) return 0;
    if (!parse_uint(f[4], 65535, &sv->players)) return 0;
    if (!parse_uint(f[5], 65535, &sv->max)) return 0;
    if (!copy_text(sv->mode, sizeof sv->mode, f[6])) return 0;
    if (!copy_text(sv->version, sizeof sv->version, f[7])) return 0;
    return 1;
}

int ms_parse_list_lines(const char* body, ms_server* out, int cap, int* skipped)
{
    int count = 0;
    int bad = 0;
    const char* p = body;
    char line[MS_LINE_MAX];

    while (*p) {
        const char* eol = strchr(p, '\n');
        size_t len = eol ? (size_t)(eol - p) : strlen(p);
        if (len > 0 && p[len - 1] == '\r') len--;
        if (len > 0) {
            if (len >= sizeof line) {
                bad++;
            } else {
                memcpy(line, p, len);
                line[len] = '\0';
                if (count < cap) {
                    if (parse_line(line, &out[count])) count++;
                    else bad++;
                }
            }
        }
        if (!eol) break;
        p = eol + 1;
    }
    if (skipped) *skipped = bad;
    return count;
}

int ms_list(ms_transport t, const char* base, ms_server* out, int cap, int* count, int* skipped)
{
    char url[256];
    char body[16384];
    int status = -1;
    if (ms_list_url(url, sizeof url, base) != 0 || !t.get) return 1;
    if (t.get(t.ctx, url, body, sizeof body, &status) != 0) return 1;  /* no answer */
    if (status != 200) return 2;                                        /* master refused */
    *count = ms_parse_list_lines(body, out, cap, skipped);
    return 0;
}
