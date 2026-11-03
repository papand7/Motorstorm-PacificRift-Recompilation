import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
n = s.count('\x08')
s = s.replace('\x08', '\\b')
open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('replaced', n)
