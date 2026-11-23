/* The original MotorStorm Wws_Job PM at EBOOT guest EA 0x00FFCC80.
 * Its 0x2D00-byte FNV fingerprint and LS 0xA00 entry were verified against
 * the decrypted executable and a native SPURS dispatch trace. */
#include "spu_workload.h"

extern void spu_begin_image(int image_id);
extern void mspr_wws_pm_spu_func_00000A00(spu_context* ctx);
extern void mspr_wws_pm_spu_recomp_register(void);

static void mspr_register_wws_job_pm(void)
{
    const int image_id = 0x4D535052; /* MSPR, distinct from ELF-image ids */
    spu_begin_image(image_id);
    mspr_wws_pm_spu_recomp_register();
    spu_workload_register_img(0x093FC7EE6C9F7E84ULL,
                              mspr_wws_pm_spu_func_00000A00,
                              image_id, "MotorStorm Wws_Job PM");
    spu_begin_image(0);
}

__attribute__((constructor)) static void mspr_register_wws_job_pm_ctor(void)
{
    mspr_register_wws_job_pm();
}
