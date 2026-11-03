"""T122: PS3_TEX_SNAPSHOT_EPOCH in the D3D12 backend (tree = argv[1])."""
import sys
from pathlib import Path
NL = chr(10)
root = Path(sys.argv[1])


def sub(p, old, new):
    f = root / p; raw = f.read_bytes(); crlf = b'\r\n' in raw
    t = raw.decode('utf-8').replace(chr(13), '')
    assert t.count(old) == 1, (p, old[:70], t.count(old))
    t = t.replace(old, new)
    if crlf: t = t.replace(NL, chr(13) + NL)
    f.write_bytes(t.encode('utf-8'))


B = 'libs/video/rsx_d3d12_backend.c'
sub(B, '''        const int r = ps3_rtrb_apply(&s_rtrb, q, (const uint8_t*)mp, vm_base, &bad);
''', '''        const int r = ps3_rtrb_apply(&s_rtrb, q, (const uint8_t*)mp, vm_base, &bad);
        { extern void cellGcm_sync_epoch_bump(void); cellGcm_sync_epoch_bump(); }   /* guest memory written */
''')
sub(B, '''static void render_frame(void)
{
    pp_note(PP_REPLAY);
    if (gsy_on()) s_gsy.passes++;
''', '''/* PS3_TEX_SNAPSHOT_EPOCH=1 (off by default): the texture snapshot reuses a
 * capture made in the same RSX sync epoch (cellGcmSys.c) without hashing the
 * guest bytes again (ps3emu/tex_snapshot.h). In the race one 2 MB linear B8
 * texture is bound on ~1300 draws a frame and never changes: 2.7 GB hashed. */
static void tsnap_epoch_init(void)
{
    static int done = 0;
    if (done) return;
    done = 1;
    const char* e = getenv("PS3_TEX_SNAPSHOT_EPOCH");
    if (!e || e[0] != '1' || e[1]) return;
    extern volatile long g_cellGcm_sync_epoch;
    s_texsnap.epoch_src = &g_cellGcm_sync_epoch;
    fprintf(stderr, "[tex-snapshot] sync epoch on: one hash per texture per epoch%c", 10);
}

static void render_frame(void)
{
    pp_note(PP_REPLAY);
    if (gsy_on()) s_gsy.passes++;
    tsnap_epoch_init();
''')
print('ok', root)
