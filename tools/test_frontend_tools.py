import unittest

from trace_frontend import instrument, watch_expression
from summarize_probe import summarize


class FrontendToolsTests(unittest.TestCase):
    def test_instrument_entry_and_all_returns(self):
        source = (b"#include <stdio.h>\r\n"
                  b"void func_00001234(ppu_context* ctx) {\r\n"
                  b"if (ctx->gpr[3]) return;\r\n"
                  b"return;\r\n}\r\n"
                  b"void func_00005678(ppu_context* ctx) {}\r\n")
        modified, exits = instrument(source, 0x1234, 4, "r3+4")
        self.assertEqual(exits, 2)
        self.assertEqual(modified.count(b"[FT] fn=00001234 exit"), 2)
        self.assertIn(b"if (ctx->gpr[3]) {", modified)
        self.assertIn(b"vm_read32(ctx->gpr[3] + 0x4)", modified)
        self.assertEqual(modified.count(b"vm_read32(ctx->gpr[3] + 0x4)"), 1)
        self.assertIn(b"void func_00005678(ppu_context* ctx) {}", modified)

    def test_exit_label_and_validation(self):
        source = (b"#include <stdio.h>\nvoid func_00001234(ppu_context* ctx) {\n"
                  b"loc_00001238:\nreturn;\n}\nvoid func_00005678(ppu_context* ctx) {}\n")
        modified, exits = instrument(source, 0x1234, 2, exit_label="0x1238")
        self.assertEqual(exits, 1)
        self.assertIn(b"[FT] fn=00001234 label", modified)
        with self.assertRaises(ValueError):
            instrument(source, 0x1234, 2, exit_label="0x9999")
        with self.assertRaises(ValueError):
            watch_expression("r32+4")

    def test_after_call_is_specific(self):
        source = (b"#include <stdio.h>\nvoid func_00001234(ppu_context* ctx) {\n"
                  b"ctx->lr = 0x00001240; func_00005678(ctx); DRAIN_TRAMPOLINE(ctx);\n"
                  b"return;\n}\nvoid func_00005678(ppu_context* ctx) {}\n")
        modified, points = instrument(source, 0x1234, 5, after_call="0x1240",
                                      include_returns=True)
        self.assertEqual(points, 2)
        self.assertIn(b"[FT] fn=00001234 after-call", modified)
        self.assertEqual(modified.count(b"[FT] fn=00001234 exit"), 1)

    def test_multiple_return_checkpoints(self):
        source = (b"#include <stdio.h>\nvoid func_00001234(ppu_context* ctx) {\n"
                  b"ctx->lr = 0x00001240; func_00005678(ctx); DRAIN_TRAMPOLINE(ctx);\n"
                  b"ctx->lr = 0x00001244; func_00005678(ctx); DRAIN_TRAMPOLINE(ctx);\n"
                  b"return;\n}\nvoid func_00005678(ppu_context* ctx) {}\n")
        modified, points = instrument(source, 0x1234, 5,
                                      after_call="0x1240,0x1244")
        self.assertEqual(points, 2)
        self.assertIn(b"after-00001240", modified)
        self.assertIn(b"after-00001244", modified)

    def test_label_checkpoints(self):
        source = (b"#include <stdio.h>\nvoid func_00001234(ppu_context* ctx) {\n"
                  b"loc_00001238:\nreturn;\n}\nvoid func_00005678(ppu_context* ctx) {}\n")
        modified, points = instrument(source, 0x1234, 5, labels=["0x1238"])
        self.assertEqual(points, 2)
        self.assertIn(b"at-00001238", modified)
        sampled, _ = instrument(source, 0x1234, 5, labels=["0x1238"],
                                sample_power2=True)
        self.assertIn(b"hit=%u", sampled)
        self.assertIn(b"hit & (hit - 1u)", sampled)

    def test_entry_only_does_not_expand_trampoline_returns(self):
        source = (b"#include <stdio.h>\nvoid func_00001234(ppu_context* ctx) {\n"
                  + b"return;\n" * 100
                  + b"}\nvoid func_00005678(ppu_context* ctx) {}\n")
        modified, points = instrument(source, 0x1234, 5, entry_only=True)
        self.assertEqual(points, 0)
        self.assertEqual(modified.count(b"[FT] fn=00001234 entry"), 1)
        self.assertNotIn(b"[FT] fn=00001234 exit", modified)
        self.assertEqual(modified.count(b"return;"), 100)
        with self.assertRaises(ValueError):
            instrument(source, 0x1234, 5, entry_only=True, after_call="0x1240")
        filtered, _ = instrument(source, 0x1234, 5, entry_only=True,
                                 lr_filter=0x82B8)
        self.assertIn(b"(uint32_t)ctx->lr == 0x000082B8u", filtered)

    def test_log_summary_is_bounded(self):
        lines = ["[WAIT] polling\n"] * 100 + ["[FT] fn=1 exit\n", "[RSX] draw 6\n", "error: sample\n"]
        result = summarize(lines, "00000001")
        self.assertIn("lines=103", result)
        self.assertIn("[FT] fn=1 exit", result)
        self.assertIn("[RSX] draw 6", result)
        self.assertIn("error: sample", result)
        self.assertLess(len(result.splitlines()), 30)

    def test_runtime_trace_sections(self):
        lines = [
            "[PT] t=1 ev=config mask=03 fn=2 ret=0 bb=0 hle=0 sc=1 tids=0 watches=1 hooks=1\n",
            "[PT] t=5 tid=1 ev=enter pc=001E8058 lr=001F6014 fn=001E8058 depth=1 n=1 r3=1\n",
            "[PT] t=9 tid=1 ev=exit pc=001F6014 lr=001F6014 fn=001E8058 site=001F6014 how=ret dur_us=4 depth=0 n=1\n",
            "[PT] t=10 tid=1 ev=enter pc=001E8058 lr=001F6014 fn=001E8058 depth=1 n=2 r3=1\n",
            "[PT] t=12 tid=1 ev=enter pc=00584C20 lr=00586D38 fn=00584C20 depth=2 n=1 r3=4015BEA0\n",
            "[PT] t=900 tid=1 ev=stall fn=00584C20 age_ms=5000 depth=2 pc=00584D70 hooks_since_sample=812 in=guest:00000000 stack=00584C20<001E8058 recent=00584D70\n",
            "[PT] t=950 tid=24 ev=sc num=00000082 pc=00632DB4 lr=00632DB4 dur_us=12000 a3=11 a4=0 a5=0 a6=0 ret=00000000\n",
            "[PT] t=960 tid=24 ev=sc num=00000082 pc=00632DB4 lr=00632DB4 dur_us=14000 a3=11 a4=0 a5=0 a6=0 ret=00000000\n",
            "[PT] t=970 tid=1 ev=mem kind=ppu-write addr=010D529C len=1 val=0 pc=0 fn=00094D98 hostfn=00094D98 lr=0 n=1\n",
            "[PT] t=980 tid=1 ev=mem kind=ppu-write addr=010D529C len=1 val=1 pc=0 fn=00094D98 hostfn=00094D98 lr=0 n=2\n",
            "[PT] t=990 tid=3 ev=mem kind=ppu-read addr=010D529C len=1 val=1 pc=0 fn=00014898 hostfn=00014898 lr=0 n=3\n",
            "[PT] t=1000 tid=1 ev=hot what=fn fn=00584C20 samples=90 pct=90.0\n",
            "[PT] t=1000 ev=fnstat fn=00584C20 entries=1 returns=0 open=1 total_us=0 max_us=0\n",
            "[PT] t=1000 ev=fnstat fn=001E8058 entries=2 returns=1 open=1 total_us=4 max_us=4\n",
        ]
        result = summarize(lines)
        self.assertIn("001E8058: entries=2 returns=1 open=1", result)
        self.assertIn("unmatched calls (entered, not returned):", result)
        self.assertIn("00584C20: last entry line 5", result)
        self.assertIn("ev=stall fn=00584C20 age_ms=5000", result)
        self.assertIn("sc 00000082 tid=24: calls=2 total_ms=26.0 max_ms=14.0", result)
        self.assertIn("tid=1 what=fn fn=00584C20 samples=90", result)
        self.assertIn("producers={'ppu-write@00094D98': 2} consumers={'ppu-read@00014898': 1}", result)
        self.assertIn("value transitions 0<-00094D98/t1 1<-00094D98/t1", result)


if __name__ == "__main__":
    unittest.main()
