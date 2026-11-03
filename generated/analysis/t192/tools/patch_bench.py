p='tests/test_spu_ib_fast.c'
s=open(p,encoding='utf-8',newline='').read()
nl='\r\n' if '\r\n' in s else '\n'
s=s.replace('\r\n','\n')
i=s.index("        else if (b->pat[0] == 'j') {")
j=s.index("        else if (b->pat[0] == 'f')")
new='''        else if (b->pat[0] == 'j') { c->resident_code[0].image_id = OWN[0]; c->resident_code[0].lsa = 0x20000u; c->resident_code[0].size = 0x400; c->resident_code[0].link_base = 0x4000u; c->pc = 0x20080u; }   /* one intra-slot target (relocatable slot) */
        else if (b->pat[0] == 'k') { x ^= x << 13; x ^= x >> 7; x ^= x << 17; c->resident_code[0].image_id = OWN[0]; c->resident_code[0].lsa = 0x20000u; c->resident_code[0].size = 0x400; c->resident_code[0].link_base = 0x4000u; c->pc = 0x20000u + 0x80u * (x & 7); }   /* 8 intra-slot targets */
        else if (b->pat[0] == 'x') { int o = (int)(i & 1); c->resident_code[0].image_id = OWN[o]; c->resident_code[0].lsa = 0x20000u; c->resident_code[0].size = 0x400; c->resident_code[0].link_base = 0x4000u; c->pc = 0x20000u + 0x40u * (uint32_t)o; }   /* slot replaced by another owner every branch (same address, other code) */
        else if (b->pat[0] == 'w') {   /* Wws-style: a job module is installed (alternating bases, so the delta changes), runs 15 intra-slot branches, a branch leaves the slot, then it is replaced */
            const long ph = i & 15; const uint32_t base = (i & 16) ? 0x24000u : 0x20000u;
            if (ph == 0) { c->resident_code[0].image_id = OWN[0]; c->resident_code[0].lsa = base; c->resident_code[0].size = 0x400; c->resident_code[0].link_base = 0x4000u; }
            if (ph == 15) { c->pc = targets[0]; }                                   /* exit: back to the image's own code */
            else { x ^= x << 13; x ^= x >> 7; x ^= x << 17; c->pc = c->resident_code[0].lsa + 0x80u * (x & 7); }
        }
        else if (b->pat[0] == 'u') { c->pc = 0x2FC0u; }                                       /* invalid target: always the resolver's miss path */
'''
s=s[:i]+new+s[j:]
open(p,'w',encoding='utf-8',newline='').write(s.replace('\n',nl))
