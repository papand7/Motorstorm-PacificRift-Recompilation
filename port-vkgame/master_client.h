/* MotorStorm: Pacific Rift master server client (host/join browser, phase 1).
 *
 * Talks to the master's api.php: announce (every 30 s while hosting), remove
 * (when hosting stops) and list (format=lines). Our own code, written from the
 * request shapes in server/master/api.php; no code is taken from another game.
 *
 * The HTTP layer is injected (ms_transport) so the request strings, the 30 s
 * cadence and the list parser can be tested without a network. No transport
 * is bound in the port yet: see docs/MULTIPLAYER_BROWSER.md (blocker f).
 *
 * Game id "motorstorm" is ours; the master keeps MotorStorm listings apart from
 * the other games' lists. */
#ifndef MASTER_CLIENT_H
#define MASTER_CLIENT_H

#include <stddef.h>

#define MS_GAME_ID "motorstorm"
#define MS_VERSION_TAG "pr-1"        /* protocol tag sent as v=; bump with the wire format */
#define MS_ANNOUNCE_PERIOD_MS 30000  /* announce cadence while hosting */
#define MS_DEFAULT_URL "https://masterserver.dankelsoft.dk/api.php"

/* GET url. On an answer, returns 0, stores the HTTP status and a NUL-terminated
 * body. A body that does not fit in cap is an error: return nonzero. Nonzero
 * means no answer. */
typedef struct ms_transport {
    int (*get)(void* ctx, const char* url, char* body, size_t cap, int* status);
    void* ctx;
} ms_transport;

typedef struct ms_server {
    char address[16];   /* IPv4 "a.b.c.d" */
    int port;
    char name[64];
    char map[64];
    int players;
    int max;
    char mode[32];
    char version[24];
} ms_server;

typedef struct ms_publisher {
    const char* base_url;   /* api.php URL */
    ms_transport transport;
    int port;               /* the session port announced */
    int max;                /* max players announced */
    int active;             /* 1 between start and stop */
    long long next_announce_ms;
    int last_status;        /* HTTP status of the last request, or -1 for no answer */
    int announces;          /* announce requests sent (for tests and logs) */
    int removes;            /* remove requests sent */
} ms_publisher;

/* URL builders (buf of cap bytes). Return 0 on success, nonzero if too long. */
int ms_announce_url(char* buf, size_t cap, const char* base, int port, int max);
int ms_remove_url(char* buf, size_t cap, const char* base, int port);
int ms_list_url(char* buf, size_t cap, const char* base);

/* Hosting. start() arms the publisher; the first announce is due at once.
 * tick(now_ms) sends an announce when one is due (every 30 s; a failed announce
 * still waits 30 s). stop() sends one remove if active, then disarms. */
void ms_publisher_start(ms_publisher* p, const char* base, ms_transport t, int port, int max, long long now_ms);
void ms_publisher_tick(ms_publisher* p, long long now_ms);
void ms_publisher_stop(ms_publisher* p);

/* Parses a list response (format=lines): one server per line, eight
 * tab-separated fields: address, port, name, map, players, max, mode, version.
 * Blank lines and CRLF endings are accepted. A malformed line (wrong field
 * count, bad IPv4, bad port, bad number, overlong field) is skipped and counted
 * in *skipped. Returns the number stored (at most cap). */
int ms_parse_list_lines(const char* body, ms_server* out, int cap, int* skipped);

/* Fetches the list. Returns 0 and fills *count when the master answered with
 * HTTP 200; nonzero when there was no answer or a non-200 status. */
int ms_list(ms_transport t, const char* base, ms_server* out, int cap, int* count, int* skipped);

#endif
