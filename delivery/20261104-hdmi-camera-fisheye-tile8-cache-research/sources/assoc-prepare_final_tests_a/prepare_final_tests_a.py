"""Reproduce final unit and old collision adaptations; never invoke a simulator."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] / 'distortion'


def save_identical(path, text):
    data = text.encode('utf-8')
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('refuse overwriting different generated test: ' + str(path))
    else:
        with path.open('xb') as stream:
            stream.write(data)
    return hashlib.sha256(data).hexdigest()


def main():
    text = (HERE / 'tests/tb_assoc2_cache_a.sv').read_text()
    marker = 'query(q+2,0,q*3,q*7,200+q);'
    if text.count(marker) != 1:
        raise ValueError('original intended fractional prewarm anchor differs')
    text = text.replace(marker, 'query(q+2,0,(q*3)&255,(q*7)&255,200+q);')
    result = {'BenchSHA256': save_identical(HERE / 'tests/tb_assoc2_cache_b.sv', text)}
    runner = (HERE / 'run_unit_a.py').read_text()
    runner = runner.replace('ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_a.v', 'ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_b.v')
    runner = runner.replace('tb_assoc2_cache_a.sv', 'tb_assoc2_cache_b.sv')
    marker = "        cases[suffix] = {**value, 'IndependentTrace': trace}"
    if runner.count(marker) != 1:
        raise ValueError('unit validator insertion anchor differs')
    runner = runner.replace(marker, r"""        rows = re.findall(r'ASSOC_ORACLE WIDTH(\d+) INDEX(\d+) checks(\d+) fillways(\d+)/(\d+) fastway1(\d+) invalid(\d+)/(\d+) lru(\d+)/(\d+)', log)
        actual = [tuple(map(int,row)) for row in rows if int(row[0])==width and int(row[1])==index]
        require(len(actual)==1 and all(n>0 for n in actual[0][2:]), 'both ways / invalid priorities / BOTH LRU victim directions must execute')
        fields=('Width','IndexBits','SlowOracleChecks','Way0Fills','Way1Fills','FastWay1Touches','InvalidWay0Choices','InvalidWay1Choices','LRUVictimWay0Choices','LRUVictimWay1Choices')
        cases[suffix] = {**value, 'IndependentTrace': trace, 'AssociativeOracle':dict(zip(fields,actual[0]))}""")
    result['RunnerSHA256'] = save_identical(HERE / 'run_unit_c.py', runner)
    boundary = (ROOT / 'tests/tb_directfill_tagpipe_commit_collision.sv').read_text()
    if boundary.count('.INDEX_BITS(9)') != 1:
        raise ValueError('original boundary INDEX_BITS anchor differs')
    boundary = boundary.replace('.INDEX_BITS(9)', '.INDEX_BITS(10)').replace('\\"IndexBits\\":9', '\\"IndexBits\\":10')
    result['BoundaryBenchSHA256'] = save_identical(HERE / 'tests/tb_assoc2_commit_collision_a.sv', boundary)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
