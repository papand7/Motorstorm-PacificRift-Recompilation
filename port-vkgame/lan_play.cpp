/* LAN play: the Host and Join runtime behind the LAN screen (lan_play.h, lan_menu.h).
 *
 * One thread (lan_thread) owns every socket: the room server (lrn_*), the hosting UDP answer
 * socket and the browsing UDP socket. The page calls lan_play_* under s_cs. Windows only; on other
 * hosts every call is a no-op. The protocol and list are in lan_room.h, lan_room_net.h,
 * lan_browser.h and lan_discovery.h, each with its test under port-vkgame/tests/. */
#include "lan_play.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include "lan_room_net.h"
#include "lan_discovery.h"
#include "np_psnr.h"     /* libs/network: the game's connection to the room server */
#include <windows.h>

#define LAN_MAX_DEFAULT 8          /* HYPOTHESIS: the room size advertised before a room exists */
#define LAN_BROWSE_MS   2000u      /* the list is searched while the page touched it this recently */
#define LAN_QUERY_MS    1000u      /* one query per second (lan_browser.h) */

static CRITICAL_SECTION s_cs;
static LONG s_inited;
static HANDLE s_thread;
static volatile LONG s_quit;

static lrn s_room;                  /* the room server (valid while s_hosting) */
static SOCKET s_host_sock = INVALID_SOCKET;
static SOCKET s_qry_sock = INVALID_SOCKET;
static int s_hosting;
static int s_set_env;               /* this process set PSNR_SERVER / PS3_NET_ONLINE for hosting or a join */
static uint64_t s_session;
static char s_name[LANB_NAME_MAX + 1];
static char s_msg[160];             /* the last host or join outcome */
static lanb_list s_list;
static uint32_t s_touch_ms, s_last_query_ms, s_nonce = 1;

static void lock(void) { EnterCriticalSection(&s_cs); }
static void unlock(void) { LeaveCriticalSection(&s_cs); }

/* _putenv_s with an empty value removes the variable (getenv then returns NULL). */
static void set_env(const char* name, const char* value)
{
    _putenv_s(name, value);
}

/* The answer this PC gives to queries: the room's size when a room exists. */
static lanb_answer host_answer(void)
{
    lanb_answer a;
    memset(&a, 0, sizeof a);
    a.ver = LANB_VERSION;
    a.session = s_session;
    a.room_port = LANB_ROOM_PORT;
    a.state = LANB_STATE_LOBBY;
    int players = 0, max = LAN_MAX_DEFAULT;
    if (lr_room_info(&s_room.s, NULL, &players, &max) == 0) { players = 0; max = LAN_MAX_DEFAULT; }
    a.players = (uint8_t)(players > 255 ? 255 : players);
    a.max = (uint8_t)(max > 255 ? 255 : max);
    snprintf(a.name, sizeof a.name, "%s", s_name);
    return a;
}

/* Drops this process's connection to a room server and stops reconnecting (np_psnr.h). The
 * server then removes the player from its room and tells the others. */
static void drop_connection(void)
{
    np_psnr_retry_on(0);
    np_psnr_disconnect();
}

static void stop_hosting_locked(void)
{
    if (!s_hosting) return;
    if (s_host_sock != INVALID_SOCKET) closesocket(s_host_sock);
    s_host_sock = INVALID_SOCKET;
    drop_connection();          /* the game's own connection is to this room server */
    lrn_close(&s_room);
    s_hosting = 0;
    if (s_set_env) {
        set_env("PSNR_SERVER", "");
        set_env("PS3_NET_ONLINE", "");
        s_set_env = 0;
    }
}

static DWORD WINAPI lan_thread(void* arg)
{
    (void)arg;
    while (!s_quit) {
        lock();
        const uint32_t now = GetTickCount();
        if (s_hosting) {
            lrn_step(&s_room, 0);
            const lanb_answer a = host_answer();
            lad_host_serve(s_host_sock, &a);
        }
        const int browsing = (uint32_t)(now - s_touch_ms) < LAN_BROWSE_MS;
        if (browsing) {
            if (s_qry_sock == INVALID_SOCKET) s_qry_sock = lad_udp(0, 1);
            if (s_qry_sock != INVALID_SOCKET) {
                if (!s_last_query_ms || now - s_last_query_ms >= LAN_QUERY_MS) {
                    s_last_query_ms = now;
                    s_nonce++;
                    lad_query(s_qry_sock, LANB_PORT, s_nonce, now);
                }
                lad_browse_read(s_qry_sock, &s_list, now);
            }
        } else if (s_qry_sock != INVALID_SOCKET) {
            closesocket(s_qry_sock);
            s_qry_sock = INVALID_SOCKET;
        }
        lanb_expire(&s_list, now);
        unlock();
        Sleep(5);
    }
    return 0;
}

/* Starts the thread on first use. Caller holds s_cs. */
static void ensure_thread_locked(void)
{
    if (s_thread) return;
    s_quit = 0;
    s_thread = CreateThread(NULL, 0, lan_thread, NULL, 0, NULL);
}

void lan_play_init(void)
{
    if (InterlockedCompareExchange(&s_inited, 1, 0) != 0) return;
    InitializeCriticalSection(&s_cs);
    WSADATA w;
    WSAStartup(MAKEWORD(2, 2), &w);
    s_session = ((uint64_t)GetTickCount() << 32) ^ ((uint64_t)GetCurrentProcessId() << 16) ^ 0x4D535052ull;
    char host[MAX_COMPUTERNAME_LENGTH + 1];
    DWORD n = sizeof host;
    if (!GetComputerNameA(host, &n)) host[0] = 0;
    lanb_host_name(host, s_name);
    lanb_reset(&s_list, 1);
    s_host_sock = s_qry_sock = INVALID_SOCKET;
    snprintf(s_msg, sizeof s_msg, "%s", "Not hosting.");
    atexit(lan_play_shutdown);  /* every exit path, the title's sys_process_exit included */
}

void lan_play_shutdown(void)
{
    if (!s_inited) return;
    lock();
    stop_hosting_locked();
    if (s_set_env) drop_connection();   /* a joined game's connection, if it is still up */
    if (s_qry_sock != INVALID_SOCKET) closesocket(s_qry_sock);
    s_qry_sock = INVALID_SOCKET;
    unlock();
    s_quit = 1;
    if (s_thread) { WaitForSingleObject(s_thread, 2000); CloseHandle(s_thread); s_thread = NULL; }
}

int lan_play_hosting(void)
{
    if (!s_inited) return 0;
    lock();
    const int h = s_hosting;
    unlock();
    return h;
}

int lan_play_set_host(int on)
{
    if (!s_inited) return -1;
    lock();
    int rc = 0;
    if (on && !s_hosting) {
        if (lrn_open(&s_room, LANB_ROOM_PORT, 0, GetTickCount())) {
            snprintf(s_msg, sizeof s_msg, "Port %u is in use (another game or host on this PC).", LANB_ROOM_PORT);
            rc = -1;
        } else {
            s_host_sock = lad_udp(LANB_PORT, 1);
            if (s_host_sock == INVALID_SOCKET) {
                lrn_close(&s_room);
                snprintf(s_msg, sizeof s_msg, "Port %u is in use (another host on this PC).", LANB_PORT);
                rc = -1;
            } else {
                s_hosting = 1;
                s_set_env = 1;
                set_env("PSNR_SERVER", "127.0.0.1:36100");
                set_env("PS3_NET_ONLINE", "1");
                np_psnr_disconnect();          /* a connection to another game, if any, goes */
                np_psnr_retry_on(1);           /* the game connects to this room server at its next Matching2 start */
                snprintf(s_msg, sizeof s_msg, "Hosting as %s. Start a race lobby in the game.", s_name);
                ensure_thread_locked();
            }
        }
    } else if (!on && s_hosting) {
        stop_hosting_locked();
        snprintf(s_msg, sizeof s_msg, "%s", "Not hosting.");
    }
    unlock();
    return rc;
}

void lan_play_status(char* out, size_t cap)
{
    if (!cap) return;
    if (!s_inited) { snprintf(out, cap, "%s", "Off"); return; }
    lock();
    snprintf(out, cap, "%s", s_msg);
    unlock();
}

void lan_play_touch(void)
{
    if (!s_inited) return;
    lock();
    s_touch_ms = GetTickCount();
    ensure_thread_locked();
    unlock();
}

void lan_play_refresh(void)
{
    if (!s_inited) return;
    lock();
    lanb_reset(&s_list, s_list.nonce + 1);
    s_last_query_ms = 0;
    unlock();
}

int lan_play_entries(void)
{
    if (!s_inited) return 0;
    lock();
    const int n = s_list.n;
    unlock();
    return n;
}

int lan_play_entry(int i, char* label, size_t label_cap, char* value, size_t value_cap, int* joinable)
{
    if (!s_inited) return 0;
    lock();
    int ok = 0;
    if (i >= 0 && i < s_list.n) {
        const lanb_entry* e = &s_list.e[i];
        lanb_row_label(e, label, label_cap);
        lanb_row_value(e, value, value_cap);
        if (joinable) *joinable = lanb_joinable(e);
        ok = 1;
    }
    unlock();
    return ok;
}

int lan_play_join(int i, char* msg, size_t cap)
{
    if (!s_inited) return -1;
    lock();
    int rc = -1;
    if (s_hosting) {
        snprintf(msg, cap, "%s", "Stop hosting first.");
    } else if (i < 0 || i >= s_list.n) {
        snprintf(msg, cap, "%s", "That game is no longer listed.");
    } else if (!lanb_joinable(&s_list.e[i])) {
        snprintf(msg, cap, "%s", s_list.e[i].a.ver != LANB_VERSION ? "Different version: it cannot be joined."
                                                                  : "That game is full.");
    } else {
        char addr[64];
        lanb_server(&s_list.e[i], addr, sizeof addr);
        set_env("PSNR_SERVER", addr);
        set_env("PS3_NET_ONLINE", "1");
        s_set_env = 1;
        np_psnr_disconnect();          /* a game joined earlier in this run lets go of its server */
        np_psnr_retry_on(1);           /* the game's next Matching2 start (or its next call) connects here */
        snprintf(msg, cap, "Joining %s at %s. Enter the game's multiplayer menu to connect.", s_list.e[i].a.name, addr);
        snprintf(s_msg, sizeof s_msg, "%s", msg);
        rc = 0;
    }
    unlock();
    return rc;
}

void lan_play_leave(void)
{
    if (!s_inited) return;
    lock();
    drop_connection();
    snprintf(s_msg, sizeof s_msg, "%s", s_hosting ? "Left the game. Still hosting."
                                                 : "Left the game. Join or host again to play on the LAN.");
    unlock();
}

#else   /* not Windows: no LAN play */
void lan_play_init(void) {}
void lan_play_shutdown(void) {}
int lan_play_hosting(void) { return 0; }
int lan_play_set_host(int on) { (void)on; return -1; }
void lan_play_status(char* out, size_t cap) { if (cap) snprintf(out, cap, "%s", "LAN play is Windows only."); }
void lan_play_touch(void) {}
void lan_play_refresh(void) {}
int lan_play_entries(void) { return 0; }
int lan_play_entry(int i, char* l, size_t lc, char* v, size_t vc, int* j) { (void)i; (void)l; (void)lc; (void)v; (void)vc; (void)j; return 0; }
int lan_play_join(int i, char* msg, size_t cap) { (void)i; (void)msg; (void)cap; return -1; }
void lan_play_leave(void) {}
#endif
