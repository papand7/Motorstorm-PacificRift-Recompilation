/* LAN play: the room server a hosting PC runs for the game's own Matching2 rooms.
 *
 * The framework's sceNpMatching2 (ps3recomp-vkgame/libs/network/sceNpMatching2.c) keeps the game's
 * rooms on a psnr server (libs/network/psnr/psnr.h, np_psnr.c). This is the part of that protocol
 * the Matching2 module uses, written from the client's side of it (the payload comments in
 * sceNpMatching2.c and psnr.c), our own code: HELLO, HEARTBEAT, CREATE_ROOM, SEARCH_ROOMS,
 * JOIN_ROOM, LEAVE_ROOM, SET_ROOM_DATA, ROOM_MESSAGE, KICK_MEMBER and the pushes they cause.
 * Not served: scores, the relay and UDP NAT probes (players on one LAN reach each other directly).
 *
 * Frames: type u8 | len u16 | body. Requests and replies carry req u32 first (counted in len),
 * pushes (0xAx) do not. Attribute blobs are opaque here, as on psnr.
 *
 * The host's own game connects over loopback. Its address in a member entry would then read
 * 127.0.0.1 for a player on another PC, so for such a reader it is replaced by the address that
 * reader reached this server at (the host's LAN address as that reader sees it).
 *
 * Socket-free and single-threaded: lan_play.cpp owns the sockets and calls lr_feed / drains each
 * client's out buffer; port-vkgame/tests/test_lan_room.c drives it directly. */
#ifndef LAN_ROOM_H
#define LAN_ROOM_H

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define LR_CLIENTS 16
#define LR_ROOMS   8
#define LR_MEMBERS 16
#define LR_BLOB_MAX 8192
#define LR_FRAME_MAX 0xFFFF

enum {
    LR_HELLO = 0x01, LR_HEARTBEAT = 0x02,
    LR_CREATE_ROOM = 0x10, LR_SEARCH_ROOMS = 0x11, LR_JOIN_ROOM = 0x12, LR_LEAVE_ROOM = 0x13,
    LR_SET_ROOM_DATA = 0x14, LR_ROOM_MESSAGE = 0x15, LR_KICK_MEMBER = 0x16,
    LR_HELLO_ACK = 0x81, LR_ERROR = 0x8F, LR_ROOM_JOINED = 0x90, LR_ROOM_LIST = 0x91, LR_OK = 0x93,
    LR_MEMBER_JOINED = 0xA1, LR_MEMBER_LEFT = 0xA2, LR_ROOM_DATA = 0xA3, LR_ROOM_MSG = 0xA4, LR_KICKED = 0xA5
};
enum { LR_E_BAD_REQUEST = 1, LR_E_NOT_FOUND = 2, LR_E_ROOM_FULL = 3, LR_E_NOT_OWNER = 4,
       LR_E_NOT_IN_ROOM = 5, LR_E_LIMIT = 6, LR_E_NO_HELLO = 7, LR_E_NAME_TAKEN = 8 };

typedef struct { uint8_t* b; size_t n, cap; } lr_buf;

typedef struct {
    int used, hello;
    uint32_t user, token;
    char comm[13], name[17];
    uint8_t ip[4], local_ip[4];   /* the peer's address, and this server's address on that connection */
    uint16_t p2p;
    int room;                     /* room index, or -1 */
    uint16_t member;              /* member id in that room */
    lr_buf data;                  /* member data blob */
    lr_buf rx, out;
} lr_client;

typedef struct {
    int used;
    uint64_t id;
    char comm[13];
    uint8_t max;
    uint32_t flags;
    lr_buf ext, in;
    int m[LR_MEMBERS], n;         /* client indices, in join order */
    uint16_t owner, next_member;
} lr_room;

typedef struct {
    lr_client c[LR_CLIENTS];
    lr_room r[LR_ROOMS];
    uint32_t next_user;
    uint64_t next_room;
} lr_server;

/* ---- buffers ---- */
static inline int lr_put(lr_buf* b, const void* p, size_t n)
{
    if (b->n + n > b->cap) {
        size_t cap = b->cap ? b->cap : 256;
        while (cap < b->n + n) cap *= 2;
        uint8_t* nb = (uint8_t*)realloc(b->b, cap);
        if (!nb) return -1;
        b->b = nb; b->cap = cap;
    }
    if (n) memcpy(b->b + b->n, p, n);
    b->n += n;
    return 0;
}
static inline void lr_free(lr_buf* b) { free(b->b); b->b = NULL; b->n = b->cap = 0; }
static inline void lr_set(lr_buf* b, const uint8_t* p, size_t n) { b->n = 0; lr_put(b, p, n); }
static inline void lr_u8(lr_buf* b, uint32_t v) { uint8_t t = (uint8_t)v; lr_put(b, &t, 1); }
static inline void lr_u16(lr_buf* b, uint32_t v) { uint8_t t[2] = { (uint8_t)(v >> 8), (uint8_t)v }; lr_put(b, t, 2); }
static inline void lr_u32(lr_buf* b, uint32_t v) { lr_u16(b, v >> 16); lr_u16(b, v); }
static inline void lr_u64(lr_buf* b, uint64_t v) { lr_u32(b, (uint32_t)(v >> 32)); lr_u32(b, (uint32_t)v); }
static inline void lr_fixed(lr_buf* b, const char* s, size_t n)
{
    uint8_t t[32] = { 0 };
    size_t k = strlen(s);
    memcpy(t, s, k < n ? k : n);
    lr_put(b, t, n);
}
static inline uint32_t lr_g16(const uint8_t* p) { return (uint32_t)p[0] << 8 | p[1]; }
static inline uint32_t lr_g32(const uint8_t* p) { return lr_g16(p) << 16 | lr_g16(p + 2); }
static inline uint64_t lr_g64(const uint8_t* p) { return (uint64_t)lr_g32(p) << 32 | lr_g32(p + 4); }

/* A frame to client c: reply (with req) or push (req ignored). */
static inline void lr_send(lr_server* s, int c, uint8_t type, uint32_t req, const lr_buf* body)
{
    const int push = (type & 0xF0) == 0xA0;
    const size_t len = (body ? body->n : 0) + (push ? 0 : 4);
    if (len > LR_FRAME_MAX) return;
    lr_buf* o = &s->c[c].out;
    lr_u8(o, type);
    lr_u16(o, (uint32_t)len);
    if (!push) lr_u32(o, req);
    if (body && body->n) lr_put(o, body->b, body->n);
}
static inline void lr_error(lr_server* s, int c, uint32_t req, uint32_t code)
{
    lr_buf b = { 0 };
    lr_u32(&b, code);
    lr_send(s, c, LR_ERROR, req, &b);
    lr_free(&b);
}
static inline void lr_ok(lr_server* s, int c, uint32_t req) { lr_send(s, c, LR_OK, req, NULL); }

/* ---- server ---- */
static inline void lr_init(lr_server* s, uint64_t room_seed)
{
    memset(s, 0, sizeof *s);
    s->next_user = 1;
    s->next_room = room_seed ? room_seed : 1;
}

static inline int lr_connect(lr_server* s, const uint8_t ip[4], const uint8_t local_ip[4])
{
    for (int i = 0; i < LR_CLIENTS; i++) {
        if (s->c[i].used) continue;
        lr_client* c = &s->c[i];
        memset(c, 0, sizeof *c);
        c->used = 1;
        c->room = -1;
        memcpy(c->ip, ip, 4);
        memcpy(c->local_ip, local_ip, 4);
        return i;
    }
    return -1;
}

static inline int lr_is_loopback(const uint8_t ip[4]) { return ip[0] == 127; }

/* member entry, as reader sees it: id u16 | user u32 | online_id [16] | ip [4] | port u16 | owner u8 | data */
static inline void lr_member(lr_server* s, lr_buf* b, const lr_room* r, int ci, int reader)
{
    const lr_client* c = &s->c[ci];
    const uint8_t* ip = c->ip;
    if (lr_is_loopback(c->ip) && !lr_is_loopback(s->c[reader].ip)) ip = s->c[reader].local_ip;
    lr_u16(b, c->member);
    lr_u32(b, c->user);
    lr_fixed(b, c->name, 16);
    lr_put(b, ip, 4);
    lr_u16(b, c->p2p);
    lr_u8(b, c->member == r->owner);
    lr_u16(b, (uint32_t)c->data.n);
    lr_put(b, c->data.b, c->data.n);
}

/* ROOM_JOINED: room u64 | me u16 | owner u16 | max u8 | flags u32 | ext blob | int blob | n u8 | members */
static inline void lr_joined(lr_server* s, int ci, uint32_t req)
{
    const lr_room* r = &s->r[s->c[ci].room];
    lr_buf b = { 0 };
    lr_u64(&b, r->id);
    lr_u16(&b, s->c[ci].member);
    lr_u16(&b, r->owner);
    lr_u8(&b, r->max);
    lr_u32(&b, r->flags);
    lr_u16(&b, (uint32_t)r->ext.n); lr_put(&b, r->ext.b, r->ext.n);
    lr_u16(&b, (uint32_t)r->in.n);  lr_put(&b, r->in.b, r->in.n);
    lr_u8(&b, (uint32_t)r->n);
    for (int k = 0; k < r->n; k++) lr_member(s, &b, r, r->m[k], ci);
    lr_send(s, ci, LR_ROOM_JOINED, req, &b);
    lr_free(&b);
}

/* Leaves its room (by choice, kick or disconnect): MEMBER_LEFT to the rest, the owner passes to
 * the longest-standing member, an empty room goes. */
static inline void lr_leave(lr_server* s, int ci)
{
    lr_client* c = &s->c[ci];
    if (c->room < 0) return;
    lr_room* r = &s->r[c->room];
    int w = 0;
    for (int k = 0; k < r->n; k++) if (r->m[k] != ci) r->m[w++] = r->m[k];
    r->n = w;
    c->room = -1;
    if (!r->n) { lr_free(&r->ext); lr_free(&r->in); memset(r, 0, sizeof *r); return; }
    if (c->member == r->owner) r->owner = s->c[r->m[0]].member;
    lr_buf b = { 0 };
    lr_u64(&b, r->id);
    lr_u16(&b, c->member);
    lr_u16(&b, r->owner);
    for (int k = 0; k < r->n; k++) lr_send(s, r->m[k], LR_MEMBER_LEFT, 0, &b);
    lr_free(&b);
}

static inline void lr_disconnect(lr_server* s, int ci)
{
    if (ci < 0 || ci >= LR_CLIENTS || !s->c[ci].used) return;
    lr_leave(s, ci);
    lr_client* c = &s->c[ci];
    lr_free(&c->data); lr_free(&c->rx); lr_free(&c->out);
    memset(c, 0, sizeof *c);
    c->room = -1;
}

static inline int lr_find_room(lr_server* s, uint64_t id)
{
    for (int i = 0; i < LR_ROOMS; i++) if (s->r[i].used && s->r[i].id == id) return i;
    return -1;
}

/* Reads a u16-length blob at *p; NULL when it runs past end. */
static inline const uint8_t* lr_blob(const uint8_t* p, const uint8_t* end, const uint8_t** data, uint32_t* len)
{
    if (end - p < 2) return NULL;
    *len = lr_g16(p);
    if ((uint32_t)(end - p - 2) < *len || *len > LR_BLOB_MAX) return NULL;
    *data = p + 2;
    return p + 2 + *len;
}

/* One request from client ci. */
static inline void lr_request(lr_server* s, int ci, uint8_t type, uint32_t req, const uint8_t* d, uint32_t n)
{
    lr_client* c = &s->c[ci];
    const uint8_t* end = d + n;
    if (type == LR_HEARTBEAT) return;   /* keeps the client's connection; no answer */
    if (type == LR_HELLO) {
        /* HELLO: comm_id [12] | online_id [16] | p2p_port u16 -> user u32 | ip [4] | token u32 | flags u8 */
        if (n < 30 || c->hello) { lr_error(s, ci, req, LR_E_BAD_REQUEST); return; }
        char comm[13] = { 0 }, name[17] = { 0 };
        memcpy(comm, d, 12);
        memcpy(name, d + 12, 16);
        for (int i = 0; i < LR_CLIENTS; i++)
            if (i != ci && s->c[i].used && s->c[i].hello && !strcmp(s->c[i].comm, comm) && !strcmp(s->c[i].name, name)) {
                lr_error(s, ci, req, LR_E_NAME_TAKEN);
                return;
            }
        memcpy(c->comm, comm, 13);
        memcpy(c->name, name, 17);
        c->p2p = (uint16_t)lr_g16(d + 28);
        c->user = s->next_user++;
        c->token = c->user * 2654435761u ^ 0x5A17C0DEu;
        c->hello = 1;
        lr_buf b = { 0 };
        lr_u32(&b, c->user);
        lr_put(&b, c->ip, 4);
        lr_u32(&b, c->token);
        lr_u8(&b, 0);   /* no relay */
        lr_send(s, ci, LR_HELLO_ACK, req, &b);
        lr_free(&b);
        return;
    }
    if (!c->hello) { lr_error(s, ci, req, LR_E_NO_HELLO); return; }

    switch (type) {
    case LR_CREATE_ROOM: {
        /* max u8 | flags u32 | external blob | internal blob | member data blob */
        const uint8_t *ext, *in, *mine, *p = d + 5;
        uint32_t le, li, lm;
        if (n < 5 || !(p = lr_blob(p, end, &ext, &le)) || !(p = lr_blob(p, end, &in, &li)) ||
            !(p = lr_blob(p, end, &mine, &lm))) { lr_error(s, ci, req, LR_E_BAD_REQUEST); return; }
        int k = -1;
        for (int i = 0; i < LR_ROOMS; i++) if (!s->r[i].used) { k = i; break; }
        if (k < 0) { lr_error(s, ci, req, LR_E_LIMIT); return; }
        lr_leave(s, ci);
        lr_room* r = &s->r[k];
        memset(r, 0, sizeof *r);
        r->used = 1;
        r->id = s->next_room++;
        memcpy(r->comm, c->comm, 13);
        r->max = d[0] ? d[0] : 1;
        if (r->max > LR_MEMBERS) r->max = LR_MEMBERS;
        r->flags = lr_g32(d + 1);
        lr_set(&r->ext, ext, le);
        lr_set(&r->in, in, li);
        r->next_member = 1;
        c->member = r->next_member++;
        r->owner = c->member;
        r->m[r->n++] = ci;
        c->room = k;
        lr_set(&c->data, mine, lm);
        lr_joined(s, ci, req);
        return;
    }
    case LR_SEARCH_ROOMS: {
        /* start u16 | max u16 -> total u16 | count u16 | (room u64 | owner [16] | cur u8 | max u8 | flags u32 | ext blob)... */
        if (n < 4) { lr_error(s, ci, req, LR_E_BAD_REQUEST); return; }
        const uint32_t start = lr_g16(d), want = lr_g16(d + 2);
        uint32_t total = 0, count = 0;
        lr_buf rows = { 0 };
        for (int i = 0; i < LR_ROOMS; i++) {
            const lr_room* r = &s->r[i];
            if (!r->used || strcmp(r->comm, c->comm)) continue;
            if (total++ < start || count >= want) continue;
            count++;
            const char* owner = "";
            for (int k = 0; k < r->n; k++) if (s->c[r->m[k]].member == r->owner) owner = s->c[r->m[k]].name;
            lr_u64(&rows, r->id);
            lr_fixed(&rows, owner, 16);
            lr_u8(&rows, (uint32_t)r->n);
            lr_u8(&rows, r->max);
            lr_u32(&rows, r->flags);
            lr_u16(&rows, (uint32_t)r->ext.n);
            lr_put(&rows, r->ext.b, r->ext.n);
        }
        lr_buf b = { 0 };
        lr_u16(&b, total);
        lr_u16(&b, count);
        lr_put(&b, rows.b, rows.n);
        lr_send(s, ci, LR_ROOM_LIST, req, &b);
        lr_free(&b); lr_free(&rows);
        return;
    }
    case LR_JOIN_ROOM: {
        /* room u64 | member data blob */
        const uint8_t* mine;
        uint32_t lm;
        if (n < 8 || !lr_blob(d + 8, end, &mine, &lm)) { lr_error(s, ci, req, LR_E_BAD_REQUEST); return; }
        const int k = lr_find_room(s, lr_g64(d));
        if (k < 0 || strcmp(s->r[k].comm, c->comm)) { lr_error(s, ci, req, LR_E_NOT_FOUND); return; }
        lr_room* r = &s->r[k];
        if (c->room == k) { lr_joined(s, ci, req); return; }
        if (r->n >= r->max) { lr_error(s, ci, req, LR_E_ROOM_FULL); return; }
        lr_leave(s, ci);
        c->member = r->next_member++;
        lr_set(&c->data, mine, lm);
        r->m[r->n++] = ci;
        c->room = k;
        lr_joined(s, ci, req);
        for (int m = 0; m < r->n; m++) {
            if (r->m[m] == ci) continue;
            lr_buf b = { 0 };
            lr_u64(&b, r->id);
            lr_member(s, &b, r, ci, r->m[m]);
            lr_send(s, r->m[m], LR_MEMBER_JOINED, 0, &b);
            lr_free(&b);
        }
        return;
    }
    default:
        break;
    }

    /* The rest name a room the client must be in: room u64 first. */
    if (n < 8) { lr_error(s, ci, req, LR_E_BAD_REQUEST); return; }
    const int k = lr_find_room(s, lr_g64(d));
    if (k < 0) { lr_error(s, ci, req, LR_E_NOT_FOUND); return; }
    if (c->room != k) { lr_error(s, ci, req, LR_E_NOT_IN_ROOM); return; }
    lr_room* r = &s->r[k];
    switch (type) {
    case LR_LEAVE_ROOM:
        lr_leave(s, ci);
        lr_ok(s, ci, req);
        return;
    case LR_SET_ROOM_DATA: {
        /* room u64 | which u8 (0 external, 1 internal, 2 flags) | blob; pushed to the others */
        const uint8_t* blob;
        uint32_t l;
        if (n < 9 || d[8] > 2 || !lr_blob(d + 9, end, &blob, &l) || (d[8] == 2 && l != 4)) {
            lr_error(s, ci, req, LR_E_BAD_REQUEST);
            return;
        }
        if (d[8] == 0) lr_set(&r->ext, blob, l);
        else if (d[8] == 1) lr_set(&r->in, blob, l);
        else r->flags = lr_g32(blob);
        lr_ok(s, ci, req);
        lr_buf b = { 0 };
        lr_put(&b, d, 9 + 2 + l);
        for (int m = 0; m < r->n; m++) if (r->m[m] != ci) lr_send(s, r->m[m], LR_ROOM_DATA, 0, &b);
        lr_free(&b);
        return;
    }
    case LR_ROOM_MESSAGE: {
        /* room u64 | to u16 (0 = everyone else) | len u16 | bytes -> ROOM_MSG room u64 | from u16 | to u16 | len u16 | bytes */
        if (n < 12 || 12 + lr_g16(d + 10) > n) { lr_error(s, ci, req, LR_E_BAD_REQUEST); return; }
        const uint32_t to = lr_g16(d + 8), l = lr_g16(d + 10);
        lr_buf b = { 0 };
        lr_u64(&b, r->id);
        lr_u16(&b, c->member);
        lr_u16(&b, to);
        lr_u16(&b, l);
        lr_put(&b, d + 12, l);
        for (int m = 0; m < r->n; m++) {
            const lr_client* t = &s->c[r->m[m]];
            if (r->m[m] != ci && (!to || t->member == to)) lr_send(s, r->m[m], LR_ROOM_MSG, 0, &b);
        }
        lr_free(&b);
        lr_ok(s, ci, req);
        return;
    }
    case LR_KICK_MEMBER: {
        if (n < 10) { lr_error(s, ci, req, LR_E_BAD_REQUEST); return; }
        if (c->member != r->owner) { lr_error(s, ci, req, LR_E_NOT_OWNER); return; }
        const uint32_t target = lr_g16(d + 8);
        int t = -1;
        for (int m = 0; m < r->n; m++) if (s->c[r->m[m]].member == target) t = r->m[m];
        if (t < 0 || t == ci) { lr_error(s, ci, req, LR_E_NOT_FOUND); return; }
        lr_buf b = { 0 };
        lr_u64(&b, r->id);
        lr_send(s, t, LR_KICKED, 0, &b);
        lr_free(&b);
        lr_leave(s, t);
        lr_ok(s, ci, req);
        return;
    }
    default:
        lr_error(s, ci, req, LR_E_BAD_REQUEST);
        return;
    }
}

/* Bytes from client ci's socket: every complete frame is handled. -1: a frame too short to carry
 * its request id (the socket layer closes the connection). */
static inline int lr_feed(lr_server* s, int ci, const uint8_t* bytes, size_t n)
{
    lr_client* c = &s->c[ci];
    if (lr_put(&c->rx, bytes, n)) return -1;
    size_t off = 0;
    while (c->rx.n - off >= 3) {
        const uint8_t type = c->rx.b[off];
        const uint32_t len = lr_g16(c->rx.b + off + 1);
        if (c->rx.n - off < 3 + (size_t)len) break;
        if (len < 4) return -1;
        const uint8_t* p = c->rx.b + off + 3;
        lr_request(s, ci, type, lr_g32(p), p + 4, len - 4);
        c = &s->c[ci];
        off += 3 + (size_t)len;
    }
    memmove(c->rx.b, c->rx.b + off, c->rx.n - off);
    c->rx.n -= off;
    return 0;
}

/* For the discovery answer: the largest room of this title (players, max), or 0 when none. */
static inline int lr_room_info(const lr_server* s, const char* comm, int* players, int* max)
{
    int best = -1;
    for (int i = 0; i < LR_ROOMS; i++)
        if (s->r[i].used && (!comm || !comm[0] || !strcmp(s->r[i].comm, comm)) && (best < 0 || s->r[i].n > s->r[best].n))
            best = i;
    if (best < 0) return 0;
    *players = s->r[best].n;
    *max = s->r[best].max;
    return 1;
}

static inline void lr_shutdown(lr_server* s)
{
    for (int i = 0; i < LR_CLIENTS; i++) if (s->c[i].used) lr_disconnect(s, i);
}

#endif
