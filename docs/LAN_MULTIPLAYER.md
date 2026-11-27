# LAN (system link) multiplayer: investigation and design plan

Status: investigation only. Nothing was implemented, built, run, committed or pushed. Private inputs (EBOOT, extracted GUI pages, traces) were read but not copied. Only addresses, NIDs and function names are quoted.

Labels: **VERIFIED** (read in our notes or code, with a cited location), **PARTIAL**, **HYPOTHESIS**, **BLOCKED**. Each finding is tagged **[existing]** when it comes from notes already in the repo, or **[new]** when this investigation added it.

## Summary

- **System link is not confirmed.** No "System Link", "LAN" or equivalent label or handler name appears in any extracted data. The visible frontend uses a "Wreckreation" hub with Free Play, Split Screen and Online items, and the Online items use the NP Matching2 room API (`GoOnlineAndCreateRoom`, `JoinRoom`, `IAmSessionMaster`). Whether the retail 1.03 game also offers a LAN option is **BLOCKED** until the localized string table is read. [new]
- **The game's online path is PSN-shaped.** It imports about 100 `sceNp*` and `sceNp2` functions, mostly Matching2 room calls. Those are matchmaking calls against a server. [new]
- **The port already has a non-PSN stand-in for that path.** `libs/network/psnr` and `sysNet.c` implement Matching2 rooms on a self-hosted psnr server, with host UDP/TCP sockets for P2P traffic, gated by `PS3_NET_ONLINE`. It was verified with Simpsons Arcade (two instances, one machine). It has **not** been run with MotorStorm. [existing, for the framework]
- **Offline answer:** `cellNetCtlGetState` reports `Disconnected` (after Init), and every `sys_net` socket call is faked unless `PS3_NET_ONLINE` is set. [existing + new citations]
- **Blocker:** the game has not yet reached a title or menu in the native port (`docs/COMPATIBILITY.md`, `docs/STATUS.md`). Any multiplayer test is downstream of that. [existing]
- **Recommendation:** treat LAN as a later milestone. The first step is a framework-only two-process transport test that needs no game and no PSN. Afterwards, decide between extending the existing psnr-style LAN stand-in (option B) and a native broadcast discovery layer (option A). Do not emulate PSN servers.

## 1. Does the retail game have system link or LAN multiplayer?

### 1a. Menu topology

- Main menu entries: Festival, Wreckreation, Garage, Options, MotorStore. Festival calls `GameTypeSetFestival`; Wreckreation opens the `wreckreation` page; the others go to garage, options and motorstore. **VERIFIED (static)**, `generated/analysis/garage_menu/FINDINGS.md`, "Menu state machine". [existing]
- Game-type setters (the names are in the frontend script table; handler addresses from `generated/analysis/frontend_commands.txt`, which the garage audit warns may be shifted by one entry, so treat addresses as **PARTIAL**):

| Setter | Address (dump) | Meaning (inferred from name) |
|---|---|---|
| GameTypeSetWreckreationFreePlay | 0x0076E6D0 | Offline free play (**HYPOTHESIS** on meaning) |
| GameTypeSetWreckreationSplitScreen | 0x0076E738 | Local split screen |
| GameTypeSetWreckreationOnline | 0x0076E7A0 | Online session, Wreckreation rules |
| GameTypeSetRankedOnline | 0x0076E808 | Online, ranked |
| GameTypeSetCasualOnline | 0x0076E870 | Online, casual |
| GameTypeSetDemoSplitScreen / GameTypeSetDemo | 0x0076E940 / 0x0076E8D8 | Demo modes |
[new, names from `frontend_commands.txt`]

- Pause menu pages exist for `pausemenu-online` and `pausemenu-splitscreen` (extracted `.gui` pages, private). **VERIFIED** that the pages exist; their labels come from string IDs. [new]
- Race lobby options (ambience, privacy) exist, as text choices. **VERIFIED** in `generated/analysis/pcmenu/GUIFORMAT.md` (line 108). [existing]

### 1b. What each online entry calls

| Frontend command | Address (dump) | Role inferred from name | Relevant imports |
|---|---|---|---|
| Online / OnlineOnline / OnlineGame | 0x00782F50 / 0x00783358 / 0x00779410 | Enter online mode | NP manager |
| NoNetwork | 0x00782C60 | Offline branch | none |
| GoOnlineStart | 0x00776520 | Start online flow | NP init |
| GoOnlineAndCreateRoom | 0x00776568 | Create a Matching2 room | `sceNpMatching2createJoinRoom` |
| JoinRoom / RoomJoined / IAmSessionMaster | 0x007794F0 / 0x007796C8 / 0x007795E0 | Join and session-master roles | Matching2 room data |
| JoinCustomGame | 0x00777448 | Join a custom game | Matching2 search |
| ExitOnline / SetExitOnline / LeaveOnlineRace / QuitOnlineRace | 0x00782EB0 / 0x00782E68 / 0x00777A38 / 0x00777A80 | Leave | Matching2 leave |

Addresses are from `frontend_commands.txt` (**PARTIAL**). The `SetExitOnline` path (0x00782E68) is the one already traced in `docs/RESEARCH.md` "Frontend handoff after SetExitOnline (2026-10-21)" and is **VERIFIED** as a command transition only. [existing + new]

### 1c. Conclusion for question 1

- **VERIFIED (absence in the extracted symbol and command data):** no system link or LAN label or handler appears in `frontend_commands.txt`, the `.gui` page names, or the GUI notes. [new]
- **BLOCKED:** the visible labels are string IDs. The localized string table has not been extracted (`generated/analysis/pcmenu/GUIFORMAT.md` line 102: "string table not read"). So whether a LAN item exists on screen is unknown. The next step is to read that table from the private extraction.
- **Ranked online** depends on PSN ranking and scoring (`sceNpScore`), so LAN cannot provide it. This is **VERIFIED** from the imports and names, not from behaviour. [new]

## 2. Network APIs the game uses

Import counts come from `generated/analysis/EBOOT.imports.json`. NID names come from two tables: `ps3recomp/tools/nid_from_protos.json` and the comments in `ps3recomp/tools/nid_database.py` (lines 429–450). [new, counts and matches verified in this investigation]

| Library | Imports | Named by the two tables | Unnamed |
|---|---|---|---|
| sys_net | 25 | 20 | 5 (0x139A9E9B, 0x03F09E20A, 0x051EE3EE, 0x0A9A079E0, 0x0B68D5625) |
| cellNetCtl | 6 | 2 (NetStartDialogLoadAsync, NetStartDialogUnloadAsync) | 4 (0x105EE2CB, 0x1E585B5D, 0x08B3EBA69, 0x0BD5A59FC) |
| sceNp | 69 | 17 | 52 |
| sceNp2 | 25 | 14 | 11 |
| sceNpTrophy | 11 | 1 | 10 |
| cellGame | 5 | 0 | 5 |

- **sys_net named calls:** socket, bind, connect, send, recv, sendto, recvfrom, setsockopt, getsockopt, socketclose, accept, listen, shutdown, getsockname, gethostbyname, inet_addr, inet_ntoa, sys_net_free_thread_context, _sys_net_errno_loc, sys_net_show_ifconfig. **VERIFIED** by NID match. [new]
- **sceNp2 / Matching2 imports named:** Init2, Term2, createJoinRoom, contextStartasync, SetRoomdataexternal, SetRoomdataInternal, GetRoomdataexternalList, KickoutRoomMember, RegisterRoomMessagecallback, Registercontextcallback, GetServerIdListLocal, Geteventdata. **VERIFIED** by NID match (e.g. sceNpMatching2Init2 = 0xF4BABD3F). [new]
- **sceNp imports named:** lookup, manager account and entitlement queries, ticket request, score term, basic messaging. **VERIFIED** by NID match. [new]
- **evo::network (game socket layer):** `generated/analysis/c38/rv/symbols.txt` lists `evo::network::simplesocket` (connect, listen, send, recv, set_nodelay, anything_waiting), `socketbuffer` and `net_start`/`net_stop`. These are plain TCP wrappers over the sys_net calls. **HYPOTHESIS** that they belong to the 1.03 EBOOT (the c38 folder's provenance is not confirmed). Their use in race traffic is **BLOCKED** until traced. [new]
- **hkPs3NetworkInit / hkPs3NetworkQuit (Havok):** present as symbols. **HYPOTHESIS** that they are Havok glue, not gameplay. [new]
- **cellNetCtl imports:** the two named ones are the "net start dialog" calls. The other four are unknown. **BLOCKED** until resolved.

### 2a. What the framework already implements (sources)

| Area | Where | State |
|---|---|---|
| sys_net host sockets | `ps3recomp/libs/network/sysNet.c` (about 1,060 lines; `ps3_net_host_register` at 1062) | VERIFIED by `libs/network/tests/test_sys_net.c` (loopback, P2P bind, accept port). Enabled only by `PS3_NET_ONLINE`. [existing] |
| Offline sys_net model | `ps3recomp/runtime/ppu/ppu_sysprx.cpp` 516–600, gate at 859–862 | `socket` returns fake fds from 3; `sendto` reports full length; `recv`/`poll`/`select` report nothing ready after honoring the timeout. VERIFIED by reading. [new citation] |
| cellNetCtl | `ps3recomp/libs/network/cellNetCtl.c` lines 5, 41–47, 148–163 | Initialized offline state is `Disconnected`. Connected only if `PS3_NET_ONLINE` is set (line 47). VERIFIED by reading. [existing + new citation] |
| Matching2 stand-in | `libs/network/sceNpMatching2.c` (about 54 KB), `np_psnr.c/.h`, `psnr/psnr.c` (vendored, MIT, from another project) | Rooms, search, join, kick, room data and messages on a psnr server. Verified only for Simpsons Arcade with two local instances (`generated/analysis/t122/.../ONLINE.md`, reference notes; **not** our project). [existing, reference only] |
| sceNpScore, sceNpLookup, sceNpTrophy | `libs/network/sceNpScore.c`, `sceNpLookup`, `sceNpTrophy.c` | Score on psnr leaderboards; lookup answered locally; trophy imports present. Not verified for MotorStorm. [existing] |
| Voice | `cellSysutilAvc2.c` | Loads and joins; no audio. [existing] |

### 2b. What is missing for MotorStorm

- **MISSING (verified by NID coverage):** the 87 unnamed imports above. Several are likely in the Matching2 and NP manager families, and we cannot tell whether the framework implements them until they are named. **PARTIAL.** [new]
- **MISSING:** a check that each named import used by the game reaches an implemented handler. The framework's NID set (`ps3recomp/tools/nid_from_protos.json`, 379 entries) matches 34 of the 141 network imports. The matching implementation is not verified against the game's call sites. **PARTIAL.** [new]
- **BLOCKED:** UDP broadcast use. No `SO_BROADCAST` or broadcast address appears in our notes. The `setsockopt` call sites are not yet traced. **HYPOTHESIS** only. [new]

## 3. What the port returns now, and where it is decided

- **Offline (default):** `cellNetCtlInit` then `cellNetCtlGetState` returns success with `Disconnected`. Source: `cellNetCtl.c` lines 148–163. **VERIFIED** by `docs/RESEARCH.md` "2026-10-20 loading composition and network state" (the earlier `NOT_INITIALIZED` bug was fixed there). [existing]
- **Offline sockets:** `sys_net` calls are answered by the offline model in `ppu_sysprx.cpp` 516–600. The model never sends traffic. **VERIFIED** by reading. [new citation]
- **Gate:** `PS3_NET_ONLINE` set in the environment switches both: cellNetCtl reports connected (`cellNetCtl.c:47`) and `ps3_net_host_register` installs real sockets (`ppu_sysprx.cpp:862`). **VERIFIED** by reading. [new]
- **Documentation:** `docs/COMPATIBILITY.md` line 50 lists "Input, audio, networking" as UNTESTED with this title. **VERIFIED**. [existing]
- **Pin mismatch:** `ps3recomp/` is at HEAD `f373398c` with two modified scratch files. `AGENTS.md` pins `0fe7dbf5db9a467aca268865fb26170ea113c541`, which exists in the repo history. **VERIFIED**: the checkout is not at the pin. Resolve before any network work, because `sysNet.c` and `sceNpMatching2.c` may differ between the two. [new]

## 4. Design options

| Option | Summary | Effort | Risk | What must be reverse-engineered | Proprietary dependency |
|---|---|---|---|---|---|
| **A. Native LAN session** | Make the game's own online flow find peers by UDP broadcast on the LAN, then run the game's session protocol over host sockets. | High. Needs the game's room and session logic, in-race packet formats and a discovery design. | High. Replacing Matching2 changes game-logic call paths; the discovery protocol would be our own design. | Matching2 caller sequence (from `GoOnlineAndCreateRoom`, `JoinRoom`, `IAmSessionMaster`), `evo::network` packet formats, whatever `setsockopt` does. | None needed from Sony if the packets are the game's own. Matching2 server replies are PSN-defined and cannot be reproduced without PSN. |
| **B. Bridge to host sockets, LAN stand-in for Matching2** | Use the existing `sysNet.c` and psnr-style room stand-in, run the room server on one LAN PC, and point all PCs at it. Peers exchange traffic over host UDP/TCP. | Low to medium. Most code exists. Work is the MotorStorm-specific call coverage and a LAN server build. | Medium. Verified only on Simpsons. The psnr protocol is not Sony's but is still not what the game expects from PSN, so the game's own replies must match what the stand-in returns. | Named Matching2 calls and their reply shapes for MotorStorm; NID coverage for the 87 unnamed imports. | No Sony protocol needed. The stand-in is a self-hosted server, not an emulation of PSN servers. |
| **C. Hybrid** | Keep B's room stand-in, but add LAN broadcast discovery in front of it so no server is needed. Clients find a host on the LAN, then use B's P2P path. | Medium. Adds a discovery module and a host role. | Medium. Discovery is simple; the room state machine is the risky part. | Same as B, plus the room state machine's expectations of the server. | None from Sony. |
| **D. Emulate PSN servers** | Reproduce Sony's Matching2 and NP servers. | Very high. | Very high. | Full PSN wire protocol. | **Not allowed by project policy.** We will not emulate PSN servers. |

Notes:
- Options A and C change the number of pieces that talk to each other. Option B changes only the server side and keeps the game's code path.
- Ranked and any PSN-backed feature (leaderboards, trophies) stay out of scope for LAN.

## 5. Smallest first milestone

Milestone prerequisites (**BLOCKED** today): the original game must reach a title or menu in the native port. Until then, no online test is meaningful. This is the current frontend work in `docs/STATUS.md`.

**M0 (no game, can start now): two-process transport proof in the framework.**
- Goal: two processes on one machine, then two machines on the LAN, discover each other with UDP broadcast on one port, then open a TCP session and exchange a session blob. This proves the host transport only.
- Build: a small test program in `ps3recomp/libs/network/tests/`, not in the game port. It uses the existing `sysNet` host-socket path, or plain host sockets if that is simpler.
- Test without the game: run the two processes headless, on loopback with different ports and then on the LAN with broadcast. Keep runs under 60 seconds. Do not start a D3D window. Do not run during a race or RDP session on the user's machine.
- Pass criteria: each process logs the other's discovery and a session blob arrives intact on both sides.

**M1 (after the title is reached): game-side Matching2 round trip.**
- Goal: the game's `GoOnlineAndCreateRoom` reaches `createJoinRoom` in instance 1, and `JoinRoom` in instance 2 sees the room, using option B with a local room server.
- Test: two instances from the same port template, `PS3_NET_ONLINE=1`, `PS3_NET_P2P_PORT` different per instance, the room server on localhost. Follow `ps3recomp/docs` and the reference ONLINE notes for the flags (reference only, not our project).
- Pass criteria: room visible on both sides; no crashes; the call sequence matches the traced sequence in `frontend_commands.txt`.

**M2: session traffic.** Trace `evo::network` on the race path and confirm one packet exchange between instances during a race load. Only after M1.

## 6. Open decisions for the user

1. **Is LAN in scope at all?** The retail game may have no system link mode. Reading the string table decides this. Should we read it first?
2. **Option B or A?** B reuses existing code and needs a LAN room server. A needs more reverse engineering and changes call paths.
3. **Host role.** Who runs the room server for LAN in option B? A PC on the LAN, or a bundled binary from the framework's psnr project (MIT, separate repo)?
4. **Pin.** Re-pin `ps3recomp/` to `0fe7dbf` before any network work, or upgrade deliberately?
5. **Public/private boundary.** Any LAN stand-in code goes in `ps3recomp/` (framework, public) and does not contain game data. Confirm that the stand-in and tests may ship publicly.
6. **Testing policy.** Confirm that two-process tests may run on this machine, only outside race sessions and RDP use, and how long they may run.
7. **Ranked and PSN features.** Confirm they stay out of scope for LAN.

## Evidence index

- `docs/COMPATIBILITY.md` line 50 (networking UNTESTED) [existing]
- `docs/RESEARCH.md` "2026-10-20 loading composition and network state" and "Frontend handoff after SetExitOnline" [existing]
- `generated/analysis/garage_menu/FINDINGS.md` (menu state machine) [existing]
- `generated/analysis/pcmenu/GUIFORMAT.md` lines 87–110 (text and option widgets; string table not read) [existing]
- `generated/analysis/frontend_commands.txt` (game-type and online command names and addresses) [new]
- `generated/analysis/EBOOT.imports.json` (141 network imports) [new]
- `ps3recomp/tools/nid_from_protos.json`, `ps3recomp/tools/nid_database.py` lines 429–450 [new]
- `ps3recomp/libs/network/sysNet.c` (header lines 1–16; host-socket gate; `ps3_net_host_register` at 1062) [new]
- `ps3recomp/libs/network/cellNetCtl.c` lines 5, 41–47, 148–163 [new]
- `ps3recomp/runtime/ppu/ppu_sysprx.cpp` lines 516–600, 859–862 [new]
- `ps3recomp/libs/network/np_psnr.h` (psnr stand-in, PS3_NET_ONLINE/PSNR_SERVER) [existing]
- `generated/analysis/c38/rv/symbols.txt` (evo::network symbols; provenance unconfirmed) [new]
- Reference only, not our project: `generated/analysis/t122/src/ps3recomp-c/docs/ONLINE.md` (ideas only; no code copied)

## 7. Update 2026-11-27: what the online flow really needs, and two PCs

Details, runs and proofs: `generated/analysis/lan_menu/RESULTS.md` (private notes).

- **The game's online server is Medius (SCE-RT 3.03), reached before any Matching2 call.** VERIFIED in the game:
  after the LAN page's HOST, the original flow signs in to NP, gets a ticket, resolves `motorstorm2ps3.online.scee.com`
  with its own DNS client (UDP to the DNS server cellNetCtl reports) and connects TCP 10071, where it sends an
  SCE-RT hello carrying the title's X.509 certificate. Matching2 rooms are only the party room after that login.
  The psnr room server the LAN host starts is unused by this game. A Medius stand-in is the remaining blocker for
  host/join/race; see the decision in the notes (option D in section 4 excluded PSN emulation; Medius is not PSN).
- **Fixed on the way** (framework): host sockets switchable at run time (`ps3_net_set_switchable`), cellNetCtl
  following `PS3_NET_ONLINE`, `PS3_NET_HOST_MAP` (gethostbyname and the title's own DNS queries answered locally
  for listed names), NP account region, tickets, entitlements, custom-invitation count. (Port) the LAN page's
  `Lan*` functions are now answered; one browser row per host.
- **Two instances on one PC:** VERIFIED for the browser: B's FIND A GAME lists A (`HostRacer  Lobby 0/8  0 ms`);
  Back works. Only one instance per PC can host (TCP 36100 and UDP 36101 are fixed). A joiner needs no fixed port.
  If a later stage binds P2P sockets in both, give the second instance `PS3_NET_P2P_PORT` (default 3658).

### Two PCs (not run yet)

1. Same subnet (discovery is a UDP broadcast: 255.255.255.255 and each adapter's directed broadcast), and the
   Windows network profile **Private** on both (Settings > Network > Properties).
2. Host PC, inbound rules for the game exe (or accept the Windows Firewall prompt for *Private* networks the first
   time it hosts):
   ```
   netsh advfirewall firewall add rule name="MotorStorm LAN discovery" dir=in action=allow protocol=UDP localport=36101 profile=private program="<path>\MotorStormPacificRiftRecomp.exe"
   netsh advfirewall firewall add rule name="MotorStorm LAN room"      dir=in action=allow protocol=TCP localport=36100 profile=private program="<path>\MotorStormPacificRiftRecomp.exe"
   netsh advfirewall firewall add rule name="MotorStorm LAN server"    dir=in action=allow protocol=TCP localport=10071 profile=private program="<path>\MotorStormPacificRiftRecomp.exe"
   ```
   (10071: the game's own server port, needed once a Medius stand-in listens there; the race transport's ports are
   not known yet.)
3. Joining PC: no inbound rule for the browser (answers come back to the query's port). FIND A GAME lists hosts that
   answered in the last 3.5 s, refreshed every second while the page is open; ping is the round trip of that query.
4. Each PC its own `playername` (launcher Settings > Multiplayer, or `playername = <name>` in settings.ini): the
   browser row and the game's NP name. Two PCs with the same name are two players with the same name.
5. Join sets the game's server name to the host's LAN address (`PS3_NET_HOST_MAP`), so nothing else is configured.
   A host behind another router (different subnet) is not found by the browser; that case is out of scope.
