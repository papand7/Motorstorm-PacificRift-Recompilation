/* LAN play room server (port-vkgame/lan_room.h, lan_room_net.h).
 *  1. protocol, socket-free: frames in, frames out, parsed the way sceNpMatching2.c parses them;
 *  2. loopback, Windows: the framework's own psnr client (ps3recomp-vkgame/libs/network/psnr/psnr.c)
 *     against lan_room_net.h on 127.0.0.1, an ephemeral port, a server thread that stops with the test.
 * Build: generated/analysis/pcmenu/tools/build_tests.cmd */
#include "lan_room_net.h"

#include <stdio.h>

static int fails;
#define CHECK(c) do { if (!(c)) { fails++; printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)

/* ---- 1. socket-free ---- */
typedef struct { uint8_t type; uint32_t req; const uint8_t* d; uint32_t n; } frame;

/* The next frame queued for client c (consumed). */
static int next(lr_server* s, int c, frame* f, size_t* off)
{
    lr_buf* o = &s->c[c].out;
    if (*off + 3 > o->n) return 0;
    const uint8_t* p = o->b + *off;
    uint32_t len = lr_g16(p + 1);
    f->type = p[0];
    f->req = 0;
    f->d = p + 3;
    f->n = len;
    if ((f->type & 0xF0) != 0xA0) { f->req = lr_g32(p + 3); f->d += 4; f->n -= 4; }
    *off += 3 + len;
    return 1;
}
static void clear(lr_server* s, int c, size_t* off) { s->c[c].out.n = 0; *off = 0; }

static void req(lr_server* s, int c, uint8_t type, uint32_t id, const uint8_t* body, uint32_t n)
{
    uint8_t f[512];
    f[0] = type;
    f[1] = (uint8_t)((n + 4) >> 8); f[2] = (uint8_t)(n + 4);
    f[3] = (uint8_t)(id >> 24); f[4] = (uint8_t)(id >> 16); f[5] = (uint8_t)(id >> 8); f[6] = (uint8_t)id;
    memcpy(f + 7, body, n);
    /* fed in two pieces: framing must survive a split */
    CHECK(lr_feed(s, c, f, 2) == 0);
    CHECK(lr_feed(s, c, f + 2, 7 + n - 2) == 0);
}

static void hello(lr_server* s, int c, const char* name, uint16_t p2p)
{
    uint8_t b[30] = { 0 };
    memcpy(b, "NPWR00000_00", 12);
    strncpy((char*)b + 12, name, 16);
    b[28] = (uint8_t)(p2p >> 8); b[29] = (uint8_t)p2p;
    req(s, c, LR_HELLO, 1, b, 30);
}

static void protocol(void)
{
    lr_server s;
    lr_init(&s, 1000);
    const uint8_t lo[4] = { 127, 0, 0, 1 }, lan_host[4] = { 192, 168, 1, 10 }, lan_peer[4] = { 192, 168, 1, 22 };
    const int h = lr_connect(&s, lo, lo);            /* the host's own game */
    const int j = lr_connect(&s, lan_peer, lan_host); /* a PC on the LAN; it reached us at .10 */
    CHECK(h == 0 && j == 1);
    size_t oh = 0, oj = 0;
    frame f;

    /* before HELLO */
    uint8_t s4[4] = { 0, 0, 0, 10 };
    req(&s, h, LR_SEARCH_ROOMS, 9, s4, 4);
    CHECK(next(&s, h, &f, &oh) && f.type == LR_ERROR && f.req == 9 && lr_g32(f.d) == LR_E_NO_HELLO);
    clear(&s, h, &oh);

    hello(&s, h, "host", 3658);
    CHECK(next(&s, h, &f, &oh) && f.type == LR_HELLO_ACK && f.req == 1 && f.n >= 13);
    CHECK(lr_g32(f.d) == 1 && !memcmp(f.d + 4, lo, 4) && f.d[12] == 0);
    hello(&s, j, "host", 3659);                      /* same name, same title: refused */
    CHECK(next(&s, j, &f, &oj) && f.type == LR_ERROR && lr_g32(f.d) == LR_E_NAME_TAKEN);
    clear(&s, j, &oj);
    s.c[j].hello = 0;
    hello(&s, j, "guest", 3659);
    CHECK(next(&s, j, &f, &oj) && f.type == LR_HELLO_ACK && lr_g32(f.d) == 2);
    clear(&s, h, &oh); clear(&s, j, &oj);

    /* CREATE_ROOM: max 4 | flags | ext {id 0x4C int 7} | int {} | member data {} */
    uint8_t cr[64], *p = cr;
    *p++ = 4;
    *p++ = 0; *p++ = 0; *p++ = 0; *p++ = 0x20;
    *p++ = 0; *p++ = 7; *p++ = 0; *p++ = 0x4C; *p++ = 0; *p++ = 0; *p++ = 0; *p++ = 0; *p++ = 7;
    *p++ = 0; *p++ = 0;
    *p++ = 0; *p++ = 0;
    req(&s, h, LR_CREATE_ROOM, 2, cr, (uint32_t)(p - cr));
    CHECK(next(&s, h, &f, &oh) && f.type == LR_ROOM_JOINED && f.req == 2);
    const uint64_t room = lr_g64(f.d);
    CHECK(room == 1000);
    CHECK(lr_g16(f.d + 8) == 1 && lr_g16(f.d + 10) == 1 && f.d[12] == 4 && lr_g32(f.d + 13) == 0x20);
    CHECK(lr_g16(f.d + 17) == 7);                     /* ext blob kept */
    clear(&s, h, &oh);
    int pl = 0, mx = 0;
    CHECK(lr_room_info(&s, "NPWR00000_00", &pl, &mx) && pl == 1 && mx == 4);

    /* SEARCH_ROOMS from the LAN player */
    req(&s, j, LR_SEARCH_ROOMS, 3, s4, 4);
    CHECK(next(&s, j, &f, &oj) && f.type == LR_ROOM_LIST && f.req == 3);
    CHECK(lr_g16(f.d) == 1 && lr_g16(f.d + 2) == 1);
    CHECK(lr_g64(f.d + 4) == room && !strcmp((const char*)f.d + 12, "host") && f.d[28] == 1 && f.d[29] == 4);
    CHECK(lr_g16(f.d + 34) == 7);
    clear(&s, j, &oj);

    /* JOIN_ROOM: the joiner gets ROOM_JOINED with both members; the host a MEMBER_JOINED push */
    uint8_t jr[10];
    for (int i = 0; i < 8; i++) jr[i] = (uint8_t)(room >> (56 - 8 * i));
    jr[8] = 0; jr[9] = 0;
    req(&s, j, LR_JOIN_ROOM, 4, jr, 10);
    CHECK(next(&s, j, &f, &oj) && f.type == LR_ROOM_JOINED && f.req == 4);
    CHECK(lr_g16(f.d + 8) == 2 && lr_g16(f.d + 10) == 1);
    {
        const uint8_t* m = f.d + 17;
        m += 2 + lr_g16(m);
        m += 2 + lr_g16(m);
        CHECK(*m == 2);
        m++;
        /* first member: the host, seen from the LAN at the address the joiner reached us at */
        CHECK(lr_g16(m) == 1 && !strcmp((const char*)m + 6, "host") && !memcmp(m + 22, lan_host, 4));
        CHECK(lr_g16(m + 26) == 3658 && m[28] == 1);
        m += 31 + lr_g16(m + 29);
        CHECK(lr_g16(m) == 2 && !strcmp((const char*)m + 6, "guest") && !memcmp(m + 22, lan_peer, 4) && m[28] == 0);
    }
    CHECK(next(&s, h, &f, &oh) && f.type == LR_MEMBER_JOINED && f.req == 0);
    CHECK(lr_g64(f.d) == room && lr_g16(f.d + 8) == 2 && !memcmp(f.d + 8 + 22, lan_peer, 4));
    clear(&s, h, &oh); clear(&s, j, &oj);

    /* full: a third player cannot join a room of 2 */
    s.r[0].max = 2;
    const uint8_t ip3[4] = { 192, 168, 1, 30 };
    const int t = lr_connect(&s, ip3, lan_host);
    size_t ot = 0;
    hello(&s, t, "third", 3660);
    clear(&s, t, &ot);
    req(&s, t, LR_JOIN_ROOM, 5, jr, 10);
    CHECK(next(&s, t, &f, &ot) && f.type == LR_ERROR && lr_g32(f.d) == LR_E_ROOM_FULL);
    clear(&s, t, &ot);
    s.r[0].max = 4;

    /* SET_ROOM_DATA internal: OK to the writer, ROOM_DATA push to the other */
    uint8_t sd[16];
    memcpy(sd, jr, 8);
    sd[8] = 1; sd[9] = 0; sd[10] = 3; sd[11] = 0xAA; sd[12] = 0xBB; sd[13] = 0xCC;
    req(&s, h, LR_SET_ROOM_DATA, 6, sd, 14);
    CHECK(next(&s, h, &f, &oh) && f.type == LR_OK && f.req == 6);
    CHECK(next(&s, j, &f, &oj) && f.type == LR_ROOM_DATA && f.n == 14 && f.d[8] == 1 && f.d[13] == 0xCC);
    clear(&s, h, &oh); clear(&s, j, &oj);

    /* ROOM_MESSAGE to everyone */
    uint8_t rm[16];
    memcpy(rm, jr, 8);
    rm[8] = 0; rm[9] = 0; rm[10] = 0; rm[11] = 2; rm[12] = 'h'; rm[13] = 'i';
    req(&s, j, LR_ROOM_MESSAGE, 7, rm, 14);
    CHECK(next(&s, j, &f, &oj) && f.type == LR_OK);
    CHECK(next(&s, h, &f, &oh) && f.type == LR_ROOM_MSG && lr_g16(f.d + 8) == 2 && lr_g16(f.d + 12) == 2 && f.d[14] == 'h');
    clear(&s, h, &oh); clear(&s, j, &oj);

    /* KICK by a non-owner is refused */
    uint8_t kk[10];
    memcpy(kk, jr, 8); kk[8] = 0; kk[9] = 1;
    req(&s, j, LR_KICK_MEMBER, 8, kk, 10);
    CHECK(next(&s, j, &f, &oj) && f.type == LR_ERROR && lr_g32(f.d) == LR_E_NOT_OWNER);
    clear(&s, j, &oj);

    /* the host drops: the guest owns the room now */
    lr_disconnect(&s, h);
    CHECK(next(&s, j, &f, &oj) && f.type == LR_MEMBER_LEFT && lr_g16(f.d + 8) == 1 && lr_g16(f.d + 10) == 2);
    clear(&s, j, &oj);
    /* LEAVE: the room empties and goes */
    req(&s, j, LR_LEAVE_ROOM, 9, jr, 8);
    CHECK(next(&s, j, &f, &oj) && f.type == LR_OK && f.req == 9);
    CHECK(!lr_room_info(&s, NULL, &pl, &mx));
    clear(&s, j, &oj);
    req(&s, j, LR_LEAVE_ROOM, 10, jr, 8);
    CHECK(next(&s, j, &f, &oj) && f.type == LR_ERROR && lr_g32(f.d) == LR_E_NOT_FOUND);

    /* a frame too short for its request id closes the connection */
    uint8_t bad[3] = { LR_SEARCH_ROOMS, 0, 2 };
    uint8_t bad2[2] = { 0, 0 };
    CHECK(lr_feed(&s, j, bad, 3) == 0);
    CHECK(lr_feed(&s, j, bad2, 2) == -1);
    lr_shutdown(&s);
}

/* ---- 2. loopback with the framework's psnr client ---- */
#ifdef _WIN32
#include "psnr/psnr.h"

static volatile LONG s_stop;
static DWORD WINAPI server_thread(void* v)
{
    lrn* n = (lrn*)v;
    while (!s_stop) lrn_step(n, 10);
    return 0;
}

static int wait_push(psnr_client* c, uint8_t type, psnr_msg* m)
{
    for (int i = 0; i < 300; i++) {
        int r = psnr_poll(c, m);
        if (r < 0) return 0;
        if (r == 1) {
            if (m->type == type) return 1;
            psnr_msg_free(m);
            continue;
        }
        Sleep(10);
    }
    return 0;
}

static void loopback(void)
{
    static lrn n;
    if (lrn_open(&n, 0, 1, 500)) { fails++; printf("FAIL: cannot listen on 127.0.0.1\n"); return; }
    HANDLE th = CreateThread(NULL, 0, server_thread, &n, 0, NULL);
    uint32_t uh = 0, uj = 0;
    uint8_t ip[4];
    psnr_client* host = psnr_connect("127.0.0.1", n.port, "NPWR00000_00", "host", 3658, &uh, ip);
    psnr_client* join = psnr_connect("127.0.0.1", n.port, "NPWR00000_00", "guest", 3659, &uj, ip);
    CHECK(host && join && uh == 1 && uj == 2 && ip[0] == 127);
    psnr_client* dup = psnr_connect("127.0.0.1", n.port, "NPWR00000_00", "guest", 3660, NULL, NULL);
    CHECK(!dup && psnr_connect_error() == PSNR_E_NAME_TAKEN);
    if (host && join) {
        psnr_msg m;
        uint8_t cr[] = { 8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
        CHECK(psnr_call(host, PSNR_CREATE_ROOM, cr, sizeof cr, &m, 3000) == 1 && m.type == PSNR_ROOM_JOINED);
        const uint64_t room = m.len >= 8 ? psnr_get64(m.data) : 0;
        CHECK(room == 500);
        psnr_msg_free(&m);
        uint8_t sr[4] = { 0, 0, 0, 100 };
        CHECK(psnr_call(join, PSNR_SEARCH_ROOMS, sr, 4, &m, 3000) == 1 && m.type == PSNR_ROOM_LIST);
        CHECK(m.len >= 4 && psnr_get16(m.data + 2) == 1 && psnr_get64(m.data + 4) == room);
        psnr_msg_free(&m);
        uint8_t jr[10];
        psnr_put64(jr, room);
        jr[8] = jr[9] = 0;
        CHECK(psnr_call(join, PSNR_JOIN_ROOM, jr, 10, &m, 3000) == 1 && m.type == PSNR_ROOM_JOINED);
        CHECK(m.len > 17 && psnr_get16(m.data + 8) == 2);
        psnr_msg_free(&m);
        CHECK(wait_push(host, PSNR_MEMBER_JOINED, &m) && m.req == 0 && psnr_get64(m.data) == room);
        psnr_msg_free(&m);
        uint8_t rm[14];
        psnr_put64(rm, room);
        psnr_put16(rm + 8, 1);
        psnr_put16(rm + 10, 2);
        rm[12] = 'g'; rm[13] = 'o';
        CHECK(psnr_call(join, PSNR_ROOM_MESSAGE, rm, 14, &m, 3000) == 1 && m.type == PSNR_OK);
        psnr_msg_free(&m);
        CHECK(wait_push(host, PSNR_ROOM_MSG, &m) && m.len == 16 && m.data[14] == 'g');
        psnr_msg_free(&m);
        psnr_close(join);   /* dropping out: the host hears MEMBER_LEFT */
        join = NULL;
        CHECK(wait_push(host, PSNR_MEMBER_LEFT, &m) && psnr_get16(m.data + 8) == 2);
        psnr_msg_free(&m);
    }
    if (host) psnr_close(host);
    if (join) psnr_close(join);
    InterlockedExchange(&s_stop, 1);
    WaitForSingleObject(th, 5000);
    CloseHandle(th);
    lrn_close(&n);
}
#endif

int main(void)
{
    protocol();
#ifdef _WIN32
    loopback();
#endif
    printf("test_lan_room: %d failure(s)\n", fails);
    return fails ? 1 : 0;
}
