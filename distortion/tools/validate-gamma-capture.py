"""Fail closed unless the board candidate matches the completed native regression."""
from pathlib import Path
import hashlib,json,re
ROOT = Path(__file__).resolve().parents[1]
read = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))


def validate():
    check = read(ROOT/'results/lab-20261008/gamma-frozen-native-simulation-check.json')
    if not (check['passed'] and check['shape'] == [480,640] and check['radius_guard'] == 1976439
            and check['uart_packets'] == 9 and check['pixels_compared'] == 2764800 and check['modes'] == [1,2,0]):
        raise ValueError('Full bounded native regression did not pass')
    for name,digest in check['source_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper() != digest:
            raise ValueError(f'Native-validated source changed: {name}')
    work = ROOT/'build/gamma_frozen_native_20261008_sim'
    if Path(check['work_directory'].replace('\\','/')).name != work.name:
        raise ValueError('Unexpected regression directory')
    for name,digest in check['artifacts_sha256'].items():
        if hashlib.sha256((work/name).read_bytes()).hexdigest().upper() != digest:
            raise ValueError(f'Native regression artifact changed: {name}')
    ref = read(work/'reference.json')
    warmup=ROOT/'build/capture_warmup_sim'
    for name,digest in read(warmup/'source-sha256.json').items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper()!=digest:
            raise ValueError(f'Capture warmup source changed: {name}')
    log=(warmup/'simulation.log').read_text()
    if 'PASS capture warmup:' not in log or re.search(r'(?i)fatal:|error:',log):
        raise ValueError('Capture warmup regression did not pass')
    parameters = []
    for bits,value in re.findall(r"=(24|32)'sh([0-9a-fA-F]+);", (ROOT/'board/calibration-trial.vh').read_text()):
        n = int(value,16)
        parameters.append(n-(1<<int(bits)) if n>>(int(bits)-1) else n)
    if parameters != ref['parameters']:
        raise ValueError('Board calibration differs from native regression')
    header = (ROOT/'board/rotation-domain.vh').read_text()
    if not re.search(r"ROT_MAX_R2_Q22\s*=\s*(?:(?:24|32)'sd)?1976439\s*;",header):
        # Existing header uses a hex literal.
        match = re.search(r"ROT_MAX_R2_Q22\s*=\s*(?:24|32)'(?:s)?h([0-9a-fA-F]+)\s*;",header)
        if not match or int(match[1],16) != ref['radius_guard']:
            raise ValueError('Board radius guard differs from native regression')
    print(json.dumps({'passed':True,'native_packets':9,'pixels_compared':2764800,'radius_guard':1976439}))


if __name__ == '__main__':
    validate()
