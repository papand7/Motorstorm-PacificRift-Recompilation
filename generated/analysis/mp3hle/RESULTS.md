# LibMP3 stereo job HLE (private; 2026-11-16)

Exe: build/motorstorm-vkgame-100-mp3hle/MotorStormPacificRiftRecomp.exe
SHA-256 d3f27ba4d65e986fce2b55333f83c3db95673d5f7fddd59125ad7b9697d0e4f8
Sources: ps3recomp-mp3 (copy of ps3recomp-vkgame + generic job hook), port-mp3 (copy of port-vkgame + mp3_hle.c, mp3_hle_core.c, tests/mp3_hle_replay.c).
Config: as build/motorstorm-vkgame-100-next, PS3RECOMP_DIR=ps3recomp-mp3, source port-mp3, own LTO cache lto-cache-100-mp3.

VERIFIED (menu music, boots via tools/boot.py, fresh scratch roots):
- Job interface: PM API +0x34 (0,1,0,1)/(0,2,0,1) -> buffer A (8 KB MP3 window + 0xB110-byte stream object S at +0x2000), buffer B (PCM); API +0x44 once; 1 frame/job, 1152 stereo BE float interleaved, PUT to [S+0x58]; S PUT back to [S+0x5C]. See mp3_hle.c header.
- capo (PS3_MP3_HLE=0) vs capn2 (HLE) 900 jobs (~23.5 s, several loops of the 381704-byte menu track):
  identical input stream (947556 B), PCM same job index SNR 111.3 dB, max |diff| 4.29e-6, 0 frames > 1e-4;
  header words +00,+08..+24 identical; PUT lists (LS, EA, size, tag) identical 900/900; consumed (+04) differs by about 1 byte in 138/900 jobs (totals equal).
- Offline replay (bin/mp3_hle_replay.exe over cap1, 300 jobs): SNR 111.2 dB, max 4.05e-6.
- Cost: original job 1045 us/job (PS3_SPU_WWS_STATS, ab0: 2315 jobs 2.419 s); HLE 73 us/job (ab1, 2314 jobs). Cadence 38.3 jobs/s both.
- Off switch: PS3_MP3_HLE=0 -> module AOT-installed and run every job (wws-stats installed=2315).
Not covered: flashMP3 (MultiStream, image 283218738 -> overlay 2061190609), race tracks (no race run).
