"""Combine two independently unit-checked slow-path experiments in a fresh RTL."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    parent = HERE / 'decoded-slow-probe-b.v'
    expected = 'f2c16c15c7f73f93d792e63c80494c40b57522885e47c1d0e28cb7ebaaf9c1d2'
    if hashlib.sha256(parent.read_bytes()).hexdigest() != expected:
        raise ValueError('unit-checked decoded-slow source drift')
    text = parent.read_text()
    changes = []

    def replace(old, new, role):
        nonlocal text
        if text.count(old) != 1:
            raise ValueError('exact unique transformation required: ' + role)
        text = text.replace(old, new)
        changes.append(role)

    replace('RESULT=7,FAULT=8,CHECK=9;', 'RESULT=7,FAULT=8,CHECK=9,BULK_CHECK=10,BULK_LOAD=11,BULK_PICK=12;', 'postcommit batch states')
    replace('    wire all_hit=&line_hit;',
            '    wire all_hit=&line_hit;\n    wire [3:0] bulk_line_hit;\n    wire bulk_all_hit=&bulk_line_hit;\n    wire [ADDRESS_BITS-1:0] bulk_pixel_address[0:3];', 'snapshot full-tag resident test')
    replace('        assign pixel_address[n]=pixel_number[n][1 +: ADDRESS_BITS];',
            '        assign pixel_address[n]=pixel_number[n][1 +: ADDRESS_BITS];\n'
            '        assign bulk_pixel_address[n]=slow_number[n][1 +: ADDRESS_BITS];\n'
            '        assign bulk_line_hit[n]=!slow_bounds[n] || (valid_lines[slow_number[n][7 +: INDEX_BITS]] &&\n'
            '            tags[slow_number[n][7 +: INDEX_BITS]]==slow_number[n][31:7]);', 'same-index different-tag fallback')
    replace('    wire read_enable=rst_n && !failed && (accept_fast || state==LOAD || state==CHECK);\n    wire read_lower=rst_n && accept_fast;',
            '    wire bulk_read=state==BULK_LOAD;\n'
            '    wire read_enable=rst_n && !failed && (accept_fast || state==LOAD || state==CHECK || bulk_read);\n'
            '    wire read_lower=rst_n && !failed && (accept_fast || bulk_read);', 'four synchronous RAM ports after commit')
    replace('    wire [ADDRESS_BITS-1:0] even_read_upper=(state==LOAD || state==CHECK) ? selected_pixel_address:even_upper;\n'
            '    wire [ADDRESS_BITS-1:0] odd_read_upper=(state==LOAD || state==CHECK) ? selected_pixel_address:odd_upper;',
            '    wire [ADDRESS_BITS-1:0] bulk_even_upper=slow_number[0][0] ? bulk_pixel_address[1]:bulk_pixel_address[0];\n'
            '    wire [ADDRESS_BITS-1:0] bulk_odd_upper=slow_number[0][0] ? bulk_pixel_address[0]:bulk_pixel_address[1];\n'
            '    wire [ADDRESS_BITS-1:0] bulk_even_lower=slow_number[2][0] ? bulk_pixel_address[3]:bulk_pixel_address[2];\n'
            '    wire [ADDRESS_BITS-1:0] bulk_odd_lower=slow_number[2][0] ? bulk_pixel_address[2]:bulk_pixel_address[3];\n'
            '    wire [ADDRESS_BITS-1:0] even_read_upper=(state==LOAD || state==CHECK) ? selected_pixel_address:bulk_read ? bulk_even_upper:even_upper;\n'
            '    wire [ADDRESS_BITS-1:0] odd_read_upper=(state==LOAD || state==CHECK) ? selected_pixel_address:bulk_read ? bulk_odd_upper:odd_upper;\n'
            '    wire [ADDRESS_BITS-1:0] even_read_lower=bulk_read ? bulk_even_lower:even_lower;\n'
            '    wire [ADDRESS_BITS-1:0] odd_read_lower=bulk_read ? bulk_odd_lower:odd_lower;', 'snapshot parity/address routing')
    replace('write_address_b:even_lower[ADDRESS_BITS-1:2]', 'write_address_b:even_read_lower[ADDRESS_BITS-1:2]', 'even lower address')
    replace('write_address_b:odd_lower[ADDRESS_BITS-1:2]', 'write_address_b:odd_read_lower[ADDRESS_BITS-1:2]', 'odd lower address')
    replace('even_lane_lower<=even_lower[1:0];', 'even_lane_lower<=even_read_lower[1:0];', 'even lower registered lane')
    replace('odd_lane_lower<=odd_lower[1:0];', 'odd_lane_lower<=odd_read_lower[1:0];', 'odd lower registered lane')
    replace('    wire [2:0] hit_increment=accept_fast ? fast_hit_increment:\n        slow_hit_increment ? 3\'d1:3\'d0;',
            '    wire [2:0] bulk_hit_increment={2\'b0,(neighbour<1 && slow_bounds[1])}+\n'
            '        {2\'b0,(neighbour<2 && slow_bounds[2])}+{2\'b0,(neighbour<3 && slow_bounds[3])};\n'
            '    wire [2:0] hit_increment=accept_fast ? fast_hit_increment:\n'
            '        state==BULK_CHECK && bulk_all_hit ? bulk_hit_increment:\n'
            '        slow_hit_increment ? 3\'d1:3\'d0;', 'unchanged public neighbour-hit count')
    replace('                        tags[write_commit_line]<=fill_write_block;\n                        state<=LOAD;',
            '                        tags[write_commit_line]<=fill_write_block;\n'
            '                        state<=neighbour==3 ? LOAD:BULK_CHECK;', 'only check after true final write and with remaining neighbours')
    replace('                LOAD:state<=PICK;',
            '                BULK_CHECK:state<=bulk_all_hit ? BULK_LOAD:LOAD;\n'
            '                BULK_LOAD:state<=BULK_PICK;\n'
            '                BULK_PICK:begin\n'
            '                    slow_pixel[0]<=slow_bounds[0] ? expand565(slow_number[0][0] ? odd_q_upper:even_q_upper):24\'d0;\n'
            '                    slow_pixel[1]<=slow_bounds[1] ? expand565(slow_number[1][0] ? odd_q_upper:even_q_upper):24\'d0;\n'
            '                    slow_pixel[2]<=slow_bounds[2] ? expand565(slow_number[2][0] ? odd_q_lower:even_q_lower):24\'d0;\n'
            '                    slow_pixel[3]<=slow_bounds[3] ? expand565(slow_number[3][0] ? odd_q_lower:even_q_lower):24\'d0;\n'
            '                    state<=RESULT;\n'
            '                end\n'
            '                LOAD:state<=PICK;', 'batch read or original conflict fallback')
    destination = HERE / 'combined-cache-probe-c.v'
    with destination.open('x', encoding='utf-8', newline='\n') as target:
        target.write(text)
    result = {'Schema': 'tile8-combined-slow-bulk-experiment-source-v1', 'ExperimentalOnly': True,
              'Parent': {'Path': str(parent), 'SHA256': expected},
              'Variant': {'Path': str(destination), 'SHA256': hashlib.sha256(destination.read_bytes()).hexdigest()},
              'Transformations': changes, 'NativeEDAExecuted': False, 'HardwareAccessed': False}
    with (HERE / 'combined-cache-probe-source-c.json').open('x', encoding='utf-8') as target:
        json.dump(result, target, indent=2); target.write('\n')
    runner_parent = HERE / 'run_decoded_slow_unit_b.py'
    runner = runner_parent.read_text().replace('decoded-slow-probe-b.v', 'combined-cache-probe-c.v')
    runner = runner.replace('decoded-slow-probe-source-b.json', 'combined-cache-probe-source-c.json')
    runner = runner.replace('tile8-decoded-slow-unit-experiment-v1', 'tile8-combined-slow-bulk-unit-experiment-v1')
    runner = runner.replace('decoded_unit_b', 'combined_unit_c')
    with (HERE / 'run_combined_cache_unit_c.py').open('x', encoding='utf-8', newline='\n') as target:
        target.write(runner)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
