"""Prepare the bounded post-reset delay experiment; no automatic I2C retry."""
from pathlib import Path
import argparse
import json
import prepare_hdmi_uart_control_diagnostic as control
from prepare_hdmi_uart_diagnostic import sha

ROOT=control.ROOT
TOP='hdmi_uart_delayed_diag'


def prepare(work):
    work=Path(work).resolve()
    # Reuse the exact 42-pin configuration-only recipe, then change only its
    # selected top before any native process is started.
    plan=control.prepare(work)
    old=ROOT/'board/hdmi_uart_control_diag.v'
    new=ROOT/'board/hdmi_uart_delayed_diag.v'
    text=(work/'build.tcl').read_text(encoding='utf-8')
    if text.count(old.as_posix())!=1 or text.count('compile -top_module '+control.TOP)!=1:
        raise ValueError('control recipe anchors changed')
    text=text.replace(old.as_posix(),new.as_posix()).replace('compile -top_module '+control.TOP,'compile -top_module '+TOP)
    (work/'build.tcl').write_text(text,encoding='utf-8',newline='\n')
    plan['Target']=TOP
    plan['Schema']='hdmi-uart-delayed-diagnostic-build-v1'
    plan['PostPeripheralResetWaitCycles']=2700000
    plan['PostPeripheralResetWaitNominalMS']=100
    plan['I2CAutomaticRetry']=False
    del plan['InputSHA256']['board/hdmi_uart_control_diag.v']
    plan['InputSHA256']['board/hdmi_uart_delayed_diag.v']=sha(new)
    plan['InputSHA256']['tools/prepare_hdmi_uart_delayed_diagnostic.py']=sha(__file__)
    plan['TclSHA256']=sha(work/'build.tcl')
    plan['Command'][-1]=TOP
    (work/'build-plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    return plan


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workdir',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(prepare(a.workdir),indent=2))
