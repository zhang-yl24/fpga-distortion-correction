"""Verify the board-tested C closure and prepare an isolated 60 FPS candidate."""
import argparse, hashlib, importlib.util, json, re, sys
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
REPO=HERE.parents[1]
BASELINE=REPO/'delivery/20261103-hdmi-camera-fisheye-c'

def sha(data): return hashlib.sha256(data).hexdigest()

def prepare(output,tile_width=8,cache_index_bits=None,cache_profile='rowpad',ddr_fanout=False):
    output=Path(output).resolve()
    if output.exists(): raise ValueError('Choose a new output directory')
    if tile_width not in (8,32):raise ValueError('Tile width must be 8 or 32')
    if cache_index_bits not in (None,7,8,9,10):raise ValueError('Cache index bits must be 7, 8, 9 or 10')
    if cache_profile not in ('rowpad','balanced'):raise ValueError('Unknown cache profile')
    if cache_index_bits is not None:
        top_bits=bottom_bits=cache_index_bits;top_pad=bottom_pad=0
        config_name=f'uniform{cache_index_bits}';build_id=0x11036000+cache_index_bits
    elif cache_profile=='rowpad':
        top_bits,bottom_bits,top_pad,bottom_pad=10,9,1,0
        config_name='rowpad';build_id=0x11036003
    else:
        top_bits=bottom_bits=9;top_pad=bottom_pad=0
        config_name='balanced';build_id=0x11036009
    if tile_width==32:build_id+=0x100
    if ddr_fanout:build_id+=0x1000
    configuration={'name':config_name,'top_index_bits':top_bits,'bottom_index_bits':bottom_bits,
                   'top_row_padded_index':top_pad,'bottom_row_padded_index':bottom_pad,
                   'native_top_rows':640 if config_name=='rowpad' else 544,'ddr_ca_fanout16':ddr_fanout}
    sys.path.insert(0,str(BASELINE))
    import prepare_build
    baseline_receipt=prepare_build.prepare(REPO,output)
    (output/'rebuild-plan.json').rename(output/'baseline-preparation.json')
    compiled=output/'compiled'
    originals={p.name:p for p in compiled.rglob('*') if p.is_file()}
    extra=[];changes=[]
    for source in sorted((HERE/'rtl').glob('*.v')):
        target=originals.get(source.name,compiled/'rtl/experimental'/source.name)
        old=target.read_bytes() if target.exists() else None
        data=source.read_bytes()
        text=data.decode('utf-8-sig')
        def include(m):
            name=m.group(1).replace('\\','/').split('/')[-1]
            if name not in originals:raise ValueError('Unbound include '+name)
            return '`include "'+originals[name].as_posix()+'"'
        text=re.sub(r'`include\s+"([^"]+)"',include,text)
        if source.name=='hdmi_camera_fisheye_top.v':
            text=text.replace('parameter integer INPUT_TIMING_CONFIGURED=0','parameter integer INPUT_TIMING_CONFIGURED=1')
            text,count=re.subn(r"\.BUILD_ID\(32'h[0-9a-fA-F]+\)",f".BUILD_ID(32'h{build_id:08x})",text)
            assert count==1,'Build ID replacement must bind exactly once'
        if source.name=='hdmi_camera_fisheye_engine.v':
            text=text.replace('TIMEOUT_BITS=26,TILE_W=8,TILE_H=8',f'TIMEOUT_BITS=26,TILE_W={tile_width},TILE_H=8')
            text=text.replace('TOP_CACHE_INDEX_BITS=CACHE_INDEX_BITS',f'TOP_CACHE_INDEX_BITS={top_bits}')
            text=text.replace('BOTTOM_CACHE_INDEX_BITS=CACHE_INDEX_BITS',f'BOTTOM_CACHE_INDEX_BITS={bottom_bits}')
            text=text.replace('TOP_ROW_PADDED_INDEX=0',f'TOP_ROW_PADDED_INDEX={top_pad}')
            text=text.replace('BOTTOM_ROW_PADDED_INDEX=0',f'BOTTOM_ROW_PADDED_INDEX={bottom_pad}')
            text=text.replace('NATIVE_TOP_ROWS=640',f"NATIVE_TOP_ROWS={configuration['native_top_rows']}")
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(text.encode('utf-8'))
        if old is None:extra.append(target.as_posix())
        changes.append({'source':source.relative_to(HERE).as_posix(),'source_sha256':sha(data),
                        'compiled':target.relative_to(compiled).as_posix(),'baseline_sha256':sha(old) if old else None,
                        'compiled_sha256':sha(target.read_bytes())})
    fdc_source=HERE/'constraints/hdmi-camera-fisheye-60-internal.fdc'
    fdc_target=compiled/'board/hdmi-camera-fisheye-c-internal.fdc'
    old=fdc_target.read_bytes();fdc_target.write_bytes(fdc_source.read_bytes())
    changes.append({'source':fdc_source.relative_to(HERE).as_posix(),'source_sha256':sha(fdc_source.read_bytes()),
                    'compiled':fdc_target.relative_to(compiled).as_posix(),'baseline_sha256':sha(old),
                    'compiled_sha256':sha(fdc_target.read_bytes())})
    tcl=(output/'build.tcl').read_text(encoding='utf-8')
    marker='compile -top_module hdmi_camera_fisheye_top'
    assert tcl.count(marker)==1
    extra_constraints=[]
    constraint_sources=sorted((HERE/'constraints').glob('*.fdc'))
    if ddr_fanout:constraint_sources.append(HERE/'docs/optional-physical/ddr-ca-maxfan16.fdc')
    for source in constraint_sources:
        if source==fdc_source:continue
        target=compiled/'board'/source.name;target.write_bytes(source.read_bytes());extra_constraints.append(target.as_posix())
        changes.append({'source':source.relative_to(HERE).as_posix(),'source_sha256':sha(source.read_bytes()),
                        'compiled':target.relative_to(compiled).as_posix(),'baseline_sha256':None,'compiled_sha256':sha(target.read_bytes())})
    tcl=tcl.replace(marker,''.join('add_design {'+p+'}\n' for p in extra)+
                   ''.join('add_constraint {'+p+'}\n' for p in extra_constraints)+marker)
    # Summary checks still cover all endpoints; cap only the detailed path dump.
    tcl=tcl.replace('-max_path 10000','-max_path 1000')
    assert '-report_max_skew' not in tcl
    tcl,count=re.subn(r'(?m)^(report_timing[^\n]*)$',r'\1 -report_max_skew',tcl)
    assert count==1,'Exactly one timing report command is required'
    (output/'build.tcl').write_text(tcl,encoding='utf-8',newline='\n')
    files={p.relative_to(compiled).as_posix():sha(p.read_bytes()) for p in compiled.rglob('*') if p.is_file()}
    receipt={'schema':'fisheye60-candidate-v1','baseline_commit':'b3b2969','baseline_bitstream':baseline_receipt['ReleasedBitstreamSHA256'],
        'build_id':f'{build_id:08x}','profile_id':'ed59f83e3cfbc77b','tile_width':tile_width,'tile_height':8,'cache_configuration':configuration,
        'clock_hz':125000000,'output_clock':'camera input pixel clock (nominal 148.5 MHz)',
        'pnr_mode':'default',
        'source_files':files,'overlays':changes,'build_tcl_sha256':sha((output/'build.tcl').read_bytes()),
        'source_identity':sha(json.dumps(files,sort_keys=True).encode()),'hardware_tested':False,
        'baseline_timing_signoff_inherited':False,'physical_timing_verified':False}
    (output/'candidate-plan.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--tile-width',type=int,choices=(8,32),default=8)
    p.add_argument('--cache-index-bits',type=int,choices=(7,8,9,10),help='Override both lanes with a uniform linear cache')
    p.add_argument('--cache-profile',choices=('rowpad','balanced'),default='rowpad')
    p.add_argument('--ddr-fanout16',action='store_true',help='Enable the separately audited vendor CA fanout experiment')
    a=p.parse_args()
    r=prepare(a.output,a.tile_width,a.cache_index_bits,a.cache_profile,a.ddr_fanout16)
    print(json.dumps({'prepared':True,'files':len(r['source_files']),'tile_width':r['tile_width'],'identity':r['source_identity']}))
