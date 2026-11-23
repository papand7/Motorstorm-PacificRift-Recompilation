"""Condition register in a local (translator rework, 2026-11-12): a source transform of lifted PPU functions.

Inside each `void func_X(ppu_context* ctx) { ... }` the condition register lives in `auto _cr = ctx->cr;`: every
`ctx->cr` becomes `_cr`, and the context is synchronised only where something else can see it -- before and after
every call that is handed `ctx` (lifted functions, helpers, trace hooks, the trampoline drain, HLE calls) and before
every return. Within the function the compiler then sees the flags as an SSA value: a compare whose bits are never
read is dead code, and a compare followed by its branch is a compare-and-jump. No ABI assumption: every value the
context would have held at a call or exit, it holds."""
import re

FN = re.compile(r'^(void func_[0-9A-F]{8}\(ppu_context\* ctx\) \{)(.*?)^\}\n', re.M | re.S)
# a call statement with `ctx` itself (not ctx->...) among its arguments; one level of nested parentheses
CALL = re.compile(r'\b([A-Za-z_]\w*)\(((?:[^;()]|\([^;()]*\))*)\);')
KEYWORDS = {'if', 'while', 'for', 'switch', 'return', 'sizeof'}
HAS_CTX = re.compile(r'(?<![\w>.])ctx\b(?!\s*->)')


def _wrap_calls(body):
    out, pos = [], 0
    for m in CALL.finditer(body):
        name, args = m.group(1), m.group(2)
        if name in KEYWORDS or not HAS_CTX.search(args):
            continue
        # only a statement of its own: what precedes it on the line is blank or ends a statement / opens a block
        k = m.start() - 1
        while k >= 0 and body[k] in ' \t':
            k -= 1
        if k >= 0 and body[k] not in ';{}\n:':
            continue
        out.append(body[pos:m.start()])
        out.append('ctx->cr = _cr; ' + m.group(0) + ' _cr = ctx->cr;')
        pos = m.end()
    out.append(body[pos:])
    return ''.join(out)


def _one(m):
    head, body = m.group(1), m.group(2)
    body = body.replace('ctx->cr', '_cr')
    body = _wrap_calls(body)
    body = re.sub(r'(?<![\w.])return;', '{ ctx->cr = _cr; return; }', body)
    return head + ' auto _cr = ctx->cr;' + body + '    ctx->cr = _cr;\n}\n'


def cr_local(src):
    return FN.sub(_one, src)


if __name__ == '__main__':
    import sys
    t = open(sys.argv[1], encoding='latin-1').read()
    sys.stdout.write(cr_local(t))
