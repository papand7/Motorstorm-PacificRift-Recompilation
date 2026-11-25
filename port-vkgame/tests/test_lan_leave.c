/* LAN play: leaving a room tells the room server (lan_room_net.h), and the other member sees it.
 *
 * Loopback, Windows. The room server runs on a thread. A "host" uses the framework's psnr client
 * directly (psnr.c) and creates a room. The "guest" is the framework's np_psnr connection (np_psnr.c,
 * the one the game's Matching2 module uses): it connects, joins the room, then np_psnr_disconnect()
 * is the leave. The checks:
 *   - the host sees MEMBER_JOINED when the guest joins, and the room lists two members;
 *   - after the guest's disconnect the host sees MEMBER_LEFT and the room lists one member;
 *   - a later np_psnr_connect with retry off does not reconnect (the leave is final until Join).
 *
 * Build: generated/analysis/lan_menu/tools/build_tests.cmd */
#include "lan_room_net.h"
#include "np_psnr.h"

#include <stdio.h>
#include <string.h>

#define TEST_PORT 36196
#define COMM      "NPWR00000_00"

static int fails;
#define CHECK(c) do { if (!(c)) { fails++; printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)

const char* np_fake_username(void) { return "PS3Player"; }

static lrn s_room;
static volatile LONG s_quit;

static DWORD WINAPI server_thread(void* v)
{
    (void)v;
    while (!s_quit) lrn_step(&s_room, 5);
    return 0;
}

/* Waits for a push of the given type on psnr client c (other messages are dropped). 1 if it came. */
static int wait_push(psnr_client* c, uint8_t type, DWORD ms)
{
    for (DWORD t = 0; t < ms; t += 5) {
        psnr_msg m;
        while (psnr_poll(c, &m) == 1) {
            const int hit = m.req == 0 && m.type == type;
            psnr_msg_free(&m);
            if (hit) return 1;
        }
        Sleep(5);
    }
    return 0;
}

/* The member count of our room (the first row of a search), or -1. */
static int room_members(psnr_client* c)
{
    uint8_t body[4] = { 0, 0, 0, 10 };
    psnr_msg r;
    if (psnr_call(c, PSNR_SEARCH_ROOMS, body, 4, &r, 2000) != 1) return -1;
    int cur = -1;
    if (r.type == PSNR_ROOM_LIST && r.len >= 29 && psnr_get16(r.data + 2) >= 1) cur = r.data[4 + 8 + 16];
    psnr_msg_free(&r);
    return cur;
}

typedef struct { int got; uint8_t type; } reply_slot;
static void on_reply(void* user, const psnr_msg* m)
{
    reply_slot* s = (reply_slot*)user;
    s->got = 1;
    s->type = m->type;
}

int main(void)
{
    WSADATA w;
    WSAStartup(MAKEWORD(2, 2), &w);
    CHECK(lrn_open(&s_room, TEST_PORT, 1, 1000) == 0);

    HANDLE th = CreateThread(NULL, 0, server_thread, NULL, 0, NULL);

    /* host: the framework's psnr client */
    uint32_t host_uid = 0;
    uint8_t host_ip[4];
    psnr_client* host = psnr_connect("127.0.0.1", TEST_PORT, COMM, "host", 3658, &host_uid, host_ip);
    CHECK(host != NULL);
    if (!host) goto done;

    /* host creates a room of 4: max u8 | flags u32 | external, internal, member blobs (empty) */
    uint8_t create[11] = { 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
    psnr_msg r;
    CHECK(psnr_call(host, PSNR_CREATE_ROOM, create, sizeof create, &r, 2000) == 1 && r.type == PSNR_ROOM_JOINED);
    uint8_t room_id[8];
    if (r.len >= 8) memcpy(room_id, r.data, 8);
    psnr_msg_free(&r);

    /* guest: the framework's np_psnr connection, to the same server */
    _putenv_s("PS3_NET_ONLINE", "1");
    _putenv_s("PSNR_SERVER", "127.0.0.1:36196");
    CHECK(np_psnr_connect(COMM) == 0 && np_psnr_connected());

    /* guest joins: room u64 | member blob (empty) */
    uint8_t join[10];
    memcpy(join, room_id, 8);
    join[8] = 0; join[9] = 0;
    reply_slot rs = { 0, 0 };
    CHECK(np_psnr_request(PSNR_JOIN_ROOM, join, sizeof join, on_reply, &rs) != 0);
    for (int i = 0; i < 600 && !rs.got; i++) { np_psnr_pump(); Sleep(5); }
    CHECK(rs.got && rs.type == PSNR_ROOM_JOINED);

    CHECK(wait_push(host, PSNR_MEMBER_JOINED, 2000));
    CHECK(room_members(host) == 2);

    /* the leave: the connection closes; the server removes the guest and tells the host */
    np_psnr_retry_on(0);
    np_psnr_disconnect();
    CHECK(!np_psnr_connected());
    CHECK(wait_push(host, PSNR_MEMBER_LEFT, 2000));
    CHECK(room_members(host) == 1);

    /* retry off after the leave: no reconnect until the player joins again */
    CHECK(np_psnr_connect(COMM) == -1 && !np_psnr_connected());

    psnr_close(host);
done:
    s_quit = 1;
    WaitForSingleObject(th, 3000);
    CloseHandle(th);
    lrn_close(&s_room);
    WSACleanup();
    printf("test_lan_leave: %d failure(s)\n", fails);
    return fails ? 1 : 0;
}
