"""Vector A4 calibration print at exact physical size; no page-fit scaling."""
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader

root=Path(__file__).resolve().parents[1]
out=root/'output/pdf';out.mkdir(parents=True,exist_ok=True)
pdf=out/'calibration-9x6-20mm-A4.pdf'
font=Path('C:/Windows/Fonts/simhei.ttf')
if font.exists():
    pdfmetrics.registerFont(TTFont('Chinese',str(font)))
else:
    raise RuntimeError('Chinese TrueType font missing; preserve source and choose an installed font.')
c=canvas.Canvas(str(pdf),pagesize=(297*mm,210*mm),pageCompression=1)
c.setTitle('FPGA camera calibration - 9x6 inner corners - 20 mm - A4')
c.setAuthor('FPGA project')
c.setFillColorRGB(0,0,0)
c.setFont('Chinese',15)
c.drawString(20*mm,195*mm,'摄像头棋盘标定板')
c.setFont('Chinese',10)
c.drawString(20*mm,187*mm,'内角点 9列 x 6行 | 方格 10列 x 7行 | 每格 20 mm | 棋盘区域 200 x 140 mm')
left,bottom=48.5*mm,35*mm
for row in range(7):
    for col in range(10):
        if (row+col)%2==0:
            c.rect(left+col*20*mm,bottom+(6-row)*20*mm,20*mm,20*mm,fill=1,stroke=0)
c.setFont('Chinese',9)
c.drawString(20*mm,20*mm,'A4横向；打印选择实际大小/100%；不缩放。固定到平整硬板，保留棋盘外围白边。')
c.drawString(20*mm,14*mm,'打印后用尺量连续五格应为100 mm；拍摄时保持完整、清晰、无反光，不遮挡内角点。')
c.setLineWidth(0.4)
c.line(left,8*mm,left+100*mm,8*mm)
for pos in (left,left+100*mm):c.line(pos,6*mm,pos,10*mm)
c.setFont('Chinese',8);c.drawString(left+103*mm,7*mm,'100 mm 比例尺')
c.showPage();c.save()
r=PdfReader(str(pdf));assert len(r.pages)==1
size=list(map(float,r.pages[0].mediabox))
assert abs(size[2]/mm-297)<0.001 and abs(size[3]/mm-210)<0.001
meta={'pdf':str(pdf),'page_mm':[297,210],'inner_corners':[9,6],'squares':[10,7],
      'square_mm':20,'pattern_mm':[200,140],'printed_pattern_must_be_flat':True,
      'outer_white_border_at_least_mm':8,'scale_bar_mm':100,
      'print_mode':'Actual size / 100 percent, no fit-to-page',
      'purchase_spec':'9x6 inner corners OR 10x7 squares, 20mm squares; flat rigid matte surface with white border. Confirm vendor count convention.',
      'source':'https://docs.opencv.org/4.13.0/da/d0d/tutorial_camera_calibration_pattern.html'}
(root/'results/calibration-board-spec-20261006.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(meta,ensure_ascii=False,indent=2))
