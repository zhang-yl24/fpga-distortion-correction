"""Prepare, never execute, a later volatile-SRAM session for this output bit.

The board is currently powered off. Scan/program files are reviewable local
artifacts, not permission to power or program it and not a hardware result.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import re

import processed_output_bitstream as bit
import program_native_raw as native


def bound_inputs(bit_work, verified, pds):
    """Reconstruct the complete binding; a plan cannot omit a checked input."""
    plan = bit.load(bit_work/'bitstream-plan.json')
    bindings = dict(plan['ProjectInputSHA256'])
    for group in (plan['WorkInputSHA256'],verified['EvidenceSHA256']):
        for name,digest in group.items():
            path = bit_work/name
            bit.require(bit.sha(path)==digest, 'verified bit input drift')
            bindings[str(path)] = digest
    source_bit = Path(verified['Bitstream']['Path'])
    helpers = Path(__file__).resolve().parent
    for path in (source_bit,Path(__file__).resolve(),Path(native.__file__).resolve(),
                 helpers/'execute_processed_output_program.py',helpers/'native_camera_capture.py',
                 helpers/'frame_protocol.py',helpers/'camera_eye_pin_audit.py'):
        bindings[str(path)] = bit.sha(path)
    for name in ('cdt_js.exe','cdt_cfg_shell.exe'):
        bindings[str(pds/name)] = bit.sha(pds/name)
    return bindings


def prepare(bit_work, work):
    bit_work = bit.work_path(bit_work)
    work = Path(work).absolute()
    bit.require(work == work.resolve() and work.parent == bit.BUILD
                and re.fullmatch(r'program-[A-Za-z0-9_-]+',work.name)
                and not work.exists(), 'new canonical program-* work directory required')
    verified = bit.verify(bit_work)
    bit.require(verified.get('Verified') is True and verified.get('FinalADFSHA256') == bit.ADF_SHA,
                'verified final processed-output bit required')
    source_bit = Path(verified['Bitstream']['Path'])
    pds = native.resolve_pds_bin(bit.export.PDS.parent)
    bindings = bound_inputs(bit_work, verified, pds)
    scripts = native._scripts({'bitstream_path':str(source_bit)},'1MHz')
    bit.require(set(scripts)=={'scan','program'} and all('flash' not in v.lower() for v in scripts.values()),
                'unexpected programming script')
    work.mkdir()
    for stage,text in scripts.items():
        with (work/(stage+'.tcl')).open('x',encoding='utf-8',newline='\n') as stream:
            stream.write(text)
    bit.require(all(bit.sha(name)==digest for name,digest in bindings.items()), 'input drift while preparing')
    result = {'Schema':'processed-output-sram-plan-v1','Target':bit.TARGET,
              'PreparedUTC':datetime.now(timezone.utc).isoformat(),'WorkDirectory':str(work),
              'BitstreamWorkDirectory':str(bit_work),'Operation':'volatile_sram_only',
              'ExpectedDevice':native.DEVICE,'ExpectedDeviceID':native.DEVICE_ID,
              'CableIndex':0,'Frequency':'1MHz','ServerPort':native.PORT,'PDSBin':str(pds),
              'Bitstream':verified['Bitstream'],'FinalADFSHA256':bit.ADF_SHA,
              'BoundInputSHA256':bindings,
              'Tcl':{stage:{'Path':str(work/(stage+'.tcl')),'SHA256':bit.sha(work/(stage+'.tcl'))}
                     for stage in scripts},
              'PreparedOnly':True,'HardwareAccessed':False,'Executed':False,
              'ProgrammingAttempted':False,'DoneConfirmed':False,'FlashWritten':False,
              'ExecutionSupported':True,'RequiresExplicitExecuteAndBoardPowered':True,
              'BoardPowerLastReported':'off','UserMustBeNotifiedBeforeBoardSession':True,
              'DDRProcessingIncluded':True,'PhysicalInputCaptureIncluded':False,
              'HardwareReleaseAllowed':False,
              'NextChecks':['Complete candidate CDC/TX review, then notify user that board power is needed.',
                            'After power confirmation, reverify artifacts and scan exact device/ID.',
                            'Execute only volatile SRAM with an owned JTAG server and verify DONE.',
                            'Validate corrected test image and frame progress separately from programmer success.']}
    bit.write_json(work/'plan.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bit-work',type=Path,required=True)
    parser.add_argument('--work-dir',type=Path,required=True)
    args=parser.parse_args()
    result=prepare(args.bit_work,args.work_dir)
    print(json.dumps({'PreparedOnly':True,'HardwareAccessed':False,
                      'Plan':str(Path(result['WorkDirectory'])/'plan.json')}))


if __name__=='__main__':
    main()
