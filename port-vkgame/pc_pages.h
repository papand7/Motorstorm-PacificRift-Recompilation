/* PC Settings pages: which rows each page holds. A row is a setting
 * (pc_settings.h k_pcs_defs, ids 0..PCS_COUNT-1) or a key binding
 * (pc_keys.h, ids PCS_COUNT.. in PAD_ACT_* order, PCK_COUNT of them). A page lists consecutive ids.
 *
 * The PCP lines below are read by the page generator (tools/pcmenu/make_pcmenu.py)
 * and by the tests; keep one PCP(...) per line:
 *   PCP(<file name>, <title>, <first row>, <rows>, <hub label>, <hub info>)
 * A page holds at most 8 rows (two columns of four). The hub page is
 * options-pc: one item per page below, in this order. */
#ifndef PC_PAGES_H
#define PC_PAGES_H

#include "pc_settings.h"
#include "pc_keys.h"

typedef struct { const char* file; const char* title; int first, rows; const char* label; const char* info; } pcp_page;

#define PCP(file, title, first, rows, label, info) { file, title, first, rows, label, info },
#define PCP_ROWS_MAX 8

static const pcp_page k_pcp_pages[] = {
PCP("options-pcd", "Display", 0, 8, "DISPLAY", "Window, resolution, V-Sync, frame rate, upscaling and HDR.")
PCP("options-pcg", "Graphics", 8, 8, "GRAPHICS", "Motion blur, texture filtering and packs, detail, fidelity, shadows and button prompts.")
PCP("options-pcw", "Racing Wheel", 16, 8, "RACING WHEEL", "Steering range, pedals and force feedback for a racing wheel.")
PCP("options-pcf", "Effects", 24, 4, "EFFECTS", "Volumetric fog, wheel ruts, effects quality and extra particles. Need Fidelity Enhanced.")
PCP("options-pcp", "Performance", 28, 8, "PERFORMANCE", "Lower quality for slower PCs: shadows, textures, effects, other cars, debris; frame generation.")
PCP("options-pck1", "Keyboard: Driving", 36, 8, "DRIVING KEYS", "Choose the keys for driving.")
PCP("options-pck2", "Keyboard: Buttons", 44, 5, "BUTTON KEYS", "Choose the keys for Circle, L1, R1, Start and Select.")
PCP("options-pck3", "Keyboard: Arrows", 49, 4, "ARROW KEYS", "Up, Down, Left and Right: menus, the d-pad and driving.")
};
#define PCP_COUNT ((int)(sizeof k_pcp_pages / sizeof k_pcp_pages[0]))
/* Every key action is on a page: the key rows are ids PCS_COUNT..PCS_COUNT+PCK_COUNT-1. */
#define PCK_PAGE_ACTIONS PCK_COUNT
#define PCP_ROWS (PCS_COUNT + PCK_PAGE_ACTIONS)

#endif
