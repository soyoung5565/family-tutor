import fitz
for day in ['day2', 'day3', 'day4']:
    doc = fitz.open(f'D:/projects/family-tutor/materials/math/math_{day}.pdf')
    page = doc[0]
    pix = page.get_pixmap(dpi=150)
    pix.save(f'D:/projects/family-tutor/materials/verify_math_{day}.png')
    print(f'done {day}')