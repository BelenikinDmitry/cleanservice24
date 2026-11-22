import sys, site
sys.path.append(site.getusersitepackages())
import xlrd
D='/home/lordvoldemort/cleanservice24/yadirect/клининговые услуги/import/'
a=xlrd.open_workbook(D+'716527410.xls'); b=xlrd.open_workbook(D+'716527410_new.xls')
print(a.sheet_names()==b.sheet_names())
for n in a.sheet_names():
    x,y=a.sheet_by_name(n),b.sheet_by_name(n)
    diff=[(r,c) for r in range(x.nrows) for c in range(x.ncols) if x.cell(r,c).ctype!=y.cell(r,c).ctype or x.cell_value(r,c)!=y.cell_value(r,c)]
    rows=sorted({r for r,c in diff}); cols=sorted({c for r,c in diff})
    print(n,'размер',(x.nrows,x.ncols)==(y.nrows,y.ncols),'отличий',len(diff),'строки',rows[:3],'..',rows[-3:] if rows else '', 'колонки',cols)
y=b.sheet_by_name('Тексты')
for r in (133,149,150,151):
    print(r,y.cell_value(r,7),[y.cell_value(r,c) for c in (14,20,21,23)], y.cell_value(r,0))
