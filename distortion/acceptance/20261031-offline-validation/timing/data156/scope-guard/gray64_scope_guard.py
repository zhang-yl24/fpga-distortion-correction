"""Strict static validator for this fixed, source-bound Gray constraint set.

Only exact anchored bit alternations or already-expanded native member lists are
accepted. General regexes/globs are rejected rather than evaluated in a partial
universe. This module does not invoke PDS or alter constraints.
"""
from collections import Counter
from decimal import Decimal
import re

WIDTHS = {'edge': 32, 'vs': 16, 'href': 16}
BUDGET = Decimal('6.657789500')

def pin_members(group, stage, bits):
    return [f'input_status/geometry/{group}_{stage}[{WIDTHS[group]-1}:0]/D[{b}]' for b in bits]

def resolve_target(group, descriptor):
    cell = f'input_status/geometry/{group}_meta[{WIDTHS[group]-1}:0]'
    kind = descriptor['kind']
    if kind == 'exact_bit_regex':
        value = descriptor['value']
        prefix, suffix = '^' + re.escape(cell) + r'/D\[', r'\]$'
        assert value.startswith(prefix) and value.endswith(suffix), 'Not an exact first-stage bit selector'
        inner = value[len(prefix):-len(suffix)]
        if inner.startswith('(') and inner.endswith(')'): inner = inner[1:-1]
        terms = inner.split('|')
        assert terms and all(re.fullmatch(r'0|[1-9][0-9]*', t) for t in terms), 'Unsupported or broad regex syntax'
        bits = [int(t) for t in terms]
        assert len(bits) == len(set(bits)), 'Duplicate selector bit'
        assert all(0 <= b < WIDTHS[group] for b in bits), 'Selector bit outside packed width'
        return set(pin_members(group, 'meta', bits))
    assert kind == 'expanded_native_members', 'Unsupported collection representation'
    members = descriptor['members']
    assert members and len(members) == len(set(members)), 'Missing or duplicate expanded members'
    for member in members:
        m = re.fullmatch(re.escape(cell) + r'/D\[(\d+)\]', member)
        assert m and 0 <= int(m.group(1)) < WIDTHS[group], 'Expanded member outside exact first-stage scope'
    return set(members)

def extract_collection(text):
    # This is the exact syntax already serialized by the current PDS Map DMR.
    m = re.fullmatch(r'\[get_pins -hierarchical -hsc (?:/|\{/\}) -regexp \{([^}]+)\}\]', text.strip())
    assert m, 'Unexpected native collection syntax; do not guess'
    return m.group(1)

def parse_constraint(line):
    front, rest = line.strip().split(' -from ', 1)
    source, target = rest.split(' -to ', 1)
    fields = front.split()
    assert fields[0] in ('set_max_delay', 'set_max_skew')
    assert Decimal(fields[1]) == BUDGET, 'Changed timing budget'
    assert fields[2:] == (['-datapath_only'] if fields[0] == 'set_max_delay' else []), 'Changed timing options'
    source_pattern = extract_collection(source)
    matches = [g for g, n in WIDTHS.items() if source_pattern == '^' + re.escape(f'input_status/geometry/{g}_gray[{n-1}:0]/CLK') + '$']
    assert len(matches) == 1, 'Changed or broad source CLK selector'
    g = matches[0]
    descriptor = {'kind': 'exact_bit_regex', 'value': extract_collection(target)}
    return {'command': fields[0], 'group': g, 'members': resolve_target(g, descriptor), 'source_regex': source_pattern, 'target_descriptor': descriptor}

def validate_constraints(lines):
    assert len(lines) == 67, 'Expected exactly64 max and3 skew statements'
    records = [parse_constraint(line) for line in lines]
    scope = []
    for group, width in WIDTHS.items():
        expected = set(pin_members(group, 'meta', range(width)))
        maxima = [r for r in records if r['group'] == group and r['command'] == 'set_max_delay']
        skew = [r for r in records if r['group'] == group and r['command'] == 'set_max_skew']
        assert len(maxima) == width and len(skew) == 1, 'Wrong group command count'
        assert all(len(r['members']) == 1 for r in maxima), 'Scalar max selector became a group'
        counter = Counter(m for r in maxima for m in r['members'])
        assert set(counter) == expected and all(n == 1 for n in counter.values()), 'Missing/duplicate/wrong max member'
        assert skew[0]['members'] == expected, 'Missing/extra skew member'
        second = set(pin_members(group, 'sync', range(width)))
        assert not expected & second and all('/D[' in p for p in expected)
        scope.append({'group': group, 'bits': width, 'max_statements': len(maxima), 'skew_statements': 1, 'target_members': sorted(expected), 'second_stage_and_RS_intersection': 0})
    return scope
