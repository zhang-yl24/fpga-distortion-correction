"""Run the ready wrapper on the unchanged seven-scenario wire test oracle."""
from datetime import datetime, timezone
from pathlib import Path
import csv
import hashlib
import json
import re
import sys
import time

ROOT = Path('D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion')
WORK = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
from run_gamma_pipeline_d5_sim import tool
from simulation_tools import resolve_vivado_bin
from run_ms72xx_checked_sim import command_rows, validate_wire_trace

SOURCES = ('rtl/experimental/ms7200_1080p30_ready_ctl.v',
           'rtl/experimental/ms72xx_ready_observed_ctl.v',
           'rtl/experimental/ms7210_checked_ctl.v','rtl/experimental/iic_dri_checked.v')
TB = 'tests/tb_ms72xx_observed_e2e.sv'
BOUND = SOURCES + (TB,'rtl/experimental/ms7200_1080p30_ctl.v',
                  'tools/run_hdmi_uart_sim.py','tools/run_gamma_pipeline_d5_sim.py',
                  'tools/run_ms72xx_checked_sim.py','tools/simulation_tools.py')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def require(value,message):
    if not value:raise ValueError(message)

def main():
    require(set(p.name for p in WORK.iterdir())=={'run_ready_e2e.py'},'fresh work required')
    hashes={name:sha(ROOT/name) for name in BOUND}
    original=(ROOT/TB).read_text(encoding='utf-8')
    anchor='ms72xx_observed_ctl dut('
    require(original.count(anchor)==1,'DUT anchor differs')
    generated=original.replace(anchor,'ms72xx_ready_observed_ctl dut(',1)
    tb=WORK/'tb_ms72xx_ready_observed_e2e.sv'
    tb.write_text(generated,encoding='utf-8',newline='\n')
    require(command_rows(ROOT/SOURCES[0],311)==command_rows(ROOT/'rtl/experimental/ms7200_1080p30_ctl.v',311),'RX register/EDID table differs')
    for filename,source,count in [('rx_expected.hex','rtl/experimental/ms7200_1080p30_ctl.v',311),('tx_expected.hex',SOURCES[2],49)]:
        (WORK/filename).write_text('\n'.join(command_rows(ROOT/source,count))+'\n',encoding='ascii',newline='\n')
    generated_hashes={p.name:sha(p) for p in WORK.iterdir() if p.is_file()}
    report=dict(Schema='ms72xx-ready-wire-simulation-v1',Passed=False,StartedUTC=datetime.now(timezone.utc).isoformat(),
                SourceSHA256=hashes,GeneratedSHA256=generated_hashes,
                TBTransformation='Only ms72xx_observed_ctl dut( is replaced by ms72xx_ready_observed_ctl dut( in a new TB copy.',
                All311RXCommandsUnchanged=True,Original49TXVectorUsed=True,Commands=[],HardwareAccessed=False,PDSAccessed=False,
                TransactionDriverStub=False,WireLevelI2CExecuted=True,
                Limits='Synthetic I2C slave replies using the actual ready RX, checked TX, checked driver and new wrapper. No physical board, PHY lock, real HDMI pixels, CDC/STA or output acceptance.')
    started=time.monotonic()
    try:
        bin_dir=resolve_vivado_bin(ROOT.parent)
        for name,args,stage in [('xvlog.bat',['--sv',*[str(ROOT/s) for s in SOURCES],str(tb)],'compile'),
                                ('xelab.bat',['tb_ms72xx_observed_e2e','-s','ready_wire_e2e'],'elaborate'),
                                ('xsim.bat',['ready_wire_e2e','-runall','-log','simulation.log'],'simulate')]:
            row=dict(Stage=stage,Argv=[str(bin_dir/name),*args],ReturnCode=None)
            report['Commands'].append(row)
            tool(bin_dir,name,args,WORK,started+300,stage)
            row['ReturnCode']=0
        log=(WORK/'simulation.log').read_text(encoding='utf-8',errors='replace')
        require('MS72XX_OBSERVED_E2E_SIM_PASS' in log and not re.search(r'(?im)^\s*(fatal|error):',log),'native assertions did not complete')
        require([int(n) for n in re.findall(r'(?m)^MS72XX_E2E_SCENARIO_PASS scenario=(\d+)\b',log)]==list(range(7)),'seven scenarios required')
        report['WireTraceAudit']=validate_wire_trace(WORK/'wire-transactions.csv')
        require(report['WireTraceAudit']['Transactions']==2117,'2117 wire transactions required')
        summary=json.loads((WORK/'summary.json').read_text())
        for key,wanted in dict(Passed=True,Scenarios=7,TelemetryComparedToWire=True,SuccessfulTelemetryUpdates=2112,NACKTelemetrySuppressed=5,FailureSameCycleGating=True,NoAutoRetry=True,BackgroundRXPollResumed=True,CommonResetRecovery=True,HardwareAccessed=False).items():
            require(type(summary.get(key)) is type(wanted) and summary[key]==wanted,'summary mismatch: '+key)
        with (WORK/'wire-transactions.csv').open(encoding='ascii',newline='') as stream:wire=list(csv.DictReader(stream))
        with (WORK/'telemetry-transactions.csv').open(encoding='ascii',newline='') as stream:telemetry=list(csv.DictReader(stream))
        successes=[row for row in wire if int(row['nack'])==0]
        require(len(successes)==2112 and len(telemetry)==2112,'independent telemetry row count differs')
        counters={}
        for w,t in zip(successes,telemetry):
            scenario=int(w['scenario']);counters[scenario]=counters.get(scenario,0)+1
            expected_value=w['response'] if int(w['read']) else w['data']
            meta=(2 if int(w['device'],16)==0xb2 else 0)|int(w['read'])
            require(int(t['scenario'])==scenario and t['request']==w['request'] and int(t['completed'])==counters[scenario] and int(t['meta'],16)==meta and t['addr']==w['addr'] and t['value']==expected_value,'independent wire/telemetry trace differs')
        report.update(Passed=True,Summary=summary,IndependentWireTelemetryRowsVerified=2112,
                      PassLines=[line for line in log.splitlines() if '_PASS' in line])
    except Exception as error:
        report['Error']=type(error).__name__+': '+str(error)
    finally:
        report['SourceDrift']=[name for name,wanted in hashes.items() if sha(ROOT/name)!=wanted]
        report['GeneratedDrift']=[name for name,wanted in generated_hashes.items() if sha(WORK/name)!=wanted]
        report['Passed']=report['Passed'] and not report['SourceDrift'] and not report['GeneratedDrift']
        report['EndedUTC']=datetime.now(timezone.utc).isoformat()
        report['ElapsedSeconds']=round(time.monotonic()-started,3)
        report['EvidenceSHA256']={p.name:sha(p) for p in WORK.iterdir() if p.is_file() and p.suffix in ('.py','.sv','.hex','.log','.csv','.json')}
        with (WORK/'simulation-result.json').open('x',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report.get(key) for key in ('Passed','Error','ElapsedSeconds','SourceDrift','GeneratedDrift','IndependentWireTelemetryRowsVerified')}))
    return 0 if report['Passed'] else 1

if __name__=='__main__':raise SystemExit(main())
