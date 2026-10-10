"""Fetch official public manuals; never substitutes for board example sources."""
from pathlib import Path
import urllib.request
import json
from urllib.parse import quote

def main():
    root=Path(__file__).resolve().parents[2]/'vendor'/'board'
    root.mkdir(parents=True,exist_ok=True)
    docs={
        'hardware-guide.pdf':'2025/12/教程1_硬件实验指导手册_盘古676系列100Pro开发板.pdf',
        'image-guide.pdf':'2025/12/教程3_图像实验指导手册_盘古676系列100Pro开发板.pdf',
        'fmc-guide.pdf':'2026/02/FMC扩展卡硬件指导手册.pdf'}
    records=[]
    for name,tail in docs.items():
        url='https://szlogicmatrix.com/wp-content/uploads/'+quote(tail)
        try:
            data=urllib.request.urlopen(url,timeout=25).read()
            if not data.startswith(b'%PDF-'):raise ValueError('Response is not a PDF')
            (root/name).write_bytes(data)
            records.append({'file':name,'url':url,'bytes':len(data)})
            print(f'{name}: {len(data)} bytes')
        except Exception as e:
            records.append({'file':name,'url':url,'error':str(e)})
            print(f'{name}: {e}')
    (root/'sources.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8')

if __name__=='__main__':main()
