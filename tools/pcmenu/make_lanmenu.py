"""LAN play screen pages, made from the game's own Wreckreation page (the output is game data: keep it private, never ship or commit it).

Input (retail only):
  gui/wreckreation.gui   the Wreckreation page   (from MS2.PSARC, member "/gui/wreckreation.gui")

The game's main menu opens it (WRECKREATION); its ONLINE item runs the game's online start (GameTypeSetWreckreationOnline,
then wreckreation-communicating: the Matching2 context, then wreckreation-online with CUSTOM GAME / CREATE GAME / FIND GAME).
On this port that item opens the LAN screen first, then goes on into exactly those original actions.

Outputs, in <out>/gui/ (served through PS3_VFS_OVERLAY; pc_menu.cpp reads gui/wreckreatioz.gui for gui/wreckreation.gui):
  wreckreatioz.gui          the Wreckreation page with its ONLINE item opening wreckreation-lan (everything else untouched)
  wreckreation-lan.gui      the same page: three items, HOST A GAME, FIND A GAME, LEAVE (the ONLINE, FREE-PLAY and
                            SPLIT-SCREEN items copied, so their look, sounds, highlight and intro animation are the original's).
                            Host runs LanHost, then the original ONLINE actions; Find opens wreckreation-lanfind; Leave runs LanLeave.
  wreckreation-lanfind.gui  the server browser: the page's five items as rows (LanRow0..4: host name, event, players, ping),
                            Accept joins (LanPick0..4) and then runs the original ONLINE actions, Left/Right page through the list
All text comes from the port at run time (lan_menu.h: ExecuteFunction(LanRow0) then SetChannelValue(currentReturnValue, widget,
text)); no string table is changed. Written pages are re-walked: every pointer field reached must be relocated.

usage: py -3 make_lanmenu.py --out <dir> (--psarc <MS2.PSARC> | --gui <dir>)
         --gui   a folder that already holds gui_wreckreation.gui
Exit code 0 only when every written page re-walks clean."""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_pcmenu import (Ed, END, REC, chain, extract_psarc, find, sha, text_acts, write_pack)  # noqa: E402
from actions import handler  # noqa: E402
from page import Page  # noqa: E402

PAGE_UPDATE, PAGE_ENTER = 0x50, 0x54          # page-level handler slots (Back 0x48, Accept 0x4C)
ACCEPT, GAIN, UPDATE, INIT, LEFT, RIGHT = 0x3C, 0x40, 0x48, 0x4C, 0x5C, 0x60   # widget handler slots
ROW_FONT = 'kab_plain19'                       # a font this page already uses (its header), for the long rows
INFO = 'Info Box 1 text'
ROWS = 5
FILES = ('wreckreatioz', 'wreckreation-lan', 'wreckreation-lanfind')


def acts_of(ed, rec, slot):
    """(entry, actions) of the handler at rec+slot, END as 0xFFFFFFFF."""
    p = Page(data=bytes(ed.d), rel=ed.rel)
    e, _, acts = handler(p, ed.u(rec + slot))
    return e, [(nm, args, [x & 0xFFFFFFFF for x in succ]) for nm, args, succ in acts]


def shift(acts, by):
    return [(nm, args, [x if x == END else x + by for x in succ]) for nm, args, succ in acts]


def then(parts, entry_acts):
    """parts (linear lists, chained) and then the handler (entry, acts): the last part continues into it."""
    e, acts = entry_acts
    head = chain(*parts)
    base = len(head)
    head = [(nm, args, [base + e if x == END and i == len(head) - 1 else x for x in succ])
            for i, (nm, args, succ) in enumerate(head)]
    return head + shift(acts, base)


def pre_enter(ed, slot_owner, slot, parts):
    """The handler at slot_owner+slot, with parts run first."""
    ed.set_slot(slot_owner, slot, then(parts, acts_of(ed, slot_owner, slot)))


def post(ed, rec, slot, parts):
    """The widget's handler followed by parts (every end of it continues into them)."""
    e, acts = acts_of(ed, rec, slot)
    tail = chain(*parts)
    base = len(acts)
    out = [(nm, args, [base if x == END else x for x in succ]) for nm, args, succ in acts] + shift(tail, base)
    ed.ptr(rec + slot, ed.handler(out, e))


def guarded(call, ok_entry_acts, fail_text):
    """call (a bool function), then the original actions when it is true, else the status into the info bar."""
    e, ok = ok_entry_acts
    fail = chain([('ScrollTextReset', [INFO], [END])], text_acts(fail_text, INFO))
    n_fail = len(fail)
    head = [('ExecuteFunction', [call], [1]), ('TestBoolean', [], [2, 2 + n_fail + e])]
    return head + shift(fail, 2) + shift(ok, 2 + n_fail)


def goto(page):
    """NoCommandsActive, then the page (the original ONLINE item's own guard)."""
    return [('ExecuteFunction', ['NoCommandsActive'], [1]), ('TestBoolean', [], [END, 2]),
            ('TransitionPage', [page, 'Undefined'], [END])]


def gain(label_fn):
    return chain([('PlaySoundEvent', ['highlight'], [END])], [('ScrollTextReset', [INFO], [END])], text_acts(label_fn, INFO))


def load(gui):
    p = Page(os.path.join(gui, 'gui_wreckreation.gui'))
    ed = Ed(p)
    menu = find(p, 'wreckreation_menu')
    items = [p.u(menu + 0x30) + REC * i for i in range(p.u(menu + 0x2C))]
    names = [p.s(p.u(r + 0x88)) for r in items]
    assert names == ['ONLINE', 'FREE-PLAY', 'SPLIT-SCREEN', 'TIME ATTACK', 'LEADERBOARDS'], names
    return p, ed, menu, items


def make_replaced(gui, out):
    """wreckreatioz.gui: the Wreckreation page with ONLINE opening the LAN screen."""
    p, ed, menu, items = load(gui)
    ed.set_slot(items[0], ACCEPT, goto('wreckreation-lan'))
    write_pack(os.path.join(gui, 'gui_wreckreation.gui'), ed, os.path.join(out, 'gui', 'wreckreatioz.gui'), 'lanmenu-wreckreation')


def make_root(gui, out):
    """wreckreation-lan.gui: HOST A GAME / FIND A GAME / LEAVE."""
    p, ed, menu, items = load(gui)
    online = acts_of(ed, items[0], ACCEPT)               # the original online start
    host = ed.widget(items[0], name='LANHOST')
    find_ = ed.widget(items[1], name='LANFIND')
    leave = ed.widget(items[2], name='LANLEAVE')
    ed.set_slot(host, ACCEPT, guarded('LanHost', online, 'LanStatus'))
    ed.set_slot(find_, ACCEPT, goto('wreckreation-lanfind'))
    ed.set_slot(leave, ACCEPT, chain([('ExecuteFunction', ['LanLeave'], [END])], [('ScrollTextReset', [INFO], [END])],
                                     text_acts('LanStatus', INFO)))
    for w, kind in ((host, 'Host'), (find_, 'Find'), (leave, 'Leave')):
        ed.set_slot(w, GAIN, gain(f'Lan{kind}Info'))
        ed.set_slot(w, INIT, text_acts(f'Lan{kind}Label', 'currentWidget'))
    ed.children(menu, [host, find_, leave])
    pre_enter(ed, 0, PAGE_ENTER, [text_acts('LanTitle', 'Wreckreation')])
    write_pack(os.path.join(gui, 'gui_wreckreation.gui'), ed, os.path.join(out, 'gui', 'wreckreation-lan.gui'), 'lanmenu-root')


def make_find(gui, out):
    """wreckreation-lanfind.gui: the server browser."""
    p, ed, menu, items = load(gui)
    online = acts_of(ed, items[0], ACCEPT)
    rows = []
    for i in range(ROWS):
        w = ed.widget(items[i], name=f'LANROW{i}')
        cls = ed.u(w + 0x84)                              # the text class block: string id, font name
        ed.ptr(cls + 4, ed.string(ROW_FONT))
        ed.set_slot(w, ACCEPT, guarded(f'LanPick{i}', online, 'LanStatus'))
        ed.set_slot(w, GAIN, gain(f'LanRowInfo{i}'))
        post(ed, w, UPDATE, [text_acts(f'LanRow{i}', 'currentWidget')])
        ed.set_slot(w, INIT, text_acts(f'LanRow{i}', 'currentWidget'))   # no frame with the original item's text
        ed.set_slot(w, LEFT, [('ExecuteFunction', ['LanPagePrev'], [END])])
        ed.set_slot(w, RIGHT, [('ExecuteFunction', ['LanPageNext'], [END])])
        rows.append(w)
    ed.children(menu, rows)
    pre_enter(ed, 0, PAGE_ENTER, [text_acts('LanFindTitle', 'Wreckreation')])
    pre_enter(ed, 0, PAGE_UPDATE, [[('ExecuteFunction', ['LanTouch'], [END])]])   # keep browsing while it is on screen
    write_pack(os.path.join(gui, 'gui_wreckreation.gui'), ed, os.path.join(out, 'gui', 'wreckreation-lanfind.gui'), 'lanmenu-find')


def build(gui, out):
    """The three pages into <out>/gui; returns {file: sha256}."""
    make_replaced(gui, out)
    make_root(gui, out)
    make_find(gui, out)
    return {f + '.gui': sha(os.path.join(out, 'gui', f + '.gui')) for f in FILES}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--psarc')
    ap.add_argument('--gui')
    a = ap.parse_args(argv)
    assert a.psarc or a.gui, 'usage: make_lanmenu.py --out <dir> (--psarc <MS2.PSARC> | --gui <dir>)'
    gui = a.gui
    if a.psarc:
        gui = os.path.join(a.out, '_src')
        extract_psarc(a.psarc, '/gui/wreckreation.gui', os.path.join(gui, 'gui_wreckreation.gui'))
    outs = build(gui, a.out)
    print(f'{len(outs)} pages in {os.path.join(a.out, "gui")}')


if __name__ == '__main__':
    main(sys.argv[1:])
