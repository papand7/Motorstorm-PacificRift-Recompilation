/* Master client: request strings, 30 s cadence, remove on stop, list parsing.
 * No network: a fake transport records each URL and returns canned answers.
 *   clang -O2 -I port-vkgame port-vkgame\tests\test_master_client.c port-vkgame\master_client.c -o test_master_client.exe
 *   test_master_client.exe */
#include <stdio.h>
#include <string.h>
#include "master_client.h"

static int fails;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)

#define BASE "https://masterserver.dankelsoft.dk/api.php"

/* fake HTTP layer */
#define MAX_CALLS 32
static char calls[MAX_CALLS][256];
static int ncalls;
static int fake_fail;      /* 1: no answer */
static int fake_status = 200;
static const char* fake_body = "";

static int fake_get(void* ctx, const char* url, char* body, size_t cap, int* status)
{
    (void)ctx;
    if (ncalls < MAX_CALLS) strcpy(calls[ncalls], url);
    ncalls++;
    if (fake_fail) return 1;
    if (strlen(fake_body) >= cap) return 1;
    strcpy(body, fake_body);
    *status = fake_status;
    return 0;
}

static ms_transport fake(void)
{
    ms_transport t;
    t.get = fake_get;
    t.ctx = NULL;
    return t;
}

static void reset(void)
{
    ncalls = 0;
    fake_fail = 0;
    fake_status = 200;
    fake_body = "";
}

static void test_urls(void)
{
    char u[256];
    CHECK(ms_announce_url(u, sizeof u, BASE, 47613, 8) == 0);
    CHECK(!strcmp(u, BASE "?a=announce&game=motorstorm&port=47613&max=8&v=pr-1"));
    CHECK(ms_remove_url(u, sizeof u, BASE, 47613) == 0);
    CHECK(!strcmp(u, BASE "?a=remove&game=motorstorm&port=47613"));
    CHECK(ms_list_url(u, sizeof u, BASE) == 0);
    CHECK(!strcmp(u, BASE "?a=list&game=motorstorm&format=lines"));
    /* the game id never names another game */
    CHECK(strstr(u, "nightfire") == NULL);
    CHECK(strcmp(MS_GAME_ID, "motorstorm") == 0);
    /* a buffer that is too small is reported */
    CHECK(ms_list_url(u, 10, BASE) != 0);
}

static void test_cadence(void)
{
    ms_publisher p;
    reset();
    ms_publisher_start(&p, BASE, fake(), 47613, 8, 1000);
    CHECK(ncalls == 0);                       /* start alone sends nothing */
    ms_publisher_tick(&p, 1000);              /* due at once */
    CHECK(ncalls == 1);
    ms_publisher_tick(&p, 1000 + 29999);      /* not yet */
    CHECK(ncalls == 1);
    ms_publisher_tick(&p, 1000 + 30000);      /* due */
    CHECK(ncalls == 2);
    ms_publisher_tick(&p, 1000 + 30001);
    CHECK(ncalls == 2);
    ms_publisher_tick(&p, 1000 + 60000);
    CHECK(ncalls == 3);
    CHECK(!strcmp(calls[0], BASE "?a=announce&game=motorstorm&port=47613&max=8&v=pr-1"));
    CHECK(p.announces == 3);

    /* a failed announce still waits the full 30 s, and is retried then */
    reset();
    fake_fail = 1;
    ms_publisher_start(&p, BASE, fake(), 47613, 8, 0);
    ms_publisher_tick(&p, 0);
    CHECK(ncalls == 1 && p.last_status == -1);
    fake_fail = 0;
    ms_publisher_tick(&p, 29999);
    CHECK(ncalls == 1);
    ms_publisher_tick(&p, 30000);
    CHECK(ncalls == 2 && p.last_status == 200);
}

static void test_remove_on_stop(void)
{
    ms_publisher p;
    reset();
    ms_publisher_start(&p, BASE, fake(), 47613, 8, 0);
    ms_publisher_tick(&p, 0);
    ms_publisher_stop(&p);
    CHECK(ncalls == 2);
    CHECK(!strcmp(calls[1], BASE "?a=remove&game=motorstorm&port=47613"));
    CHECK(p.removes == 1 && p.active == 0);

    /* after stop: no announce, no second remove */
    ms_publisher_tick(&p, 60000);
    ms_publisher_stop(&p);
    CHECK(ncalls == 2);

    /* stop without start sends nothing */
    reset();
    ms_publisher q;
    memset(&q, 0, sizeof q);
    ms_publisher_stop(&q);
    CHECK(ncalls == 0);

    /* a remove that gets no answer is still sent once, and the publisher is disarmed */
    reset();
    fake_fail = 1;
    ms_publisher_start(&p, BASE, fake(), 47613, 8, 0);
    ms_publisher_stop(&p);
    CHECK(ncalls == 1 && p.last_status == -1 && p.active == 0);
}

static void test_parse(void)
{
    ms_server sv[8];
    int skipped = -1;
    int n;

    /* empty list: no lines, nothing skipped */
    n = ms_parse_list_lines("", sv, 8, &skipped);
    CHECK(n == 0 && skipped == 0);
    n = ms_parse_list_lines("\n", sv, 8, &skipped);
    CHECK(n == 0 && skipped == 0);

    /* two good lines (one with CRLF), one malformed line (7 fields), one bad IP,
     * one bad port, and one with a non-numeric player count */
    fake_body = "203.0.113.5\t47613\tAlpha\tDesert Ridge\t3\t8\tRace\tpr-1\n"
                "198.51.100.7\t47700\tBeta\tPacific Bay\t1\t6\tRace\tpr-1\r\n"
                "203.0.113.9\t47613\tBroken\tMap\t1\t8\tRace\n"
                "999.1.1.1\t47613\tBadIP\tMap\t1\t8\tRace\tpr-1\n"
                "203.0.113.10\t0\tBadPort\tMap\t1\t8\tRace\tpr-1\n"
                "203.0.113.11\t47613\tNoNum\tMap\tx\t8\tRace\tpr-1\n";
    n = ms_parse_list_lines(fake_body, sv, 8, &skipped);
    CHECK(n == 2);
    CHECK(skipped == 4);
    CHECK(!strcmp(sv[0].address, "203.0.113.5") && sv[0].port == 47613);
    CHECK(!strcmp(sv[0].name, "Alpha") && !strcmp(sv[0].map, "Desert Ridge"));
    CHECK(sv[0].players == 3 && sv[0].max == 8);
    CHECK(!strcmp(sv[0].mode, "Race") && !strcmp(sv[0].version, "pr-1"));
    CHECK(!strcmp(sv[1].address, "198.51.100.7") && sv[1].port == 47700);
    CHECK(!strcmp(sv[1].version, "pr-1"));   /* CRLF stripped */

    /* the cap stops storage; the rest of the lines are not counted as skipped */
    n = ms_parse_list_lines(fake_body, sv, 1, &skipped);
    CHECK(n == 1);

    /* a single line with no trailing newline */
    n = ms_parse_list_lines("10.0.0.1\t27787\tGamma\tLobby\t0\t4\tRace\tpr-1", sv, 8, &skipped);
    CHECK(n == 1 && skipped == 0 && sv[0].players == 0);

    /* a list fetch: 200 with lines, a refused status, and no answer */
    reset();
    fake_body = "10.0.0.1\t27787\tGamma\tLobby\t0\t4\tRace\tpr-1\n";
    int count = -1;
    CHECK(ms_list(fake(), BASE, sv, 8, &count, &skipped) == 0 && count == 1);
    CHECK(!strcmp(calls[0], BASE "?a=list&game=motorstorm&format=lines"));

    reset();
    fake_status = 400;
    fake_body = "{\"ok\":false,\"error\":\"unknown game\"}";
    CHECK(ms_list(fake(), BASE, sv, 8, &count, &skipped) == 2);

    reset();
    fake_fail = 1;
    CHECK(ms_list(fake(), BASE, sv, 8, &count, &skipped) == 1);
}

int main(void)
{
    test_urls();
    test_cadence();
    test_remove_on_stop();
    test_parse();
    printf("test_master_client: %d failure(s)\n", fails);
    return fails ? 1 : 0;
}
