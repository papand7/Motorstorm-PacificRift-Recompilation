/* LAN play: the room server's sockets (lan_room.h holds the protocol). Windows (Winsock).
 *
 * lrn_open listens on a TCP port; lrn_step(timeout) accepts, reads, hands complete frames to
 * lan_room.h and writes what it queued, without blocking longer than timeout. One thread calls
 * these (lan_play.cpp's LAN thread, or the test). */
#ifndef LAN_ROOM_NET_H
#define LAN_ROOM_NET_H

#include "lan_room.h"

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <winsock2.h>
#include <ws2tcpip.h>
#ifdef _MSC_VER
#pragma comment(lib, "ws2_32.lib")
#endif

typedef struct {
    lr_server s;
    SOCKET lsock;
    SOCKET sock[LR_CLIENTS];
    size_t sent[LR_CLIENTS];   /* bytes of the out buffer already written */
    uint16_t port;
} lrn;

static inline void lrn_nonblock(SOCKET s) { u_long nb = 1; ioctlsocket(s, FIONBIO, &nb); }

/* 0 when listening on port (0.0.0.0, or 127.0.0.1 with loopback_only); -1 when the port is taken. */
static inline int lrn_open(lrn* n, uint16_t port, int loopback_only, uint64_t room_seed)
{
    WSADATA w;
    WSAStartup(MAKEWORD(2, 2), &w);
    memset(n, 0, sizeof *n);
    lr_init(&n->s, room_seed);
    for (int i = 0; i < LR_CLIENTS; i++) n->sock[i] = INVALID_SOCKET;
    n->lsock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (n->lsock == INVALID_SOCKET) return -1;
    BOOL excl = TRUE;   /* a second host on this PC must fail, not share the port */
    setsockopt(n->lsock, SOL_SOCKET, SO_EXCLUSIVEADDRUSE, (const char*)&excl, sizeof excl);
    struct sockaddr_in a;
    memset(&a, 0, sizeof a);
    a.sin_family = AF_INET;
    a.sin_port = htons(port);
    a.sin_addr.s_addr = htonl(loopback_only ? INADDR_LOOPBACK : INADDR_ANY);
    if (bind(n->lsock, (struct sockaddr*)&a, sizeof a) || listen(n->lsock, 8)) {
        closesocket(n->lsock);
        n->lsock = INVALID_SOCKET;
        return -1;
    }
    int len = sizeof a;
    getsockname(n->lsock, (struct sockaddr*)&a, &len);
    n->port = ntohs(a.sin_port);
    lrn_nonblock(n->lsock);
    return 0;
}

static inline void lrn_drop(lrn* n, int i)
{
    if (n->sock[i] != INVALID_SOCKET) closesocket(n->sock[i]);
    n->sock[i] = INVALID_SOCKET;
    n->sent[i] = 0;
    lr_disconnect(&n->s, i);
}

/* Writes what is queued for client i; the unsent rest waits for the next step. */
static inline void lrn_flush(lrn* n, int i)
{
    lr_buf* o = &n->s.c[i].out;
    while (n->sent[i] < o->n) {
        const int k = send(n->sock[i], (const char*)o->b + n->sent[i], (int)(o->n - n->sent[i]), 0);
        if (k <= 0) {
            if (k < 0 && WSAGetLastError() == WSAEWOULDBLOCK) return;
            lrn_drop(n, i);
            return;
        }
        n->sent[i] += (size_t)k;
    }
    o->n = 0;
    n->sent[i] = 0;
}

static inline void lrn_step(lrn* n, int timeout_ms)
{
    if (n->lsock == INVALID_SOCKET) return;
    WSAPOLLFD pf[1 + LR_CLIENTS];
    int idx[1 + LR_CLIENTS], np = 0;
    pf[np].fd = n->lsock; pf[np].events = POLLRDNORM; pf[np].revents = 0; idx[np++] = -1;
    for (int i = 0; i < LR_CLIENTS; i++) {
        if (n->sock[i] == INVALID_SOCKET) continue;
        pf[np].fd = n->sock[i];
        pf[np].events = POLLRDNORM | (n->s.c[i].out.n ? POLLWRNORM : 0);
        pf[np].revents = 0;
        idx[np++] = i;
    }
    if (WSAPoll(pf, (ULONG)np, timeout_ms) <= 0) return;
    if (pf[0].revents & POLLRDNORM) {
        struct sockaddr_in a, l;
        int al = sizeof a, ll = sizeof l;
        SOCKET c = accept(n->lsock, (struct sockaddr*)&a, &al);
        if (c != INVALID_SOCKET) {
            getsockname(c, (struct sockaddr*)&l, &ll);
            const int i = lr_connect(&n->s, (const uint8_t*)&a.sin_addr, (const uint8_t*)&l.sin_addr);
            if (i < 0) closesocket(c);
            else {
                int one = 1;
                setsockopt(c, IPPROTO_TCP, TCP_NODELAY, (const char*)&one, sizeof one);
                lrn_nonblock(c);
                n->sock[i] = c;
                n->sent[i] = 0;
            }
        }
    }
    for (int k = 1; k < np; k++) {
        const int i = idx[k];
        if (n->sock[i] == INVALID_SOCKET) continue;
        if (pf[k].revents & (POLLRDNORM | POLLHUP | POLLERR)) {
            uint8_t buf[8192];
            for (;;) {
                const int r = recv(n->sock[i], (char*)buf, sizeof buf, 0);
                if (r > 0) {
                    if (lr_feed(&n->s, i, buf, (size_t)r)) { lrn_drop(n, i); break; }
                    continue;
                }
                if (r < 0 && WSAGetLastError() == WSAEWOULDBLOCK) break;
                lrn_drop(n, i);   /* closed or failed */
                break;
            }
        }
    }
    /* a request can queue frames for any client (pushes) */
    for (int i = 0; i < LR_CLIENTS; i++)
        if (n->sock[i] != INVALID_SOCKET && n->s.c[i].out.n) lrn_flush(n, i);
}

static inline void lrn_close(lrn* n)
{
    for (int i = 0; i < LR_CLIENTS; i++) if (n->sock[i] != INVALID_SOCKET) lrn_drop(n, i);
    if (n->lsock != INVALID_SOCKET) closesocket(n->lsock);
    n->lsock = INVALID_SOCKET;
    lr_shutdown(&n->s);
}
#endif /* _WIN32 */

#endif
