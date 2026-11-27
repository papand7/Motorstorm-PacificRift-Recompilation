/* LAN play: finding games on this network (Host / Join pages, lan_play.cpp).
 *
 * Our own protocol, one UDP port (LANB_PORT), no game data in it:
 *   query   "MSLQ" ver u8 | nonce u32 | sent_ms u32                                   13 bytes
 *   answer  "MSLA" ver u8 | nonce u32 | sent_ms u32 (echoed) | session u64 | room_port u16
 *           | players u8 | max u8 | state u8 | name [24] | event [32]                 82 bytes
 * A joining PC broadcasts a query about once a second while the Join page is up; a hosting PC
 * answers each query with its session. The answer echoes the query's clock, so the asker gets
 * the round trip (the ping) without the two clocks agreeing. Entries the host stops answering
 * for LANB_EXPIRE_MS leave the list. A different ver is listed (greyed: "different version"),
 * not hidden, so a player sees why a friend's game cannot be joined.
 *
 * Header-only and socket-free: lan_play.cpp does the sending; port-vkgame/tests/test_lan_browser.c
 * drives everything here. */
#ifndef LAN_BROWSER_H
#define LAN_BROWSER_H

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define LANB_VERSION   1        /* bump with the wire format or the room protocol */
#define LANB_PORT      36101    /* discovery (UDP); the room server is LANB_ROOM_PORT (TCP) */
#define LANB_ROOM_PORT 36100    /* psnr's default port: the game's Matching2 module dials it */
#define LANB_QUERY_LEN 13
#define LANB_ANSWER_LEN 82
#define LANB_NAME_MAX  24
#define LANB_EVENT_MAX 32
#define LANB_EXPIRE_MS 3500u
#define LANB_MAX       16

enum { LANB_STATE_LOBBY = 0, LANB_STATE_RACING = 1, LANB_STATE_STARTING = 2 };

typedef struct {
    uint32_t nonce, sent_ms;
    uint64_t session;
    uint16_t room_port;
    uint8_t players, max, state, ver;
    char name[LANB_NAME_MAX + 1], event[LANB_EVENT_MAX + 1];
} lanb_answer;

typedef struct {
    uint8_t ip[4];
    lanb_answer a;
    uint32_t seen_ms;   /* last answer */
    uint32_t ping_ms;   /* round trip of the last answer */
} lanb_entry;

typedef struct {
    lanb_entry e[LANB_MAX];
    int n;
    uint32_t nonce;     /* the current search; answers to older ones still count (late) */
} lanb_list;

static inline void lanb_w16(uint8_t* p, uint32_t v) { p[0] = (uint8_t)(v >> 8); p[1] = (uint8_t)v; }
static inline void lanb_w32(uint8_t* p, uint32_t v) { lanb_w16(p, v >> 16); lanb_w16(p + 2, v); }
static inline uint32_t lanb_r16(const uint8_t* p) { return (uint32_t)p[0] << 8 | p[1]; }
static inline uint32_t lanb_r32(const uint8_t* p) { return lanb_r16(p) << 16 | lanb_r16(p + 2); }

/* Printable ASCII only (names come from the network and go on screen); returns the length. */
static inline int lanb_clean(char* dst, const char* src, int cap_chars)
{
    int n = 0;
    for (int i = 0; i < cap_chars && src[i]; i++)
        dst[n++] = (src[i] >= 32 && src[i] < 127) ? src[i] : '?';
    dst[n] = 0;
    return n;
}

static inline int lanb_query(uint8_t out[LANB_QUERY_LEN], uint32_t nonce, uint32_t now_ms)
{
    memcpy(out, "MSLQ", 4);
    out[4] = LANB_VERSION;
    lanb_w32(out + 5, nonce);
    lanb_w32(out + 9, now_ms);
    return LANB_QUERY_LEN;
}

/* 1 and the query's nonce and clock, when buf is a query of any version (a host answers every
 * version, so an older or newer build sees this game as "different version"). */
static inline int lanb_parse_query(const uint8_t* buf, int len, uint32_t* nonce, uint32_t* sent_ms)
{
    if (len < LANB_QUERY_LEN || memcmp(buf, "MSLQ", 4)) return 0;
    *nonce = lanb_r32(buf + 5);
    *sent_ms = lanb_r32(buf + 9);
    return 1;
}

static inline int lanb_answer_pack(uint8_t out[LANB_ANSWER_LEN], const lanb_answer* a)
{
    memset(out, 0, LANB_ANSWER_LEN);
    memcpy(out, "MSLA", 4);
    out[4] = LANB_VERSION;
    lanb_w32(out + 5, a->nonce);
    lanb_w32(out + 9, a->sent_ms);
    lanb_w32(out + 13, (uint32_t)(a->session >> 32));
    lanb_w32(out + 17, (uint32_t)a->session);
    lanb_w16(out + 21, a->room_port);
    out[23] = a->players;
    out[24] = a->max;
    out[25] = a->state;
    strncpy((char*)out + 26, a->name, LANB_NAME_MAX);
    strncpy((char*)out + 50, a->event, LANB_EVENT_MAX);
    return LANB_ANSWER_LEN;
}

static inline int lanb_answer_parse(const uint8_t* buf, int len, lanb_answer* a)
{
    if (len < LANB_ANSWER_LEN || memcmp(buf, "MSLA", 4)) return 0;
    memset(a, 0, sizeof *a);
    a->ver = buf[4];
    a->nonce = lanb_r32(buf + 5);
    a->sent_ms = lanb_r32(buf + 9);
    a->session = (uint64_t)lanb_r32(buf + 13) << 32 | lanb_r32(buf + 17);
    a->room_port = (uint16_t)lanb_r16(buf + 21);
    a->players = buf[23];
    a->max = buf[24];
    a->state = buf[25];
    char t[LANB_EVENT_MAX + 1];
    memcpy(t, buf + 26, LANB_NAME_MAX); t[LANB_NAME_MAX] = 0;
    lanb_clean(a->name, t, LANB_NAME_MAX);
    memcpy(t, buf + 50, LANB_EVENT_MAX); t[LANB_EVENT_MAX] = 0;
    lanb_clean(a->event, t, LANB_EVENT_MAX);
    if (!a->name[0]) snprintf(a->name, sizeof a->name, "LAN game");
    if (a->room_port == 0) return 0;
    return 1;
}

static inline void lanb_reset(lanb_list* l, uint32_t nonce) { memset(l, 0, sizeof *l); l->nonce = nonce; }

/* Sort: same version first, then by name, then address (a stable order while the list refreshes). */
static inline int lanb_before(const lanb_entry* x, const lanb_entry* y)
{
    const int xv = x->a.ver == LANB_VERSION, yv = y->a.ver == LANB_VERSION;
    if (xv != yv) return xv > yv;
    const int c = strcmp(x->a.name, y->a.name);
    if (c) return c < 0;
    const int m = memcmp(x->ip, y->ip, 4);
    if (m) return m < 0;
    return x->a.room_port < y->a.room_port;
}

static inline void lanb_sort(lanb_list* l)
{
    for (int i = 1; i < l->n; i++)
        for (int j = i; j > 0 && lanb_before(&l->e[j], &l->e[j - 1]); j--) {
            lanb_entry t = l->e[j]; l->e[j] = l->e[j - 1]; l->e[j - 1] = t;
        }
}

static inline int lanb_loopback(const uint8_t ip[4]) { return ip[0] == 127; }

/* An answer from ip at now_ms. Keyed by the host's session (one host answers once per path: a host on
 * this PC answers both the loopback query and the broadcast, Klp1b showed it listed twice), else by
 * address and room port (a host's new session replaces its old one). Of two paths the LAN address is
 * kept: it is the one other PCs see. Returns the entry's index after sorting, or -1 when full. */
static inline int lanb_add(lanb_list* l, const uint8_t ip[4], const lanb_answer* a, uint32_t now_ms)
{
    int k = -1;
    if (a->session)
        for (int i = 0; i < l->n; i++)
            if (l->e[i].a.session == a->session && l->e[i].a.room_port == a->room_port) { k = i; break; }
    if (k < 0)
        for (int i = 0; i < l->n; i++)
            if (!memcmp(l->e[i].ip, ip, 4) && l->e[i].a.room_port == a->room_port) { k = i; break; }
    if (k < 0) {
        if (l->n >= LANB_MAX) return -1;
        k = l->n++;
        memcpy(l->e[k].ip, ip, 4);
    }
    lanb_entry* e = &l->e[k];
    if (!(lanb_loopback(ip) && !lanb_loopback(e->ip) && e->a.session == a->session)) memcpy(e->ip, ip, 4);
    e->a = *a;
    e->seen_ms = now_ms;
    e->ping_ms = now_ms - a->sent_ms;   /* our own clock, echoed */
    if (e->ping_ms > 9999) e->ping_ms = 9999;
    const lanb_entry key = *e;
    lanb_sort(l);
    for (int i = 0; i < l->n; i++)
        if (!memcmp(l->e[i].ip, key.ip, 4) && l->e[i].a.room_port == key.a.room_port && l->e[i].a.session == key.a.session)
            return i;
    return -1;
}

/* Drops entries not heard from for LANB_EXPIRE_MS; returns how many went. */
static inline int lanb_expire(lanb_list* l, uint32_t now_ms)
{
    int w = 0, gone = 0;
    for (int i = 0; i < l->n; i++) {
        if (now_ms - l->e[i].seen_ms > LANB_EXPIRE_MS) { gone++; continue; }
        l->e[w++] = l->e[i];
    }
    l->n = w;
    return gone;
}

/* Can this entry be joined: same version, a room port, not full. */
static inline int lanb_joinable(const lanb_entry* e)
{
    return e->a.ver == LANB_VERSION && e->a.room_port && (e->a.max == 0 || e->a.players < e->a.max);
}

/* The row's two texts: the label (host name) and the value (event, players x/max, ping). */
static inline void lanb_row_label(const lanb_entry* e, char* out, size_t cap)
{
    snprintf(out, cap, "%s", e->a.name);
}

static inline void lanb_row_value(const lanb_entry* e, char* out, size_t cap)
{
    if (e->a.ver != LANB_VERSION) { snprintf(out, cap, "Different version"); return; }
    const char* ev = e->a.event[0] ? e->a.event
                   : e->a.state == LANB_STATE_RACING ? "Racing"
                   : e->a.state == LANB_STATE_STARTING ? "Starting" : "Lobby";
    if (e->a.max) snprintf(out, cap, "%s  %u/%u  %u ms", ev, e->a.players, e->a.max, e->ping_ms);
    else snprintf(out, cap, "%s  %u  %u ms", ev, e->a.players, e->ping_ms);
}

/* "a.b.c.d:port" of an entry's room server, for PSNR_SERVER. */
static inline void lanb_server(const lanb_entry* e, char* out, size_t cap)
{
    snprintf(out, cap, "%u.%u.%u.%u:%u", e->ip[0], e->ip[1], e->ip[2], e->ip[3], e->a.room_port);
}

/* A host's display name from settings.ini "lanname" or the PC's name: printable, at most 24
 * characters, "LAN game" when nothing is left. */
static inline void lanb_host_name(const char* want, char out[LANB_NAME_MAX + 1])
{
    char t[LANB_NAME_MAX + 1];
    int n = 0;
    if (want) for (; want[n] && n < LANB_NAME_MAX; n++) t[n] = want[n];
    t[n] = 0;
    while (n > 0 && t[n - 1] == ' ') t[--n] = 0;
    const char* s = t;
    while (*s == ' ') s++;
    if (!lanb_clean(out, s, LANB_NAME_MAX)) snprintf(out, LANB_NAME_MAX + 1, "LAN game");
}

#endif
