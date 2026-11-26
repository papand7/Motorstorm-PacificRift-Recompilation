/* stdout and stderr written on a background thread (PS3_STDIO_ASYNC, on unless =0).
 *
 * Why: every late "GcKernel::Present() Timeout" with a host stack (Kwarmold1, Kpr1, Klt20c, Kst4; 2026-11-26
 * analysis, generated/analysis/startup_timeout/RESULTS.md) had the RSX FIFO/present thread inside
 * fprintf -> _write -> WriteFile -> ZwWriteFile on the stderr file, or waiting for the stdio lock a thread in
 * WriteFile held, for 20-48 s while the disk stalled. The guest gives up on a flip after about 4 s.
 *
 * How: fd 1 and fd 2 (and the Win32 std handles) become the write ends of two pipes. One reader thread per
 * pipe only copies what arrives into a memory queue (it never touches the disk, so the pipe never fills and a
 * game thread's write never waits for the disk); one writer thread writes the queue to the original handles.
 * The queue is capped (PS3_STDIO_ASYNC_MB, default 256): past it, output is dropped and counted, never waited
 * for. A write that takes over a second is reported ("[stdio-async] ... the game did not wait"). At exit the
 * queue is drained for up to 3 s.
 *
 * The queue (sa_queue_*) is plain C and host-testable (tests/test_stdio_async.c). */
#ifndef PORT_STDIO_ASYNC_H
#define PORT_STDIO_ASYNC_H
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* ---- the queue: a FIFO of malloc'd chunks with a byte cap ---- */
typedef struct sa_chunk { struct sa_chunk* next; size_t n, off; char data[1]; } sa_chunk;
typedef struct {
    sa_chunk *head, *tail;
    size_t bytes, cap;              /* queued bytes, cap (0 = none) */
    uint64_t dropped, dropped_bytes;
} sa_queue;

/* Queues a copy of data; 0, or -1 when it is dropped (over the cap or out of memory). */
static inline int sa_queue_push(sa_queue* q, const void* data, size_t n)
{
    if (!n) return 0;
    if (q->cap && q->bytes + n > q->cap) { q->dropped++; q->dropped_bytes += n; return -1; }
    sa_chunk* c = (sa_chunk*)malloc(sizeof(sa_chunk) + n);
    if (!c) { q->dropped++; q->dropped_bytes += n; return -1; }
    c->next = NULL; c->n = n; c->off = 0;
    memcpy(c->data, data, n);
    if (q->tail) q->tail->next = c; else q->head = c;
    q->tail = c;
    q->bytes += n;
    return 0;
}
/* The oldest unwritten bytes (NULL when empty); sa_queue_consume marks n of them written. */
static inline const char* sa_queue_peek(const sa_queue* q, size_t* n)
{
    if (!q->head) { *n = 0; return NULL; }
    *n = q->head->n - q->head->off;
    return q->head->data + q->head->off;
}
static inline void sa_queue_consume(sa_queue* q, size_t n)
{
    sa_chunk* c = q->head;
    if (!c) return;
    if (n > c->n - c->off) n = c->n - c->off;
    c->off += n;
    q->bytes -= n;
    if (c->off == c->n) {
        q->head = c->next;
        if (!q->head) q->tail = NULL;
        free(c);
    }
}
static inline void sa_queue_free(sa_queue* q)
{
    while (q->head) { sa_chunk* c = q->head; q->head = c->next; free(c); }
    q->tail = NULL; q->bytes = 0;
}

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <fcntl.h>
#include <io.h>
#include <stdio.h>

typedef struct {
    int fd;                         /* 1 or 2 */
    HANDLE rd, sink;                /* pipe read end; the original handle (a file, the console) */
    sa_queue q;
    SRWLOCK mu;
    CONDITION_VARIABLE cv;          /* the writer waits on it */
    volatile LONG writing;          /* the writer holds a chunk outside the lock */
    volatile LONG reader_done;
} sa_stream;
static sa_stream s_sa[2];
static volatile LONG s_sa_on;

static DWORD WINAPI sa_reader(LPVOID arg)
{
    sa_stream* s = (sa_stream*)arg;
    static char bufs[2][1 << 16];
    char* buf = bufs[s->fd - 1];
    DWORD n;
    while (ReadFile(s->rd, buf, (DWORD)sizeof bufs[0], &n, NULL) && n) {
        AcquireSRWLockExclusive(&s->mu);
        sa_queue_push(&s->q, buf, n);
        ReleaseSRWLockExclusive(&s->mu);
        WakeConditionVariable(&s->cv);
    }
    InterlockedExchange(&s->reader_done, 1);
    WakeConditionVariable(&s->cv);
    return 0;
}
static DWORD WINAPI sa_writer(LPVOID arg)
{
    sa_stream* s = (sa_stream*)arg;
    uint64_t reported = 0;
    for (;;) {
        AcquireSRWLockExclusive(&s->mu);
        size_t n = 0;
        const char* p;
        while (!(p = sa_queue_peek(&s->q, &n)) && !s->reader_done)
            SleepConditionVariableSRW(&s->cv, &s->mu, INFINITE, 0);
        const uint64_t dropped = s->q.dropped_bytes;
        if (p) InterlockedExchange(&s->writing, 1);
        ReleaseSRWLockExclusive(&s->mu);
        if (!p) return 0;
        /* The chunk stays in the queue (only this thread consumes), so p is valid outside the lock. */
        const ULONGLONG t0 = GetTickCount64();
        DWORD w = 0;
        const BOOL ok = WriteFile(s->sink, p, (DWORD)(n > (1u << 30) ? (1u << 30) : n), &w, NULL);
        const ULONGLONG dt = GetTickCount64() - t0;
        AcquireSRWLockExclusive(&s->mu);
        sa_queue_consume(&s->q, ok && w ? w : n);   /* a failed write drops the chunk, never loops */
        InterlockedExchange(&s->writing, 0);
        const size_t left = s->q.bytes;
        ReleaseSRWLockExclusive(&s->mu);
        char note[200];
        int k = 0;
        if (dt >= 1000)
            k = snprintf(note, sizeof note, "[stdio-async] fd %d: one write took %llu ms (the game did not wait; %zu bytes queued)\n",
                         s->fd, (unsigned long long)dt, left);
        if (dropped != reported) {
            k += snprintf(note + k, sizeof note - (size_t)k, "[stdio-async] fd %d: %llu bytes dropped so far (queue cap)\n",
                          s->fd, (unsigned long long)dropped);
            reported = dropped;
        }
        if (k > 0) { DWORD w2; WriteFile(s->sink, note, (DWORD)k, &w2, NULL); }
    }
}

/* Waits (up to ms) until both pipes and queues are empty. */
static void stdio_async_drain(DWORD ms)
{
    if (!s_sa_on) return;
    fflush(stdout); fflush(stderr);
    const ULONGLONG end = GetTickCount64() + ms;
    for (;;) {
        int busy = 0;
        for (int i = 0; i < 2; i++) {
            DWORD avail = 0;
            if (PeekNamedPipe(s_sa[i].rd, NULL, 0, NULL, &avail, NULL) && avail) busy = 1;
            AcquireSRWLockShared(&s_sa[i].mu);
            if (s_sa[i].q.bytes || s_sa[i].writing) busy = 1;
            ReleaseSRWLockShared(&s_sa[i].mu);
        }
        if (!busy || GetTickCount64() >= end) return;
        Sleep(5);
    }
}
static void stdio_async_atexit(void) { stdio_async_drain(3000); }

/* Call once, early in main, before other threads start. 0 = on. */
static int stdio_async_start(void)
{
    const char* e = getenv("PS3_STDIO_ASYNC");
    if (e && e[0] == '0') return -1;
    size_t cap = (size_t)256 << 20;
    const char* m = getenv("PS3_STDIO_ASYNC_MB");
    if (m && atoi(m) > 0) cap = (size_t)atoi(m) << 20;
    fflush(stdout); fflush(stderr);
    for (int i = 0; i < 2; i++) {
        sa_stream* s = &s_sa[i];
        const int fd = i + 1;
        memset(s, 0, sizeof *s);
        s->fd = fd;
        s->q.cap = cap;
        InitializeSRWLock(&s->mu);
        InitializeConditionVariable(&s->cv);
        const HANDLE orig = (HANDLE)_get_osfhandle(fd);
        if (orig == INVALID_HANDLE_VALUE || orig == NULL) return -1;   /* no stream (a GUI launch): nothing to protect */
        if (!DuplicateHandle(GetCurrentProcess(), orig, GetCurrentProcess(), &s->sink, 0, FALSE, DUPLICATE_SAME_ACCESS))
            return -1;
        HANDLE wr;
        if (!CreatePipe(&s->rd, &wr, NULL, 1u << 20)) return -1;
        const int mode = _setmode(fd, _O_BINARY);   /* the stream's text/binary mode, kept across the swap */
        const int nfd = _open_osfhandle((intptr_t)wr, _O_WRONLY | _O_BINARY);
        if (nfd < 0 || _dup2(nfd, fd) != 0) return -1;
        _close(nfd);   /* fd keeps its own duplicate of the write end */
        if (mode != -1) _setmode(fd, mode);
        SetStdHandle(fd == 1 ? STD_OUTPUT_HANDLE : STD_ERROR_HANDLE, (HANDLE)_get_osfhandle(fd));
        HANDLE t1 = CreateThread(NULL, 0, sa_reader, s, 0, NULL);
        HANDLE t2 = CreateThread(NULL, 0, sa_writer, s, 0, NULL);
        if (!t1 || !t2) return -1;
        SetThreadPriority(t1, THREAD_PRIORITY_ABOVE_NORMAL);   /* keep the pipe empty */
        CloseHandle(t1); CloseHandle(t2);
        if (!InterlockedExchange(&s_sa_on, 1)) atexit(stdio_async_atexit);
    }
    return 0;
}
#endif /* _WIN32 */
#endif
