"""PC Settings page files, made from the game's own pages (the output is game data: keep it private, never ship or commit it).

Inputs (retail only; nothing else of the game is read):
  gui/options.gui           the Options page      (from MS2.PSARC, member "/gui/options.gui")
  gui/options-controls.gui  the Controller page   (member "/gui/options-controls.gui")
  port-vkgame/pc_pages.h    the page table (PCP lines) and port-vkgame/pc_settings.h (the number of settings)

Outputs, in <out>/gui/ (the port serves this folder through PS3_VFS_OVERLAY; the exe
looks for a "pcmenu" folder beside it):
  optionz.gui       options.gui with a PC SETTINGS item before LANGUAGE (the port reads it for
                    gui/options.gui, pc_menu.cpp pcmenu_page_load / pcmenu_load_sync)
  options-pc.gui    the hub: options.gui's layout, one item per PCP page (six), titled PC Settings
  options-pc*.gui   one page per PCP line, made from options-controls.gui: its rows replaced by one row
                    per setting or key binding (two columns of four), the header titled by PcTitle<n>
  pcmenu.json       what it was made from and what it made (sha256), for the launcher: regenerate when
                    the page table, the game files or this tool change

All text comes from the port at run time (ExecuteFunction(PcName0) etc., then
SetChannelValue(currentReturnValue, <widget>, text)), so no string table is changed.
Pages are edited in their page segment only (appended objects, relocation entries added;
the page section is the pack's last). Each written page is re-walked: every pointer
field reached must be relocated.

usage: py -3 make_pcmenu.py --out <dir> (--psarc <MS2.PSARC> | --gui <dir>) [--port <port-vkgame dir>]
         --psarc   extracts the two pages from the archive itself (into <out>/_src)
         --gui     a folder that already holds gui_options.gui and gui_options-controls.gui
         --port    the folder with pc_pages.h and pc_settings.h (default: ../../port-vkgame)
       py -3 make_pcmenu.py <gui dir> <out dir>      (old form)
Needs, in this folder: page.py, actions.py, widgets.py, coverage.py, pack.py (the .gui readers).
Exit code 0 only when every written page re-walks clean."""
import argparse
import hashlib
import json
import os
import re
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from page import Page                   # noqa: E402
from actions import handler             # noqa: E402
from coverage import walk_page          # noqa: E402
from pack import parse                  # noqa: E402

REC = 0x8C
END = 0xFFFFFFFF
SLOTS = [0x34, 0x38, 0x3C, 0x40, 0x44, 0x48, 0x4C, 0x54, 0x58, 0x5C, 0x60]
CLASS_SIZE = {0: 0x40, 1: 0x20, 9: 0x0C, 8: 0x08}
P32 = lambda v: struct.pack('>I', v & 0xFFFFFFFF)


class Ed:
    """A page segment being edited: data, relocation entries, appended objects."""

    def __init__(self, p):
        self.d = bytearray(p.data)
        self.rel = list(p.rel)
        self.relset = set(self.rel)

    def u(self, o): return struct.unpack_from('>I', self.d, o)[0]
    def f(self, o): return struct.unpack_from('>f', self.d, o)[0]
    def put(self, o, v): struct.pack_into('>I', self.d, o, v & 0xFFFFFFFF)
    def putf(self, o, v): struct.pack_into('>f', self.d, o, v)

    def s(self, o):
        e = self.d.index(b'\0', o)
        return self.d[o:e].decode('latin1')

    def align(self):
        while len(self.d) % 4: self.d.append(0xFF)

    def raw(self, b):
        self.align(); o = len(self.d); self.d += b; return o

    def string(self, t):
        self.align(); o = len(self.d); self.d += t.encode('latin1') + b'\0'; self.align(); return o

    def ptr(self, at, target):
        """Store a pointer field (relocated); 0 clears it."""
        if target:
            self.put(at, target)
            if at not in self.relset: self.rel.append(at); self.relset.add(at)
        else:
            self.put(at, 0)
            if at in self.relset: self.rel.remove(at); self.relset.discard(at)

    def copy(self, src, size):
        """A copy of size bytes at src; relocated fields inside keep pointing at their targets."""
        o = self.raw(bytes(self.d[src:src + size]))
        for k in range(0, size, 4):
            if src + k in self.relset: self.rel.append(o + k); self.relset.add(o + k)
        return o

    def handler(self, acts, entry=0):
        """acts: [(name, [args], [successor indices])], END = 0xFFFFFFFF."""
        h = self.raw(P32(entry) + P32(len(acts)) + P32(0) + P32(0))
        ab = self.raw(b'\0' * (20 * len(acts)))
        self.ptr(h + 12, ab)
        for i, (nm, args, succ) in enumerate(acts):
            a = ab + 20 * i
            self.ptr(a, self.string(nm)); self.put(a + 4, len(args))
            if args:
                arr = self.raw(b'\0' * 4 * len(args))
                for k, t in enumerate(args): self.ptr(arr + 4 * k, self.string(t))
                self.ptr(a + 8, arr)
            self.put(a + 12, len(succ))
            self.ptr(a + 16, self.raw(b''.join(P32(x) for x in succ)))
        return h

    def recopy_handler(self, h):
        p = Page(data=bytes(self.d), rel=self.rel)
        e, _, acts = handler(p, h)
        return self.handler([(nm, args, [x & 0xFFFFFFFF for x in succ]) for nm, args, succ in acts], e)

    def widget(self, src, name=None, y=None, x=None, keep_children=True):
        """A deep copy of the widget record at src (own geo/state/class blocks and handlers);
        returns the new record's offset. Children are copied the same way."""
        o = self.copy(src, REC)
        if src in self.relset: self.ptr(o, self.copy(self.u(src), 0x30))
        if src + 4 in self.relset: self.ptr(o + 4, self.copy(self.u(src + 4), 0x2C))
        cls = self.u(src + 0x64)
        if src + 0x84 in self.relset and cls in CLASS_SIZE:
            self.ptr(o + 0x84, self.copy(self.u(src + 0x84), CLASS_SIZE[cls]))
        for sl in SLOTS:
            if src + sl in self.relset: self.ptr(o + sl, self.recopy_handler(self.u(src + sl)))
        n = self.u(src + 0x2C)
        if n and src + 0x30 in self.relset and keep_children:
            self.children(o, [self.u(src + 0x30) + REC * i for i in range(n)])
        if name is not None: self.ptr(o + 0x88, self.string(name))
        if y is not None: self.putf(self.u(o) + 4, y)
        if x is not None: self.putf(self.u(o), x)
        return o

    def children(self, parent, recs, deep=False):
        """Give parent (a record, or None for the page's top level) a new array of the
        records at recs, copied as they are (shared sub-objects) unless deep."""
        arr = self.raw(b'\0' * REC * len(recs))
        for i, r in enumerate(recs):
            if deep:
                r = self.widget(r)
            self.d[arr + REC * i:arr + REC * (i + 1)] = self.d[r:r + REC]
            for k in range(0, REC, 4):
                if r + k in self.relset: self.rel.append(arr + REC * i + k); self.relset.add(arr + REC * i + k)
        if parent is None:
            self.put(0, len(recs)); self.ptr(4, arr)
        else:
            self.put(parent + 0x2C, len(recs)); self.ptr(parent + 0x30, arr)
        return arr

    def set_slot(self, rec, slot, acts):
        self.ptr(rec + slot, self.handler(acts) if acts else 0)

    def page(self):
        self.align()
        return Page(data=bytes(self.d), rel=self.rel)


def find(p, name):
    from widgets import all_widgets
    hits = [r for _, _, r, _ in all_widgets(p) if p.s(p.u(r + 0x88)) == name]
    assert len(hits) >= 1, name
    return hits[0]


def text_acts(func, widget):
    """ExecuteFunction(func) then its text into widget."""
    return [('ExecuteFunction', [func], [1]), ('SetChannelValue', ['currentReturnValue', widget, 'text'], [END])]


def chain(*parts):
    """Join linear action lists (successors relative to their part, last action -> END):
    each part's END continues with the next part."""
    out = []
    for j, part in enumerate(parts):
        base, nxt = len(out), len(out) + len(part)
        last = j == len(parts) - 1
        for nm, args, succ in part:
            out.append((nm, args, [(END if last else nxt) if x == END else x + base for x in succ]))
    return out


def write_pack(src_file, ed, out_file, salt):
    """The source pack with its page section replaced by ed's page and a fresh page id."""
    d = bytearray(open(src_file, 'rb').read())
    r = parse(bytes(d))
    root = bytes.fromhex(r['rootid'])
    ent = [e for e in r['ents'] if e['id'] == r['rootid']][0]
    assert ent['off'] + ent['size'] == len(d), 'page section is not last'
    p = ed.page()
    new_id = root[:2] + hashlib.sha256(root + salt.encode()).digest()[:6]
    sec = bytearray(d[ent['off']:ent['off'] + 0x1C])
    sec[8:16] = new_id
    struct.pack_into('>II', sec, 0x14, p.N, 4 * len(p.rel))
    body = bytes(sec) + p.data + b''.join(P32(x) for x in p.rel)
    d = d[:ent['off']] + body
    # directory: root id, the entry's id and size
    D = r['doff']
    assert d.count(root) >= 2
    rid_at = D + 16 + 28
    assert bytes(d[rid_at:rid_at + 8]) == root
    d[rid_at:rid_at + 8] = new_id
    e_at = bytes(d).index(root + P32(ent['size']) + P32(ent['off']), D)
    d[e_at:e_at + 8] = new_id
    struct.pack_into('>I', d, e_at + 8, len(body))
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    open(out_file, 'wb').write(bytes(d))
    q = Page(out_file)
    reached, missing = walk_page(q)
    assert not missing, missing[:5]
    print(f'{out_file}: {len(d)} bytes, page {p.N:#x} + {len(p.rel)} relocs, id {new_id.hex()}, '
          f'walk ok ({len(reached)} pointers)')


def read_pages(port):
    """(pages, n_settings) from the port's headers. pages: [(file, title, first, rows, label, info)]"""
    pp = open(os.path.join(port, 'pc_pages.h'), encoding='utf8').read()
    pages = []
    for m in re.finditer(r'^PCP\("([^"]+)", "([^"]+)", (\d+), (\d+), "([^"]+)", "([^"]+)"\)\s*$', pp, re.M):
        f, t, first, rows, label, info = m.groups()
        pages.append((f, t, int(first), int(rows), label, info))
    assert pages, 'no PCP lines in pc_pages.h'
    ps = open(os.path.join(port, 'pc_settings.h'), encoding='utf8').read()
    body = ps[ps.index('k_pcs_defs[] = {'):]
    body = body[:body.index('\n};')]
    n_settings = len(re.findall(r'^\s*\{ "[a-z0-9]+", "[^"]+", (?:"[A-Z0-9_]+"|NULL), \d+, \d+, \d+, \d+,\s*$', body, re.M))
    assert n_settings > 0
    nxt = 0
    for f, t, first, rows, label, info in pages:
        assert first == nxt and 1 <= rows <= 8, (f, first, rows)
        nxt += rows
    assert len(pages) == 6, 'the hub has six items (make_hub places six)'
    return pages, n_settings


def extract_psarc(psarc, name, target):
    """One member of an MS2.PSARC (zlib, MD5 of the upper-case member path) into target."""
    h = hashlib.md5(name.upper().encode('ascii')).digest()
    with open(psarc, 'rb') as f:
        head = f.read(32)
        assert head[:4] == b'PSAR' and head[8:12] == b'zlib', 'not a zlib PSARC'
        toc_len, entry_len, count, block, _ = struct.unpack('>5I', head[12:32])
        assert entry_len == 30 and block == 65536
        toc = f.read(count * entry_len)
        hits = [i for i in range(count) if toc[i * entry_len:i * entry_len + 16] == h]
        assert len(hits) == 1, f'{name}: {len(hits)} entries'
        e = toc[hits[0] * entry_len:(hits[0] + 1) * entry_len]
        zidx = int.from_bytes(e[16:20], 'big')
        size = int.from_bytes(e[20:25], 'big')
        off = int.from_bytes(e[25:30], 'big')
        f.seek(32 + entry_len * count + 2 * zidx)
        lengths = [int.from_bytes(f.read(2), 'big') for _ in range((size + block - 1) // block)]
        f.seek(off)
        data = bytearray()
        for ln in lengths:
            n = ln or block
            chunk = f.read(n)
            try:
                chunk = zlib.decompress(chunk)
            except zlib.error:
                assert n == block
            data.extend(chunk)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    open(target, 'wb').write(bytes(data[:size]))


def make_options(gui, out):
    """optionz.gui: the Options page with a PC SETTINGS item (to options-pc) before LANGUAGE."""
    src = os.path.join(gui, 'gui_options.gui')
    p = Page(src); ed = Ed(p)
    menu = find(p, 'Options_menu')
    items = [p.u(menu + 0x30) + REC * i for i in range(p.u(menu + 0x2C))]
    names = [p.s(p.u(r + 0x88)) for r in items]
    assert names == ['AUDIO', 'DISPLAY', 'CONTROLLER', 'LANGUAGE'], names
    ctrl, lang = items[2], items[3]
    gy = lambda r: p.f(p.u(r) + 4)
    gx = lambda r: p.f(p.u(r))
    step = gy(lang) - gy(ctrl)
    pc = ed.widget(ctrl, name='PCSETTINGS', y=gy(lang), x=gx(lang))
    ed.set_slot(pc, 0x3C, [('TransitionPage', ['options-pc', 'Undefined'], [END])])
    ed.set_slot(pc, 0x40, chain([('PlaySoundEvent', ['highlight'], [END])],
                                [('ScrollTextReset', ['Info Box 1 text'], [END])],
                                text_acts('PcMenuInfo', 'Info Box 1 text')))
    ed.set_slot(pc, 0x4C, text_acts('PcMenuLabel', 'currentWidget'))
    lang2 = ed.widget(lang, y=gy(lang) + step)
    ed.children(menu, items[:3] + [pc, lang2])
    write_pack(src, ed, os.path.join(out, 'gui', 'optionz.gui'), 'pcmenu-options')


def make_hub(gui, out, pages):
    """options-pc.gui: the Options page's layout with one item per PC page (five slots: the four
    retail items and the slot LANGUAGE's hidden copy takes in optionz.gui)."""
    src = os.path.join(gui, 'gui_options.gui')
    p = Page(src); ed = Ed(p)
    menu = find(p, 'Options_menu')
    items = [p.u(menu + 0x30) + REC * i for i in range(p.u(menu + 0x2C))]
    assert [p.s(p.u(r + 0x88)) for r in items] == ['AUDIO', 'DISPLAY', 'CONTROLLER', 'LANGUAGE']
    ctrl, lang = items[2], items[3]
    gy = lambda r: p.f(p.u(r) + 4)
    gx = lambda r: p.f(p.u(r))
    step = gy(lang) - gy(ctrl)
    ys = [gy(r) for r in items] + [gy(lang) + k * step for k in (1, 2)]   # six slots: four retail rows + two more
    xs = [gx(r) for r in items] + [gx(lang), gx(lang)]
    assert len(pages) <= len(ys), 'the hub has six item slots'
    new = []
    for i, (fname, title, first, rows, label, info) in enumerate(pages):
        w = ed.widget(ctrl, name=f'PCHUB{i}', y=ys[i], x=xs[i])
        ed.set_slot(w, 0x3C, [('TransitionPage', [fname, 'Undefined'], [END])])
        ed.set_slot(w, 0x40, chain([('PlaySoundEvent', ['highlight'], [END])],
                                   [('ScrollTextReset', ['Info Box 1 text'], [END])],
                                   text_acts(f'PcHubInfo{i}', 'Info Box 1 text')))
        ed.set_slot(w, 0x4C, text_acts(f'PcHubLabel{i}', 'currentWidget'))
        new.append(w)
    ed.children(menu, new)
    find(p, 'Options')
    ed.set_slot(0, 0x54, chain(text_acts('PcTitle0', 'Options'),
                               [('PushPage', ['buttons_select_back', 'Undefined', 'False'], [END])],
                               [('PushPage', ['invitation-popup', 'Undefined', 'False'], [END])]))
    write_pack(src, ed, os.path.join(out, 'gui', 'options-pc.gui'), 'pcmenu-hub')


def make_page(gui, out, page, index, n_settings):
    """One row page. index: its number in the page table (the title is PcTitle<index + 1>)."""
    fname, ptitle, first, nrows, _, _ = page
    src = os.path.join(gui, 'gui_options-controls.gui')
    p = Page(src); ed = Ed(p)
    top = [p.u(4) + REC * i for i in range(p.u(0))]
    tname = lambda r: p.s(p.u(r + 0x88))
    drop = {'Audio_blackbox_plain1', 'Audio_blackbox_plain2', 'Audio_blackbox_plain3', 'Audio_blackbox_plain4',
            'Audio_blackbox_plain5', 'Audio_blackbox_plain6', 'D-pad'}
    keep = [r for r in top if tname(r) not in drop]
    assert len(keep) == len(top) - len(drop), [tname(r) for r in top]
    row = find(p, 'Audio_blackbox_plain4')          # Directional Buttons Music Control: label, on, off, arrows
    kids = [p.u(row + 0x30) + REC * i for i in range(p.u(row + 0x2C))]
    kn = [p.s(p.u(r + 0x88)) for r in kids]
    assert kn == ['Directional Buttons Music Control', 'directionalmusiccontrolon', 'directionalmusiccontroloff',
                  'main_arrow_right2', 'main_arrow_left2'], kn
    lbl, val, ar, al = kids[0], kids[1], kids[3], kids[4]
    ys = [p.f(p.u(find(p, n)) + 4) for n in ('Audio_blackbox_plain2', 'Audio_blackbox_plain3',
                                              'Audio_blackbox_plain4', 'Audio_blackbox_plain5')]
    xs = [p.f(p.u(row)), p.f(p.u(find(p, 'D-pad')))]
    rows = []
    for i in range(nrows):
        gid = first + i                              # the row's number in the port: PcName<gid>
        is_key = gid >= n_settings
        col, k = divmod(i, 4)
        box = ed.widget(row, name=f'pc_box{i}', x=xs[col], y=ys[k], keep_children=False)
        L = ed.widget(lbl, name=f'pc_lbl{i}')
        V = ed.widget(val, name=f'pc_val{i}')
        R = ed.widget(ar, name=f'pc_ar{i}')
        Lf = ed.widget(al, name=f'pc_al{i}')
        if i == 0: ed.put(V + 0x14, 1)              # initial focus: the first row
        up, dn = f'pc_val{(i - 1) % nrows}', f'pc_val{(i + 1) % nrows}'
        info = text_acts(f'PcInfo{gid}', 'Info Box 1 text')
        ed.set_slot(V, 0x4C, chain(text_acts(f'PcValue{gid}', 'currentWidget'), text_acts(f'PcName{gid}', f'pc_lbl{i}')))
        ed.set_slot(V, 0x40, chain([('PlaySoundEvent', ['highlight'], [END])],
                                   [('SetVisible', [f'pc_ar{i}'], [END])], [('SetVisible', [f'pc_al{i}'], [END])],
                                   [('ScrollTextReset', ['Info Box 1 text'], [END])], info))
        ed.set_slot(V, 0x44, chain([('SetInVisible', [f'pc_ar{i}'], [END])], [('SetInVisible', [f'pc_al{i}'], [END])]))
        sel = [('TestIfSelected', [], [1, 2]),
               ('SetChannelValue', ['0.5', f'pc_box{i}', 'visibility'], [END]),
               ('SetChannelValue', ['1', f'pc_box{i}', 'visibility'], [END])]
        # a key row shows what the port is doing (Press a key... / the new key) every frame
        ed.set_slot(V, 0x48, chain(text_acts(f'PcValue{gid}', 'currentWidget'), sel) if is_key else sel)
        for slot, fn in ((0x5C, 'PcPrev'), (0x60, 'PcNext')):
            ed.set_slot(V, slot, chain([('ExecuteFunction', [f'{fn}{gid}'], [END])],
                                       text_acts(f'PcValue{gid}', 'currentWidget'), info))
        ed.set_slot(V, 0x54, [('TransitionPage', ['Undefined', up], [END])])
        ed.set_slot(V, 0x58, [('TransitionPage', ['Undefined', dn], [END])])
        for sl in (0x34, 0x38):
            ed.set_slot(V, sl, None)
        # Accept: a key row waits for the next key; a setting row does nothing
        ed.set_slot(V, 0x3C, chain([('ExecuteFunction', [f'PcKey{gid}'], [END])],
                                   text_acts(f'PcValue{gid}', 'currentWidget')) if is_key else None)
        ed.children(box, [L, V, R, Lf])
        rows.append(box)
    for r in keep:                                   # nothing else may hold the first focus
        if ed.u(r + 0x14) == 1: ed.put(r + 0x14, END)
    ed.children(None, keep[:1] + rows + keep[1:])
    # page enter: the title, then the original enter actions (invites popup, info scroll)
    title = 'Controller Options'
    find(p, title)
    ed.set_slot(0, 0x54, chain(text_acts(f'PcTitle{index + 1}', title),
                               [('PushPage', ['invitation-popup', 'Undefined', 'False'], [END])],
                               [('ScrollText', ['Info Box 1 text', '2', '0'], [END])]))
    ed.set_slot(0, 0x48, chain([('ExecuteFunction', ['PcSave'], [END])], [('PlaySoundEvent', ['back'], [END])],
                               [('TransitionBack', [], [END])]))
    write_pack(src, ed, os.path.join(out, 'gui', fname + '.gui'), 'pcmenu-' + fname)


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out')
    ap.add_argument('--psarc')
    ap.add_argument('--gui')
    ap.add_argument('--port', default=os.path.normpath(os.path.join(HERE, '..', '..', 'port-vkgame')))
    ap.add_argument('pos', nargs='*')
    a = ap.parse_args(argv)
    if a.pos and not (a.out or a.psarc or a.gui):     # old form: <gui dir> <out dir>
        assert len(a.pos) == 2
        a.gui, a.out = a.pos
    assert a.out and (a.psarc or a.gui), 'usage: make_pcmenu.py --out <dir> (--psarc <MS2.PSARC> | --gui <dir>)'
    gui = a.gui
    if a.psarc:
        gui = os.path.join(a.out, '_src')
        extract_psarc(a.psarc, '/gui/options.gui', os.path.join(gui, 'gui_options.gui'))
        extract_psarc(a.psarc, '/gui/options-controls.gui', os.path.join(gui, 'gui_options-controls.gui'))
    pages, n_settings = read_pages(a.port)
    make_options(gui, a.out)
    make_hub(gui, a.out, pages)
    for i, pg in enumerate(pages):
        make_page(gui, a.out, pg, i, n_settings)
    outs = {}
    for fn in ['optionz', 'options-pc'] + [pg[0] for pg in pages]:
        outs[fn + '.gui'] = sha(os.path.join(a.out, 'gui', fn + '.gui'))
    meta = {
        'inputs': {'gui_options.gui': sha(os.path.join(gui, 'gui_options.gui')),
                   'gui_options-controls.gui': sha(os.path.join(gui, 'gui_options-controls.gui')),
                   'pc_pages.h': sha(os.path.join(a.port, 'pc_pages.h')),
                   'pc_settings.h': sha(os.path.join(a.port, 'pc_settings.h')),
                   'make_pcmenu.py': sha(os.path.abspath(__file__))},
        'outputs': outs, 'pages': [list(pg) for pg in pages], 'settings': n_settings,
    }
    json.dump(meta, open(os.path.join(a.out, 'pcmenu.json'), 'w'), indent=1)
    print(f'{len(outs)} pages in {os.path.join(a.out, "gui")}, manifest pcmenu.json')


if __name__ == '__main__':
    main(sys.argv[1:])
