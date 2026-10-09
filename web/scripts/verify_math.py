import fitz
doc = fitz.open(r'D:\projects\family-tutor\materials\math\math_day1.pdf')
page = doc[0]
pix = page.get_pixmap(dpi=150)
pix.save(r'D:\projects\family-tutor\materials\verify_math_day1.png')
print('done')