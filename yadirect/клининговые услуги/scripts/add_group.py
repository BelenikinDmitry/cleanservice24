"""Добавляет в копию выгрузки Директа новую группу «Заказать уборку и клининг»
по образцу группы «Клининг услуги»: фразы из keywords.txt, К1–К3 из раздела 3 ads.md."""
import sys, site, re
sys.path.append(site.getusersitepackages())
import xlrd
from xlutils.copy import copy

import argparse
ap = argparse.ArgumentParser()
ap.add_argument('--group', default='Заказать уборку и клининг')       # название новой группы
ap.add_argument('--section', default='## 3.')                         # префикс раздела в ads.md
ap.add_argument('--keywords', default='заказать уборку и клининг')   # каталог с keywords.txt
ap.add_argument('--dlink', default='заказать-уборку')                # отображаемая ссылка (≤20 знаков)
ap.add_argument('--src', default='716527410_new.xls')                # исходная выгрузка (в import/)
ap.add_argument('--dst', default='716527410_v2.xls')                 # результат (в import/), не перезаписывается без --force
ap.add_argument('--ads', default='ads.md')                           # файл с объявлениями: от D или абсолютный путь
ap.add_argument('--kwfile', default=None)                            # файл с фразами (абсолютный путь); по умолчанию <keywords>/keywords.txt
ap.add_argument('--url', default=None)                               # посадочная страница группы (по умолчанию — из шаблона)
ap.add_argument('--region', default=None)                            # регион группы (по умолчанию — из шаблона)
ap.add_argument('--exclude', default=None)                           # regex: фразы, которые не брать в группу
ap.add_argument('--template', default='Клининг услуги')                # группа-образец в выгрузке: из неё берутся изображения, ссылка, регион, организация
ap.add_argument('--force', action='store_true')
A = ap.parse_args()

D = '/home/lordvoldemort/cleanservice24/yadirect/клининговые услуги/'
SRC, DST = D + 'import/' + A.src, D + 'import/' + A.dst
GROUP, TEMPLATE, SECTION = A.group, A.template, A.section
import os
assert len(A.dlink) <= 20, 'отображаемая ссылка длиннее 20 знаков'
assert A.force or not os.path.exists(DST), DST + ' уже есть (--force, чтобы перезаписать)'

# 1. тексты К1–К3
md = open(os.path.join(D, A.ads), encoding='utf-8').read().split('\n')
s = next(i for i, l in enumerate(md) if l.startswith(SECTION))
e = next((i for i, l in enumerate(md) if l.startswith('## ') and i > s), len(md))
B, cur, mode = {}, None, None
for l in md[s:e]:
    m = re.match(r'\*\*(К[123])\b', l)
    if m: cur = m.group(1); B[cur] = {'h': [], 't': []}; continue
    if cur is None: continue
    if l.startswith('Заголовки'): mode = 'h'; continue
    if l.startswith('Тексты'): mode = 't'; continue
    m = re.match(r'\d+\.\s+(.*)', l)
    if m and mode: B[cur][mode].append(m.group(1).strip())
for k, v in B.items():
    assert len(v['h']) == 7 and len(v['t']) == 3, k
    assert all(len(h) <= 56 for h in v['h']) and all(len(t) <= 81 for t in v['t']), k

# 2. фразы
kw = [l.split('\t')[0].strip() for l in open(A.kwfile or D + A.keywords + '/keywords.txt', encoding='utf-8').read().split('\n')[1:] if l.strip()]
if A.exclude:
    dropped = [k for k in kw if re.search(A.exclude, k)]
    kw = [k for k in kw if k not in dropped]
    print('исключено фраз:', len(dropped), dropped)
assert len(kw) == len(set(kw)), 'дубли фраз'

# 3. шаблон
rb = xlrd.open_workbook(SRC, formatting_info=True)
rs = rb.sheet_by_name('Тексты')
rows = [r for r in range(11, rs.nrows) if rs.cell_value(r, 3) == TEMPLATE]
ad_ids = list(dict.fromkeys(str(rs.cell_value(r, 7)) for r in rows))
first = {a: next(r for r in rows if str(rs.cell_value(r, 7)) == a) for a in ad_ids}
assert not any(rs.cell_value(r, 3) == GROUP for r in range(11, rs.nrows)), 'группа уже есть'
group_no = str(int(max(float(rs.cell_value(r, 4)) for r in range(11, rs.nrows))) + 1)
t0 = first[ad_ids[0]]
link, dlink, org, region = (rs.cell_value(t0, c) for c in (46, 47, 49, 48))
link = A.url or link
region = A.region or region
dlink = A.dlink  # своя отображаемая ссылка группы, не из шаблона

wb = copy(rb)
ws = wb.get_sheet(rb.sheet_names().index('Тексты'))
r = rs.nrows
def put(r, ad_key, phrase, with_region):
    # '-' — основное объявление группы (с фразами), '+' — дополнительные; группа не может состоять только из '+'
    ws.write(r, 0, '-' if ad_key == 'К1' else '+'); ws.write(r, 1, 'Комбинаторное'); ws.write(r, 3, GROUP); ws.write(r, 4, group_no)
    if phrase: ws.write(r, 6, phrase)
    for i, h in enumerate(B[ad_key]['h']): ws.write(r, 14 + i, h)
    for i, t in enumerate(B[ad_key]['t']): ws.write(r, 21 + i, t)
    src = first[ad_ids[int(ad_key[1]) - 1]]
    for c in range(34, 39):
        if rs.cell_value(src, c) != '': ws.write(r, c, rs.cell_value(src, c))
    ws.write(r, 46, link); ws.write(r, 47, dlink); ws.write(r, 49, org)
    if with_region: ws.write(r, 48, region)
n = 0
for ph in kw + ['---autotargeting']:
    put(r, 'К1', ph, True); r += 1; n += 1
put(r, 'К2', None, False); r += 1
put(r, 'К3', None, False); r += 1
wb.save(DST)
print('группа №', group_no, '| строк добавлено:', r - rs.nrows, '| фраз:', len(kw), '->', DST)
