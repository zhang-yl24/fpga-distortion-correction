"""Source-bound permission to inspect one diagnostic-bearing pixel build.

This sidecar preserves the failed receipt and all critical diagnostics. It only
permits read-only ADF inspection; it is never a timing/bitstream/hardware release.
Native unused-pad disposition and source accumulator reductions remain unaccepted.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

import hdmi_camera_pixel_build as build

SELF=Path(__file__).resolve()
SCHEMA='hdmi-camera-pixel-readonly-build-review-v1'
OMITTED={'b_in[0]':113,'b_in[1]':114,'b_in[2]':115,'g_in[0]':125,'g_in[1]':126,
         'r_in[0]':135,'r_in[1]':136,'r_in[2]':137}
DANGLING_LOGS=('flow.log','place_route/run_place.log','run.log','stdout.log')
REDUCTION_LOGS=('compile/run.log','flow.log','run.log','stdout.log')
REDUCTIONS=((build.TOP,47,'cfg_wait_count',32,22),(build.TOP,170,'pclk_age',32,22),
    ('rtl/experimental/iic_dri_checked.v',93,'watchdog',32,17),
    (build.IP+'/rtl/mcdq_ctrl/ips2l_mcdq_dcp_buf_v1_2.vp',541,'cnt',7,6),
    (build.IP+'/rtl/ddrphy/ips2l_ddrphy_data_slice_wrcal_v1_10.vp',614,'delay_cnt',4,2))
require,sha,read,ref=build.require,build.sha,build.read,build.ref


def compact(text):
    text=re.sub(r'/\*.*?\*/|//[^\r\n]*','',text,flags=re.S)
    return re.sub(r'\s+','',text)


def source_quantization(plan,work):
    """Bind the actual frozen RGB chain, without asserting native connectivity."""
    sources=(build.TOP,build.SAMPLER,'rtl/experimental/hdmi1080_video_system_cdc_reset.v',
        'rtl/experimental/hdmi1080_input_write_link.v','rtl/experimental/hdmi1080_input_dma.v',
        'rtl/experimental/hdmi1080_capture_cdc.v')
    texts={n:compact((work/'compiled'/n).read_text(encoding='utf-8-sig')) for n in sources}
    expected={build.TOP:('.raw_rgb({r_in,g_in,b_in})','.sampled_rgb(sampled_rgb)',
                         '.pix_in_rgb(sampled_rgb)'),
        build.SAMPLER:('{sampled_vs,sampled_hs,sampled_de,sampled_rgb}<={raw_vs,raw_hs,raw_de,raw_rgb};',),
        sources[2]:('.pix_rgb(pix_in_rgb)',),sources[3]:('.pix_rgb(pix_rgb)',),
        sources[4]:('.pix_rgb(pix_rgb)',),
        sources[5]:('wire[15:0]pixel565={pix_rgb[23:19],pix_rgb[15:10],pix_rgb[7:3]};',)}
    counts={build.TOP:{'r_in':2,'g_in':2,'b_in':2,'sampled_rgb':4},
        build.SAMPLER:{'raw_rgb':2,'sampled_rgb':3},sources[2]:{'pix_in_rgb':2},
        sources[3]:{'pix_rgb':3},sources[4]:{'pix_rgb':3},sources[5]:{'pix_rgb':4}}
    # Compact text joins declarations; token counts must use the original text.
    for name in sources:
        for statement in expected[name]:require(texts[name].count(statement)==1,'frozen RGB source chain differs: '+name)
        original=re.sub(r'/\*.*?\*/|//[^\r\n]*','',(work/'compiled'/name).read_text(encoding='utf-8-sig'),flags=re.S)
        for token,count in counts[name].items():
            require(len(re.findall(r'\b'+token+r'\b',original))==count,'additional/different RGB source use: '+name+'/'+token)
    rows={row['Source']:row for row in plan['CompiledInputs']}
    require(all(n in rows for n in sources),'RGB source missing from compiled closure')
    return {'Sources':[{**ref(build.ROOT/n),'Compiled':ref(work/'compiled'/n)} for n in sources],
        'SourceRGBOrder':'{r_in,g_in,b_in}',
        'CaptureRGB565Selection':'{pix_rgb[23:19],pix_rgb[15:10],pix_rgb[7:3]}',
        'SourceDiscardedPads':sorted(OMITTED),'SourceSelectionVerified':True,
        'NativeNoBusinessDependencyVerified':False,'NativeUnusedPadDispositionVerified':False,
        'DeclaredTopPorts':142,'ExpectedRetainedAfterRGB565Pruning':134,
        'ActualNativeActivePortCountVerified':False,'All27InputsHaveBusinessConsumers':False}


def expected_diagnostics(plan,work):
    native=build.paths.alias_path(build.ROOT,plan['RepoAlias'],work)
    pcf_native=native+'/device_map/'+build.TARGET+'.pcf'
    dangling={port:("C: ConstraintEditor-2001: ["+pcf_native+"(line number: "+str(line)+
        ")] Object '"+port+"' is dangling, which has no connection. it will be ignored.") for port,line in OMITTED.items()}
    reductions=['C: Sdm-3003: ['+native+'/compiled/'+name+'(line number: '+str(line)+
        ')] Reduce accumulator '+counter+' size from '+str(old)+' to '+str(new)+
        '. If this is not intended behavior, please drive '+counter+' with valid values.'
        for name,line,counter,old,new in REDUCTIONS]
    expected=[log+': '+body for log in DANGLING_LOGS for body in dangling.values()]
    expected += [log+': '+body for log in REDUCTION_LOGS for body in reductions]
    return expected,dangling,reductions


def derive(receipt_path):
    receipt_path=Path(receipt_path).absolute();work=build.work_path(receipt_path.parent)
    require(receipt_path==work/'execution-result.json','exact source pixel build receipt required')
    saved=read(receipt_path);plan_path=work/'plan.json';plan=build.validate(plan_path)
    require(saved.get('Schema')=='hdmi-camera-pixel-build-execution-v1' and saved.get('Target')==build.TARGET
        and saved.get('BuildCompleted') is False,'original failed pixel receipt required')
    require(saved['PlanSHA256']==sha(plan_path) and saved['Command']==plan['Command']
        and saved['ExitCode']==0 and saved['EDAExecuted'] is True and saved['TimedOut'] is False
        and saved['StoppedForUnexpectedStage'] is False and not saved.get('Error')
        and saved['InputDrift']==[] and saved['Cleanup']['Complete'] is True
        and saved['Cleanup']['ParentExited'] is True,'pixel inspection source did not finish all native work cleanly')
    actual_logs={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*.log')}
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='strict')
    require(saved['NativeLogSHA256']==actual_logs and saved['Diagnostics']==build.diagnostics(work)
        and saved['ActualEvents']==build.events(log)==[[s,e] for s in build.STAGES for e in ('started','done')],
        'pixel build logs/events differ')
    expected,dangling,reductions=expected_diagnostics(plan,work)
    require(Counter(saved['Diagnostics'])==Counter(expected),'pixel build has unknown/missing/duplicate critical diagnostics')
    errors=[row for row in saved['Diagnostics'] if not re.search(r': C: Sdm-3003: ',row)]
    require(saved['NativeErrors']==errors and len(errors)==32,'original eight-port critical diagnostics differ')
    adf=work/'place_route'/(build.TARGET+'_pnr.adf');report=work/'report_timing'/(build.TARGET+'.rtr')
    require(saved['ADF']==str(adf) and saved['ADFSHA256']==sha(adf) and saved['TimingReport']==ref(report),
        'source pixel ADF/report binding differs')
    require(all(saved.get(k) is False for k in ('HardwareAccessed','BitstreamRequested','HardwareReleaseAllowed',
        'TimingAccepted','ExternalACAccepted','DiagnosticsReviewed','DiagnosticsCleared',
        'InitialSTAADFBeforeAfterVerified')),'source pixel receipt overclaims acceptance')
    pcf=work/'device_map'/(build.TARGET+'.pcf');pcf_text=pcf.read_text(encoding='gb18030',errors='strict')
    inventory=build.pins.pcf_pins(pcf_text)
    require(inventory=={n:{k:v for k,v in row.items() if k!='DIRECTION'} for n,row in plan['Pins']['PinInventory'].items()}
        and len(inventory)==142,'native PCF differs from declared142-pad contract')
    for port,line in OMITTED.items():
        require(pcf_text.splitlines()[line-1].startswith('def_port {'+port+'} '),'dangling PCF line/port differs')
    quantization=source_quantization(plan,work)
    watched={}
    for name,h in {**plan['InputSHA256'],**plan['PreparedSHA256']}.items():build.add(watched,name,h)
    for name,h in actual_logs.items():build.add(watched,work/name,h)
    for path in (plan_path,receipt_path,adf,report,pcf,SELF,Path(sys.executable).resolve()):build.add(watched,path)
    value={'Schema':SCHEMA,'Target':build.TARGET,'ReviewScope':'ReadOnlyInspection',
        'ReadOnlyInspectionAllowed':True,'BuildPlan':ref(plan_path),'SourceBuildReceipt':ref(receipt_path),
        'SourceADF':ref(adf),'SourceTimingReport':ref(report),'NativePCF':ref(pcf),
        'OriginalBuildCompleted':False,'SourceDiagnostics':saved['Diagnostics'],
        'SourceNativeErrors':saved['NativeErrors'],'AllowedReadonlyDiagnosticBodies':sorted(set(dangling.values())|set(reductions)),
        'DanglingRGB565Ports':sorted(OMITTED),'SourceQuantization':quantization,
        'Reductions':[{'Source':n,'Line':line,'Accumulator':counter,'OriginalBits':old,'ReducedBits':new,
            'SafetyAccepted':False} for n,line,counter,old,new in REDUCTIONS],
        'SourceDiagnosticsPreserved':True,'DiagnosticsCleared':False,'IndependentDiagnosticReviewPassed':False,
        'NativeUnusedPadDispositionVerified':False,'BitstreamAllowed':False,'HardwareReleaseAllowed':False,
        'HardwareAccessed':False,'TimingAccepted':False,'ExternalACAccepted':False,
        'AliasRequiredForHistoricalVerification':False,'InputSHA256':watched,
        'Limits':'Only independent read-only ADF inspection. Eight RGB565 discarded low bits remain critical diagnostics. '
            'Native no-business-dependency, actual unused pad/bitgen UNUSED disposition, active-port count, '
            'five reduction safety reviews and all physical/release checks remain required.'}
    return value,{Path(p):h for p,h in watched.items()}


def verify(path):
    path=Path(path).absolute();saved=read(path)
    require(saved.get('Schema')==SCHEMA,'pixel readonly review schema differs')
    expected,watched=derive(saved['SourceBuildReceipt']['Path'])
    require(saved==expected,'pixel readonly build review differs from complete recomputation')
    require(path not in watched,'review must not overwrite original source evidence')
    watched[path]=sha(path)
    return saved,watched


def prepare(receipt,output):
    output=Path(output).absolute();value,watched=derive(receipt)
    require(output==output.resolve() and output.parent==build.WORK.resolve() and output.suffix=='.json'
        and output not in watched,'new canonical pixel-work sidecar output required')
    build.write(output,value);return output


def main():
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True)
    m.add_argument('--source-receipt',type=Path);m.add_argument('--verify',type=Path)
    p.add_argument('--output',type=Path);a=p.parse_args()
    if a.verify:verify(a.verify);print('{"Verified":true,"ReviewScope":"ReadOnlyInspection"}');return 0
    require(a.output is not None,'--output required');path=prepare(a.source_receipt,a.output)
    print(json.dumps({'Review':str(path),'ReadOnlyInspectionAllowed':True,'DiagnosticsCleared':False}));return 0


if __name__=='__main__':raise SystemExit(main())
