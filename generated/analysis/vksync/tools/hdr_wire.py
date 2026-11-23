r"""One-off edit: wires the RSX_HDR present (rsx_vulkan_backend.c HDR section) into the swapchain,
the window present, window drop and init. usage: py -3 hdr_wire.py <rsx_vulkan_backend.c>"""
import sys

p = sys.argv[1]
s = open(p, encoding='utf-8').read()


def rep(old, new, count=1):
    global s
    assert s.count(old) == count, (old, s.count(old))
    s = s.replace(old, new)


rep('s_hdr.want = (_stricmp(e, "scrgb") == 0) ? 2 : 1;',
    "s_hdr.want = (e[0] == 's' || e[0] == 'S') ? 2 : 1;   /* scrgb */")
rep(r'''    VkFormatProperties fp;
    pvkGetPhysicalDeviceFormatProperties(s_vk.phys, fmt.format, &fp);
    if (!(fp.optimalTilingFeatures & VK_FORMAT_FEATURE_BLIT_DST_BIT)) {''',
    r'''    /* RSX_HDR: the surface's HDR10 / scRGB format, drawn to by vk_hdr_record */
    int hdr = 0;
    if (vk_hdr_wanted() && s_hdr.ext) {
        if (!s_hdr.queried) {
            s_hdr.queried = 1;
            s_hdr.paper = vk_hdr_envf("RSX_HDR_PAPER", 200.0f);
            s_hdr.peak  = vk_hdr_envf("RSX_HDR_PEAK", 600.0f);
            s_hdr.knee  = vk_hdr_envf("RSX_HDR_KNEE", 0.5f);
            s_hdr.expo  = vk_hdr_envf("RSX_HDR_CURVE", 2.0f);
            s_hdr.gamma = vk_hdr_envf("RSX_HDR_GAMMA", 2.2f);
            if (s_hdr.paper < 1.0f) s_hdr.paper = 1.0f;
            if (s_hdr.expo < 1.0f) s_hdr.expo = 1.0f;
            vk_hdr_query_display();
        }
        VkSurfaceFormatKHR hf;
        if (!(caps.supportedUsageFlags & VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT))
            VK_LOG("HDR: swapchain images cannot be drawn to, staying SDR\n");
        else if (vk_hdr_pick_format(fmts, nf, s_hdr.want, &hf) == 0) { fmt = hf; hdr = 1; }
        else if (vk_hdr_pick_format(fmts, nf, 3 - s_hdr.want, &hf) == 0) { fmt = hf; hdr = 1; }
        else VK_LOG("HDR: the surface offers no HDR10 or scRGB format (%u formats), staying SDR\n", nf);
    }
    VkFormatProperties fp;
    pvkGetPhysicalDeviceFormatProperties(s_vk.phys, fmt.format, &fp);
    if (!hdr && !(fp.optimalTilingFeatures & VK_FORMAT_FEATURE_BLIT_DST_BIT)) {''')
rep('''        .imageUsage = VK_IMAGE_USAGE_TRANSFER_DST_BIT,
        .imageSharingMode = VK_SHARING_MODE_EXCLUSIVE,''',
    '''        .imageUsage = hdr ? VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT : VK_IMAGE_USAGE_TRANSFER_DST_BIT,
        .imageSharingMode = VK_SHARING_MODE_EXCLUSIVE,''')
rep('''    VkSwapchainKHR sc = VK_NULL_HANDLE;
    VkResult r = pvkCreateSwapchainKHR(s_vk.device, &sci, NULL, &sc);''',
    '''    VkSwapchainKHR sc = VK_NULL_HANDLE;
    vk_hdr_free_targets();   /* views of the old swapchain's images */
    VkResult r = pvkCreateSwapchainKHR(s_vk.device, &sci, NULL, &sc);''')
rep(r'''    s_vk.sc_extent = ext;
    s_vk.sc_count = n;
    VK_LOG("window swapchain %ux%u, %u images, format %d\n", ext.width, ext.height, n, (int)fmt.format);''',
    r'''    s_vk.sc_extent = ext;
    s_vk.sc_count = n;
    if (hdr) {
        if (vk_hdr_build(fmt.format, s_vk.sc_images, n, ext) == 0) {
            s_hdr.on = 1;
            s_hdr.mode = fmt.colorSpace == VK_COLOR_SPACE_EXTENDED_SRGB_LINEAR_EXT ? 1 : 0;
            VK_LOG("HDR on: %s, paper white %.0f nits, peak %.0f nits, knee %.2f, curve %.1f, gamma %.2f\n",
                   s_hdr.mode ? "scRGB (FP16)" : "HDR10 (PQ, BT.2020)", s_hdr.paper, s_hdr.peak,
                   s_hdr.knee, s_hdr.expo, s_hdr.gamma);
        } else {
            /* this swapchain cannot take the SDR blit (no transfer usage): make it again, SDR */
            VK_LOG("HDR: present pipeline could not be built, staying SDR\n");
            vk_hdr_free_all();
            s_hdr.ext = 0;
            return vk_create_swapchain();
        }
    }
    VK_LOG("window swapchain %ux%u, %u images, format %d, colour space %d\n",
           ext.width, ext.height, n, (int)fmt.format, (int)fmt.colorSpace);''')
rep('''    vk_barrier_image_on(cb, s_vk.color.img, VK_IMAGE_ASPECT_COLOR_BIT, VK_IMAGE_LAYOUT_GENERAL);
    VkImageMemoryBarrier b = {
        .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
        .srcAccessMask = 0, .dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,''',
    '''    vk_barrier_image_on(cb, s_vk.color.img, VK_IMAGE_ASPECT_COLOR_BIT, VK_IMAGE_LAYOUT_GENERAL);
    VkPipelineStageFlags wait_stage = VK_PIPELINE_STAGE_TRANSFER_BIT;
    if (s_hdr.on && idx < s_hdr.n) {
        vk_hdr_record(cb, idx);
        wait_stage = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
    } else {
    VkImageMemoryBarrier b = {
        .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
        .srcAccessMask = 0, .dstAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,''')
rep(r'''    pvkCmdPipelineBarrier(cb, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,
                          0, 0, NULL, 0, NULL, 1, &b);
    if (pvkEndCommandBuffer(cb) != VK_SUCCESS) { VK_LOG("vkEndCommandBuffer failed\n"); return; }

    VkPipelineStageFlags wait_stage = VK_PIPELINE_STAGE_TRANSFER_BIT;''',
    r'''    pvkCmdPipelineBarrier(cb, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,
                          0, 0, NULL, 0, NULL, 1, &b);
    }
    if (pvkEndCommandBuffer(cb) != VK_SUCCESS) { VK_LOG("vkEndCommandBuffer failed\n"); return; }
''')
rep('''        if (s_vk.sem_acquire) pvkDestroySemaphore(s_vk.device, s_vk.sem_acquire, NULL);
        if (s_vk.swapchain && pvkDestroySwapchainKHR)''',
    '''        if (s_vk.sem_acquire) pvkDestroySemaphore(s_vk.device, s_vk.sem_acquire, NULL);
        if (pvkDestroyRenderPass) vk_hdr_free_all();
        if (s_vk.swapchain && pvkDestroySwapchainKHR)''')
rep('''    VkInstanceCreateInfo ci = { .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
                                .pApplicationInfo = &app };
    if (s_vk.windowed) {''',
    '''    VkInstanceCreateInfo ci = { .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
                                .pApplicationInfo = &app };
    vk_hdr_add_instance_ext();
    if (s_vk.windowed) {''')
rep('''                        VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT |
                        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT, VK_IMAGE_ASPECT_COLOR_BIT)) return -1;''',
    '''                        VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT |
                        VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT |
                        (vk_hdr_wanted() ? VK_IMAGE_USAGE_SAMPLED_BIT : 0), VK_IMAGE_ASPECT_COLOR_BIT)) return -1;''')
open(p, 'w', encoding='utf-8').write(s)
print('ok')
