"""Remove only a syntactically unreachable legacy state from experiment c."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def main():
    source = HERE / 'combined-cache-probe-c.v'
    pin = '2828700483c478688cddf249608456f4f1253c5091687c11accc98a833b2df6e'
    if hashlib.sha256(source.read_bytes()).hexdigest() != pin:
        raise ValueError('independently unit-checked c source differs')
    text = source.read_text()
    code = re.sub(r'//[^\n]*|/\*[\s\S]*?\*/', '', text)
    assignments = re.findall(r'\bstate\s*<=\s*([^;]+);', code)
    if not assignments or any(re.search(r'\bSELECT\b', value) for value in assignments):
        raise ValueError('SELECT still has an incoming state assignment')
    if not re.search(r'if\(!rst_n\)begin\s*state<=IDLE;', code):
        raise ValueError('required reset IDLE proof differs')
    changes = []

    def replace(old, new, role):
        nonlocal text
        if text.count(old) != 1:
            raise ValueError('exact unique transformation required: ' + role)
        text = text.replace(old, new)
        changes.append(role)

    start = text.index('                SELECT:begin')
    end = text.index('                CHECK:begin', start)
    dead_case = text[start:end]
    replace(dead_case, '', 'remove SELECT case with no incoming reachable edge')
    replace('    reg signed [16:0] slow_x,slow_y;\n', '', 'remove private legacy coordinate registers')
    replace('slow_x<=0;slow_y<=0;', '', 'remove reset writes to deleted private registers')
    replace('                        slow_x<=query_x;slow_y<=query_y;\n', '', 'remove writes used only by deleted state')
    start = text.index('    wire signed [16:0] nx=')
    end = text.index('    function [23:0] expand565', start)
    arithmetic = text[start:end]
    if not all(token in arithmetic for token in ('slow_x', 'slow_y', 'neighbour_in_bounds', 'selected_number')):
        raise ValueError('unexpected legacy arithmetic section')
    replace(arithmetic, '', 'remove legacy row multiply/add and bounds feeding only SELECT')
    remaining = re.sub(r'//[^\n]*|/\*[\s\S]*?\*/', '', text)
    if re.search(r'\b(slow_x|slow_y|neighbour_in_bounds|selected_number)\b', remaining):
        raise ValueError('deleted legacy arithmetic still has references')
    if re.findall(r'\bstate\s*<=\s*([^;]+);', remaining) != assignments:
        # The deleted unreachable state's outgoing edges are intentionally absent.
        code_start = code.index('                SELECT:begin')
        code_end = code.index('                CHECK:begin', code_start)
        old_live = code[:code_start] + code[code_end:]
        if re.findall(r'\bstate\s*<=\s*([^;]+);', remaining) != re.findall(r'\bstate\s*<=\s*([^;]+);', old_live):
            raise ValueError('reachable-state assignments changed')
    destination = HERE / 'dead-select-probe-d.v'
    with destination.open('x', encoding='utf-8', newline='\n') as target:
        target.write(text)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    result = {'Schema': 'tile8-unreachable-select-elimination-source-v1', 'ExperimentalOnly': True,
              'Parent': {'Path': str(source), 'SHA256': pin},
              'Variant': {'Path': str(destination), 'SHA256': digest},
              'StateAssignmentRHSBefore': assignments, 'NoStateAssignmentCanEnterSELECT': True,
              'ResetState': 'IDLE', 'DeletedCaseSHA256': hashlib.sha256(dead_case.encode()).hexdigest(),
              'Changes': changes, 'NoReachableProtocolOrCycleChangeIntended': True,
              'ArbitraryVerilogEquivalenceProved': False, 'NativeEDAExecuted': False, 'HardwareAccessed': False}
    with (HERE / 'dead-select-probe-source-d.json').open('x', encoding='utf-8') as target:
        json.dump(result, target, indent=2); target.write('\n')
    unit = (HERE / 'run_combined_cache_unit_c.py').read_text()
    unit = unit.replace('combined-cache-probe-c.v', destination.name).replace('combined-cache-probe-source-c.json', 'dead-select-probe-source-d.json')
    unit = unit.replace('tile8-combined-slow-bulk-unit-experiment-v1', 'tile8-dead-select-unit-experiment-v1').replace('combined_unit_c', 'dead_select_unit_d')
    with (HERE / 'run_dead_select_unit_d.py').open('x', encoding='utf-8', newline='\n') as target:
        target.write(unit)
    system = (HERE / 'run_combined_system_probe_c.py').read_text()
    system = system.replace('combined-cache-probe-c.v', destination.name).replace(pin, digest)
    system = system.replace('combined-unit-c/simulation.json', 'dead-select-unit-d/simulation.json')
    system = system.replace("'combined-'", "'dead-select-'").replace("'-c'", "'-d'")
    system = system.replace('tile8-combined-cache-full-system-experiment-v1', 'tile8-dead-select-full-system-experiment-v1')
    with (HERE / 'run_dead_select_system_d.py').open('x', encoding='utf-8', newline='\n') as target:
        target.write(system)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
