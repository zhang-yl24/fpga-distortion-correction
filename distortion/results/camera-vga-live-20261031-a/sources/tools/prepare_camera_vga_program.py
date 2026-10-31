"""Prepare a reviewable camera-only volatile SRAM plan without hardware access.

Camera CDC structural and pin evidence are mandatory and hash-bound, but their
limited diagnostic scope is preserved. No external AC or universal CDC pass is
invented. A later execution requires a new user confirmation that power is on.
"""
from datetime import datetime,timezone
from pathlib import Path
import argparse
import json
import re

import camera_vga_bitstream as bit
import program_native_raw as native


def evidence(path,kind):
    path=Path(path).absolute()
    bit.require(path==path.resolve() and path.is_relative_to(bit.PROJECT) and path.is_file(),
                'canonical camera evidence file required')
    value=bit.load(path)
    if kind=='cdc':
        bit.require(value.get('Schema')=='camera-vga-cdc-structural-v1' and value.get('AuditPassed') is True and
                    value.get('CandidateADFSHA256')==bit.ADF_SHA,'camera structural CDC proof differs')
        bit.require(value['Scope'].get('AnalogMTBFProven') is False and
                    value['Scope'].get('AllCDCUniversallyProven') is False,'CDC evidence must preserve stated diagnostic limits')
        bit.require(value['Scope'].get('NativeInterstageTimingComplete') is True and
                    value['Scope'].get('GrayDatapathBoundComplete') is True,
                    'complete native interstage and Gray datapath evidence is required for the final SRAM plan')
        scope={'StructuralAuditPassed':True,'NativeInterstageTimingComplete':value['Scope'].get('NativeInterstageTimingComplete') is True,
               'GrayDatapathBoundComplete':True,
               'AnalogMTBFProven':False,'AllCDCUniversallyProven':False,'Summary':value['Summary']}
    elif kind=='pin':
        bit.require(value.get('Schema')=='camera-vga-io-evidence-v1' and value.get('AuditCompleted') is True and
                    value.get('CandidateADF',{}).get('SHA256')==bit.ADF_SHA,'camera IO evidence differs')
        bit.require(value['Pins'].get('DeclarationAndSourceBuildMappingPassed') is True and
                    value['Pins'].get('FinalFunctionalPadSiteMappingPassed') is True,'camera pin mapping not proved')
        bit.require(value['TX'].get('ExternalTimingAccepted') is False and value['DVP'].get('ExternalTimingAccepted') is False,
                    'diagnostic camera IO scope differs')
        scope={'PinMappingsPassed':True,'FinalNativeElectricalAttributesVerified':value['Pins'].get('FinalNativeElectricalAttributesVerified') is True,
               'TXExternalTimingAccepted':False,'DVPExternalTimingAccepted':False}
    else:raise ValueError('unknown camera evidence kind')
    bit.require(value.get('HardwareReleaseAllowed') is False,'evidence must not claim hardware release')
    bindings={str(path):bit.sha(path)}
    for key in ('InputSHA256','ToolSHA256'):
        bit.require(isinstance(value.get(key),dict) and value[key],'evidence input/tool hashes required')
        for name,wanted in value[key].items():
            source=Path(name).absolute()
            bit.require(source==source.resolve() and source.is_file() and
                        (source.is_relative_to(bit.PROJECT.parent) or source.is_relative_to(bit.PDS.parent.parent)),
                        'unexpected evidence input location')
            bit.require(bit.sha(source)==wanted,'camera evidence hash drift: '+name);bindings[str(source)]=wanted
    return {'Path':str(path),'SHA256':bit.sha(path),'Scope':scope},bindings


def bound_inputs(bit_work,verified,pds,cdc_path,pin_path):
    plan=bit.load(bit_work/'bitstream-plan.json');bindings=dict(plan['ProjectInputSHA256'])
    for group in (plan['WorkInputSHA256'],verified['EvidenceSHA256']):
        for name,wanted in group.items():
            source=bit_work/name;bit.require(bit.sha(source)==wanted,'verified bit input drift');bindings[str(source)]=wanted
    cdc,cb=evidence(cdc_path,'cdc');pin,pb=evidence(pin_path,'pin');bindings.update(cb);bindings.update(pb)
    helpers=Path(__file__).resolve().parent
    for source in (Path(verified['Bitstream']['Path']),Path(__file__).resolve(),Path(native.__file__).resolve(),
                   helpers/'execute_camera_vga_program.py',helpers/'native_camera_capture.py',
                   helpers/'frame_protocol.py',helpers/'camera_eye_pin_audit.py',pds/'cdt_js.exe',pds/'cdt_cfg_shell.exe'):
        bindings[str(source)]=bit.sha(source)
    return bindings,cdc,pin


def prepare(bit_work,work,cdc_path,pin_path):
    bit_work=bit.work_path(bit_work);work=Path(work).absolute()
    bit.require(work==work.resolve() and work.parent==bit.BUILD and re.fullmatch(r'program-[A-Za-z0-9_-]+',work.name)
                and not work.exists(),'fresh camera program-* direct workspace child required')
    verified=bit.verify(bit_work)
    bit.require(verified.get('Verified') is True and verified.get('FinalADFSHA256')==bit.ADF_SHA,
                'verified final camera bitstream required')
    pds=native.resolve_pds_bin(bit.PDS.parent)
    bindings,cdc,pin=bound_inputs(bit_work,verified,pds,cdc_path,pin_path)
    scripts=native._scripts({'bitstream_path':verified['Bitstream']['Path']},'1MHz')
    bit.require(set(scripts)=={'scan','program'} and all('flash' not in text.lower() for text in scripts.values()),
                'unexpected SRAM programming recipe')
    work.mkdir()
    for stage,text in scripts.items():
        with (work/(stage+'.tcl')).open('x',encoding='utf-8',newline='\n') as stream:stream.write(text)
    bit.require(all(bit.sha(name)==h for name,h in bindings.items()),'input drift during SRAM preparation')
    result={'Schema':'camera-vga-sram-plan-v1','Target':bit.TARGET,'PreparedUTC':datetime.now(timezone.utc).isoformat(),
            'WorkDirectory':str(work),'BitstreamWorkDirectory':str(bit_work),'Operation':'volatile_sram_only',
            'ExpectedDevice':native.DEVICE,'ExpectedDeviceID':native.DEVICE_ID,'CableIndex':0,'Frequency':'1MHz',
            'ServerPort':native.PORT,'PDSBin':str(pds),'Bitstream':verified['Bitstream'],'FinalADFSHA256':bit.ADF_SHA,
            'BoundInputSHA256':bindings,'CDCEvidence':cdc,'PinEvidence':pin,
            'Tcl':{stage:{'Path':str(work/(stage+'.tcl')),'SHA256':bit.sha(work/(stage+'.tcl'))} for stage in scripts},
            'PreparedOnly':True,'HardwareAccessed':False,'Executed':False,'ProgrammingAttempted':False,'DoneConfirmed':False,
            'FlashWritten':False,'ExecutionSupported':True,'RequiresExplicitExecuteAndBoardPowered':True,
            'BoardPowerLastReported':'off','RequiresNewPowerConfirmation':True,'UserMustBeNotifiedBeforeBoardSession':True,
            'DDRProcessingIncluded':True,'PhysicalInputCaptureIncluded':True,'CameraInterface':'CAM2_OV5640_DVP_RGB565',
            'DiagnosticOnly':True,'ExternalIOAccepted':False,'CDCPhysicalAccepted':False,'HardwareReleaseAllowed':False,
            'NextChecks':['Notify user before board session and obtain a new power-on confirmation.',
                          'Recheck exact candidate bit/evidence, scan one PG2L100H and verify exact device ID.',
                          'Program volatile SRAM only and verify post-program DONE.',
                          'Observe sensor initialization, live camera image, capture/processing progress and fault LED.',
                          'External AC, sustained camera operation and complete CDC physical signoff remain separate.']}
    bit.write_json(work/'plan.json',result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('bit-work','work-dir','cdc-evidence','pin-evidence'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();result=prepare(args.bit_work,args.work_dir,args.cdc_evidence,args.pin_evidence)
    print(json.dumps({'PreparedOnly':True,'HardwareAccessed':False,'Plan':str(Path(result['WorkDirectory'])/'plan.json')}))


if __name__=='__main__':main()
