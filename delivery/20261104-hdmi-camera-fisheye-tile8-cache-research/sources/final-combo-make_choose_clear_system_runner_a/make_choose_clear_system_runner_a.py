"""Derive only the FRAME_CLEAR cache small-system A/B from CHOOSE control."""
import argparse
import hashlib
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'assoc2way256-choose-a/run_choose_system_a.py'
BASE_SHA='16bb659bd79dc30a9234449800252a38c1cc7140150d351fd3dada128f2dd392'
OLD_CACHE='ea561f9e487e1f03141f13139a8f7ccbb338c2b8e256a4ca81ed73298e6e69d1'
NEW_CACHE='62225f2694f1c7441ec8c37b219d20643fce5b3847897d4ec590d3a306a4d728'

def main():
    parser=argparse.ArgumentParser()
    for name in ('unit-sha','boundary-sha','unit-schema','boundary-schema'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    data=BASE.read_bytes()
    assert hashlib.sha256(data).hexdigest()==BASE_SHA
    text=data.decode()
    def replace(old,new):
        nonlocal text
        assert text.count(old)==1,repr(old)
        text=text.replace(old,new)
    replace(text[:text.index('import argparse')],
        '"""FRAME_CLEAR-only cache A/B against the completed CHOOSE small systems.\n'
        'The candidate adds a registered clear boundary after drained frame admission.\n'
        'Common reset and every original system assertion remain unchanged.\n"""\n')
    replace("'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_choose_a.v'",
            "'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_choose_clear_a.v'")
    replace('a3353523c7a8b4629a901622c645ba3b96725eff596c46aafd5a459e6796ffce',args.unit_sha)
    replace('c3c5d3e0d37f1e55bf4adebfd0ef0ab0c86690adbb91ca3baf9e2cf95fb40361',args.boundary_sha)
    replace("UNIT: 'tile8-assoc2-choose-tagpipe-independent-cache-simulation-v1'","UNIT: "+repr(args.unit_schema))
    replace("BOUNDARY: 'tile8-assoc2-choose-tagpipe-independent-boundary-simulation-v1'","BOUNDARY: "+repr(args.boundary_schema))
    replace("SCHEMA = 'tile8-assoc2way256-choose-research-system-simulation-v1'",
            "SCHEMA = 'tile8-assoc2way256-choose-clear-research-system-simulation-v1'")
    replace("CONTRACT_SCHEMA = 'tile8-assoc2way256-choose-system-source-contract-v1'",
            "CONTRACT_SCHEMA = 'tile8-assoc2way256-choose-clear-system-source-contract-v1'")
    # New candidate identity is used in both its gate pin and the A/B checker.
    assert text.count(OLD_CACHE)==2
    text=text.replace(OLD_CACHE,NEW_CACHE)
    replace("old_work = FIFO_BASE / ('system-' + kind + '-small-a')",
            "old_work = HERE.parent / 'assoc2way256-choose-a' / ('system-' + kind + '-small-a')")
    replace("value.get('Schema') == 'tile8-assoc2way256-fifo-research-system-simulation-v1'",
            "value.get('Schema') == 'tile8-assoc2way256-choose-research-system-simulation-v1'")
    replace("sha(original) == '745f4f2cbc26f733d991eca2998484542a131c47f2d747504194f8ecaca95f0b'",
            "sha(original) == "+repr(OLD_CACHE))
    replace("'PriorFIFOSmallABReference': ab_ref", "'PriorCHOOSESmallABReference': ab_ref")
    replace("'EngineChange': 'FIFO d17 identical to A-B control; cache alone adds registered slow-way CHOOSE',",
            "'EngineChange': 'FIFO d17 identical; CHOOSE cache adds a one-cycle frame-clear boundary',")
    replace("'Limits': 'Only the CHOOSE cache differs from the completed FIFO small control; engine, configuration, bench, headers, fixtures and all original assertions remain identical. CHOOSE costs one cycle per in-bounds slow neighbour, at most about 0.6ms on the prior full trace; small results are not native performance, STA or board FPS.'",
            "'Limits': 'Only FRAME_CLEAR cache bytes differ from completed CHOOSE small control. External FIFO admission remains closed until the private clear edge. Standard ready/valid accepts a later continuously asserted request as a new transaction when ready returns. Common reset, engine, fixtures and all system assertions remain unchanged. Small results are not native performance, STA or board FPS.'")
    text=text.replace('CHOOSE A-B','FRAME_CLEAR A-B').replace('CHOOSE control','FRAME_CLEAR control')
    text=text.replace('only registered slow-way choice cache bytes','only registered frame clear cache bytes')
    replace("snapshot = 'assoc2way256_choose_'", "snapshot = 'assoc2way256_choose_clear_'")
    with (HERE/'run_choose_clear_system_a.py').open('xb') as stream:stream.write(text.encode())
    print(hashlib.sha256(text.encode()).hexdigest())

if __name__=='__main__':main()
