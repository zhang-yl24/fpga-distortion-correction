"""Derive an isolated small-system runner from the frozen FIFO control."""
import argparse
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent/'assoc2way256-fifo-a/run_fifo_system_a.py'
BASE_SHA = 'ba5707'
OLD_CACHE = '745f4f2cbc26f733d991eca2998484542a131c47f2d747504194f8ecaca95f0b'
NEW_CACHE = 'ea561f9e487e1f03141f13139a8f7ccbb338c2b8e256a4ca81ed73298e6e69d1'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--base-sha',required=True)
    p.add_argument('--unit-sha',required=True)
    p.add_argument('--boundary-sha',required=True)
    p.add_argument('--unit-schema',required=True)
    p.add_argument('--boundary-schema',required=True)
    args=p.parse_args()
    data=BASE.read_bytes()
    assert hashlib.sha256(data).hexdigest()==args.base_sha
    text=data.decode()
    text=text.replace(text[:text.index('import argparse')],
        '"""CHOOSE-only cache A/B against the completed FIFO small-system control.\n'
        'Only registered slow-way choice differs; all original CRC, reset, ownership\n'
        'and drain assertions remain. This runner permits small simulations only.\n"""\n')
    def replace(old,new):
        nonlocal text
        assert text.count(old)==1,repr(old)
        text=text.replace(old,new)
    replace("SOURCE = ASSOC_BASE / 'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_b.v'",
            "SOURCE = HERE / 'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_choose_a.v'")
    replace("UNIT = ASSOC_BASE / 'unit-c/simulation.json'", "UNIT = HERE / 'unit-a/simulation.json'")
    replace("BOUNDARY = ASSOC_BASE / 'boundary-a/simulation.json'", "BOUNDARY = HERE / 'boundary-a/simulation.json'")
    replace("FIFO_UNIT = HERE / 'unit-a/simulation.json'", "FIFO_BASE = HERE.parent / 'assoc2way256-fifo-a'\nFIFO_UNIT = FIFO_BASE / 'unit-a/simulation.json'")
    replace("ENGINE_SOURCE = HERE / 'rtl/hdmi_camera_fisheye_engine_index10_fifo_a.v'",
            "ENGINE_SOURCE = FIFO_BASE / 'rtl/hdmi_camera_fisheye_engine_index10_fifo_a.v'")
    replace(OLD_CACHE,NEW_CACHE)
    replace('1c14772b24377b60c96ad2dd2ff01643e85dd91dcb8fb842bdc6ced3714a3339',args.unit_sha)
    replace('6b4656881c44cec0d60bb53a00919af28fe7873b1b730858058d231164da698f',args.boundary_sha)
    replace("UNIT: 'tile8-assoc2-tagpipe-independent-cache-simulation-v1'", "UNIT: "+repr(args.unit_schema))
    replace("BOUNDARY: 'tile8-assoc2-tagpipe-independent-boundary-simulation-v1'", "BOUNDARY: "+repr(args.boundary_schema))
    replace("SCHEMA = 'tile8-assoc2way256-fifo-research-system-simulation-v1'",
            "SCHEMA = 'tile8-assoc2way256-choose-research-system-simulation-v1'")
    replace("CONTRACT_SCHEMA = 'tile8-assoc2way256-fifo-system-source-contract-v1'",
            "CONTRACT_SCHEMA = 'tile8-assoc2way256-choose-system-source-contract-v1'")
    start=text.index('def bind_ab_reference(')
    end=text.index('\n\ndef run(args):',start)
    text=text[:start]+'''def bind_ab_reference(kind, payloads, work, evidence):
    old_work = FIFO_BASE / ('system-' + kind + '-small-a')
    path = old_work / 'simulation.json'
    value = read(path)
    require(value.get('Schema') == 'tile8-assoc2way256-fifo-research-system-simulation-v1' and
            value.get('Passed') is True and value.get('InputDrift') == [] and
            value.get('Kind') == kind and value.get('Mode') == 'small',
            'actual completed same-engine FIFO small control required')
    evidence.add(path)
    evidence.merge(value['InputSHA256'])
    for name, pin in value['OutputSHA256'].items():
        evidence.add(old_work / name, pin)
    differences = []
    for target, data in payloads.items():
        relative = target.relative_to(work)
        original = old_work / relative
        evidence.add(original)
        if data != original.read_bytes():
            differences.append(relative.as_posix())
            require(relative.as_posix() == 'compiled-sources/' + CACHE and
                    sha(original) == '''+repr(OLD_CACHE)+''' and
                    digest(data) == '''+repr(NEW_CACHE)+''',
                    'unexpected CHOOSE A-B input difference')
    require(differences == ['compiled-sources/' + CACHE],
            'only registered slow-way choice cache bytes may differ from FIFO control')
    return ref(path)
'''+text[end:]
    replace("'PriorAssocSmallABReference': ab_ref, 'OnlyABPreparedDifference': ENGINE,",
            "'PriorFIFOSmallABReference': ab_ref, 'OnlyABPreparedDifference': CACHE,")
    replace("'EngineChange': 'INDEX10 retained; one-entry elastic buffer to two-entry occupancy-only-ready FIFO',",
            "'EngineChange': 'FIFO d17 identical to A-B control; cache alone adds registered slow-way CHOOSE',")
    oldlimits="'Limits': 'Engine result FIFO only differs from the completed assoc2way256 small A-B reference; cache, INDEX10 configuration, bench, headers, fixtures, pixel oracle and all assertions are unchanged. The original INDEX8 cycle comparison is historical context, not this single-variable A-B control. Small 32x16 results prove finite pixel/ownership/reset/drain behavior, not full-1080 performance, STA or board FPS.'"
    replace(oldlimits,"'Limits': 'Only the CHOOSE cache differs from the completed FIFO small control; engine, configuration, bench, headers, fixtures and all original assertions remain identical. CHOOSE costs one cycle per in-bounds slow neighbour, at most about 0.6ms on the prior full trace; small results are not native performance, STA or board FPS.'")
    replace("snapshot = 'assoc2way256_fifo_'", "snapshot = 'assoc2way256_choose_'")
    target=HERE/'run_choose_system_a.py'
    with target.open('xb') as stream:stream.write(text.encode())
    print(hashlib.sha256(text.encode()).hexdigest())

if __name__=='__main__':main()
