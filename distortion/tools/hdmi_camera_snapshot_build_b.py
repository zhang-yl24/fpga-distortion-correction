"""Freeze/build an independent RGB888 direct-display diagnostic; no hardware.

Only eleven RTL files plus a new70-pin FDC are compiled. Configuration sources
are byte-identical to the validated raw v2 baseline; there is no DDR or video PLL. The source-bound snapshot adds one immutable
BRAM bank and a TX-only PGFRAME1 grayscale packet stream.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

import audit_board1080_pin_contract as pins
import prepare_board1080_timing as paths
import run_camera_vga_output_diagnostic as cleanup
import hdmi_raw_status as raw_status

ROOT=Path(__file__).resolve().parents[1]
SELF=Path(__file__).resolve()
WORK=ROOT/'work/hdmi-camera-snapshot-20261102-a'
RAW_WORK=ROOT/'work/hdmi-camera1080-raw-20261102-a'
TARGET='hdmi_camera_snapshot_top'
TOP='board/'+TARGET+'.v'
SAMPLER='rtl/experimental/hdmi_camera_pixel_sampler.v'
FDC='board/hdmi-camera-snapshot-b-internal.fdc'
MANIFEST='board/hdmi-camera-snapshot-b-build-sources.json'
SCHEMA='hdmi-camera-snapshot-build-v1'
MANIFEST_SCHEMA='hdmi-camera-snapshot-source-closure-v1'
BASE_FDC='board/board1080-checked-i2c.fdc'
BASE_FDC_SHA='4fd34ebc9d39642e2539610211fe20778971bf9870b53e8f479bcf164c3cf37c'
REARM_PLAN=RAW_WORK/'build-d/plan.json'
PROFILE=RAW_WORK/'input-timing-profile-v2-a.json'
CFG_PLL='platform/video_base/ipcore/cfg_pll/cfg_pll.v'
RETAINED=('rtl/experimental/ms72xx_rearm_observed_ctl.v',
    'rtl/experimental/ms7200_1080p30_rearm_ctl.v','rtl/experimental/ms7210_checked_ctl.v',
    'rtl/experimental/iic_dri_checked.v',CFG_PLL)
CAPTURE='rtl/experimental/hdmi_camera_snapshot_capture.v'
RAM='rtl/experimental/hdmi_camera_snapshot_ram.v'
REF='rtl/experimental/hdmi_camera_snapshot_ref.v'
UART='rtl/uart_tx.v'
SOURCES=(TOP,SAMPLER,*RETAINED,CAPTURE,RAM,REF,UART)
DIRECT_PLAN=ROOT/'work/direct-20261102-a/build-a/plan.json'
DIRECT_TOP='board/hdmi_camera_direct_top.v'
UART_FDC='board/bringup.fdc'
GTP_MODEL=Path('D:/pango/PDS_2023.2/arch/vendor/pango/verilog/simulation/GTP_DRM18K_E1.v')
NATIVE_MODEL=Path('D:/pango/PDS_2023.2/arch/vendor/pango/verilog/bsim/V_DRM18K_E1.v')
STAGES=['Compile','Synthesize','Device Map','Place','Route','Route Optimize','Report Timing']
EVIDENCE_NOTE=ROOT.parent/'handoff/HDMI_CAMERA_DIRECT_20261102.md'
TX_DATASHEET=ROOT.parent/'vendor/board/盘古100Pro+开发板（MES2L676-100HP）配套资料/4_IC_datasheet/HDMI PHY/《MS7210 Datasheet-CN》-sp(1).pdf'
TX_DATASHEET_SHA='2e9ea30aaf970a5b53a6f9d71185959a8145df45f1ef0d516b77e13f6c5d25f3'
TX_REFERENCE=ROOT.parent/'vendor/reference/video/4_12_HDMI_IN_DDR3_HDMI_OUT/4_12_HDMI_IN_DDR3_HDMI_OUT/5_12_HDMI_IN_DDR3_HDMI_OUT/source/hdmi/ms7210_ctl.v'
TX_REFERENCE_SHA='c9b101e58f381ddf3c6d663d0003c18065302659424b8345022161413ccf09ae'
TX_REFERENCE_TOP=TX_REFERENCE.parent.parent/'rtl/HDMI_IN_DDR3_HDMI_OUT_top.v'
TX_REFERENCE_TOP_SHA='ca0d180208c8eca76f24b53aced44fe03d7bc9d8a28f39d622e220694dfb56a6'
sha=paths.sha


def require(ok,message):
    if not ok:raise ValueError(message)


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def utc():return datetime.now(timezone.utc).isoformat()
def digest(data):return hashlib.sha256(data).hexdigest()
def ref(path):return {'Path':str(Path(path).resolve()),'SHA256':sha(path)}


def write(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n')as out:
        json.dump(value,out,indent=2,allow_nan=False);out.write('\n')


def add(watched,path,expected=None):
    path=Path(path).absolute();require(path==path.resolve()and path.is_file(),'canonical snapshot input required: '+str(path))
    actual=sha(path);require(expected is None or actual==expected,'snapshot input SHA differs: '+str(path))
    require(str(path)not in watched or watched[str(path)]==actual,'conflicting snapshot input SHA')
    watched[str(path)]=actual;return path


def work_path(value):
    path=Path(value).absolute();require(path==path.resolve()and path.parent==WORK.resolve()
        and re.fullmatch(r'[A-Za-z0-9_-]+',path.name),'canonical snapshot work child required')
    return path


def top_ports(text):
    text,count=re.subn(r'\bmodule\s+'+TARGET+r'\s*#\(.*?\)\s*\(','module board1080_top(',text,count=1,flags=re.S)
    require(count==1,'one parameterized snapshot top required');return pins.top_ports(text)


def render_constraints(base_text,top_text):
    actual=top_ports(top_text);old=pins.fdc_pins(base_text)
    uart=pins.fdc_pins((ROOT/UART_FDC).read_text(encoding='ascii'))['uart_txd']
    old={**old,'uart_txd':{**uart,'DIRECTION':'OUTPUT'}}
    require(len(actual)==70 and set(actual)<=set(old),'exact70 snapshot pins must come from checked board and prior UART')
    require(len({old[n]['LOC']for n in actual})==70 and all(old[n]['DIRECTION']==d for n,d in actual.items()),
            'snapshot pin location/direction differs')
    physical=[]
    for line in base_text.splitlines():
        match=re.fullmatch(r'define_attribute \{p:([^}]+)\} \{PAP_IO_(\w+)\} \{([^}]+)\}',line)
        if match and match[1]in actual:physical.append(line)
    physical.append('define_attribute {p:uart_txd} {PAP_IO_DIRECTION} {OUTPUT}')
    physical.extend(line for line in (ROOT/UART_FDC).read_text(encoding='ascii').splitlines() if line.startswith('define_attribute {p:uart_txd} '))
    clocks=['create_clock -name board27 -period 37.037037 [get_ports clk_27m]',
        'create_clock -name input_pixel -period 6.6667 [get_ports pixclk_in]',
        'create_generated_clock -name pixel_clk -source [get_ports pixclk_in] -divide_by 1 [get_ports pix_clk]',
        'create_generated_clock -name cfg_clk -source [get_ports clk_27m] -multiply_by 10 -divide_by 27 [get_pins configuration_pll/clkout0]']
    text=('# Independent RGB888 snapshot diagnostic; input-clock forwarding, no video PLL/DDR.\n'
        '#150MHz envelope; source phase, RGB format, board skew and external AC are unaccepted.\n'
        '# No inherited CDC/reset/multicycle exception.\n'+'\n'.join(clocks+physical)+'\n')
    attributes=pins.fdc_pins(text)
    require(attributes=={n:old[n]for n in actual},'snapshot pin attributes were lost')
    return text,{'TopPortCount':70,'PinInventory':attributes,'DeclaredPinsAndElectricalPreserved':True,
        'NativePinMappingVerified':False,'NativeElectricalParametersVerified':False,
        'All27InputBitsHaveBusinessConsumersRequired':True,'ExternalACAccepted':False}


def evidence(watched):
    add(watched,TX_DATASHEET,TX_DATASHEET_SHA);add(watched,TX_REFERENCE,TX_REFERENCE_SHA);add(watched,EVIDENCE_NOTE)
    add(watched,TX_REFERENCE_TOP,TX_REFERENCE_TOP_SHA)
    expression=r"6'd(\d+)\s*:\s*cmd_data\s*=\s*\{16'h([0-9a-fA-F]+),8'h([0-9a-fA-F]+)\}"
    original=re.findall(expression,TX_REFERENCE.read_text(encoding='utf-8-sig'))
    checked=re.findall(expression,(ROOT/RETAINED[2]).read_text(encoding='utf-8-sig'))
    require(len(original)==49 and original==checked,'checked TX49 commands differ from official148.5MHz example')
    return {'Note':ref(EVIDENCE_NOTE),'OfficialTXDatasheet':ref(TX_DATASHEET),
        'OfficialTXReference':ref(TX_REFERENCE),'OfficialTXExampleTop':ref(TX_REFERENCE_TOP),
        'TXCommandCount':49,'TXCommandsAddressValueOrderIdentical':True,
        'TXSupportsRGB44424BitSDR148_5MHzPerTable':True,'ActualRegisterSamplingEdgeVerified':False,
        'ActualRGBFormatVerified':False,'ExternalACAccepted':False}


def direct_display_binding():
    baseline=read(DIRECT_PLAN);require(baseline.get('Target')=='hdmi_camera_direct_top',
        'actual accepted direct source plan required')
    sources=[r for r in baseline['CompiledInputs'] if r['Source']==DIRECT_TOP]
    require(len(sources)==1 and sources[0]['OriginalSHA256']==sha(ROOT/DIRECT_TOP),
        'direct display source drift')
    original=(ROOT/DIRECT_TOP).read_text(encoding='utf-8-sig')
    expected=original.replace('module hdmi_camera_direct_top #(','module hdmi_camera_snapshot_top #(',1)
    expected=expected.replace('    output rstn_out,output [7:0] led',
        '    output rstn_out,output [7:0] led,output uart_txd',1)
    new=(ROOT/TOP).read_text(encoding='utf-8-sig');marker='\n    // Independent snapshot branch;'
    require(new.count(marker)==1 and new.split(marker)[0]==expected.rsplit('endmodule',1)[0],
        'snapshot changes the validated direct display body')
    return {'Original':ref(ROOT/DIRECT_TOP),'DirectBuildPlan':ref(DIRECT_PLAN),
        'OriginalDisplayBodyPreserved':True,'OnlyTopNameUARTPortAndSnapshotBranchAdded':True,
        'PriorPhysicalProofCountsInherited':False}


def snapshot_contract():
    return {'Protocol':'PGFRAME1','HeaderBytes':32,'TrailerMagic':'PGEND001','TrailerBytes':12,
        'Format':0x3859,'CaptureWidth':960,'CaptureHeight':540,'PayloadBytes':518400,
        'NativeWidth':1920,'NativeHeight':1080,'Step':[2,2],'OriginHalf':[1,1],
        'GrayFormula':'(R+2*G+B)>>2','BoxFormula':'sum(four truncated gray8 pixels)>>2',
        'SingleFrozenBank':True,'NextRequestOnlyAfterFinalUARTByteDone':True,'UARTBaud':921600,
        'DeclaredSnapshotBytes':1<<19,'Declared18KHalves':256,'Equivalent36KBlocks':128,
        'Device36KBlocks':155,'ActualMappedResourceReviewRequired':True,'DDRIncluded':False}


def expected_manifest(fdc_bytes=None):
    require(sha(ROOT/BASE_FDC)==BASE_FDC_SHA,'checked electrical baseline changed')
    fdc,pin_review=render_constraints((ROOT/BASE_FDC).read_text(encoding='ascii'),(ROOT/TOP).read_text(encoding='utf-8-sig'))
    if fdc_bytes is not None:require(fdc_bytes==fdc.encode('ascii'),'snapshot FDC creation differs')
    else:require((ROOT/FDC).read_bytes()==fdc.encode('ascii'),'snapshot FDC differs from exact derivation')
    direct_display_binding()
    rearm=read(REARM_PLAN);refs=[];hashes={}
    require(rearm.get('Schema')=='hdmi-camera-raw-build-v1' and rearm.get('Target')=='hdmi_camera_raw_diag',
            'raw v2 configuration source reference required')
    for name in SOURCES:
        data=(ROOT/name).read_bytes();require(b'`include'not in data,'unbound include in snapshot closure')
        hashes[name]=sha(ROOT/name)
        if name in RETAINED:
            frozen=REARM_PLAN.parent/'frozen-inputs'/name
            require(hashes[name]==sha(frozen)==rearm['PreparedSHA256'][str(frozen.resolve())],
                    'retained configuration source differs from raw v2: '+name)
            refs.append(ref(frozen))
    hashes[FDC]=digest(fdc.encode('ascii'));profile,_=profile_binding();proof=evidence({})
    return {'Schema':MANIFEST_SCHEMA,'Target':TARGET,'source_files':[*SOURCES,FDC],
        'SourceSHA256':hashes,'Constraint':FDC,'RearmReferencePlan':ref(REARM_PLAN),
        'RetainedRearmFrozenSources':refs,'InputTiming':profile,'OfficialTXEvidence':proof,
        'TopPortCount':pin_review['TopPortCount'],'InputPixelPeriodNS':6.6667,'OutputClockForwarded':True,
        'ConfigurationMHz':10.0,'DDRIncluded':False,'UARTIncluded':True,'SnapshotsIncluded':True,
        'VideoPLLIncluded':False,'TimingExceptionsInherited':False,
        'SnapshotContract':snapshot_contract(),'DirectDisplaySource':ref(ROOT/DIRECT_TOP),'DirectBuildPlan':ref(DIRECT_PLAN),
        'FrozenTopParameterOverride':{'Parameter':'INPUT_TIMING_CONFIGURED','Original':0,'Compiled':1},
        'HardwareAccessed':False,'HardwareReleaseAllowed':False,'ExternalACAccepted':False}


def write_manifest():
    require(not(ROOT/MANIFEST).exists()and not(ROOT/FDC).exists(),'fresh snapshot manifest and FDC required')
    data,_=render_constraints((ROOT/BASE_FDC).read_text(encoding='ascii'),(ROOT/TOP).read_text(encoding='utf-8-sig'))
    value=expected_manifest(data.encode('ascii'));(ROOT/FDC).write_bytes(data.encode('ascii'));write(ROOT/MANIFEST,value)
    return ROOT/MANIFEST


def compiled_source(name,data,work,alias):
    changes=[]
    if name==TOP:
        expression=rb'(parameter[ \t]+integer[ \t]+INPUT_TIMING_CONFIGURED[ \t]*=[ \t]*)0(?=[ \t]*[,\r\n])'
        require(len(re.findall(expression,data))==1,'one unconfigured snapshot top default required')
        data,count=re.subn(expression,rb'\g<1>1',data,count=1)
        changes=[{'Kind':'SelectedDigitalTimingOnly','Parameter':'INPUT_TIMING_CONFIGURED','Original':0,
            'Compiled':1,'ReplacementCount':count,'RGBPixelsVerified':False,'CapturePhaseVerified':False,'ExternalACAccepted':False}]
    return data,changes


def pll_clocks():
    text=(ROOT/CFG_PLL).read_text(encoding='utf-8');values={}
    for key in ('CLKIN_FREQ','STATIC_RATIOI','STATIC_RATIOM','STATIC_RATIO0','STATIC_RATIOF'):
        matches=re.findall(r'localparam\s+(?:real|integer)\s+'+key+r'\s*=\s*([0-9.]+)\s*;',text)
        require(len(matches)==1,'ambiguous configuration PLL ratio');values[key]=float(matches[0])
    mhz=values['CLKIN_FREQ']*values['STATIC_RATIOM']*values['STATIC_RATIOF']/values['STATIC_RATIOI']/values['STATIC_RATIO0']
    require(values['CLKIN_FREQ']==27.0 and abs(mhz-10.0)<1e-9,'configuration PLL must output10MHz')
    return [{'Source':CFG_PLL,'Parameters':values,'ComputedOutputMHz':mhz}]


def render_tcl(work,alias):
    compiled=lambda n:paths.tcl_path(paths.alias_path(ROOT,alias,work/'compiled'/n))
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'+
        '\n'.join('add_design '+compiled(n)for n in SOURCES)+'\nadd_constraint '+compiled(FDC)+'\n'
        'compile -top_module '+TARGET+'\nsynthesize -ads -selected_syn_tool_opt 2\ndev_map\n'
        'pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 '
        '-fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE\n'
        'report_timing -force_to_run -delay_type min_max -max_path 10000 -nworst 4 -report_exception TRUE\n')


def recipe(work,alias='P:/',maximum=900,require_alias=False):
    work=work_path(work);alias=paths.alias_format(alias)
    require(type(maximum)is int and 60<=maximum<=1800,'bounded60..1800 second snapshot build required')
    if require_alias:paths.validate_repo_alias(ROOT,alias)
    saved=read(ROOT/MANIFEST);require(saved==expected_manifest(),'snapshot source manifest differs from exact recipe')
    profile,watched=profile_binding();evidence(watched)
    for name,h in saved['SourceSHA256'].items():add(watched,ROOT/name,h)
    for path in (ROOT/BASE_FDC,ROOT/MANIFEST,REARM_PLAN,ROOT/UART_FDC,ROOT/DIRECT_TOP,DIRECT_PLAN,GTP_MODEL,NATIVE_MODEL):add(watched,path)
    for row in saved['RetainedRearmFrozenSources']:add(watched,row['Path'],row['SHA256'])
    _,pin_review=render_constraints((ROOT/BASE_FDC).read_text(encoding='ascii'),(ROOT/TOP).read_text(encoding='utf-8-sig'))
    payloads={};copies=[]
    for name in saved['source_files']:
        data,changes=compiled_source(name,(ROOT/name).read_bytes(),work,alias);path=work/'compiled'/name
        payloads[path]=data;copies.append({'Source':name,'OriginalSHA256':sha(ROOT/name),'CompiledPath':str(path),
            'NativeCompiledPath':paths.alias_path(ROOT,alias,path),'CompiledSHA256':digest(data),'Changes':changes})
    payloads[work/'build.tcl']=render_tcl(work,alias).encode('ascii')
    config=ROOT.parent/'team-config.local.json';pds=Path(read(config)['pds_bin'])/'pds_shell.exe'
    require(pds.is_file(),'configured PDS executable missing')
    for module in (pins,paths,cleanup,raw_status):add(watched,module.__file__)
    for path in (SELF,config,pds):add(watched,path)
    native_work=paths.alias_path(ROOT,alias,work)
    return {'Schema':SCHEMA,'Target':TARGET,'ProjectRoot':str(ROOT),'WorkDirectory':str(work),
        'RepoAlias':alias,'AliasExpectedRepository':str(ROOT.parent.resolve()),'AliasRequiredForNativeExecutionOnly':True,
        'Manifest':ref(ROOT/MANIFEST),'SourceFiles':saved['source_files'],
        'SourceRoles':{'ExplicitDesigns':list(SOURCES),'Headers':[],'IDFExpandedSources':[]},
        'CompiledInputs':copies,'InputTiming':profile,'OfficialTXEvidence':saved['OfficialTXEvidence'],
        'Pins':pin_review,'PLLClocks':pll_clocks(),'InputPixelPeriodNS':6.6667,
        'OutputClockForwarded':True,'OutputMHzEstimate':profile['MeasuredPCLKHzEstimate']/1e6,'ConfigurationMHz':10.0,
        'InputSHA256':watched,'PreparedSHA256':{str(p):digest(v)for p,v in payloads.items()},
        'ExpectedStages':STAGES,'MaximumSeconds':maximum,
        'Command':[str(pds),'-file',native_work+'/build.tcl','-work_dir',native_work,'-project_name',TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'HardwareReleaseAllowed':False,'TimingAccepted':False,
        'ExternalACAccepted':False,'NativePinsVerified':False,'RGBPixelsVerified':False,'CapturePhaseVerified':False,
        'DDRIncluded':False,'UARTIncluded':True,'SnapshotsIncluded':True,'VideoPLLIncluded':False,
        'SnapshotContract':snapshot_contract(),'DeviceDRMCapacityMustBeMapped':True,
        'InitialSTAADFBeforeAfterVerified':False,'TimingExceptionsInherited':False,
        'Limits':'Independent reversible snapshot RGB display experiment. Actual same-source sampler/control simulation, '
            'native IO/reset/CDC/clock-forwarding/full timing and bitstream binding remain required. '
            'No physical proof, source sampling/CRC acceptance or external AC is inherited.'},payloads


def prepare(work,alias='P:/',maximum=900):
    work=work_path(work);require(not work.exists(),'fresh snapshot build work directory required')
    value,payloads=recipe(work,alias,maximum);work.mkdir(parents=True)
    for path,data in payloads.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    value['PreparedUTC']=utc();write(work/'plan.json',value);return value


def validate(path,require_alias=False):
    path=Path(path).absolute();work=work_path(path.parent);saved=read(path)
    require(path.name=='plan.json','exact snapshot build plan filename required')
    expected,payloads=recipe(work,saved['RepoAlias'],saved['MaximumSeconds'],require_alias=require_alias)
    require(set(saved)==set(expected)|{'PreparedUTC'}and {k:v for k,v in saved.items()if k!='PreparedUTC'}==expected,
        'snapshot build plan differs from exact current recipe')
    require({p for p in (work/'compiled').rglob('*')if p.is_file()}==
        {p for p in payloads if p.is_relative_to(work/'compiled')},'snapshot compiled inventory differs')
    for path,data in payloads.items():require(path.is_file()and path.read_bytes()==data,'frozen snapshot source/Tcl/FDC differs: '+str(path))
    for name,h in saved['InputSHA256'].items():require(sha(name)==h,'snapshot build input drift: '+name)
    return saved


def diagnostics(work):
    return [p.relative_to(work).as_posix()+': '+line.strip()for p in sorted(Path(work).rglob('*.log'))
        for line in p.read_text(encoding='gb18030',errors='replace').splitlines()
        if re.match(r'\s*(C:|E:|F:|CRITICAL:|ERROR:|FATAL:|Traceback)',line)]


def events(text):return [list(row)for row in re.findall(r'^Process "([^"]+)" (started|done)\.',text,re.M)]


def memory_resource_review(work):
    path=Path(work)/'device_map/run.log'
    rows=re.findall(r'^\| DRM\s+\|\s*([0-9.]+)\s*\|\s*(\d+)\s*\|',
        path.read_text(encoding='gb18030',errors='strict'),re.M)
    require(len(rows)==1,'one actual native DRM utilization row required')
    used,available=float(rows[0][0]),int(rows[0][1])
    require(available==155 and 0<used<=available,'snapshot exceeds actual device DRM capacity')
    return {'Passed':True,'DeviceMapLog':ref(path),'Used36KBlocks':used,'Available36KBlocks':available,
        'SourceSnapshot18KHalves':256,'SourceSnapshotBytes':524288,'ActualNativeMemoryPortAuditStillRequired':True}


def diagnostic_errors(rows,plan):
    work=Path(plan['WorkDirectory']);prefix=paths.alias_path(ROOT,plan['RepoAlias'],work)+'/compiled/'
    top_lines=(work/'compiled'/TOP).read_text(encoding='utf-8-sig').splitlines()
    start=next(i for i,line in enumerate(top_lines)if 'reg [31:0] cfg_wait_count=0;'in line)
    line=next(i+1 for i in range(start+1,len(top_lines))if 'always @(posedge clk_27m or negedge global_reset_n)'in top_lines[i])
    allowed=set()
    for source,number,counter,new in ((TOP,line,'cfg_wait_count',22),('rtl/experimental/iic_dri_checked.v',93,'watchdog',17)):
        allowed.add('C: Sdm-3003: ['+prefix+source+'(line number: '+str(number)+
            ')] Reduce accumulator '+counter+' size from 32 to '+str(new)+
            '. If this is not intended behavior, please drive '+counter+' with valid values.')
    capture_lines=(work/'compiled'/CAPTURE).read_text(encoding='utf-8-sig').splitlines()
    reset_line=next(i for i,text in enumerate(capture_lines) if 'native_pixels<=0;' in text)
    capture_line=max(i+1 for i,text in enumerate(capture_lines[:reset_line]) if 'always @(posedge pclk)' in text)
    for counter,old,new in (('native_pixels',32,21),('row_pixels',12,11)):
        allowed.add('C: Sdm-3003: ['+prefix+CAPTURE+'(line number: '+str(capture_line)+
            ')] Reduce accumulator '+counter+' size from '+str(old)+' to '+str(new)+
            '. If this is not intended behavior, please drive '+counter+' with valid values.')
    return [row for row in rows if row.split(': ',1)[-1]not in allowed]


def profile_binding(path=None):
    watched={};path=add(watched,PROFILE if path is None else path);profile=read(path)
    require(profile.get('Schema')=='hdmi-camera-observed-digital-timing-v1','observed v2 digital profile required')
    source=profile['Source'];live_path=add(watched,source['Path'],source['SHA256']);live=read(live_path)
    require(live_path.parent==RAW_WORK.resolve() and live.get('passed') is True
            and live.get('protocol')=='PGHRAW01' and live.get('packet_bytes')==128
            and live.get('uart_transmit_bytes')==0 and live.get('rejected_packets')==0,'successful receive-only v2 timing evidence required')
    wire=add(watched,live['raw_path'],live['wire_sha256'])
    require(wire.parent==RAW_WORK.resolve() and wire.stat().st_size<=raw_status.MAX_BYTES,'bound raw wire role differs')
    parser=raw_status.FrameParser();frames=parser.feed(wire.read_bytes())
    require(frames==live['frames'] and parser.accepted==live['accepted_packets']==20 and parser.rejected==0,
            'raw v2 wire/decoded packet inventory differs')
    summary=raw_status.summarize(frames)
    require(summary==live['summary'] and summary['valid_counter_windows']==19
            and summary['unavailable_reasons']=={} and summary['edge_conservation_failure_windows']==0,
            'raw v2 timing/edge conservation recomputation failed')
    require(all(f['build_tag']==0x48445202 and not f['semantic_issues'] and f['cfg_error']==0 for f in frames),
            'wrong raw sampler generation or configuration/semantic issue')
    expected={'BuildTags':['0x48445202'],'TransportPassed':True,'RejectedPackets':0,'UARTTransmitBytes':0,
        'ValidWindows':19,'UnavailableReasons':{},'EstimatedPCLKHz':summary['pclk_hz_estimate'],
        'EstimatedVSRisingHz':summary['raw_vs_rising_hz_estimate'],'EstimatedVSFallingHz':summary['raw_vs_falling_hz_estimate'],
        'VSPeriodPCLK':sorted({f['raw']['vs_period_pclk'] for f in frames}),
        'HSPeriodPCLK':sorted({f['raw']['hs_period_pclk'] for f in frames}),
        'DEHighWidthPCLK':sorted({f['raw']['de_high_width_pclk'] for f in frames}),
        'VSHighWidthPCLK':sorted({f['raw']['vs_high_width_pclk'] for f in frames}),
        'VSLowWidthPCLK':sorted({f['raw']['vs_low_width_pclk'] for f in frames}),
        'ActiveLinesPerVS':sorted({f['raw']['de_rises_per_vs_period'] for f in frames}),
        'ConfigurationErrorCodes':[0],'SemanticIssues':[],'VSActiveHighSelectedForNextPrototype':True,
        'DEActiveHighSelectedForNextPrototype':True,'RGBPixelsVerified':False,'ExternalACAccepted':False}
    require(all(profile.get(k)==v for k,v in expected.items()),'digital profile differs from source measurement/selection')
    require(expected['VSPeriodPCLK']==[2475000] and expected['HSPeriodPCLK']==[2200]
            and expected['DEHighWidthPCLK']==[1920] and expected['ActiveLinesPerVS']==[1080]
            and expected['VSHighWidthPCLK']==[11000] and expected['VSLowWidthPCLK']==[2464000]
            and 148000000<expected['EstimatedPCLKHz']<150000000,'selected150MHz envelope no longer covers observed profile')
    add(watched,raw_status.__file__)
    return {'Profile':ref(path),'Source':ref(live_path),'Wire':ref(wire),'RecomputedValidWindows':19,
        'DigitalTimingConfigured':True,'SelectedVSActiveLevel':1,'SelectedDEActiveLevel':1,
        'MeasuredPCLKHzEstimate':summary['pclk_hz_estimate'],'ProgressiveSourceVerified':False,
        'RGBPixelsVerified':False,'CapturePhaseVerified':False,'ExternalACAccepted':False},watched


def execute(path):
    path=Path(path).absolute();plan=validate(path,require_alias=True);work=path.parent
    require(os.name=='nt' and not (work/'execution-start.json').exists(),'fresh Windows snapshot build execution required')
    watched={**plan['InputSHA256'],**plan['PreparedSHA256'],str(path):sha(path)}
    result={'Schema':'hdmi-camera-snapshot-build-execution-v1','Target':TARGET,'PlanSHA256':sha(path),
        'StartedUTC':utc(),'Command':plan['Command'],'HardwareAccessed':False,'BitstreamRequested':False,
        'EDAExecuted':False,'TimedOut':False,'StoppedForUnexpectedStage':False,'ExitCode':None,
        'TimingAccepted':False,'HardwareReleaseAllowed':False,'ExternalACAccepted':False}
    write(work/'execution-start.json',result);process=None;start=time.monotonic()
    expected=[[stage,event] for stage in STAGES for event in ('started','done')]
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process=subprocess.Popen(plan['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));result.update(EDAExecuted=True,OwnedPID=process.pid)
            while process.poll() is None:
                remaining=plan['MaximumSeconds']-(time.monotonic()-start)
                if remaining<=0:result['TimedOut']=True;break
                try:process.wait(timeout=min(3,remaining))
                except subprocess.TimeoutExpired:pass
                current=events((work/'stdout.log').read_text(encoding='gb18030',errors='replace'))
                if current!=expected[:len(current)]:result['StoppedForUnexpectedStage']=True;break
    except BaseException as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        result['Cleanup']=(cleanup.stop_owned_tree(process,work,'bounded independent snapshot build')
                           if process is not None and process.poll() is None else {'Complete':True,'ParentExited':True})
        if process is not None:result['ExitCode']=process.poll()
        adf=work/'place_route'/(TARGET+'_pnr.adf');report=work/'report_timing'/(TARGET+'.rtr')
        result.update(ElapsedSeconds=round(time.monotonic()-start,3),FinishedUTC=utc(),
            InputDrift=[name for name,h in watched.items() if not Path(name).is_file() or sha(name)!=h],
            ActualEvents=events((work/'stdout.log').read_text(encoding='gb18030',errors='replace')),
            Diagnostics=diagnostics(work),ADF=str(adf),ADFSHA256=sha(adf) if adf.is_file() else None,
            TimingReport=ref(report) if report.is_file() else None,InitialSTAADFBeforeAfterVerified=False,
            NativeLogSHA256={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*.log')})
        result['NativeErrors']=diagnostic_errors(result['Diagnostics'],plan)
        try:result['MemoryResourceReview']=memory_resource_review(work)
        except Exception as error:result['Error']=type(error).__name__+': '+str(error)
        result['BuildCompleted']=(result['ExitCode']==0 and result['EDAExecuted'] and not result['TimedOut']
            and not result.get('Error') and not result['StoppedForUnexpectedStage'] and result['ActualEvents']==expected
            and result['InputDrift']==[] and adf.is_file() and report.is_file() and result['NativeErrors']==[] and result['Cleanup']['Complete'])
        result['DiagnosticsReviewed']=False;result['DiagnosticsCleared']=result['Diagnostics']==[]
        write(work/'execution-result.json',result)
    return result


def verify_execution(path):
    path=Path(path).absolute();work=work_path(path.parent);saved=read(path)
    require(path.name=='execution-result.json' and saved.get('Schema')=='hdmi-camera-snapshot-build-execution-v1'
            and saved.get('Target')==TARGET and saved.get('BuildCompleted') is True,
            'completed current snapshot build receipt required')
    plan=validate(work/'plan.json')
    require(saved['PlanSHA256']==sha(work/'plan.json') and saved['Command']==plan['Command']
            and saved['ExitCode']==0 and saved['EDAExecuted'] is True and saved['TimedOut'] is False
            and saved['StoppedForUnexpectedStage'] is False and not saved.get('Error')
            and saved['InputDrift']==[] and saved['NativeErrors']==[] and saved['Cleanup']['Complete']
            and saved['Cleanup']['ParentExited'] and diagnostic_errors(saved['Diagnostics'],plan)==[],
            'snapshot native receipt did not complete cleanly')
    actual_logs={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*.log')}
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='strict')
    require(saved['NativeLogSHA256']==actual_logs and saved['Diagnostics']==diagnostics(work)
            and saved['ActualEvents']==events(log)==[[s,e] for s in STAGES for e in ('started','done')],
            'snapshot native logs/events differ')
    require(saved['MemoryResourceReview']==memory_resource_review(work),'snapshot native memory capacity evidence differs')
    adf=work/'place_route'/(TARGET+'_pnr.adf');report=work/'report_timing'/(TARGET+'.rtr')
    require(saved['ADF']==str(adf) and saved['ADFSHA256']==sha(adf) and saved['TimingReport']==ref(report),
            'snapshot native ADF/report binding differs')
    require(all(saved.get(k) is False for k in ('HardwareAccessed','BitstreamRequested','HardwareReleaseAllowed',
                                              'TimingAccepted','ExternalACAccepted')),'snapshot receipt overclaims release')
    return saved


def main():
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True)
    m.add_argument('--write-manifest',action='store_true');m.add_argument('--prepare',type=Path)
    m.add_argument('--validate',type=Path);m.add_argument('--execute',type=Path)
    m.add_argument('--verify-result',type=Path)
    p.add_argument('--repo-alias',default='P:/');p.add_argument('--maximum-seconds',type=int,default=1800);a=p.parse_args()
    if a.write_manifest:print(json.dumps({'Created':str(write_manifest())}));return 0
    if a.prepare:v=prepare(a.prepare,a.repo_alias,a.maximum_seconds);print(json.dumps({'Prepared':True,'Plan':str(Path(v['WorkDirectory'])/'plan.json')}));return 0
    if a.validate:validate(a.validate);print('{"Validated":true,"HardwareAccessed":false}');return 0
    if a.verify_result:verify_execution(a.verify_result);print('{"Verified":true,"HardwareAccessed":false}');return 0
    v=execute(a.execute);print(json.dumps({k:v.get(k) for k in ('BuildCompleted','ExitCode','ElapsedSeconds','Error')}));return 0 if v['BuildCompleted'] else 1


if __name__=='__main__':raise SystemExit(main())
