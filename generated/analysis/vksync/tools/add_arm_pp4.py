"""run_vk.py: Pp4, the PC Settings page test (port-vkgame/pc_menu.cpp, pages from
generated/analysis/pcmenu/tools/make_pcmenu.py in build/pcmenu, served by PS3_VFS_OVERLAY).
Kk69's configuration with the route trace file (nav_sites.cfg: page loads through 0x536A30),
no race: main menu -> OPTIONS (4th item) -> PC SETTINGS (4th) -> Motion Blur (6th row) Off,
then On -> back (writes settings.ini, all defaults). Holds between steps leave time for
screenshots; the run stops 6 s after the last step.
LF file. usage: py -3 add_arm_pp4.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Pp4'" in s:
    print('already edited'); raise SystemExit
k70 = "ARMS['K'] = ('r', {**ARMS['K'][1], 'MSPR_PATCH': 'drs,vfps'})   # Kk70:"
i = s.index('\n', s.index(k70)) + 1
s = s[:i] + ("ARMS['P'] = ('r', {**{k: v for k, v in K_BY_TAG['k69'][1].items() if k != 'PS3_TRACE_FILE'}, "
             "'PS3_VFS_OVERLAY': str(HERE.parents[3] / 'build' / 'pcmenu')})   # Pp4: PC Settings page test "
             "(scripted menu walk, no race; exe with pc_menu.cpp)\n") + s[i:]
a = "'Kk70', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk70', 'Pp4', 'Yy1']")
a = 'MAX_LAUNCHES = 117'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 118')
a = 'CROSS, UP, DOWN = 0x4000, 0x0010, 0x0040\n'
assert s.count(a) == 1
s = s.replace(a, a + 'LEFT, RIGHT, CIRCLE = 0x0080, 0x0020, 0x2000\n')
a = '    def nav(self):\n'
assert s.count(a) == 1
s = s.replace(a, '''    # Pp4: the PC Settings page. (page loaded, hold s, presses): each step waits for its page
    # (first 12 characters of the path the resource loader is given), holds, then presses.
    MENU = [('gui/mainmenu', 8.0, [DOWN, DOWN, DOWN, CROSS]),
            ('gui/optionz.', 6.0, [DOWN, DOWN, DOWN, CROSS]),
            ('gui/options-', 10.0, [DOWN, DOWN, DOWN, DOWN, DOWN]),
            (None, 6.0, [RIGHT]),
            (None, 8.0, [LEFT]),
            (None, 6.0, [CIRCLE]),
            (None, 6.0, [])]

    def nav_menu(self):
        st = getattr(self, 'menu_st', None)
        if st is None:
            st = self.menu_st = {'i': 0, 't': None}
        if st['i'] >= len(self.MENU):
            return
        page, hold, keys = self.MENU[st['i']]
        if st['t'] is None:
            if page and self.npage(page) < 1:
                return
            st['t'] = self.now()
            self.note('menu_step', step=st['i'], page=page)
            return
        if self.now() - st['t'] < hold:
            return
        for k in keys:
            self.press(f'menu {st["i"]}', k, 6)
            time.sleep(0.8)
        st['i'] += 1
        st['t'] = None
        if st['i'] == len(self.MENU):
            self.finish('menu test done')

''' + a + '''        if ARM == 'P':
            return self.nav_menu()
''')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
