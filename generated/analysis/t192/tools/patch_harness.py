p='tests/test_spu_ib_fast.c'
s=open(p,encoding='utf-8',newline='').read()
nl='\r\n' if '\r\n' in s else '\n'
s=s.replace('\r\n','\n')
BS=chr(92)
def rep(old,new,cnt=1):
    global s
    assert s.count(old)==cnt,(s.count(old),old[:80])
    s=s.replace(old,new)
d=open('../generated/analysis/t192/tools/dr_chunk.c',encoding='utf-8').read()
m='/* ---- seeded random sequences ---- */'
rep(m,d+m)
rep('static void random_case(int tasks, int n)\n{','static int g_reloc_mode;      /* random --reloc: bias the sequence to relocatable slots and add slot / DMA / registry / trace events */\nstatic void random_case(int tasks, int n)\n{')
rep('        BOTH(c->gpr[3]._u32[0] = it);\n        char what[64];','''        if (g_reloc_mode) {
            uint32_t k = rnd();
            /* slot lifecycle events, applied identically to both contexts */
            if ((k & 7) < 4) {         /* install / replace a relocatable module around pc (same address, other owner or base, ...) */
                int sl = (int)((k >> 3) & 3);
                uint32_t lsa = (pc & ~0xFFu) - ((k >> 5) & 3) * 0x40u, lb = 0x4000u + (((k >> 7) & 3) ? 0u : 0x40u * ((k >> 9) & 3));
                BOTH(c->resident_code[sl].image_id = OWN[(k >> 11) & 1]; c->resident_code[sl].lsa = lsa;
                     c->resident_code[sl].size = 0x100u + ((k >> 12) & 3) * 0x100u; c->resident_code[sl].link_base = lb);
            } else if ((k & 7) == 4) BOTH(c->resident_code[(k >> 3) & 3].image_id = ((k >> 6) & 1) ? 0 : -1);          /* evict / unrecognized */
            else if ((k & 7) == 5) { uint32_t q = (k >> 3) & 0xFFFFu; BOTH(spu_overlay_note_get(c, 0x30000000u + (q << 8), c->ls + ((pc & ~0xFFu) + (q & 0x1C0u) - 0x80u), 16u + (q & 0x7F))); }   /* DMA over / near a slot */
            if (((k >> 16) & 31) == 0) {          /* a function registered at run time: moves the epoch, may shadow */
                spu_begin_image(((k >> 21) & 1) ? OWN[(k >> 22) & 1] : (((k >> 23) & 1) ? OVL[(k >> 24) % 3] : IMG[(k >> 24) & 3]));
                spu_register_function(((k >> 26) & 1) ? ((0x4000u + ((k >> 8) & 15) * 0x40u) | SPU_RELOC_KEY_BIT) : g_addrs[(k >> 4) % (uint32_t)g_naddr], STUBS[(k >> 9) & 63]);
            }
            spu_ib_fast_test_trace(((k >> 27) & 15) == 0 ? 0x3FFF8u : 0);
            spu_ib_fast_set_reloc(((k >> 31) & 1) || (it & 255));   /* the knob is off for about 1/512 of the steps */
        }
        BOTH(c->gpr[3]._u32[0] = it);
        char what[64];''')
rep('    CHECK(st0[0] > 0 && st0[1] > 0 && st0[2] > 0, "random mix exercises hits, fills and resolver fallbacks");','''    CHECK(st0[0] > 0 && st0[1] > 0 && st0[2] > 0, "random mix exercises hits, fills and resolver fallbacks");
    { unsigned long long r[32], prim = 0, probe = 0; spu_ib_fast_reasons(r); spu_ib_fast_set_reloc(1); spu_ib_fast_test_trace(0);
      for (int i = 0; i <= R_D_OTHER; i++) prim += r[i];
      for (int i = R_P_COLD; i <= R_P_EPOCH; i++) probe += r[i];
      printf("  reasons: hit %llu fill %llu policy %llu irq %llu trace %llu service %llu img23 %llu task %llu reloc_off %llu unrec %llu unresolved %llu other %llu"''' + BS + '''n",
             r[R_HIT], r[R_FILL], r[R_D_POLICY], r[R_D_IRQ], r[R_D_TRACE], r[R_D_SERVICE], r[R_D_IMG23], r[R_D_TASK], r[R_D_RELOC_OFF], r[R_D_UNREC], r[R_D_UNRESOLVED], r[R_D_OTHER]);
      CHECK(prim == g_bruns, "primary reasons are exclusive and complete (%llu vs %llu branches)", prim, g_bruns);
      CHECK(probe == r[R_FILL] + r[R_D_UNRESOLVED], "probe classes sum to fills + unresolved (%llu vs %llu)", probe, r[R_FILL] + r[R_D_UNRESOLVED]);
      if (g_reloc_mode) CHECK(r[R_O_SLOT_RELOC] > 0 && r[R_D_UNREC] > 0 && r[R_D_TRACE] > 0 && r[R_D_RELOC_OFF] > 0 && r[R_P_EPOCH] > 0, "reloc mix exercised slots, unrecognized owners, tracing, the knob and epoch misses"); }''')
rep('c->resident_code[s].link_base = ((k >> 11) & 7) == 0 ? 0x4000u : 0);','c->resident_code[s].link_base = ((k >> 11) & 3) == 0 ? 0x4000u : 0);')
rep('c->resident_ovl = (sel & 0x100) ? OVL[(sel >> 9) % 3] : ((sel & 0x200) ? 0 : c->resident_ovl));','c->resident_ovl = (sel & 0x100) ? OVL[(sel >> 9) % 3] : ((sel & 0x200) ? 0 : (((sel >> 28) & 15) == 0 ? -2 - (int)((sel >> 12) & 1) : c->resident_ovl)));')
rep('    int tasks = 0; for (int i = 1; i < argc; i++) if (!strcmp(argv[i], "--tasks")) tasks = 1;','    int tasks = 0; for (int i = 1; i < argc; i++) if (!strcmp(argv[i], "--tasks")) tasks = 1;\n    for (int i = 1; i < argc; i++) if (!strcmp(argv[i], "--reloc")) g_reloc_mode = 1;')
rep('    if (!strcmp(mode, "directed")) directed(tasks);','    if (!strcmp(mode, "directed")) directed(tasks);\n    else if (!strcmp(mode, "reloc")) directed_reloc();')
rep('    run_branch(c, o);\n    *h = ctx_hash(c);','''    if (r & 0x100000) {      /* a relocatable slot whose base depends on the worker: the same lifted code through different deltas */
        c->resident_code[0].image_id = OWN[0]; c->resident_code[0].lsa = c->pc & ~0xFFu; c->resident_code[0].size = 0x100;
        c->resident_code[0].link_base = 0x4000u + (seed & 3) * 0x40u;
    }
    run_branch(c, o);
    *h = ctx_hash(c);''')
open(p,'w',encoding='utf-8',newline='').write(s.replace('\n',nl))
print('patched')
