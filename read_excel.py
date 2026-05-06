import xlrd
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

wb = xlrd.open_workbook_xls(r'C:\Users\cvecc\Desktop\opencode\meca auto\OR   vierge.xls', encoding_override='utf-8')
for sheet_name in wb.sheet_names():
    print(f'=== SHEET: {sheet_name} ===')
    sh = wb.sheet_by_name(sheet_name)
    for r in range(min(sh.nrows, 50)):
        row = []
        for c in range(min(sh.ncols, 6)):
            val = sh.cell_value(r, c)
            row.append(str(val)[:40] if val else '')
        print(f'{r}: {" | ".join(row)}')