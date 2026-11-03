"""T122: the sync epoch in cellGcmSys.c's FIFO walker (tree = argv[1])."""
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


G = 'libs/video/cellGcmSys.c'
sub(G, '''extern void (*volatile cellGcm_drain_hook)(int begin);
void (*volatile cellGcm_drain_hook)(int begin) = NULL;
''', '''extern void (*volatile cellGcm_drain_hook)(int begin);
void (*volatile cellGcm_drain_hook)(int begin) = NULL;

/* The RSX sync epoch (PS3_TEX_SNAPSHOT_EPOCH, ps3emu/tex_snapshot.h): bumped
 * at every point where the guest can learn how far the RSX has got, or where
 * the RSX side writes guest memory, so two draws with the same epoch are ones
 * the guest cannot tell apart in time. Always maintained (one relaxed add);
 * only the texture snapshot reads it, and only when asked to. */
volatile long g_cellGcm_sync_epoch = 0;
void cellGcm_sync_epoch_bump(void) { __atomic_add_fetch(&g_cellGcm_sync_epoch, 1, __ATOMIC_RELAXED); }

/* A method packet that can neither sync with the guest nor write guest memory:
 * 3D-class methods on subchannel 0, outside the channel/notify range (below
 * 0x0180: NV406E semaphores, SET_REFERENCE, NOTIFY, WAIT_FOR_IDLE),
 * CLEAR_REPORT_VALUE (0x17C8), GET_REPORT (0x1800) and the semaphore
 * offset/releases (0x1D6C-0x1D74). Everything else -- other subchannels
 * (transfers, flips, user commands, driver methods) included -- bumps. */
static int gcm_epoch_pure(u32 subch, u32 method, u32 type, u32 count)
{
    const u32 last = (type == 0 && count) ? method + (count - 1u) * 4u : method;
    if (subch != 0 || method < 0x0180u) return 0;
    if (method <= 0x17C8u && last >= 0x17C8u) return 0;
    if (method <= 0x1800u && last >= 0x1800u) return 0;
    if (method <= 0x1D74u && last >= 0x1D6Cu) return 0;
    return 1;
}
''')
sub(G, '''static void gcm_rsx_process_fifo_unlocked(void)
{
''', '''static void gcm_rsx_process_fifo_unlocked(void)
{
    cellGcm_sync_epoch_bump();   /* a new pass: `get` was published at the end of the last one */
''')
sub(G, '''              if (!gcm_get_eq_put()) vm_write32(GCM_CONTROL_GUEST_ADDR + 4, tgt); }''',
       '''              cellGcm_sync_epoch_bump();
              if (!gcm_get_eq_put()) vm_write32(GCM_CONTROL_GUEST_ADDR + 4, tgt); }''')
sub(G, '''            u32 subch  = (w >> 13) & 7;
''', '''            u32 subch  = (w >> 13) & 7;
            if (!gcm_epoch_pure(subch, method, type, count)) cellGcm_sync_epoch_bump();
''')
print('ok', root)
sub(G, '''volatile long g_cellGcm_sync_epoch = 0;
void cellGcm_sync_epoch_bump(void)''', '''extern volatile long g_cellGcm_sync_epoch;
extern void cellGcm_sync_epoch_bump(void);
volatile long g_cellGcm_sync_epoch = 0;
void cellGcm_sync_epoch_bump(void)''')
