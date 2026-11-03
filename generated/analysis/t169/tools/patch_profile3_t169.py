MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T169 continuation: each draw its own Begin (else the backend merges them), and an H0 program for the sRGB quad (the packer needs 16-bit exports)."""
p = (MS_ROOT + r'\ps3recomp-t169\libs\video\tests\test_t169_profile_backend.c')
s = open(p, encoding='utf-8', newline='').read()


def sub(a, b):
    global s
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)


sub('''#define FP_U1    0x04000100u   /* TEX R0, TC0, unit 1 */
''', '''#define FP_U1    0x04000100u   /* TEX R0, TC0, unit 1 */
#define FP_H     0x04000200u   /* MOV H0, COL0: sRGB output needs 16-bit exports */
''')
sub('''    rsx_test_fp_tex_r0_tc0(vm_base + FP_U1, 1);
''', '''    rsx_test_fp_tex_r0_tc0(vm_base + FP_U1, 1);
    rsx_test_fp_instr(vm_base + FP_H, RSX_TEST_FP_OPC(RSX_TEST_FP_OP_MOV) | RSX_TEST_FP_MASK_XYZW | 1u << 7 |
                                      RSX_TEST_FP_INSRC_COL0 | RSX_TEST_FP_END, RSX_TEST_FP_SRC_INPUT | RSX_TEST_FP_SWZ_IDENT);
''')
sub('''    st.shader_control = 0x02008400;   /* the programs export R0, 16-bit: sRGB output applies */
''', '''    st.shader_control = 0x02008440;   /* [6]: the programs export R0 (32-bit) */
''')
sub('''        st.depth_mask = 1;
        notify(be, &st);
''', '''        st.depth_mask = 1;
        st.begin_epoch++;
        notify(be, &st);
''')
sub('''        st.shader_packer = 1;
        st.shader_program = FP_A | 1u; st.fragment_program_addr = FP_A;
        notify(be, &st);
''', '''        st.shader_packer = 1; st.shader_control = 0x02008400;
        st.shader_program = FP_H | 1u; st.fragment_program_addr = FP_H;
        st.begin_epoch++;
        notify(be, &st);
''')
sub('''        st.shader_packer = 0;
        st.begin_epoch++;
''', '''        st.shader_packer = 0; st.shader_control = 0x02008440;
        st.shader_program = FP_A | 1u; st.fragment_program_addr = FP_A;
        st.begin_epoch++;
''')
open(p, 'w', encoding='utf-8', newline='').write(s)
