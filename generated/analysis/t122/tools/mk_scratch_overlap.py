# T122 scratch (diagnostic only, never committed): lag-1 pipelining upper bound.
# Pass N records while the GPU runs pass N-1; render_frame N waits for list N-1
# only after submitting N. Allocators: a ring of 4, one per pass. Correct for
# bench_submit_sync's workload only (static, cached textures; no atlas; no RT churn).
import sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8', newline='').read().replace(chr(13) + chr(10), chr(10))
def R(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:60])
    s = s.replace(old, new)
R("    if (work_fence_ready()) work_fence_wait();   /* RSX_SUBMIT_FENCE=1: the lists, not the Present */\n    else wait_for_gpu();\n",
  "    if (!work_fence_ready()) wait_for_gpu();   /* SCRATCH overlap: no entry wait once the list fence exists */\n")
R("    s_d3d.cmd_allocators[fi]->lpVtbl->Reset(s_d3d.cmd_allocators[fi]);\n    s_d3d.cmd_list->lpVtbl->Reset(s_d3d.cmd_list, s_d3d.cmd_allocators[fi], NULL);\n    if (gsy_on()) s_gsy.resets++;",
  "    static ID3D12CommandAllocator* ring[4]; static unsigned rpass = 0;\n"
  "    ID3D12CommandAllocator* ca = s_d3d.cmd_allocators[fi];\n"
  "    if (work_fence_ready()) { unsigned k = rpass++ & 3u; if (!ring[k]) s_d3d.device->lpVtbl->CreateCommandAllocator(s_d3d.device, D3D12_COMMAND_LIST_TYPE_DIRECT, &IID_ID3D12CommandAllocator, (void**)&ring[k]); ca = ring[k]; }\n"
  "    ca->lpVtbl->Reset(ca);\n    s_d3d.cmd_list->lpVtbl->Reset(s_d3d.cmd_list, ca, NULL);\n    if (gsy_on()) s_gsy.resets++;")
R("    work_fence_signal();   /* RSX_SUBMIT_FENCE / RSX_GPU_SYNC, before the Present */\n",
  "    work_fence_signal();   /* RSX_SUBMIT_FENCE / RSX_GPU_SYNC, before the Present */\n"
  "    if (work_fence_ready() && s_wf_val > 1 && s_wf->lpVtbl->GetCompletedValue(s_wf) < s_wf_val - 1) {   /* SCRATCH: wait for list N-1 */\n"
  "        const u64 t0 = gsy_on() ? gsy_now_us() : 0;\n"
  "        s_wf->lpVtbl->SetEventOnCompletion(s_wf, s_wf_val - 1, s_wf_event); WaitForSingleObject(s_wf_event, 2000);\n"
  "        if (gsy_on()) gsy_wait(&s_gsy, -3, 1, gsy_now_us() - t0); }\n")
R("static void gts_collect(void)\n{\n    if (!s_gts_pending) return;", "static void gts_collect(void)\n{\n    if (work_fence_ready()) s_gts_pending = 0;   /* SCRATCH: the pair may still be in flight */\n    if (!s_gts_pending) return;")
open(dst, 'w', encoding='utf-8', newline='').write(s)
print('ok')
