"""Narrow extension of the tested Gray64 guard; normal-FDC logical FF D only."""
from collections import Counter
from decimal import Decimal
import re
from gray64_scope_guard import validate_constraints as validate_gray, extract_collection

def canonical(line):
    return ' '.join(line.replace('-hsc {/}', '-hsc /').split())

def validate_data156(lines, snapshot_bits, expected_lines):
    assert len(lines) == len(expected_lines) == 159
    assert Counter(map(canonical, lines)) == Counter(map(canonical, expected_lines)), 'Mapped source/target/value/options changed'
    gray, held = [], []
    for line in lines:
        if '/held_snapshot' in line: held.append(line)
        else: gray.append(line)
    assert len(gray) == 67 and len(held) == 92
    gray_scope = validate_gray(gray)
    seen = []
    for line in held:
        front, rest = line.strip().split(' -from ', 1)
        source, target = rest.split(' -to ', 1)
        fields = front.split()
        assert fields[0] == 'set_max_delay' and Decimal(fields[1]) == Decimal('18.518518500')
        assert fields[2:] == ['-datapath_only']
        src = extract_collection(source); dst = extract_collection(target)
        assert src == r'^input_status/geometry/held_snapshot\[104:0\]/CLK$'
        prefix, suffix = r'^input_status/geometry/ref_snapshot\[104:0\]/D\[', r'\]$'
        assert dst.startswith(prefix) and dst.endswith(suffix)
        bit = dst[len(prefix):-len(suffix)]
        assert re.fullmatch(r'0|[1-9][0-9]*', bit), 'No group/wildcard/non-data target'
        seen.append(int(bit))
    assert len(seen) == len(set(seen)) == 92 and set(seen) == set(snapshot_bits)
    assert len(set(snapshot_bits)) == 92
    return {'Gray': gray_scope, 'snapshot92': {'bits': sorted(seen), 'max_statements': 92, 'source_CLK': 'input_status/geometry/held_snapshot[104:0]/CLK', 'logical_capture_D_only': True}, 'max_statements': 156, 'skew_statements': 3}
