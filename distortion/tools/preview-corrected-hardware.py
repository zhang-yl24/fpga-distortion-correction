"""Label actual physical pixels, preserve native dimensions and comparison evidence."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[1]
report=json.loads((root/'results/corrected-pair-check-20261006.json').read_text())
assert report['passed']
pair=report['pairs'][-1];folder=Path(pair['directory'])
raw=Image.open(folder/'raw-source.png').convert('RGB')
corrected=Image.open(folder/'fpga-corrected.png').convert('RGB')
assert raw.size==corrected.size==(640,480) and pair['mismatched_pixels']==0
canvas=Image.new('RGB',(1280,556),'white');canvas.paste(raw,(0,48));canvas.paste(corrected,(640,48))
draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',21)
small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
draw.text((16,12),'Raw OV5640 source (same frozen frame)',fill='black',font=font)
draw.text((656,12),'Actual FPGA arithmetic remap + bilinear',fill='black',font=font)
draw.text((16,533),f"640x480 | Pair {pair['pair_id']} | All 307,200 RGB565 pixels match integer reference | Matched K, no rotation",fill='black',font=small)
out=root/'results/corrected-hardware-preview-20261006.png';canvas.save(out)
(out.with_suffix('.json')).write_text(json.dumps({'source_report':str((root/'results/corrected-pair-check-20261006.json').resolve()),
    'pair_id':pair['pair_id'],'physical_pixel_files':[str((folder/'raw-source.png').resolve()),str((folder/'fpga-corrected.png').resolve())],
    'no_geometric_or_colour_processing_applied_to_preview':True,'labels_only':True},indent=2)+'\n')
print(out.resolve())
