"""Prepare the isolated input observer build; no native timing or board claim."""
from pathlib import Path
import argparse
import json
import prepare_hdmi_uart_diagnostic as original

ROOT=original.ROOT
TOP='hdmi_uart_input_diag'
REPLACEMENTS={
    'board/hdmi_uart_diag.v':'board/hdmi_uart_input_diag.v',
    'rtl/experimental/hdmi1080_input_status.v':'rtl/experimental/hdmi1080_input_status_cdc.v',
    'rtl/experimental/dvp_mode_admission_monitor.v':'rtl/experimental/dvp_mode_admission_monitor_cdc.v',
}


def prepare(work):
    work=Path(work).resolve()
    plan=original.prepare(work)
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
                Limits='Unconstrained CDC characterization first. No DDR, pixel payload or optical acceptance. Must bind scoped CDC constraints and native evidence before programming.')
    plan['TclSHA256']=original.sha(work/'build.tcl')
    plan['Command'][-1]=TOP
    plan['InputSHA256']['tools/prepare_hdmi_input_diagnostic.py']=original.sha(__file__)
    (work/'build-plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    return plan


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.workdir),indent=2))
