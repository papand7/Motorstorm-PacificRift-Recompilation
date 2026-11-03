import re, sys
for f in sys.argv[2:]:
    d = open(f, 'r', encoding='latin1').read()
    for name in sys.argv[1].split(','):
        for m in re.finditer(r'#\s*define\s+' + name + r'\b(?:[^\n]*\\\n)*[^\n]*\n', d):
            print(f[-24:], m.group(0)[:1500]); print('---')
