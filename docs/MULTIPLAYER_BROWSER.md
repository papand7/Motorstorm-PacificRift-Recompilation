# Host / Join server browser: design (MotorStorm: Pacific Rift, native PC port)

Status: **design only**. Nothing was implemented, built, run, committed or pushed. No game data, decrypted code or
private traces are quoted. Nightfire's implementation was read for its protocol and design only; no code is copied,
and everything below is described in our own terms.

Labels: **VERIFIED** (read in our notes or code, cited), **PARTIAL**, **HYPOTHESIS**, **BLOCKED**.

## 0. Sources read

- `AGENTS.md`: ps3recomp pin, public/private boundary, audit rules. Game-specific work stays outside `ps3recomp/`. **VERIFIED**
- `docs/LAN_MULTIPLAYER.md`: investigation; the game's network imports; the Matching2 stand-in; option A/B/C/D. **VERIFIED**
- `ps3recomp-vkgame/tests/net/lan_pair.c` and `run_loopback.sh`: a two-process, framework-only test. The host sends UDP
  beacons on a discovery port and advertises a TCP port; the join finds it, connects, and sends a 64 KiB HELLO blob; the
  host answers with a WELCOME blob; both sides check the bytes. Passes on 127.0.0.1 by its own pass rule. **VERIFIED** (as
  reported; the script was read, not re-run for this document). It proves host transport only, not any game protocol.
- Nightfire (read only): `src/game/lan_play.cpp` (LAN host/join, query broadcast, publish thread), `src/game/online.cpp`
  (online list), `PROGRESS.md` entries dated 2026-11-10 ("the online browser", "the publish flag and the game's announce")
  and 2026-11-13 (bug hunt). Nightfire's master-server API (`server/master/api.php`) was read for its request shapes. **VERIFIED**

## 1. The master server API

### 1a. How Nightfire uses it (the design to reuse)

- **Announce.** While a host runs with publishing on, a background thread asks the master to "announce" this game about
  every 30 seconds. The request carries the game id, the game port, a max-player count and a version tag. The master
  replies and remembers the caller's address and port. **VERIFIED** (`lan_play.cpp` StartPublishing; PROGRESS 2026-11-10).
- **Verify, then list.** The master does not trust the announce. It sends the game's own UDP query to the caller's
  address and port, and lists only what the game answers (name, map, players). A server that does not answer is not
  listed. The master's header comment states this design. **VERIFIED** (`server/master/api.php` header and `ask_nightfire`).
- **Keep-alive window.** A server stays listed for 90 seconds after its last announce. Limits: one announce per address
  and port every 10 seconds; at most 3 servers per IP; at most 500 servers in total. **VERIFIED** (`api.php` constants).
- **Remove.** Stopping the host sends a "remove" request from the publish thread. The thread also sends it on exit. Nightfire's
  notes record a known race: a late "remove" from an old thread can land after a new host's announce. **VERIFIED** (PROGRESS
  2026-11-13, "left, reviewed, not changed"). Our design fixes this (section 3c).
- **List.** The game fetches the list on a background thread when its browse page opens. It asks for one tab-separated line
  per server (address, port, name, map, players, max, mode, version). There is no refresh button; the list refreshes on each
  open. **VERIFIED** (`online.cpp`; PROGRESS 2026-11-10 "Not done").
- **Join.** The player picks a row. The game joins by the listed address and port through the same path as a LAN host.
  Joining from the online list was not yet played through to a match. **PARTIAL** (PROGRESS 2026-11-10).
- **Selftest.** The master has a self-check that its file is writable and that it can send UDP. **VERIFIED** (`api.php` header).
- **Local LAN search (separate from the master).** Nightfire's LAN browser broadcasts a query about once per second, to the
  broadcast address and to loopback, on the game port. Hosts answer with name, map, players and port. Entries expire
  after about 3.5 seconds without an answer. **VERIFIED** (`lan_play.cpp`, the query routine).
- **Version gate.** Each protocol carries a magic value. A change to the wire format changes the magic, so old and new
  builds do not see each other (the 1.5.14 change). **VERIFIED** (`lan_play.cpp` kMagic; PROGRESS 2026-11-10).

### 1b. What our server stores

Per listed session (keyed by address, port and a host-chosen session id):

| Field | Source | Notes |
|---|---|---|
| game id | announce | fixed `motorstorm-pr` (our own id, not Sony's name) |
| session id | announce | random 64-bit, new on each Publish On. Replaces the port+address key so a late "remove" from an old session cannot delete a new one |
| display name | game's answer | player-chosen, not the PC's hostname (privacy, section 2) |
| address (IPv4) | the caller's source address | the master records it; it is the listed address |
| port | announce | game session port |
| player count | game's answer | humans in the session |
| max players | announce, confirmed by the game's answer | open question (section 7) |
| version | announce and game's answer | the protocol magic and build tag |
| optional: track, mode | game's answer | only if the game can give them without a menu read (**BLOCKED**, section 5) |
| last seen | master clock | drives the 90-second window |

Not stored: the player's real name, PSN or account identifiers, the PC's hostname, and any game data.

### 1c. API surface (our design, not yet written)

- `announce(game, port, session, max, version)`: the master probes the caller's address and port, and stores the
  entry only when the game answers.
- `remove(game, port, session)`: deletes that entry only (session must match).
- `list(game, format=lines|json)`: returns live entries.
- `selftest()`: checks writability and that a UDP probe can be sent.
- Rate limits and caps as in section 1a, tuned for a smaller user base.

## 2. Who runs the master, and the legal and privacy points

### 2a. Options

| Option | Who runs it | Pros | Cons |
|---|---|---|---|
| A. Our own server on the user's domain | the user (PHP on hosting they control, like Nightfire's API file, or a small service) | the user controls uptime, the list, the logs and the privacy notice; the code is our own; no third party's domain | the user pays hosting and handles abuse reports |
| B. The URL Nightfire uses | another party's domain (the notes give `masterserver.dankelsoft.dk`) | nothing to build for phase 1 | **Only if the user owns it**; the notes do not say so. The notes also say the live address did not resolve when checked (PROGRESS 2026-11-10). It would list MotorStorm sessions on a server that is not ours, with a Nightfire-named game id |
| C. The user's own PC on the LAN | the user, for testing only | no public listing | no internet browse |

### 2b. Recommendation

**Option A**, with option C for phase 1 tests. Reasons: the user controls the domain, the code (our own, public-safe, no game
data), the retention policy and the shutdown. It avoids a dependency on a domain whose owner and status are unknown. It keeps
MotorStorm sessions out of another game's list. Option B is acceptable only if the user confirms ownership in writing.

### 2c. Legal and privacy points

- **Public list of player addresses (VERIFIED as a Nightfire design choice; the risk is ours).** Any listed host's IP is
  public to anyone who fetches the list. Mitigations: show the address only to a player who chooses to join; purge on the
  90-second window; log nothing beyond counts and errors; publish a short privacy notice on the user's site. If any user
  is in the EU or UK, data-protection rules (for example GDPR) apply to the IP addresses the master stores. Get legal advice
  before public launch. **HYPOTHESIS** on which rules apply; **not legal advice**.
- **Names.** "MotorStorm" and "PlayStation" are trademarks of their owners (not verified here). Use "MotorStorm: Pacific Rift"
  only in descriptive text, with a clear unofficial, unaffiliated notice. The game id is our own.
- **Copyright and public source.** `AGENTS.md` bars game inputs, decrypted modules, assets and lifted code from public source.
  The master and browser code is our own and can ship publicly if it contains none of those. The browser UI may show
  game strings only from the user's own install, never from the repo.
- **No PSN.** The browser does not touch Sony's servers, does not emulate them (`LAN_MULTIPLAYER.md` option D is excluded),
  and does not use PSN identities.
- **Service terms.** Post a rule that the master lists only what a game answers, and state how to request removal.

## 3. The host side (MotorStorm)

### 3a. Where the page lives

Two candidates (decision in section 7):

1. **PC Settings hub**: a new page beside Display, Upscaling and Graphics (see `docs/SETTINGS.md`). Pros: one place for PC
   options, the same file (`settings.ini`). Cons: a settings page is a poor home for a live session.
2. **Retail menu**: a "Host Game" entry in the game's own multiplayer flow. **BLOCKED** until the menu reaches a multiplayer
   screen (section 5b).

Recommended for phase 2: a **port-side Host Game page** in the PC hub (it does not depend on the retail menu), reached from
the same pages list. It can move into the retail menu later if the game's own multiplayer screen is reached.

### 3b. Controls on the Host Game page

| Control | Choices | Default | Stored as |
|---|---|---|---|
| Publish online | Off, On | Off | `publish` in `settings.ini` (port owns the file; see SETTINGS.md) |
| Listen port | a number | a free port; not 27787 (Nightfire's) | `host_port` |
| Max players | open (section 7) | open | `max_players` |
| Display name | text (short) | empty, asks on first Publish | `host_name` |
| Start / Stop | button | | session state, not saved |

The page shows the state: "Not published", "Publishing (N players)", "Last announce failed". A failed announce is shown, not
silent.

### 3c. Publish rules (design)

- Publish starts only when the host session is live. It stops when the session ends, the page closes with Publish Off, or
  the game exits.
- A background thread sends announce about every 30 seconds with its session id. On stop it sends remove for that session
  id only. The session id prevents Nightfire's late-remove race.
- Announce requests are time-limited (Nightfire's note: up to 8 seconds). The thread must never block the game's frame.
- The game answers the master's probe on its session port (its name, players, max, version). Without that answer the
  master lists nothing, so the game must answer even with an empty lobby.

### 3d. What the game session must send

- **Probe answer** (a UDP datagram on the session port): magic and version, session id, display name, player count, max
  players, a short map or mode if known. Nothing from game memory is sent beyond these fields.
- **Join reply**: accept or refuse a join. Refusal reason: full, version mismatch, or not hosting.
- **Session data**: whatever the game's own multiplayer protocol needs. Unknown until identified (section 5a).

## 4. The join side

### 4a. Browse page

- Opens a port-side list (Browse Games). On open, a background thread fetches the master's list (`format=lines`).
- Each row shows: display name, player count / max, version (and mode or map if known). Rows whose version differs from
  ours are shown greyed with "different version", not hidden.
- While the fetch runs, the list shows "Searching...". A failed fetch says so; the list keeps the last good result.
- Refresh: each open of the page, plus a Refresh button (Nightfire has none; we add one, since a live list changes).
- A LAN search runs at the same time (section 4c), so a host on the same network shows even if the master is down.

### 4b. Join by address

- A text field takes `address` or `address:port`. A listed row fills it in.
- Join sends the game's join request to that address and port. A reply names the outcome (accepted, full, version, refused).
- A timeout (about 5 seconds, design choice) shows "No answer from host". Nothing is retried in a loop.

### 4c. LAN browse

- Broadcast a query about once per second on the session port (and to loopback), as Nightfire does. Entries expire 3.5 seconds
  after the last answer. **HYPOTHESIS** that the same probe format works for MotorStorm; the transport is **PARTIAL** (section 5).

## 5. Blockers

| # | Item | Label | Detail |
|---|---|---|---|
| a | The MotorStorm multiplayer session protocol is not identified | **BLOCKED** | No reverse engineering of it has been done. `LAN_MULTIPLAYER.md` names the Matching2 imports and the `evo::network` socket layer, but not the packet formats, the session handshake or the in-race traffic. Until traced, the game cannot be joined even if the browser works. |
| b | The game's menus must reach a multiplayer screen in our port | **BLOCKED** | The title and menu are not yet reached in the native port (`docs/STATUS.md`, `docs/RESEARCH.md`). The frontend path after `SetExitOnline` is only **PARTIAL**. No multiplayer page can be tested until this moves. |
| c | The retail GUI engine cannot easily show a dynamic list | **HYPOTHESIS** | The retail menu uses fixed `.gui` pages with string IDs. A live server list needs variable rows, which the page format may not give. Nightfire solved this with a port-side page. Expect the same: the browser is port-side, and the retail menu only gets a launch point if its engine allows one. |
| d | Max players per session is unknown | **BLOCKED** | No evidence in our notes (the LAN doc, STATUS, RESEARCH, COMPATIBILITY). The string table has not been read (`pcmenu/GUIFORMAT.md`). |
| e | Framework pin | **PARTIAL** | `LAN_MULTIPLAYER.md` section 3 records that `ps3recomp/` is not at the pinned revision `0fe7dbf5`. Network work must wait for the re-pin, or the framework code may differ. |
| f | HTTP client for the master | **PARTIAL** | Nightfire shells out to curl. Our port has a framework HTTP layer (`libs/network/cellHttp.c`, `cellHttpUtil.c`), but its use over plain HTTP or HTTPS to a public server has not been verified. The launcher must not depend on a curl binary we do not ship. |
| g | Master server does not exist yet | **BLOCKED** | No master is written, hosted or tested for MotorStorm. |
| h | Port 27787 and the session port | **PARTIAL** | Nightfire uses 27787. MotorStorm's port is undecided; `lan_pair` uses 47613 for its test only. Pick a port that does not collide with Nightfire. |

## 6. Phased plan

**Phase 1: master announce and list, with a test server (no game).**
- Write the master API (section 1c) as our own code in a public-safe folder, with a local test server. Test with a
  probe-only stub that answers the master's probe. Pass: announce, list, remove, expiry after 90 s, rate limits, and the
  selftest, all tested with a scripted client. No game build. No public hosting yet.
- Decide the master's domain and host (section 7).

**Phase 2: host and join over LAN, using the proven transport.**
- Build the Host Game page and the Browse page in the port (no retail menu). Use `lan_pair`'s transport idea (UDP beacon
  plus TCP session) for LAN discovery and join. Reuse the existing `sysNet` host socket path, gated as `PS3_NET_ONLINE`
  already is.
- Pass: two copies on loopback, then two machines on the LAN: one publishes, the other finds it by LAN browse and by master
  list (against the phase 1 server), and a join reaches "accepted" on both sides. The game's own session is not required yet.
- Do not run game tests during a race or a remote session on the user's machine. Keep runs short.

**Phase 3: the game's own session protocol.**
- Identify the MotorStorm session handshake and in-race traffic (blocker a). Connect the browser's join to the game's own
  lobby and race.
- Depends on: the title and menu reaching multiplayer (blocker b), and the framework pin (blocker e).
- Pass: two instances reach the same race with the game's own data path. Label each result VERIFIED, PARTIAL or BLOCKED.

## 7. Open decisions for the user

1. **Master server.** Option A (our server on the user's domain; recommended), option B (the Nightfire URL, only if the user
   owns it), or option C (LAN-only until later)? Which domain, and who hosts it?
2. **Max players.** The game's real limit is unknown. Options: read the lobby strings and rules first; or set a provisional
   limit (for example, the number the game's own lobby shows) and change it later. Which?
3. **Browser placement.** PC Settings hub (port-side, recommended for phase 2), or the retail multiplayer menu (blocked until
   the menu runs)?
4. **Display name and privacy.** Player-chosen names only (recommended), and a privacy notice on the user's site?
5. **Legal review.** Is the user willing to take legal advice on the IP-address list and trademark notice before any public
   launch?
6. **Pin.** Re-pin `ps3recomp/` to `0fe7dbf5` before network work (recommended), or upgrade deliberately?
7. **Testing policy.** Confirm two-process tests may run on this machine, with the time limits from `LAN_MULTIPLAYER.md`.
8. **Session port.** Choose a default that is not Nightfire's 27787.
