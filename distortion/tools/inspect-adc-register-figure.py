from pathlib import Path
import json
import subprocess
from pypdf import PdfReader
root=Path(__file__).resolve().parents[1]
doc=next((root.parent/'vendor/board').rglob('UG040009*V1.3.pdf'))
reader=PdfReader(doc)
page=next(i for i,p in enumerate(reader.pages) if '状态寄存器数据结构示意图' in p.extract_text() and 'DATA[11:0]' in p.extract_text())
out=root/'build/adc-register-figure'
subprocess.run(['pdftoppm','-f',str(page+1),'-l',str(page+1),'-r','120','-singlefile','-png',str(doc),str(out)],check=True)
(root/'build/adc-register-figure.json').write_text(json.dumps({'source':str(doc),'pdf_page':page+1,'png':str(out.with_suffix('.png'))},indent=2)+'\n')
print(json.dumps({'pdf_page':page+1,'png':str(out.with_suffix('.png'))}))
