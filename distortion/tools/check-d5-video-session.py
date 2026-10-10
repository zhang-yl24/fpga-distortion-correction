"""Accept saved corrected-Gamma serial evidence without opening hardware."""
from pathlib import Path
import hashlib,json,importlib.util,re
ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/'results/lab-20261008'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
spec=importlib.util.spec_from_file_location('rotation_metrics',ROOT/'tools/analyze-rotation-telemetry.py')
metrics=importlib.util.module_from_spec(spec);spec.loader.exec_module(metrics)
def canonical_angles(lines):
    """Treat accumulator values just below a full turn as zero, keeping raw evidence."""
    raw=[]
    for line in lines:
        matches=re.findall(r'\bRA=([0-9A-Fa-f]+)\b',line)
        if len(matches)!=1:raise ValueError('Missing or duplicate completed angle')
        phase=int(matches[0],16)
        if not 0<=phase<1<<32:raise ValueError('Phase exceeds 32 bits')
        raw.append(phase*360/(1<<32))
    canonical=[]
    for angle in raw:
        nearest=(round(angle/30)*30)%360
        error=abs((angle-nearest+180)%360-180)
        if error>0.0001:raise ValueError('Completed angle outside expected 30-degree steps')
        canonical.append(nearest)
    if sorted(set(canonical))!=list(range(0,360,30)):raise ValueError('Missing completed result angles')
    return raw,sorted(set(canonical))

def main():
    tx=read(LAB/'d5-video-auto-transaction.json')
    if not tx['acknowledged'] or tx.get('error') or tx['writes']!=1 or tx['idle_return_code']!=0:raise ValueError('Live transaction failed')
    if tx['opcode']!=2 or tx['argument']!='00000001':raise ValueError('Not automatic rotation')
    timed={'StartedUtc':tx['acknowledged_at_utc'],'Samples':[{'ReceivedUtc':row['received_utc'],'Line':row['line']} for row in tx['observations']]}
    result=metrics.analyze(timed,warmup=0)
    raw,canonical=canonical_angles([row['line'] for row in tx['observations']])
    result['raw_completed_angles_deg']=raw
    result['canonical_result_angles_deg']=canonical
    result['angle_normalization_tolerance_deg']=0.0001
    build=read(ROOT/'build/corrected_gamma_d5/validated-build.json')
    if sha(Path(build['Bitstream']))!=build['SHA256']:raise ValueError('Corrected Gamma bitstream changed')
    proofs=sorted((ROOT/'build/corrected_gamma_d5').glob('program-evidence-*/transfer.json'),key=lambda p:p.stat().st_mtime)
    transfer=read(proofs[-1])
    if not transfer['Done'] or transfer['Target']!='corrected_gamma_d5' or transfer['SHA256']!=build['SHA256']:raise ValueError('Corrected live transfer not verified')
    status=read(ROOT/'status.json')
    if status['current_sram_target']!='heartbeat':raise ValueError('Current board not idle')
    idle_paths=sorted((ROOT/'build/heartbeat').glob('program-evidence-*/transfer.json'),key=lambda p:p.stat().st_mtime)
    idle=read(idle_paths[-1])
    if not idle['Done'] or idle['CheckedOn']!=status['current_connection']['checked_on']:raise ValueError('Fresh idle transfer missing')
    result.update(target='corrected_gamma_d5',capture_transfer=transfer,idle_transfer=idle,
        transaction_sha256=sha(LAB/'d5-video-auto-transaction.json'),hardware_accessed_by_checker=False,
        visual_observation_available=False,source_sha256={'tools/check-d5-video-session.py':sha(Path(__file__)),
            'tools/analyze-rotation-telemetry.py':sha(ROOT/'tools/analyze-rotation-telemetry.py')})
    (LAB/'d5-video-check.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('passed','observed_result_angles_deg','approx_rates_per_second','temperature_celsius_range','max_process_ms_at_125mhz')}))

if __name__=='__main__':main()
