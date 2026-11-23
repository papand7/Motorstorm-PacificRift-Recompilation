/* mspr_patch_spec(): unset gives the default list (drs), "none" and an empty
 * value give no patches, any other value is used as given.
 *   clang-cl /O2 /I port-vkgame port-vkgame\tests\test_mspr_patch.c && test_mspr_patch.exe */
#include <stdio.h>
#include <string.h>
#include "mspr_patch.h"

static int fails;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)

int main(void)
{
    CHECK(!strcmp(MSPR_PATCH_DEFAULT, "drs"));
    CHECK(!strcmp(mspr_patch_spec(NULL), "drs"));
    CHECK(!strcmp(mspr_patch_spec("none"), ""));
    CHECK(!strcmp(mspr_patch_spec(""), ""));
    CHECK(!strcmp(mspr_patch_spec("drs:ab"), "drs:ab"));
    CHECK(!strcmp(mspr_patch_spec("60fps,vfps"), "60fps,vfps"));
    CHECK(!strcmp(mspr_patch_spec("nonex"), "nonex"));
    printf("test_mspr_patch: %d failure(s)\n", fails);
    return fails ? 1 : 0;
}
