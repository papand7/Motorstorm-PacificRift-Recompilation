import sys
p = sys.argv[1]
s = open(p, newline='').read().replace('\r\n', '\n')
a = """                        if (z < 0 || !((dr->fp_units >> _u) & 1u)) continue;
                        if (z == cur_z) {
                            /* RSX_DEPTH_STATE: the bound zeta read as colour
                             * (kept bound above). Its image is rebuilt from the
                             * depth so far, then it returns to depth target. */
                            if (ds_state_on() && dr->tex_src[_u] == RSXI_SRC_ZETA_AS_COLOR &&
                                !s_d3d.zeta[z].conv_ok && zeta_convert(z)) {
                                zeta_transition(z, D3D12_RESOURCE_STATE_DEPTH_WRITE);
                                conv = 1;
                            }
                            continue;
                        }
"""
b = """                        /* RSX_DEPTH_STATE: the bound zeta read as colour (kept
                         * bound above). Its image is rebuilt from the depth so
                         * far, then it returns to depth target. */
                        if (z >= 0 && z == cur_z && ((dr->fp_units >> _u) & 1u) && ds_state_on() &&
                            dr->tex_src[_u] == RSXI_SRC_ZETA_AS_COLOR &&
                            !s_d3d.zeta[z].conv_ok && zeta_convert(z)) {
                            zeta_transition(z, D3D12_RESOURCE_STATE_DEPTH_WRITE);
                            conv = 1;
                        }
                        if (z < 0 || z == cur_z || !((dr->fp_units >> _u) & 1u)) continue;
"""
assert s.count(a) == 1
s = s.replace(a, b)
open(p, 'w', newline='').write(s.replace('\n', '\r\n'))
print('ok')
