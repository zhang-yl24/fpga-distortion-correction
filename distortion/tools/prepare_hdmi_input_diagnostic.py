"""Prepare the isolated input observer build; no native timing or board claim."""
from pathlib import Path
import argparse
import json
import re
import prepare_hdmi_uart_diagnostic as original

ROOT=original.ROOT
TOP='hdmi_uart_input_diag'
REPLACEMENTS={
    'board/hdmi_uart_diag.v':'board/hdmi_uart_input_diag.v',
    'rtl/experimental/hdmi1080_input_status.v':'rtl/experimental/hdmi1080_input_status_cdc.v',
    'rtl/experimental/dvp_mode_admission_monitor.v':'rtl/experimental/dvp_mode_admission_monitor_cdc.v',
}
# Source-level register instances, not old optimized /opit_0 cell names. Keep
# both stages and every declared bit explicit; native matching is audited later.
SYNCHRONIZER_REGISTERS={
    'input_status': (
        ('p_reset',2),('r_reset',2),('polarity_sync',3),
        ('vs_level_sync',2),('hs_level_sync',2),
        ('timing_good_sync',2),('timing_bad_sync',2),
    ),
    'input_status/geometry': (
        ('p_reset',2),('r_reset',2),('p_enable',2),('r_enable',2),
        ('source_running_sync',2),('request_sync',2),('ack_sync',2),
        ('edge_meta',32),('edge_sync',32),('vs_meta',16),('vs_sync',16),
        ('href_meta',16),('href_sync',16),('healthy_sync',2),('failed_sync',2),
    ),
}
SYNCHRONIZER_SOURCES={
    'input_status':'rtl/experimental/hdmi1080_input_status_cdc.v',
    'input_status/geometry':'rtl/experimental/dvp_mode_admission_monitor_cdc.v',
}


def synchronizer_attributes():
    """Validate the fixed source whitelist and render exact per-bit FDC objects."""
    instances=[]
    for hierarchy,registers in SYNCHRONIZER_REGISTERS.items():
        source=(ROOT/SYNCHRONIZER_SOURCES[hierarchy]).read_text(encoding='utf-8')
        declarations={}
        for match in re.finditer(r'\(\*(.*?)\*\)\s*reg\s*\[(\d+):0\]\s*([^;]+);',source,re.S):
            if not re.search(r'\bsyn_preserve\s*=\s*1\b',match[1]):
                continue
            for declaration in match[3].split(','):
                name=declaration.split('=',1)[0].strip()
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',name) or name in declarations:
                    raise ValueError('ambiguous preserved register declaration: '+hierarchy+'/'+name)
                declarations[name]=int(match[2])+1
        if declarations!=dict(registers):
            raise ValueError('synchronizer source whitelist/width changed: '+hierarchy)
        instances.extend(f'i:{hierarchy}/{name}[{bit}]'
                         for name,width in registers for bit in range(width))
    if len(instances)!=161 or len(set(instances))!=len(instances):
        raise ValueError('synchronizer instance count/uniqueness changed')
    text=('# Source synchronizer attributes only; no timing exceptions.\n'
          '# Exact declared instances; native matching and mapping require audit.\n'
          + '\n'.join(f'define_attribute {{{name}}} {{PAP_ASYNC_REG}} {{TRUE}}'
                      for name in instances)+'\n')
    return text,instances


def prepare(work):
    work=Path(work).resolve()
    attributes,instances=synchronizer_attributes()
    plan=original.prepare(work)
    fdc=work/'hdmi_uart_diag.fdc'
    fdc_text=fdc.read_text(encoding='utf-8')
    if 'PAP_ASYNC_REG' in fdc_text:
        raise ValueError('base diagnostic FDC already contains synchronizer attributes')
    fdc.write_text(fdc_text+attributes,encoding='utf-8',newline='\n')
    tcl=(work/'build.tcl').read_text(encoding='utf-8')
    for old,new in REPLACEMENTS.items():
        before=(ROOT/old).as_posix()
        if tcl.count(before)!=1:
            raise ValueError('original recipe source anchor changed: '+old)
        tcl=tcl.replace(before,(ROOT/new).as_posix())
        del plan['InputSHA256'][old]
        plan['InputSHA256'][new]=original.sha(ROOT/new)
    tcl=tcl.replace('compile -top_module '+original.TOP,'compile -top_module '+TOP)
    (work/'build.tcl').write_text(tcl,encoding='utf-8',newline='\n')
    plan.update(Schema='hdmi-input-diagnostic-build-v1',Target=TOP,
                FDC=str(work/'hdmi_uart_diag.fdc'),InputObserverIncluded=True,
                PostPeripheralResetWaitCycles=2700000,I2CAutomaticRetry=False,
                CDCConstraintsApplied=False,PhysicalCDCVerified=False,
                SynchronizerAttributes={'Attribute':'PAP_ASYNC_REG','Value':'TRUE',
                    'Instances':instances,'InstanceCount':len(instances),
                    'RegisterFamilyCount':sum(len(v) for v in SYNCHRONIZER_REGISTERS.values()),
                    'HierarchyInstanceCounts':{k:sum(n for _,n in v) for k,v in SYNCHRONIZER_REGISTERS.items()},
                    'NativeAttributeMatchVerified':False},
                TimingExceptionsApplied=False,
                Limits='Explicit synchronizer mapping attributes only; no CDC timing exceptions. No DDR, pixel payload or optical acceptance. Must verify native attribute matching, mapped stages and scoped physical CDC timing before programming.')
    plan['TclSHA256']=original.sha(work/'build.tcl')
    plan['FDCSHA256']=original.sha(fdc)
    plan['Command'][-1]=TOP
    plan['InputSHA256']['tools/prepare_hdmi_input_diagnostic.py']=original.sha(__file__)
    (work/'build-plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    return plan


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.workdir),indent=2))
