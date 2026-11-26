/* stdio_async.h: the chunk queue, and (Windows) that a game thread's stderr writes never wait for a stalled sink.
 * clang -std=gnu17 -O2 -I port-vkgame port-vkgame/tests/test_stdio_async.c -o test_stdio_async.exe */
#include <stdio.h>
#include <string.h>
#include "stdio_async.h"

static int fails;
#define CHECK(c) do { if (!(c)) { fprintf(stdout, "FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)

int main(void)
{
    /* queue: order, partial consumes, the cap drops (never waits), refills after draining */
    sa_queue q;
    memset(&q, 0, sizeof q);
    q.cap = 10;
    CHECK(sa_queue_push(&q, "abcd", 4) == 0);
    CHECK(sa_queue_push(&q, "efgh", 4) == 0);
    CHECK(sa_queue_push(&q, "ijk", 3) == -1 && q.dropped == 1 && q.dropped_bytes == 3);   /* 11 > 10 */
    CHECK(sa_queue_push(&q, "ij", 2) == 0 && q.bytes == 10);
    size_t n;
    const char* p = sa_queue_peek(&q, &n);
    CHECK(p && n == 4 && !memcmp(p, "abcd", 4));
    sa_queue_consume(&q, 3);
    p = sa_queue_peek(&q, &n);
    CHECK(p && n == 1 && p[0] == 'd' && q.bytes == 7);
    sa_queue_consume(&q, 1);
    p = sa_queue_peek(&q, &n);
    CHECK(p && n == 4 && !memcmp(p, "efgh", 4));
    sa_queue_consume(&q, 99);   /* clamps to the chunk */
    p = sa_queue_peek(&q, &n);
    CHECK(p && n == 2 && !memcmp(p, "ij", 2));
    sa_queue_consume(&q, 2);
    CHECK(!sa_queue_peek(&q, &n) && n == 0 && q.bytes == 0 && !q.head && !q.tail);
    CHECK(sa_queue_push(&q, "0123456789", 10) == 0);
    CHECK(sa_queue_push(&q, "", 0) == 0 && q.bytes == 10);
    sa_queue_free(&q);
    CHECK(q.bytes == 0 && !q.head);

#ifdef _WIN32
    /* live: stderr's sink is a pipe nobody reads (a disk that never finishes a write). 8 MB of fprintf must
     * return at once; past the 2 MB cap the rest is dropped, not waited for. */
    HANDLE rd, wr;
    CHECK(CreatePipe(&rd, &wr, NULL, 4096));
    const int fd = _open_osfhandle((intptr_t)wr, _O_WRONLY | _O_BINARY);
    CHECK(fd >= 0 && _dup2(fd, 2) == 0);
    _putenv_s("PS3_STDIO_ASYNC_MB", "2");
    CHECK(stdio_async_start() == 0);
    static char line[1024];
    memset(line, 'x', sizeof line - 2); line[sizeof line - 2] = '\n'; line[sizeof line - 1] = 0;
    const ULONGLONG t0 = GetTickCount64();
    for (int i = 0; i < 8192; i++) fputs(line, stderr);
    const ULONGLONG dt = GetTickCount64() - t0;
    CHECK(dt < 1000);
    Sleep(200);
    AcquireSRWLockShared(&s_sa[1].mu);
    const uint64_t dropped = s_sa[1].q.dropped_bytes;
    const size_t queued = s_sa[1].q.bytes;
    ReleaseSRWLockShared(&s_sa[1].mu);
    CHECK(dropped > 0 && queued <= ((size_t)2 << 20));
    fprintf(stdout, "8 MB to a stalled stderr in %llu ms; %llu bytes dropped, %zu queued\n",
            (unsigned long long)dt, (unsigned long long)dropped, queued);
    fprintf(stdout, fails ? "FAIL %d\n" : "OK\n", fails);
    fflush(stdout);
    Sleep(300);   /* stdout goes through the queue too */
    _exit(fails != 0);   /* not exit(): the stalled stderr would hold the at-exit drain for its 3 s */
#else
    printf(fails ? "FAIL %d\n" : "OK\n", fails);
    return fails != 0;
#endif
}
