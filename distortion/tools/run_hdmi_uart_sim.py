"""Exercise real UART wire bytes or real HDMI I2C transactions offline."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import struct
import time
import zlib

from simulation_tools import resolve_vivado_bin
from run_gamma_pipeline_d5_sim import tool
from run_ms72xx_checked_sim import command_rows, validate_wire_trace
from hdmi_status import FrameParser

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'build/hdmi-uart-diagnostic'
COMPILE={
    'uart': ('rtl/uart_tx.v','rtl/experimental/hdmi_diag_uart.v','tests/tb_hdmi_diag_uart.sv'),
    'uart-v2': ('rtl/uart_tx.v','rtl/experimental/hdmi_diag_uart_v2.v','tests/tb_hdmi_diag_uart_v2.sv'),
    'uart-v3': ('rtl/uart_tx.v','rtl/experimental/hdmi_diag_uart_v3.v','tests/tb_hdmi_diag_uart_v3.sv'),
    'i2c': ('rtl/experimental/ms7200_1080p30_ctl.v','rtl/experimental/ms7210_checked_ctl.v',
            'rtl/experimental/ms72xx_observed_ctl.v','rtl/experimental/iic_dri_checked.v',
            'tests/tb_ms72xx_observed_e2e.sv'),
}
HELPERS=('tools/run_hdmi_uart_sim.py','tools/hdmi_status.py','tools/run_ms72xx_checked_sim.py',
         'tools/run_gamma_pipeline_d5_sim.py','tools/simulation_tools.py')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def decode_versioned_wire(raw, version):
    """Validate v2/v3 wire frames independently of the production parser."""
    if version not in (2,3):
        raise ValueError('only explicit UART extension versions 2 and 3 are supported')
    label=f'v{version}'
    if not raw or len(raw) % 64:
        raise ValueError(label+' wire evidence is empty or ends with a partial frame')
    frames=[]
    for offset in range(0,len(raw),64):
        packet=raw[offset:offset+64]
        if packet[:8]!=b'PGHDMI01' or packet[60:]!=b'HM01':
            raise ValueError(f'{label} packet {offset//64}: magic or trailer differs')
        if zlib.crc32(packet[:56])!=struct.unpack_from('<I',packet,56)[0]:
            raise ValueError(f'{label} packet {offset//64}: CRC differs')
        if struct.unpack_from('<I',packet,48)[0]!=0x48444900+version:
            raise ValueError(f'{label} packet {offset//64}: build tag differs')
        flags=struct.unpack_from('<H',packet,16)[0]
        extension_reserved=(packet[53:56]!=bytes(3)) if version==2 else packet[55]!=0
        if flags&0xE000 or packet[18]&0xF0 or packet[47]&~3 or packet[52]&0xE0 or extension_reserved:
            raise ValueError(f'{label} packet {offset//64}: reserved fields are nonzero')
        sequence=struct.unpack_from('<I',packet,8)[0]
        if frames and sequence!=((frames[-1]['sequence']+1)&0xFFFFFFFF):
            raise ValueError(f'{label} packet {offset//64}: sequence is not contiguous')
        frame={
            'sequence':sequence,
            'reference_ticks':struct.unpack_from('<I',packet,12)[0],
            'flags':flags,
            'input_fault':packet[19],
            'width':struct.unpack_from('<H',packet,20)[0],
            'height':struct.unpack_from('<H',packet,22)[0],
            'pclk_edges':struct.unpack_from('<I',packet,24)[0],
            'observer_freshness':packet[52]&0x1F,
        }
        if version==3:
            frame['vs_edge_count_ref']=struct.unpack_from('<H',packet,53)[0]
        frames.append(frame)
    return frames


def decode_v2_wire(raw):
    return decode_versioned_wire(raw,2)


def decode_v3_wire(raw):
    return decode_versioned_wire(raw,3)


def run(work,kind,maximum_seconds=240):
    work=Path(work).resolve()
    if work.parent!=BASE.resolve() or not work.is_dir() or any(work.iterdir()):
        raise ValueError('fresh empty child of build/hdmi-uart-diagnostic required')
    sources=COMPILE[kind]
    hashes={s:sha(ROOT/s) for s in (*sources,*HELPERS)}
    if kind=='i2c':
        for name,source,count in (('rx_expected.hex',sources[0],311),('tx_expected.hex',sources[1],49)):
            (work/name).write_text('\n'.join(command_rows(ROOT/source,count))+'\n',encoding='ascii')
    top=('tb_hdmi_diag_uart' if kind=='uart' else
         'tb_hdmi_diag_uart_v2' if kind=='uart-v2' else
         'tb_hdmi_diag_uart_v3' if kind=='uart-v3' else 'tb_ms72xx_observed_e2e')
    marker=('PASS hdmi_diag_uart' if kind=='uart' else
            'PASS hdmi_diag_uart_v2' if kind=='uart-v2' else
            'PASS hdmi_diag_uart_v3' if kind=='uart-v3' else 'MS72XX_OBSERVED_E2E_SIM_PASS')
    report={'Schema':'hdmi-diagnostic-simulation-v1','Kind':kind,'Passed':False,
            'StartedUTC':datetime.now(timezone.utc).isoformat(),'SourceSHA256':hashes,
            'Commands':[],'HardwareAccessed':False,'PDSAccessed':False,
            'HardwareReleaseAllowed':False,
            'Limits':'Actual UART or I2C wire RTL with synthetic device/monitor inputs. No PHY lock, real HDMI input, board output or optical acceptance.'}
    deadline=time.monotonic()+maximum_seconds
    try:
        bin_dir=resolve_vivado_bin(ROOT.parent)
        for name,args,stage in (
            ('xvlog.bat',['--sv',*[str(ROOT/s) for s in sources]],'compile'),
            ('xelab.bat',[top,'-s','hdmi_diag_tb'],'elaborate'),
            ('xsim.bat',['hdmi_diag_tb','-runall','-log','simulation.log'],'simulate'),
        ):
            row={'Stage':stage,'Argv':[str(bin_dir/name),*args],'ReturnCode':None}
            report['Commands'].append(row)
            tool(bin_dir,name,args,work,deadline,stage)
            row['ReturnCode']=0
        log=(work/'simulation.log').read_text(encoding='utf-8',errors='replace')
        if marker not in log or re.search(r'(?im)^\s*(?:fatal|error):',log):
            raise ValueError('testbench did not finish all assertions')
        if kind=='i2c':
            report['WireTraceAudit']=validate_wire_trace(work/'wire-transactions.csv')
            summary=json.loads((work/'summary.json').read_text(encoding='utf-8'))
            if (summary.get('TelemetryComparedToWire') is not True or
                summary.get('SuccessfulTelemetryUpdates')!=2112 or summary.get('NACKTelemetrySuppressed')!=5):
                raise ValueError('successful/NACK telemetry coverage differs')
            report['Summary']=summary
        elif kind in ('uart-v2','uart-v3'):
            raw=(work/'hdmi-status-wire.bin').read_bytes()
            frames=decode_versioned_wire(raw,2 if kind=='uart-v2' else 3)
            if len(frames)<4:
                raise ValueError('too few independently decoded versioned UART packets')
            parser=FrameParser()
            primary=parser.feed(raw)
            if len(primary)!=len(frames) or parser.rejected or parser.buffer:
                raise ValueError('production parser differs from independent wire frame inventory')
            for independent,parsed in zip(frames,primary):
                for name,value in independent.items():
                    key='monitor_freshness_mask' if name=='observer_freshness' else name
                    if parsed.get(key)!=value:
                        raise ValueError('production parser differs from raw wire field: '+name)
            report['UARTPackets']={
                'Count':len(frames),'Rejected':0,'NoiseBytes':0,'ResidualBytes':0,
                'WireSHA256':sha(work/'hdmi-status-wire.bin'),'Records':frames,
            }
            report['CaseLines']=[s for s in log.splitlines() if s.startswith('HDMI_UART_CASE ')]
        else:
            parser=FrameParser()
            raw=(work/'hdmi-status-wire.bin').read_bytes()
            frames=[]
            for n in range(0,len(raw),17): frames.extend(parser.feed(raw[n:n+17]))
            if len(frames)<4:
                raise ValueError('too few complete independently decoded UART packets')
            report['UARTPackets']={
                'Count':len(frames),'Rejected':parser.rejected,'NoiseBytes':parser.noise_bytes,
                'States':sorted(set(p['state'] for p in frames)),
                'ErrorCounts':dict(parser.error_counts),'ResidualBytes':len(parser.buffer),
                'WireSHA256':sha(work/'hdmi-status-wire.bin'),
                'Records':frames,
            }
            report['CaseLines']=[s for s in log.splitlines() if s.startswith('HDMI_UART_CASE ')]
        report['Passed']=True
    except (Exception,KeyboardInterrupt) as error:
        report['Error']=f'{type(error).__name__}: {error}'
    finally:
        report['SourceDrift']=[s for s,h in hashes.items() if sha(ROOT/s)!=h]
        report['Passed']=report['Passed'] and not report['SourceDrift']
        report['EndedUTC']=datetime.now(timezone.utc).isoformat()
        report['EvidenceSHA256']={p.name:sha(p) for p in work.iterdir() if p.is_file() and p.suffix in ('.log','.bin','.csv','.json','.hex')}
        (work/'simulation-result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workdir',type=Path,required=True)
    p.add_argument('--kind',choices=tuple(COMPILE),required=True)
    args=p.parse_args()
    report=run(args.workdir,args.kind)
    print(json.dumps({'Passed':report['Passed'],'Error':report.get('Error'),'Work':str(args.workdir)}))
    raise SystemExit(0 if report['Passed'] else 1)
