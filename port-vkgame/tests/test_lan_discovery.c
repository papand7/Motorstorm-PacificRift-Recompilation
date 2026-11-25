/* LAN play discovery over loopback (port-vkgame/lan_discovery.h): a hosting socket answers a query
 * sent to 127.0.0.1, the browsing socket lists the answer with its ping; a second host on the same
 * port is refused. Uses test ports, not LANB_PORT, so a running game is not disturbed.
 * Windows only. Build: generated/analysis/lan_menu/tools/build_tests.cmd */
#include "lan_discovery.h"

#include <stdio.h>

static int fails;
#define CHECK(c) do { if (!(c)) { fails++; printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)

#define TEST_PORT 36199

int main(void)
{
    WSADATA w;
    WSAStartup(MAKEWORD(2, 2), &w);

    SOCKET host = lad_udp(TEST_PORT, 1);
    CHECK(host != INVALID_SOCKET);
    CHECK(lad_udp(TEST_PORT, 1) == INVALID_SOCKET);   /* the port is taken: refused, not shared */

    SOCKET qry = lad_udp(0, 1);
    CHECK(qry != INVALID_SOCKET);

    /* nothing answered yet */
    lanb_list l;
    lanb_reset(&l, 1);
    CHECK(lad_browse_read(qry, &l, 0) == 0 && l.n == 0);

    /* one query to loopback, the host answers it with its session */
    lanb_answer a;
    memset(&a, 0, sizeof a);
    a.ver = LANB_VERSION;
    a.session = 0xABCDEF0123456789ull;
    a.room_port = LANB_ROOM_PORT;
    a.players = 2;
    a.max = 4;
    a.state = LANB_STATE_LOBBY;
    snprintf(a.name, sizeof a.name, "%s", "Test host");

    uint8_t q[LANB_QUERY_LEN];
    const uint8_t loop[4] = { 127, 0, 0, 1 };
    lanb_query(q, 77, 5000);
    lad_send_to(qry, q, LANB_QUERY_LEN, loop, TEST_PORT);

    int served = 0;
    for (int i = 0; i < 200 && served == 0; i++) {
        served = lad_host_serve(host, &a);
        if (!served) Sleep(5);
    }
    CHECK(served == 1);

    int got = 0;
    for (int i = 0; i < 200 && got == 0; i++) {
        got = lad_browse_read(qry, &l, 5012);
        if (!got) Sleep(5);
    }
    CHECK(got == 1 && l.n == 1);
    if (l.n == 1) {
        CHECK(l.e[0].a.session == a.session && l.e[0].a.players == 2 && l.e[0].a.max == 4);
        CHECK(!strcmp(l.e[0].a.name, "Test host"));
        CHECK(l.e[0].ping_ms == 12);           /* 5012 - 5000, echoed by the host */
        CHECK(lanb_joinable(&l.e[0]));
        char addr[64];
        lanb_server(&l.e[0], addr, sizeof addr);
        CHECK(!strcmp(addr, "127.0.0.1:36100"));
    }

    /* a query from the same socket with a different nonce is answered too, and lists once */
    lanb_query(q, 78, 6000);
    lad_send_to(qry, q, LANB_QUERY_LEN, loop, TEST_PORT);
    for (int i = 0; i < 200 && lad_host_serve(host, &a) == 0; i++) Sleep(5);
    got = 0;
    for (int i = 0; i < 200 && got == 0; i++) {
        got = lad_browse_read(qry, &l, 6003);
        if (!got) Sleep(5);
    }
    CHECK(got == 1 && l.n == 1 && l.e[0].ping_ms == 3);

    /* a bogus datagram is ignored by the host */
    const uint8_t junk[] = "hello";
    lad_send_to(qry, junk, sizeof junk, loop, TEST_PORT);
    Sleep(20);
    CHECK(lad_host_serve(host, &a) == 0);

    /* the directed broadcasts of this PC's networks: none is loopback or 0.0.0.0 (the machine's own
     * list is whatever it has, so only the rules are checked here) */
    uint8_t nets[16][4];
    const int nn = lad_broadcasts(nets, 16);
    CHECK(nn >= 0 && nn <= 16);
    for (int i = 0; i < nn; i++) {
        CHECK(nets[i][0] != 127 && !(nets[i][0] == 0 && nets[i][1] == 0 && nets[i][2] == 0 && nets[i][3] == 0));
        printf("  directed broadcast %u.%u.%u.%u\n", nets[i][0], nets[i][1], nets[i][2], nets[i][3]);
    }

    closesocket(qry);
    closesocket(host);
    WSACleanup();
    printf("test_lan_discovery: %d failure(s)\n", fails);
    return fails ? 1 : 0;
}
