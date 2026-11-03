p='tools/test_spu_ib_fast.py'
s=open(p,encoding='utf-8',newline='').read().replace('\r\n','\n')
def rep(old,new):
    global s
    assert s.count(old)==1,(s.count(old),old[:70])
    s=s.replace(old,new)
rep('"""T191: differential test','"""T191/T192: differential test')
rep('''  envinit           PS3_SPU_IB_FAST from the environment''','''  reloc             T192 directed: relocatable slots (intra-slot, entry/exit, replacement, same-address and
                    link-base changes, DMA, eviction), exact fallback reasons, shadowing by a later registration,
                    epoch wrap boundary, tracing, the PS3_SPU_IB_FAST_RELOC knob
  random --reloc    T192 seeded random slot lifecycles + run-time registrations + tracing on/off
  envinit           PS3_SPU_IB_FAST from the environment''')
rep('("directed", ["directed"]), ("directed --tasks", ["directed", "--tasks"]),','("directed", ["directed"]), ("directed --tasks", ["directed", "--tasks"]), ("reloc", ["reloc"]),')
rep('''            out.append((f"random seed {s}{' --tasks' if tasks else ''}", rc == 0, txt))''','''            out.append((f"random seed {s}{' --tasks' if tasks else ''}", rc == 0, txt))
        rc, txt = run(exe, "random", 100 + s, iters, "--reloc")
        out.append((f"random seed {100 + s} --reloc", rc == 0, txt))
        rc, txt = run(exe, "random", 200 + s, iters, "--reloc", "--tasks")
        out.append((f"random seed {200 + s} --reloc --tasks", rc == 0, txt))''')
rep('HASH = "((pc >> 2)','HASH = "((key >> 2)')
rep('CMP = "e->fn && e->pc == pc &&','CMP = "e->fn && e->pc == key &&')
# mutants 6 and 10 patterns, new reloc mutants
rep('''    ("fast path dispatches relocatable code slots without the delta (link_base ignored)",
     [("if (ctx->resident_code[slot].link_base || ctx->resident_code[slot].image_id <= 0) return NULL;",
       "if (ctx->resident_code[slot].image_id <= 0) return NULL;")]),''','''    ("relocatable hit does not publish reloc_delta",
     [("if (__builtin_expect(ovl == -3, 0)) ctx->reloc_delta = reloc_delta;", "")]),
    ("relocatable fill does not publish reloc_delta",
     [("    if (ovl == -3) ctx->reloc_delta = reloc_delta;\n    return fn;", "    return fn;")]),
    ("relocatable key ignores the slot's link base (wrong lifted address, still a lookup hit elsewhere)",
     [("key = (pc - lsa + ctx->resident_code[slot].link_base) | SPU_RELOC_KEY_BIT;", "key = (pc - lsa + 0x4000u) | SPU_RELOC_KEY_BIT;")]),
    ("evicted slot (image id 0) still treated as owner",
     [("if (ctx->resident_code[slot].image_id && pc >= lsa && pc - lsa < ctx->resident_code[slot].size) {",
       "if (pc >= lsa && pc - lsa < ctx->resident_code[slot].size) {")]),
    ("slot size bound ignored",
     [("if (ctx->resident_code[slot].image_id && pc >= lsa && pc - lsa < ctx->resident_code[slot].size) {",
       "if (ctx->resident_code[slot].image_id && pc >= lsa) {")]),
    ("negative resident_ovl accepted (collides with the owner-mode keys)",
     [("if (__builtin_expect(ovl < 0, 0)) { SPU_IBF_COUNT(IBR_D_OTHER); return NULL; }", "")]),
    ("PS3_SPU_IB_FAST_RELOC=0 not honoured",
     [("if (!g_spu_ib_reloc) { SPU_IBF_COUNT(IBR_D_RELOC_OFF); return NULL; }", "")]),
    ("unresolved lookups counted as hits-free fill (miss path fills a NULL function is impossible; probe class dropped)",
     [("SPU_IBF_COUNT(!e->fn ? IBR_P_COLD : e->pc != key ? IBR_P_CONFLICT : e->img != img ? IBR_P_IMAGE : e->ovl != ovl ? IBR_P_OWNER : IBR_P_EPOCH);", "")]),''')
rep('''     [("else if (s_task_elf_count | s_task_entry_count | ctx->resident_task) return NULL;", "else if (0) return NULL;")]),''','''     [("else if (s_task_elf_count | s_task_entry_count | ctx->resident_task) { SPU_IBF_COUNT(IBR_D_TASK); return NULL; }", "else if (0) return NULL;")]),''')
rep('''        for var in ("SPU_POLLTRACE"''','''        rc, txt = run(exe, "envinit", env={"PS3_SPU_IB_FAST": "1", "PS3_SPU_IB_FAST_RELOC": "0"})
        check("mode=1" in txt and "reloc=0" in txt, "PS3_SPU_IB_FAST_RELOC=0: on, relocatable slots refused")
        rc, txt = run(exe, "envinit", env={"PS3_SPU_IB_FAST": "1"})
        check("reloc=1" in txt, "PS3_SPU_IB_FAST=1: relocatable slots served by default")
        for var in ("SPU_POLLTRACE"''')
open(p,'w',encoding='utf-8',newline='').write(s)
