"""Read real VCD transitions; independently validate edge handshakes and holds."""
from pathlib import Path
import csv
import hashlib
import json

WORK = Path(__file__).resolve().parent


def parse_vcd(path):
    identifiers = {}
    events = []
    changes = {}
    t = None
    header = True
    for line in Path(path).read_text(encoding='ascii').splitlines():
        line = line.strip()
        if header:
            if line.startswith('$var '):
                _, kind, width, code, name, *_ = line.split()
                identifiers[code] = {'name': name, 'width': int(width), 'kind': kind}
            if line.startswith('$enddefinitions'):
                header = False
            continue
        if line.startswith('#'):
            if t is not None:
                events.append((t, changes))
            t, changes = int(line[1:]), {}
        elif line and not line.startswith('$'):
            if line[0] in 'bB':
                raw, code = line[1:].split()
            else:
                raw, code = line[0], line[1:]
            value = None if any(c in raw.lower() for c in 'xz') else int(raw, 2)
            changes[identifiers[code]['name']] = value
    if t is not None:
        events.append((t, changes))
    return identifiers, events


def main():
    identifiers, events = parse_vcd(WORK/'mapper.vcd')
    fixtures = [[int(line, 16) for line in (WORK/name).read_text().splitlines()]
                for name in ('corrected.mem', 'identity.mem', 'domain.mem')]
    state = {}
    queue = []
    accepted = []
    emitted = []
    stalled = []
    blocked_config = []
    edges = []
    last_t = None
    phase_indices = [0, 0, 0]
    previous_held = None
    payload_names = ['out_black', 'out_x', 'out_y', 'out_tag']
    transitions = {info['name']: [] for info in identifiers.values()}
    for t, change in events:
        before = state.copy()
        state.update(change)
        for name, value in change.items():
            transitions[name].append([t, value])
        if before.get('clk') != 0 or state.get('clk') != 1:
            continue
        if last_t is not None:
            assert t-last_t == 8000
        last_t = t
        row = {'time_ps': t, **before}
        row['in_accept'] = int(before.get('in_valid') == 1 and before.get('in_ready') == 1)
        row['out_accept'] = int(before.get('out_valid') == 1 and before.get('out_ready') == 1)
        row['output_stall'] = int(before.get('out_valid') == 1 and before.get('out_ready') == 0)
        edges.append(row)
        if before.get('rst') != 0:
            previous_held = None
            continue
        if previous_held is not None:
            assert before['out_valid'] == 1
            assert tuple(before[n] for n in payload_names) == previous_held
        if row['in_accept']:
            phase = before['phase']
            i = phase_indices[phase]
            record = fixtures[phase][i]
            assert before['in_u'] == (record >> 73) & 0xffffff
            assert before['in_v'] == (record >> 49) & 0xffffff
            queue.append((before['in_tag'], record & ((1 << 49)-1)))
            accepted.append({'time_ps': t, 'tag': before['in_tag'], 'phase': phase})
            phase_indices[phase] += 1
        if row['out_accept']:
            tag, expected = queue.pop(0)
            actual = (before['out_black'] << 48) | (before['out_x'] << 24) | before['out_y']
            assert before['out_tag'] == tag and actual == expected
            emitted.append({'time_ps': t, 'tag': tag, 'phase': before['phase']})
        if row['output_stall']:
            payload = tuple(before[n] for n in payload_names)
            assert tuple(state[n] for n in payload_names) == payload
            previous_held = payload
            stalled.append({'time_ps': t, 'tag': before['out_tag'], 'phase': before['phase'],
                            'out_x_hex': f'{before["out_x"]:06x}', 'out_y_hex': f'{before["out_y"]:06x}'})
        else:
            previous_held = None
        if before['cfg_valid'] and not before['cfg_ready']:
            blocked_config.append({'time_ps': t, 'in_tag': before['in_tag'], 'out_tag': before['out_tag']})
    assert not queue and phase_indices == [512, 4096, 1024]
    assert len(accepted) == len(emitted) == 5632
    assert len(stalled) == 844 and len(blocked_config) == 2
    assert emitted[0]['time_ps']-accepted[0]['time_ps'] == 23*8000
    first_stall = stalled[0]['time_ps']
    first_config = blocked_config[0]['time_ps']
    result = {'Passed': True, 'time_unit': 'ps', 'clock_period_ps': 8000,
              'source_vcd_sha256': hashlib.sha256((WORK/'mapper.vcd').read_bytes()).hexdigest(),
              'accepted': len(accepted), 'emitted': len(emitted), 'stalled_edges': len(stalled),
              'blocked_config_edges': blocked_config,
              'first_input_accept': accepted[0], 'first_output_accept': emitted[0],
              'first_output_valid_rise_ns': next(t/1000 for t,v in transitions['out_valid'] if v == 1),
              'first_latency_ns': (emitted[0]['time_ps']-accepted[0]['time_ps'])/1000,
              'first_latency_cycles': 23,
              'first_stalls': stalled[:8],
              'plot_windows_ns': {
                  'startup_latency': [48, 300],
                  'first_backpressure': [first_stall/1000-36, first_stall/1000+52],
                  'two_cycle_backpressure': [680, 744],
                  'busy_config_rejection': [first_config/1000-24, first_config/1000+40]},
              'interpretation': 'Handshakes evaluated at rising edges using values immediately BEFORE edge; VCD transitions at same timestamp include NBA updates. First out_valid rise is earlier than first sampled output acceptance.'}
    (WORK/'waveform-analysis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (WORK/'selected-transitions.json').write_text(json.dumps(transitions, separators=(',',':')),encoding='utf-8')
    names = ['time_ps', *[i['name'] for i in identifiers.values()], 'in_accept', 'out_accept', 'output_stall']
    with (WORK/'edge-samples.csv').open('w',newline='',encoding='utf-8') as out:
        writer=csv.DictWriter(out,fieldnames=names);writer.writeheader();writer.writerows(edges)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
