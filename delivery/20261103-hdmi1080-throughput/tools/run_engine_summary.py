"""Validate four source-bound engine reports and publish comparable RTL metrics."""
from pathlib import Path
import argparse
import hashlib
import json


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summarize(reports, output):
    rows={}
    for path in reports:
        path=path.resolve();r=json.loads(path.read_text())
        if not r.get('passed') or r.get('source_drift') or not r['metrics'].get('passed'):
            raise ValueError('Unsuccessful input report: '+str(path))
        if r['variant'] in rows:raise ValueError('Duplicate variant')
        for name,digest in r['file_sha256'].items():
            # Runtime tooling may append webtalk housekeeping after xsim exits.
            # Test vectors, exact output, and simulator evidence must stay bound.
            if name in ('expected.mem','masks.mem','engine_config.vh','output.mem','engine-summary.json','compile.log','elaborate.log','simulate.log','simulation.log'):
                if sha(path.parent/name)!=digest:raise ValueError('Evidence changed: '+name)
        if sha(path.parent/'output.mem')!=r['output_sha256']:raise ValueError('Output hash changed')
        rows[r['variant']]=(path,r)
    if set(rows)!=set(('baseline','writer','cache','both')):raise ValueError('All four variants required')
    base=rows['baseline'][1]
    summary={'passed':True,'scope':'Isolated pure-correction RTL engine; deterministic behavioral DDR with pressure',
             'hardware_verified':False,'capture_display_arbitration_modeled':False,
             'core_clock_for_conversion_hz':125000000,'width':base['width'],'height':base['height'],
             'output_sha256':base['output_sha256'],'expected_crc32':base['fixtures']['expected_crc32'],
             'variants':{}}
    for variant,(path,r) in rows.items():
        for key in ('width','height','fixtures','output_sha256'):
            if r[key]!=base[key]:raise ValueError('Input/golden/output differ: '+key)
        for key in ('expected.mem','masks.mem'):
            if r['file_sha256'][key]!=base['file_sha256'][key]:raise ValueError('Different vector '+key)
        m=r['metrics']
        if m['pixels']!=r['width']*r['height'] or m['crc32']!=summary['expected_crc32']:
            raise ValueError('Incomplete pixel or CRC comparison')
        if m['pressure']!=base['metrics']['pressure'] or m['fills']!=base['metrics']['fills']:
            raise ValueError('Different pressure or source-fill workload')
        summary['variants'][variant]={**m,'cycle_reduction_percent':100*(1-m['cycles']/base['metrics']['cycles']),
            'processing_capacity_gain_percent':100*(base['metrics']['cycles']/m['cycles']-1),
            'report_path':str(path),'report_sha256':sha(path)}
    if output.exists():raise FileExistsError('Use a new summary path')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('reports',type=Path,nargs=4)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();summarize(a.reports,a.output)
