/* LAN play discovery and browser list (port-vkgame/lan_browser.h). No sockets.
 * Build: generated/analysis/pcmenu/tools/build_tests.cmd */
#include "lan_browser.h"

#include <stdio.h>

static int fails;
#define CHECK(c) do { if (!(c)) { fails++; printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)

static lanb_answer ans(const char* name, uint16_t port, uint8_t pl, uint8_t mx, uint32_t sent)
{
    lanb_answer a;
    memset(&a, 0, sizeof a);
    a.ver = LANB_VERSION;
    a.sent_ms = sent;
    a.session = 0x1122334455667700ull ^ port;   /* one host: its name and room port */
    for (const char* c = name; *c; c++) a.session = a.session * 131u + (uint8_t)*c;
    a.room_port = port;
    a.players = pl;
    a.max = mx;
    snprintf(a.name, sizeof a.name, "%s", name);
    return a;
}

int main(void)
{
    uint8_t q[LANB_QUERY_LEN], w[LANB_ANSWER_LEN];
    uint32_t nonce = 0, sent = 0;

    /* query round trip */
    CHECK(lanb_query(q, 0xDEADBEEF, 123456) == LANB_QUERY_LEN);
    CHECK(lanb_parse_query(q, LANB_QUERY_LEN, &nonce, &sent) && nonce == 0xDEADBEEF && sent == 123456);
    CHECK(!lanb_parse_query(q, LANB_QUERY_LEN - 1, &nonce, &sent));
    q[0] = 'X';
    CHECK(!lanb_parse_query(q, LANB_QUERY_LEN, &nonce, &sent));

    /* answer round trip, with hostile text cleaned */
    lanb_answer a = ans("Julie's PC", LANB_ROOM_PORT, 2, 8, 1000), b;
    a.nonce = 7;
    snprintf(a.event, sizeof a.event, "Custom\x01Game");
    a.state = LANB_STATE_LOBBY;
    CHECK(lanb_answer_pack(w, &a) == LANB_ANSWER_LEN);
    CHECK(lanb_answer_parse(w, LANB_ANSWER_LEN, &b));
    CHECK(b.ver == LANB_VERSION && b.nonce == 7 && b.sent_ms == 1000 && b.session == a.session);
    CHECK(b.room_port == LANB_ROOM_PORT && b.players == 2 && b.max == 8);
    CHECK(!strcmp(b.name, "Julie's PC"));
    CHECK(!strcmp(b.event, "Custom?Game"));
    CHECK(!lanb_answer_parse(w, LANB_ANSWER_LEN - 1, &b));
    {   /* a full-width name is cut, not overrun; an empty name gets a default; port 0 is refused */
        lanb_answer c = ans("", 1, 0, 0, 0);
        memset(c.name, 'A', LANB_NAME_MAX); c.name[LANB_NAME_MAX] = 0;
        lanb_answer_pack(w, &c);
        CHECK(lanb_answer_parse(w, LANB_ANSWER_LEN, &b) && strlen(b.name) == LANB_NAME_MAX);
        c.name[0] = 0;
        lanb_answer_pack(w, &c);
        CHECK(lanb_answer_parse(w, LANB_ANSWER_LEN, &b) && !strcmp(b.name, "LAN game"));
        c.room_port = 0;
        lanb_answer_pack(w, &c);
        CHECK(!lanb_answer_parse(w, LANB_ANSWER_LEN, &b));
    }

    /* list: add, update in place, sort, ping, expire */
    lanb_list l;
    lanb_reset(&l, 1);
    const uint8_t ip1[4] = { 192, 168, 1, 20 }, ip2[4] = { 192, 168, 1, 7 }, ip3[4] = { 10, 0, 0, 1 };
    a = ans("Zed", LANB_ROOM_PORT, 1, 4, 1000);
    CHECK(lanb_add(&l, ip1, &a, 1012) == 0);
    CHECK(l.e[0].ping_ms == 12);
    a = ans("Amy", LANB_ROOM_PORT, 3, 4, 1000);
    CHECK(lanb_add(&l, ip2, &a, 1003) == 0);         /* sorted by name: Amy first */
    CHECK(l.n == 2 && !strcmp(l.e[1].a.name, "Zed"));
    a = ans("Zed", LANB_ROOM_PORT, 2, 4, 2000);
    CHECK(lanb_add(&l, ip1, &a, 2030) == 1);         /* same host and port: updated, not added */
    CHECK(l.n == 2 && l.e[1].a.players == 2 && l.e[1].ping_ms == 30);
    a = ans("Old", LANB_ROOM_PORT, 1, 4, 2000);
    a.ver = LANB_VERSION + 1;
    CHECK(lanb_add(&l, ip3, &a, 2001) == 2);         /* a different version sorts last */
    CHECK(!lanb_joinable(&l.e[2]));
    char t[96];
    lanb_row_value(&l.e[2], t, sizeof t);
    CHECK(!strcmp(t, "Different version"));
    lanb_row_value(&l.e[1], t, sizeof t);
    CHECK(!strcmp(t, "Lobby  2/4  30 ms"));
    lanb_row_label(&l.e[0], t, sizeof t);
    CHECK(!strcmp(t, "Amy"));
    lanb_server(&l.e[0], t, sizeof t);
    CHECK(!strcmp(t, "192.168.1.7:36100"));
    CHECK(lanb_joinable(&l.e[0]));
    a = ans("Full", 40000, 4, 4, 2000);
    lanb_add(&l, ip3, &a, 2002);
    for (int i = 0; i < l.n; i++) if (!strcmp(l.e[i].a.name, "Full")) CHECK(!lanb_joinable(&l.e[i]));
    CHECK(l.n == 4);
    /* Amy was last seen at 1003: gone after 3.5 s; the rest stay */
    CHECK(lanb_expire(&l, 1003 + LANB_EXPIRE_MS) == 0);
    CHECK(lanb_expire(&l, 1004 + LANB_EXPIRE_MS) == 1);
    CHECK(l.n == 3);
    for (int i = 0; i < l.n; i++) CHECK(strcmp(l.e[i].a.name, "Amy"));
    /* one host heard on two paths (this PC: the loopback query and the broadcast): one entry, by session,
     * and the LAN address kept whichever arrives first (Klp1b listed a host on this PC twice) */
    {
        lanb_list d;
        lanb_reset(&d, 9);
        const uint8_t lo[4] = { 127, 0, 0, 1 }, lan[4] = { 192, 168, 1, 50 };
        lanb_answer h = ans("Host", LANB_ROOM_PORT, 0, 8, 100);
        CHECK(lanb_add(&d, lo, &h, 101) == 0);
        CHECK(lanb_add(&d, lan, &h, 102) == 0);
        CHECK(d.n == 1 && !memcmp(d.e[0].ip, lan, 4));
        CHECK(lanb_add(&d, lo, &h, 103) == 0);
        CHECK(d.n == 1 && !memcmp(d.e[0].ip, lan, 4) && d.e[0].seen_ms == 103);
        lanb_answer o = ans("Other", LANB_ROOM_PORT, 0, 8, 100);   /* another host on the same PC: its own row */
        CHECK(lanb_add(&d, lo, &o, 104) >= 0 && d.n == 2);
    }
    /* clock wrap: a 32-bit millisecond clock that wrapped still gives the right ping and age */
    lanb_reset(&l, 2);
    a = ans("Wrap", LANB_ROOM_PORT, 1, 2, 0xFFFFFFF0u);
    lanb_add(&l, ip1, &a, 0x00000010u);
    CHECK(l.e[0].ping_ms == 0x20);
    CHECK(lanb_expire(&l, 0x00000010u + 100) == 0 && l.n == 1);
    /* full list */
    lanb_reset(&l, 3);
    for (int i = 0; i < LANB_MAX + 2; i++) {
        uint8_t ip[4] = { 10, 0, 1, (uint8_t)i };
        a = ans("H", LANB_ROOM_PORT, 1, 2, 0);
        a.session = (uint64_t)i + 1;            /* a different host each */
        const int r = lanb_add(&l, ip, &a, 1);
        CHECK(i < LANB_MAX ? r >= 0 : r == -1);
    }
    CHECK(l.n == LANB_MAX);

    /* host names */
    char hn[LANB_NAME_MAX + 1];
    lanb_host_name("  Living Room  ", hn);
    CHECK(!strcmp(hn, "Living Room"));
    lanb_host_name("", hn);
    CHECK(!strcmp(hn, "LAN game"));
    lanb_host_name(NULL, hn);
    CHECK(!strcmp(hn, "LAN game"));
    lanb_host_name("A very long computer name that goes on", hn);
    CHECK(strlen(hn) == LANB_NAME_MAX);

    printf("test_lan_browser: %d failure(s)\n", fails);
    return fails ? 1 : 0;
}
