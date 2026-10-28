"""Generate a source-bound, self-contained raw-image inspection page; never alter captures."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import base64
import hashlib
import json
import math
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / 'build/offline-20261024'


def dimensions(width, height, rotation):
    if type(rotation) is not int or rotation not in (0, 90, 180, 270):
        raise ValueError('rotation must be integer 0/90/180/270 clockwise')
    if any(type(v) is not int or v <= 0 for v in (width, height)):
        raise ValueError('positive integer image dimensions required')
    return (height, width) if rotation in (90, 270) else (width, height)


def native_to_view(x, y, width, height, rotation=180, flip_x=False, flip_y=False):
    """Pixel-center coordinates: clockwise rotation, then flips in viewer axes."""
    vw, vh = dimensions(width, height, rotation)
    if not all(math.isfinite(v) for v in (x, y)):
        raise ValueError('finite coordinates required')
    a, b = {0: (x, y), 90: (height-1-y, x),
            180: (width-1-x, height-1-y), 270: (y, width-1-x)}[rotation]
    return (vw-1-a if flip_x else a, vh-1-b if flip_y else b)


def view_to_native(a, b, width, height, rotation=180, flip_x=False, flip_y=False):
    vw, vh = dimensions(width, height, rotation)
    if flip_x:
        a = vw-1-a
    if flip_y:
        b = vh-1-b
    return {0: (a, b), 90: (b, height-1-a),
            180: (width-1-a, height-1-b), 270: (width-1-b, a)}[rotation]


def self_test():
    # Independent raster reference, including every pixel of a non-square image.
    from PIL import Image
    w, h = 7, 5
    source = Image.new('I', (w, h)); source.putdata(list(range(w*h)))
    checks = 0
    transpose = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
                 270: Image.Transpose.ROTATE_90}
    for rotation in (0, 90, 180, 270):
        for fx in (False, True):
            for fy in (False, True):
                ref = source.transpose(transpose[rotation]) if rotation else source.copy()
                if fx:
                    ref = ref.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if fy:
                    ref = ref.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                assert ref.size == dimensions(w, h, rotation)
                for y in range(h):
                    for x in range(w):
                        a, b = native_to_view(x, y, w, h, rotation, fx, fy)
                        assert ref.getpixel((a, b)) == source.getpixel((x, y))
                        assert view_to_native(a, b, w, h, rotation, fx, fy) == (x, y)
                        checks += 1
                for x, y in ((.125, 1.875), (w-1.25, h-1.75)):
                    a, b = native_to_view(x, y, w, h, rotation, fx, fy)
                    xx, yy = view_to_native(a, b, w, h, rotation, fx, fy)
                    assert abs(xx-x) < 1e-12 and abs(yy-y) < 1e-12
    assert native_to_view(0, 0, 640, 480, 90) == (479, 0)
    assert native_to_view(0, 0, 640, 480, 180) == (639, 479)
    assert native_to_view(0, 0, 640, 480, 270) == (0, 639)
    return {'passed': True, 'raster_pixel_checks': checks, 'transform_combinations': 16,
            'fractional_roundtrips': 32, 'hardware_accessed': False}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def coverage(points, width, height):
    counts = [[0]*3 for _ in range(3)]
    for x, y in points:
        if not all(math.isfinite(v) for v in (x, y)) or not (0 <= x < width and 0 <= y < height):
            raise ValueError('QC corner outside native image')
        counts[min(2, int(y*3/height))][min(2, int(x*3/width))] += 1
    return counts


def collect(quality_path):
    quality_path = Path(quality_path).resolve(); quality = load(quality_path)
    source_hashes = {str(quality_path): sha(quality_path)}
    rows = quality['single_pose_quality_reports']
    if not 1 <= len(rows) <= 100:
        raise ValueError('expected 1..100 explicit QC views')
    images = []; totals = {split: [[0]*3 for _ in range(3)] for split in ('train', 'held_out')}
    for row in rows:
        check_path = Path(row['check_path']); check = load(check_path)
        if sha(check_path) != row['check_sha256'].lower():
            raise ValueError('QC file hash changed')
        png_path = Path(check['image_path']); png = png_path.read_bytes()
        meta_path = Path(check['metadata_path']); meta = load(meta_path)
        raw_path = Path(check['capture_pixel_binding']['raw_path']); raw = raw_path.read_bytes()
        for path, expected in ((png_path, check['image_sha256']), (meta_path, check['metadata_sha256']),
                               (raw_path, check['capture_pixel_binding']['raw_sha256'])):
            actual = sha(path)
            if actual != expected.lower():
                raise ValueError('capture/QC source hash changed: '+str(path))
            source_hashes[str(path)] = actual
        source_hashes[str(check_path)] = sha(check_path)
        width, height = check['image_size']; dimensions(width, height, 0)
        if (png[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack_from('>II', png, 16) != (width, height)
                or len(raw) != width*height*2 or f'{zlib.crc32(raw):08X}' != meta['source_crc32'].upper()
                or meta['identity_binding'] != check['identity_binding']):
            raise ValueError('capture geometry/CRC/identity binding differs')
        points = check['corners']; counts = coverage(points, width, height)
        if (len(points) != row['corner_count'] or counts != row['coverage']
                or counts != check['source_image_3x3_corner_counts']):
            raise ValueError('QC corners and native coverage differ')
        split = row['split']
        if split not in totals:
            raise ValueError('explicit train/held_out split required')
        if row['selected']:
            for y in range(3):
                for x in range(3):
                    totals[split][y][x] += counts[y][x]
        images.append({'pose': row['pose_id'], 'split': split, 'selected': row['selected'],
            'complete': row['complete88'], 'corner_count': len(points), 'corners': points,
            'width': width, 'height': height, 'coverage': counts,
            'warnings': row['warnings'], 'exclusion': row['exclusion'],
            'filename': png_path.name, 'image_path': str(png_path), 'raw_path': str(raw_path),
            'metadata_path': str(meta_path), 'image_sha256': sha(png_path), 'raw_sha256': sha(raw_path),
            'source_crc32': meta['source_crc32'], 'identity': check['identity_binding'],
            'image': 'data:image/png;base64,'+base64.b64encode(png).decode('ascii')})
    if totals != quality['source_image_3x3_corner_counts']:
        raise ValueError('selected-view coverage does not match quality report')
    return {'images': images, 'totals': totals,
        'required': {'train': quality['required_training_corners_per_cell'],
                     'held_out': quality['required_held_out_corners_per_cell']},
        'quality_path': str(quality_path), 'quality_sha256': sha(quality_path),
        'source_sha256': source_hashes, 'orientation_status': 'operator_unconfirmed',
        'default_rotation_clockwise_deg': 180, 'orientation_reason': 'User described the original preview as upside down; physical orientation has not been confirmed.',
        'hardware_accessed': False, 'raw_or_metadata_modified': False}


HTML = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>原始帧方向与覆盖预览</title><style>
:root{color:#000;background:#e8edf2;font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif;font-size:15px}*{box-sizing:border-box}body{margin:0}button,input,select{font:inherit;color:#000}button,select{background:#fff;border:1px solid #000;padding:7px 12px;cursor:pointer}button:hover{background:#e1efff}button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #0054a5;outline-offset:3px}h1{font-size:26px;line-height:1.25;margin:0 0 8px}h2{font-size:16px;margin:0 0 8px}p{line-height:1.55;margin:6px 0}header{background:#fff;padding:20px 24px;border-bottom:2px solid #000}header p{max-width:1000px}.orientation{background:#ffe6ac;border-left:5px solid #000;padding:8px 12px;margin-top:12px;max-width:1000px}.layout{display:grid;grid-template-columns:minmax(300px,1fr) 320px;gap:16px;max-width:1450px;padding:16px;margin:auto}.stage{min-width:0}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;background:#fff;padding:12px}.toolbar label{display:flex;gap:5px;align-items:center}.viewer{background:#000;min-height:300px;display:flex;align-items:center;justify-content:center;padding:10px}canvas{max-width:100%;max-height:66vh;width:auto;height:auto;display:block;cursor:crosshair;touch-action:manipulation}.readout{background:#fff;padding:10px 12px;min-height:66px}.readout code{font-family:Consolas,monospace;font-size:13px;white-space:normal}.fileline{overflow-wrap:anywhere}.sidebar{background:#fff;padding:16px;align-self:start}.sidebar section+section{border-top:1px solid #000;margin-top:16px;padding-top:16px}.quality{border-left:5px solid #0054a5;padding-left:10px}.quality.excluded{border-color:#b65400}.small{font-size:12px;line-height:1.55}.coverage{display:grid;grid-template-columns:repeat(3,1fr);gap:4px;margin:7px 0}.coverage div{border:1px solid #000;text-align:center;padding:6px 2px;line-height:1.35}.coverage .missing{background:#ffe6ac}.coverage .enough{background:#e1efff}.coverage span{display:block;font-size:11px}.filmstrip{grid-column:1/-1;display:grid;grid-template-columns:repeat(auto-fill,minmax(112px,1fr));gap:8px}.thumb{padding:4px;text-align:left}.thumb img{display:block;width:100%;height:80px;object-fit:contain;background:#000}.thumb span{display:block;font-size:12px;margin:4px 2px}.thumb[aria-current=true]{outline:3px solid #0054a5;outline-offset:1px}.hash{word-break:break-all;font-family:Consolas,monospace;font-size:11px}details{margin:10px 0}summary{cursor:pointer}#viewtitle{font-size:20px;margin:0 0 5px}#message{min-height:22px;font-weight:700}footer{padding:0 24px 24px;max-width:1450px;margin:auto;font-size:12px}@media(max-width:850px){.layout{grid-template-columns:1fr;padding:8px}.sidebar{grid-row:auto}canvas{max-height:65vh}header{padding:16px}.filmstrip{grid-template-columns:repeat(auto-fill,minmax(96px,1fr))}}@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style></head><body>
<header><h1>先看对方向，再看棋盘位置</h1><p>这是一份已有原始帧的静态预览。旋转和镜像只作用于显示层，raw、PNG、元数据、CRC 和标定坐标均保持原样。</p><div class="orientation">默认顺时针旋转 180°：依据操作者“原图倒置”的描述，方向尚未实物确认（operator_unconfirmed）。屏幕上方不等同于物理上方。</div></header>
<main class="layout"><div class="stage"><div class="toolbar">
<button id="prev" aria-label="上一张">上一张</button><button id="next" aria-label="下一张">下一张</button>
<label>顺时针旋转 <select id="rotation"><option value="0">0° 原图方向</option><option value="90">90°</option><option value="180" selected>180° 显示默认</option><option value="270">270°</option></select></label>
<label><input id="flipx" type="checkbox">显示左右镜像</label><label><input id="flipy" type="checkbox">显示上下镜像</label>
<label><input id="grid" type="checkbox" checked>3×3 格</label><label><input id="corners" type="checkbox" checked>角点</label><button id="native">查看原图</button>
</div><div class="viewer"><canvas id="canvas" width="640" height="480" aria-label="原始图像的显示层预览，叠加已有角点与九宫格"></canvas></div>
<div class="readout"><p id="cursor">移动指针或点击九宫格，可同时查看原生坐标与显示坐标。</p><p class="small" id="mapping"></p><p id="message" aria-live="polite"></p></div></div>
<aside class="sidebar"><section><h2 id="viewtitle"></h2><p id="position"></p><p id="quality" class="quality"></p><p id="warning" class="small"></p><p id="filename" class="small fileline"></p></section>
<section><h2>已选训练图：角点覆盖</h2><p id="trainnote" class="small"></p><div id="traincoverage" class="coverage"></div><p id="trainmissing" class="small"></p></section>
<section><h2>已选留出图：角点覆盖</h2><p id="heldnote" class="small"></p><div id="heldcoverage" class="coverage"></div><p id="heldmissing" class="small"></p></section>
<section><h2>显示坐标与原始坐标</h2><p class="small">九宫格和覆盖数随当前显示方向一起旋转。鼠标读数始终同时给出 native 与 viewer 坐标，native 从原图左上像素中心 (0,0) 开始。</p><p class="small">橙色格表示现有数据的角点数量未达原质量报告门槛。镜像/旋转不会补足缺格，也不证明新姿态、平整度或标定有效。</p><details><summary>文件与完整性</summary><div id="integrity" class="small"></div></details></section></aside>
<nav id="filmstrip" class="filmstrip" aria-label="已有原始帧列表"></nav></main>
<footer>无相机连接、无自动采集、无标定结果生成。所有朝向均为显示选择；此页不声明真实物理朝向或标定完成。左右箭头可切换图片。</footer>
<script id="dataset" type="application/json">__DATA__</script>
<script>
'use strict';
const D=JSON.parse(document.getElementById('dataset').textContent),$=id=>document.getElementById(id),C=$('canvas'),ctx=C.getContext('2d');
let index=0,loadToken=0,img=null;
function geometry(){const f=D.images[index],r=Number($('rotation').value);return {w:f.width,h:f.height,r,fx:$('flipx').checked,fy:$('flipy').checked,vw:(r%180?f.height:f.width),vh:(r%180?f.width:f.height)};}
function forward(x,y,g){let a,b;if(g.r===0){a=x;b=y}else if(g.r===90){a=g.h-1-y;b=x}else if(g.r===180){a=g.w-1-x;b=g.h-1-y}else{a=y;b=g.w-1-x}return [g.fx?g.vw-1-a:a,g.fy?g.vh-1-b:b];}
function inverse(a,b,g){if(g.fx)a=g.vw-1-a;if(g.fy)b=g.vh-1-b;if(g.r===0)return[a,b];if(g.r===90)return[b,g.h-1-a];if(g.r===180)return[g.w-1-a,g.h-1-b];return[g.w-1-b,a];}
function viewCellNative(row,col,g){const [x,y]=inverse((col+.5)*g.vw/3-.5,(row+.5)*g.vh/3-.5,g);return [Math.min(2,Math.floor((y+.5)*3/g.h)),Math.min(2,Math.floor((x+.5)*3/g.w))];}
function cellName(y,x){return ['上','中','下'][y]+['左','中','右'][x];}
function coverPanel(split,prefix,g){const table=D.totals[split],need=D.required[split],box=$(prefix+'coverage');box.replaceChildren();let missing=[];
 for(let y=0;y<3;y++)for(let x=0;x<3;x++){const [ny,nx]=viewCellNative(y,x,g),count=table[ny][nx],cell=document.createElement('div');cell.className=count<need?'missing':'enough';cell.textContent=String(count);const label=document.createElement('span');label.textContent='原图 '+cellName(ny,nx);cell.append(label);box.append(cell);if(count<need)missing.push(cellName(y,x));}
 $(prefix+'note').textContent='按当前显示方向排列；每格门槛 '+need+' 个角点。';$(prefix+'missing').textContent='显示坐标缺格：'+(missing.length?missing.join('、'):'无数量缺格（不等于标定通过）');}
function label(text,x,y){ctx.font='12px Arial';const m=ctx.measureText(text);ctx.fillStyle='rgba(255,255,255,.90)';ctx.fillRect(x-4,y-13,m.width+8,18);ctx.fillStyle='#000';ctx.fillText(text,x,y);}
function render(){if(!img)return;const g=geometry(),f=D.images[index];C.width=g.vw;C.height=g.vh;ctx.setTransform(1,0,0,1,0,0);ctx.fillStyle='#000';ctx.fillRect(0,0,C.width,C.height);
 ctx.save();ctx.translate(g.vw/2,g.vh/2);ctx.scale(g.fx?-1:1,g.fy?-1:1);ctx.rotate(g.r*Math.PI/180);ctx.drawImage(img,-g.w/2,-g.h/2);ctx.restore();
 if($('grid').checked){for(let i=1;i<3;i++){ctx.beginPath();ctx.moveTo(g.vw*i/3,0);ctx.lineTo(g.vw*i/3,g.vh);ctx.moveTo(0,g.vh*i/3);ctx.lineTo(g.vw,g.vh*i/3);ctx.strokeStyle='#000';ctx.lineWidth=3;ctx.stroke();ctx.strokeStyle='#fff';ctx.lineWidth=1;ctx.stroke();}
 for(let y=0;y<3;y++)for(let x=0;x<3;x++){const [ny,nx]=viewCellNative(y,x,g);label('native '+['T','M','B'][ny]+['L','C','R'][nx],x*g.vw/3+9,y*g.vh/3+19);}}
 if($('corners').checked){for(const [x,y]of f.corners){const [a,b]=forward(x,y,g);ctx.beginPath();ctx.arc(a+.5,b+.5,2.3,0,2*Math.PI);ctx.fillStyle='#00d4e8';ctx.fill();ctx.lineWidth=.8;ctx.strokeStyle='#000';ctx.stroke();}}
 $('mapping').textContent='native '+g.w+'×'+g.h+' → 顺时针 '+g.r+'° → 显示轴镜像 X:'+g.fx+' Y:'+g.fy+' → viewer '+g.vw+'×'+g.vh+'；旋转/镜像只影响显示。';
 coverPanel('train','train',g);coverPanel('held_out','held',g);$('cursor').textContent='移动指针可读坐标；点击一个目标格可固定显示该格中心的两套坐标。';}
function coord(a,b,clicked){const g=geometry(),[x,y]=inverse(a,b,g),ny=Math.max(0,Math.min(2,Math.floor(y*3/g.h))),nx=Math.max(0,Math.min(2,Math.floor(x*3/g.w)));$('cursor').textContent='viewer ('+a.toFixed(1)+', '+b.toFixed(1)+') ↔ native ('+x.toFixed(1)+', '+y.toFixed(1)+') · 原图格 '+cellName(ny,nx)+(clicked?' · 仅显示目标，未发采集命令':'');}
C.addEventListener('pointermove',e=>{const b=C.getBoundingClientRect();coord((e.clientX-b.left)*C.width/b.width-.5,(e.clientY-b.top)*C.height/b.height-.5,false)});
C.addEventListener('click',e=>{const b=C.getBoundingClientRect(),col=Math.max(0,Math.min(2,Math.floor((e.clientX-b.left)*3/b.width))),row=Math.max(0,Math.min(2,Math.floor((e.clientY-b.top)*3/b.height)));coord((col+.5)*C.width/3-.5,(row+.5)*C.height/3-.5,true);});
function appendText(parent,text,cls){const p=document.createElement('p');p.textContent=text;if(cls)p.className=cls;parent.append(p);}
function select(i){index=(i+D.images.length)%D.images.length;const f=D.images[index],short=f.pose.split('-').pop(),token=++loadToken;img=null;$('viewtitle').textContent=short+' / '+(f.split==='train'?'训练候选':'留出候选');$('position').textContent=(index+1)+' / '+D.images.length+' · 原始帧 '+f.width+'×'+f.height;
 $('quality').className='quality'+(f.selected?'':' excluded');$('quality').textContent='检出 '+f.corner_count+'/88 角点 · '+(f.selected?'原质量报告已选':'原质量报告排除');$('warning').textContent=[f.exclusion,...f.warnings].filter(Boolean).join(' ');$('filename').textContent=f.filename;
 const box=$('integrity');box.replaceChildren();appendText(box,'CRC32 '+f.source_crc32);appendText(box,'原 PNG：'+f.image_path);appendText(box,'raw：'+f.raw_path);appendText(box,'元数据：'+f.metadata_path);appendText(box,'raw SHA256 '+f.raw_sha256,'hash');appendText(box,'镜头声明 '+f.identity.lens_id);appendText(box,'质量报告 SHA256 '+D.quality_sha256,'hash');
 document.querySelectorAll('.thumb').forEach((b,j)=>b.setAttribute('aria-current',String(j===index)));const image=new Image();image.onload=()=>{if(token!==loadToken)return;img=image;render();$('message').textContent=''};image.onerror=()=>{$('message').textContent='嵌入图片未能解码，请核对来源后重新生成预览。'};image.src=f.image;}
$('prev').onclick=()=>select(index-1);$('next').onclick=()=>select(index+1);for(const id of ['rotation','flipx','flipy','grid','corners'])$(id).onchange=render;
$('native').onclick=()=>{$('rotation').value='0';$('flipx').checked=false;$('flipy').checked=false;render()};
document.addEventListener('keydown',e=>{if(['INPUT','SELECT'].includes(document.activeElement.tagName))return;if(e.key==='ArrowLeft')select(index-1);if(e.key==='ArrowRight')select(index+1)});
D.images.forEach((f,i)=>{const b=document.createElement('button');b.className='thumb';b.title=f.pose;const image=document.createElement('img');image.src=f.image;image.alt=f.pose+' 原图方向缩略图';image.loading='lazy';const s=document.createElement('span');s.textContent=f.pose.split('-').pop()+' · '+f.corner_count+'/88'+(f.selected?'':' · 排除');b.append(image,s);b.onclick=()=>select(i);$('filmstrip').append(b)});
// Public pure coordinate functions support offline directed parity checks.
window.rawPreviewTransforms={forward,inverse,viewCellNative};select(0);
</script></body></html>'''


def build(quality_path, output):
    output = Path(output).resolve(); proof = output.with_suffix('.source-proof.json')
    if (not output.parent.is_dir() or not output.is_relative_to(APPROVED.resolve())
            or output.suffix.lower() != '.html' or output.exists() or proof.exists()):
        raise ValueError('fresh HTML in an existing approved scratch directory required')
    tests = self_test(); data = collect(quality_path)
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    with output.open('x', encoding='utf-8') as f:
        f.write(HTML.replace('__DATA__', encoded))
    unchanged = all(sha(path) == expected for path, expected in data['source_sha256'].items())
    if not unchanged:
        raise ValueError('source files changed while generating preview')
    report = {'schema': 1, 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'html': str(output), 'html_sha256': sha(output), 'tool_sha256': sha(__file__),
        'quality_path': data['quality_path'], 'quality_sha256': data['quality_sha256'],
        'image_count': len(data['images']), 'source_file_count': len(data['source_sha256']),
        'source_sha256': data['source_sha256'], 'all_sources_unchanged': unchanged,
        'default_rotation_clockwise_deg': 180, 'orientation_status': 'operator_unconfirmed',
        'rotation_order': 'clockwise_rotation_then_viewer_axis_flips', 'coordinate_origin': 'native_top_left_pixel_center_0_0',
        'self_test': tests, 'hardware_accessed': False, 'raw_or_metadata_modified': False,
        'calibration_generated': False, 'limits': 'Static derived preview only; orientation is a display choice, not physical confirmation. Missing coverage and dataset acceptance remain unchanged.'}
    with proof.open('x', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')
    return {k: v for k, v in report.items() if k != 'source_sha256'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quality'); parser.add_argument('--output'); parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(self_test(), indent=2)); return 0
    if not args.quality or not args.output:
        parser.error('--quality and --output are required')
    print(json.dumps(build(args.quality, args.output), ensure_ascii=False, indent=2)); return 0


if __name__ == '__main__':
    raise SystemExit(main())
