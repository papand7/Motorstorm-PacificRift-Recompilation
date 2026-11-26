/* bench_ai.h: MSPR_BENCH_AI, the race benchmark's AI-driven human car (opt-in, off by default).
 *
 * A Competitor (1.00 vtable 0x1035078) embeds one object of each controls class and keeps the active kind at
 * competitor+0x1930: 0 Dummy (+0x1FB8), 1 JoyStick (+0x1934, the local HUMAN), 2 AI (+0x1FA8), 3 OnLine (+0x1FB0),
 * 4 Dummy, 5 Limbo (+0x1FBC), above 5 Dummy. Two lifted sites read it to pick the active controls object:
 * the getter func_00127BC8 (returns &controls) and the switch at 0x0012A7D0 (calls controls vfunc +0x20). The game
 * itself puts its own AIControls on the human car (kind 2) when the race is over (func_00127CA0 / func_0012A100).
 *
 * With MSPR_BENCH_AI=1 those two reads see kind 1 as kind 2, so the human car is driven by its own AIControls (the
 * opponents' AI), while every write and every other field (the base kind at +0x169C, the viewport, the race's human
 * list) stays the game's: the race still counts the car as the local human. Off: the kind is returned unchanged.
 * One caller keeps the JoyStick: the getter called from 0x000327A4 (return address 0x000327A8, func_000326A8), which
 * walks the human competitors and asks each one's controls (vfunc +0x28) whether its pad pressed the button the
 * pre-race flyover's "Press X to Skip" waits for. AIControls never presses it, so without this exception the flyover
 * loops (KbraceV1). Callers seen with kind 1 (MSPR_BENCH_AI_LOG, KbraceL1): 0x327A8 (skip), 0x214678 and 0x214CE0
 * (from the flyover on), 0x7DD0D4 / 0x7DD10C / 0x7DD144 (from the race start).
 *
 * The AIControls alone drive the human car aimlessly (KbraceV2: 16th, stuck off the track, lap 0 after 2 min): the
 * game's AI only plans for the human car while the autopilot flag 0x20 of competitor+0x1698 is set, which the game's
 * own autopilot switch func_0012A100(competitor, 1) sets together with kind 2 (it is how the game drives the human
 * car itself, e.g. after the finish). So whenever a read is mapped, the flag is set too (bench_ai_flags), which makes
 * the state the one func_0012A100(competitor, 1) leaves; nothing else is written. With it the car races (KbraceX2:
 * positions 1-10, boost, lap 1 by 0:35, crash and respawn handled by the game).
 * The hook sites are applied by generated/analysis/perf60/tools/bench_ai_patch_lifted.py. Test: tests/test_bench_ai.c. */
#ifndef BENCH_AI_H
#define BENCH_AI_H
#include <stdint.h>

#define BENCH_AI_KIND_JOYSTICK 1u
#define BENCH_AI_KIND_AI 2u
#define BENCH_AI_LR_SKIP 0x000327A8u   /* func_000326A8: a human pressed the flyover skip button */

static inline uint32_t bench_ai_ctl_kind(int enabled, uint32_t kind, uint32_t lr)
{
    return (enabled && kind == BENCH_AI_KIND_JOYSTICK && lr != BENCH_AI_LR_SKIP) ? BENCH_AI_KIND_AI : kind;
}

#define BENCH_AI_FLAG_AUTOPILOT 0x20u   /* competitor+0x1698, set by func_0012A100(competitor, 1) */

/* the competitor flags word after a read of kind (from caller lr): the autopilot flag added when the read is mapped */
static inline uint32_t bench_ai_flags(int enabled, uint32_t kind, uint32_t lr, uint32_t flags)
{
    return bench_ai_ctl_kind(enabled, kind, lr) != kind ? (flags | BENCH_AI_FLAG_AUTOPILOT) : flags;
}
#endif
