import sys, site, re
sys.path.append(site.getusersitepackages())
import xlrd
from xlutils.copy import copy

D = '/home/lordvoldemort/cleanservice24/yadirect/клининговые услуги/'
SRC = D + 'import/716527410.xls'
DST = D + 'import/716527410_new.xls'

md = open(D + 'ads.md', encoding='utf-8').read().split('\n')
start = next(i for i, l in enumerate(md) if l.startswith('## 8.'))
end = next(i for i, l in enumerate(md) if l.startswith('## 9.'))
sec = md[start:end]

blocks, cur, mode = {}, None, None
for l in sec:
    m = re.match(r'\*\*(К[123])\b', l)
    if m: cur = m.group(1); blocks[cur] = {'h': [], 't': []}; continue
    if cur is None: continue
    if l.startswith('Заголовки'): mode = 'h'; continue
    if l.startswith('Тексты'): mode = 't'; continue
    m = re.match(r'\d+\.\s+(.*)', l)
    if m and mode: blocks[cur][mode].append(m.group(1).strip())

PUNCT = set('.,!?:;-—–()"«»…')
for k, v in blocks.items():
    assert len(v['h']) == 7 and len(v['t']) == 3, (k, len(v['h']), len(v['t']))
    for h in v['h']:
        assert len(h) <= 56 and max(len(w) for w in h.split()) <= 22, h
    for t in v['t']:
        p = sum(c in '.,!?:;' for c in t)
        assert len(t) <= 81 and p <= 15 and max(len(w.strip('.,!?:;—-')) for w in t.split()) <= 23, (t, len(t), p)

rb = xlrd.open_workbook(SRC, formatting_info=True)
rs = rb.sheet_by_name('Тексты')
wb = copy(rb)
ws = wb.get_sheet(rb.sheet_names().index('Тексты'))

targets = {'1927656798981618742': 'К1', '1927656798981618743': 'К2', '1927656798981618744': 'К3'}
n = 0
for r in range(11, rs.nrows):
    if rs.cell_value(r, 3) != 'Клининг услуги': continue
    k = targets[str(rs.cell_value(r, 7))]
    for i, h in enumerate(blocks[k]['h']): ws.write(r, 14 + i, h)
    for i, t in enumerate(blocks[k]['t']): ws.write(r, 21 + i, t)
    n += 1
wb.save(DST)
print('rows written:', n, '->', DST)
for k, v in blocks.items(): print(k, [len(x) for x in v['h']], [len(x) for x in v['t']])
