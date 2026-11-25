/* LAN play: the UDP side of the server browser (lan_browser.h holds the wire format).
 *
 * A hosting PC binds LANB_PORT and answers each query from the address it came from. A joining
 * PC binds an ephemeral port, sends a query to the limited broadcast and to loopback (so a host on
 * the same PC is seen), and reads the answers from that port. Both sockets are non-blocking; the
 * LAN thread in lan_play.cpp calls these. Windows (Winsock). Test: tests/test_lan_discovery.c. */
#ifndef LAN_DISCOVERY_H
#define LAN_DISCOVERY_H

#ifdef _WIN32
#include "lan_browser.h"
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <winsock2.h>
#include <ws2tcpip.h>
#include <iphlpapi.h>
#ifdef _MSC_VER
#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "iphlpapi.lib")
#endif

/* Opens a non-blocking UDP socket on port (0: ephemeral). broadcast: SO_BROADCAST. Returns
 * INVALID_SOCKET when the port is taken. */
static inline SOCKET lad_udp(uint16_t port, int broadcast)
{
    SOCKET s = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (s == INVALID_SOCKET) return s;
    if (broadcast) {
        BOOL on = TRUE;
        setsockopt(s, SOL_SOCKET, SO_BROADCAST, (const char*)&on, sizeof on);
    }
    if (port) {
        BOOL excl = TRUE;   /* a second host on this PC must fail, not share the port */
        setsockopt(s, SOL_SOCKET, SO_EXCLUSIVEADDRUSE, (const char*)&excl, sizeof excl);
    }
    struct sockaddr_in a;
    memset(&a, 0, sizeof a);
    a.sin_family = AF_INET;
    a.sin_addr.s_addr = htonl(INADDR_ANY);
    a.sin_port = htons(port);
    if (bind(s, (struct sockaddr*)&a, sizeof a)) {
        closesocket(s);
        return INVALID_SOCKET;
    }
    u_long nb = 1;
    ioctlsocket(s, FIONBIO, &nb);
    return s;
}

static inline void lad_send_to(SOCKET s, const uint8_t* buf, int len, const uint8_t ip[4], uint16_t port)
{
    struct sockaddr_in a;
    memset(&a, 0, sizeof a);
    a.sin_family = AF_INET;
    memcpy(&a.sin_addr, ip, 4);
    a.sin_port = htons(port);
    sendto(s, (const char*)buf, len, 0, (struct sockaddr*)&a, sizeof a);
}

/* The directed broadcast address of each IPv4 network this PC is on (a PC with two adapters has
 * two). Windows sends the limited broadcast on one interface only, so each network gets its own.
 * Returns the number written to out (at most cap). */
static inline int lad_broadcasts(uint8_t out[][4], int cap)
{
    IP_ADAPTER_INFO info[16];
    ULONG len = sizeof info;
    int n = 0;
    if (GetAdaptersInfo(info, &len) != NO_ERROR) return 0;
    for (PIP_ADAPTER_INFO a = info; a && n < cap; a = a->Next) {
        for (PIP_ADDR_STRING s = &a->IpAddressList; s && n < cap; s = s->Next) {
            IN_ADDR ia, ma;
            if (inet_pton(AF_INET, s->IpAddress.String, &ia) != 1 || inet_pton(AF_INET, s->IpMask.String, &ma) != 1)
                continue;
            const DWORD ip = ia.S_un.S_addr, mask = ma.S_un.S_addr;
            if (ip == 0 || mask == 0 || mask == 0xFFFFFFFFu) continue;   /* a /32 (a VPN) has no broadcast */
            if ((ntohl(ip) >> 24) == 127) continue;             /* loopback: sent separately */
            const DWORD bc = (ip & mask) | ~mask;               /* bitwise on the network-order bytes */
            memcpy(out[n], &bc, 4);
            int dup = 0;
            for (int i = 0; i < n; i++) if (!memcmp(out[i], out[n], 4)) dup = 1;
            if (!dup) n++;
        }
    }
    return n;
}

/* One query to the limited broadcast, to each network's directed broadcast, and to loopback (a
 * host on this PC is seen), on port. */
static inline void lad_query(SOCKET s, uint16_t port, uint32_t nonce, uint32_t now_ms)
{
    uint8_t q[LANB_QUERY_LEN];
    lanb_query(q, nonce, now_ms);
    const uint8_t bcast[4] = { 255, 255, 255, 255 }, loop[4] = { 127, 0, 0, 1 };
    lad_send_to(s, q, LANB_QUERY_LEN, bcast, port);
    lad_send_to(s, q, LANB_QUERY_LEN, loop, port);
    uint8_t nets[16][4];
    const int n = lad_broadcasts(nets, 16);
    for (int i = 0; i < n; i++) lad_send_to(s, q, LANB_QUERY_LEN, nets[i], port);
}

/* Reads one datagram if there is one: 1 with buf, len and the sender's address, 0 when none. */
static inline int lad_recv(SOCKET s, uint8_t* buf, int cap, int* len, uint8_t ip[4], uint16_t* from_port)
{
    struct sockaddr_in a;
    int al = sizeof a;
    const int n = recvfrom(s, (char*)buf, cap, 0, (struct sockaddr*)&a, &al);
    if (n <= 0) return 0;
    *len = n;
    memcpy(ip, &a.sin_addr, 4);
    if (from_port) *from_port = ntohs(a.sin_port);
    return 1;
}

/* Answers every query waiting on a hosting socket with the session a. Returns the number answered. */
static inline int lad_host_serve(SOCKET s, const lanb_answer* a)
{
    int served = 0;
    uint8_t buf[256], ip[4];
    int n;
    uint16_t port = 0;
    while (lad_recv(s, buf, sizeof buf, &n, ip, &port)) {
        uint32_t nonce, sent;
        if (!lanb_parse_query(buf, n, &nonce, &sent)) continue;
        lanb_answer r = *a;
        r.nonce = nonce;
        r.sent_ms = sent;
        uint8_t out[LANB_ANSWER_LEN];
        lanb_answer_pack(out, &r);
        lad_send_to(s, out, LANB_ANSWER_LEN, ip, port);
        served++;
    }
    return served;
}

/* Reads the answers waiting on a querying socket into l (at now_ms). Returns the answers read. */
static inline int lad_browse_read(SOCKET s, lanb_list* l, uint32_t now_ms)
{
    int got = 0;
    uint8_t buf[256], ip[4];
    int n;
    while (lad_recv(s, buf, sizeof buf, &n, ip, NULL)) {
        lanb_answer a;
        if (!lanb_answer_parse(buf, n, &a)) continue;
        /* answers to an older search still count (late), as lanb_list documents */
        lanb_add(l, ip, &a, now_ms);
        got++;
    }
    return got;
}

#endif /* _WIN32 */
#endif
