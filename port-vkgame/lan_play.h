/* LAN play: Host and Join behind the LAN screen (lan_menu.h, reached from the game's ONLINE item). Implemented in
 * lan_play.cpp; the game's own Matching2 client does the rest, through PSNR_SERVER.
 *
 * Hosting runs the room server (lan_room_net.h, port LANB_ROOM_PORT) and answers LAN queries
 * (LANB_PORT). Joining sends queries and lists the answers (lan_browser.h). A join sets
 * PSNR_SERVER and PS3_NET_ONLINE for the game's psnr client, which reads them when its Matching2
 * context first connects. */
#ifndef LAN_PLAY_H
#define LAN_PLAY_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

void lan_play_init(void);                      /* once, at start (before any other call) */
void lan_play_shutdown(void);                  /* stops the LAN thread and closes its sockets */
int  lan_play_hosting(void);                   /* 1 while hosting */
int  lan_play_set_host(int on);                /* 0 ok; -1 when the room or discovery port is taken */
void lan_play_status(char* out, size_t cap);   /* one line for the Host row's info */
void lan_play_touch(void);                     /* the Join list is on screen: browse while touched */
void lan_play_refresh(void);                   /* clears the list; the next queries refill it */
int  lan_play_entries(void);                   /* games listed now (sorted) */
/* Entry i's label (host name) and value ("Lobby  2/4  30 ms"); joinable is 0 for a different version or full. */
int  lan_play_entry(int i, char* label, size_t label_cap, char* value, size_t value_cap, int* joinable);
/* Joins entry i: sets PSNR_SERVER and PS3_NET_ONLINE. 0 ok; msg gets the reason otherwise. */
int  lan_play_join(int i, char* msg, size_t cap);
/* Leaves: the connection to the room server is closed (the server removes the player from its room
 * and tells the others) and reconnecting stops until Join or Host again. Safe when not joined. */
void lan_play_leave(void);

#ifdef __cplusplus
}
#endif
#endif
