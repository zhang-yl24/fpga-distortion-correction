"""Review exact raw-diagnostic accumulator reductions and native warnings.

This never clears original diagnostics or accepts external AC. Actual mapped
CDC/reset/pin and functional checks remain independent physical-proof gates.
"""
from collections import Counter
from pathlib import Path
import argparse
import json
import re

import hdmi_camera_raw_build as build
import hdmi_camera_raw_native as native

SELF = Path(__file__).resolve()
SCHEMA = 'hdmi-camera-raw-diagnostic-review-v1'
require, sha, read, write = build.require, build.sha, build.read, build.write
EXPECTED = {
    ('board/hdmi_camera_raw_diag.v', 'configuration_wait_count'): (22, 2700000, 'CFG_SETTLE_CYCLES'),
    ('rtl/experimental/hdmi_raw_activity.v', 'snapshot_timer'): (15, 27000, 'SNAPSHOT_INTERVAL_REF_CYCLES'),
    ('rtl/experimental/hdmi_camera_raw_uart.v', 'snapshot_timer'): (15, 27000, 'CFG_SNAPSHOT_CYCLES'),
    ('rtl/experimental/iic_dri_checked.v', 'watchdog'): (17, 100000, 'TIMEOUT_CYCLES'),
}
WARNING_REVIEW = {
    'Sdm-2008': 'PDS ignores async_reg; no physical CDC credit is taken from this attribute. Actual FF chain, placement, fanout and timing must be checked separately.',
    'Sdm-2000': 'Constant register-bit removal remains recorded. The four explicit counter reductions are proved below; functional protocol and mapped coverage are separate gates.',
    'ConstraintEditor-4040': 'Board pin uses a package shared-function location. Actual pad/electrical parameters and bitstream pin configuration are checked separately.',
    'Public-4008': 'Dangling/constant primitive cleanup is retained verbatim. Exposed packet/pad connectivity and required register paths must remain covered by the current netlist audit.',
    'Adm-4000': 'Constant propagated bits are retained verbatim. This review is not a source-to-netlist equivalence proof.',
    'Adm-4021': 'Native instance naming changed during packing. Physical auditors resolve actual Q/D connectivity instead of assuming RTL names are preserved.',
    'Timing-4086': 'External input AC is unaccepted; digital sampled-pin diagnosis only.',
    'Timing-4087': 'External output AC is unaccepted; synthetic bars and UART are not an input-pixel/display acceptance certificate.',
}


def parameters(text):
    groups = {}
    for match in re.finditer(r'I: Module instance \{([^}]+)\} parameter value:\s*\n((?:    [^\n]+\n)+)', text):
        name, block = match.groups()
        require(name not in groups, 'duplicate native elaborated parameter block')
        values = {}
        for line in block.splitlines():
            item = re.fullmatch(r'    (\w+) = \d+\x27b[01]+ \(\d+\x27d(\d+)\)', line.strip('\r'))
            require(item is not None, 'unparsed elaborated parameter: ' + line)
            values[item[1]] = int(item[2])
        groups[name] = values
    return groups


def reductions(text, frozen):
    pattern = (r'C: Sdm-3003: \[(.+?)\(line number: (\d+)\)\] Reduce accumulator (\w+) '
               r'size from (\d+) to (\d+)\. If this is not intended behavior, please drive \3 with valid values\.')
    rows = []
    for line in text.splitlines():
        if not line.startswith('C:'):
            continue
        match = re.fullmatch(pattern, line)
        require(match is not None, 'unreviewed critical diagnostic: ' + line)
        source = Path(match[1]).resolve()
        require(source.is_relative_to(frozen), 'diagnostic source outside frozen build')
        key = (source.relative_to(frozen).as_posix(), match[3])
        require(key in EXPECTED, 'unexpected reduced accumulator')
        bits, limit, parameter = EXPECTED[key]
        require(int(match[4]) == 32 and int(match[5]) == bits and
                (limit - 1).bit_length() == bits, 'counter range no longer fits exact native width')
        rows.append({'Source': key[0], 'Counter': key[1], 'SourceLine': int(match[2]),
                     'OldBits': 32, 'NativeBits': bits, 'Parameter': parameter,
                     'LimitExclusive': limit, 'ReachableMinimum': 0, 'ReachableMaximum': limit - 1})
    require(Counter((r['Source'], r['Counter']) for r in rows) == Counter({key: 1 for key in EXPECTED}),
            'exact four critical reductions required')
    return rows


def bounds(source, counter, limit, parameter):
    compact = re.sub(r'\s+', '', re.sub(r'//[^\n]*', '', source))
    values = re.findall(re.escape(counter) + r'<=([^;]+);', compact)
    allowed = {'0', counter + "+1'b1"} if counter != 'watchdog' else {'0', 'watchdog+1'}
    if parameter == 'CFG_SNAPSHOT_CYCLES':
        allowed.add('CFG_SNAPSHOT_CYCLES-1')
    require(values and set(values) <= allowed and any(v.startswith(counter + '+1') for v in values),
            'unreviewed counter assignment')
    if counter == 'watchdog':
        require('elseif(watchdog>=TIMEOUT_CYCLES-1)begin' in compact and
                "transaction_failed<=1;error_code<=4'hf;state<=IDLE;endelsebeginwatchdog<=watchdog+1;" in compact,
                'watchdog increment is not guarded by terminal timeout')
    else:
        require('if(' + counter + '<' + parameter + '-1)' + counter + '<=' + counter + "+1'b1;" in compact,
                'counter increment is not guarded by exact terminal bound')
    require(0 < limit <= 0xffffffff, 'invalid native bound')
    return {'Assignments': values, 'InductiveBoundVerified': True,
            'Reason': 'Reset starts at zero or the terminal value; increment is allowed only below limit-1; all other assignments hold or reset.'}


def derive(build_plan):
    build_plan = Path(build_plan).resolve()
    plan, receipt, watched = native.bind_build(build_plan)
    work = build_plan.parent
    frozen = work / 'frozen-inputs'
    compile_log = work / 'compile/run.log'
    text = compile_log.read_text(encoding='gb18030', errors='strict')
    parsed = parameters(text)
    required_params = {
        build.TARGET: {'CFG_SETTLE_CYCLES': 2700000},
        build.TARGET + '/hdmi_configuration': {'CLK_FRE': 10000000, 'TIMEOUT_CYCLES': 100000},
        build.TARGET + '/hdmi_configuration/driver': {'CLK_FRE': 10000000, 'TIMEOUT_CYCLES': 100000},
        build.TARGET + '/raw_activity': {'SNAPSHOT_INTERVAL_REF_CYCLES': 27000},
        build.TARGET + '/telemetry': {'REF_CLOCK_HZ': 27000000, 'CFG_SNAPSHOT_CYCLES': 27000},
    }
    require(all(name in parsed and all(parsed[name].get(k) == v for k, v in values.items())
                for name, values in required_params.items()), 'actual elaborated parameters differ')
    rows = reductions(text, frozen)
    for row in rows:
        source = (frozen / row['Source']).read_text(encoding='utf-8')
        row.update(bounds(source, row['Counter'], row['LimitExclusive'], row['Parameter']))
    # Four independent log copies preserve the same actual critical records.
    expected_logs = {'compile/run.log', 'flow.log', 'run.log', 'stdout.log'}
    observed = {}
    warnings = []
    for p in sorted(work.rglob('*.log')):
        content = p.read_text(encoding='gb18030', errors='strict')
        require(not re.search(r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:|Traceback)', content), 'native error remains')
        if any(line.startswith('C:') for line in content.splitlines()):
            observed[p.relative_to(work).as_posix()] = reductions(content, frozen)
        for line in content.splitlines():
            if line.startswith('W:'):
                match = re.match(r'W: ([^:]+):', line)
                require(match is not None and match[1] in WARNING_REVIEW, 'unreviewed native warning: ' + line)
                warnings.append({'File': p.relative_to(work).as_posix(), 'Code': match[1], 'Text': line})
    require(set(observed) == expected_logs and all(values == [{k: v for k, v in row.items()
            if k not in ('Assignments', 'InductiveBoundVerified', 'Reason')} for row in rows]
            for values in observed.values()), 'critical diagnostic log copies differ')
    native.add(watched, SELF)
    return {'Schema': SCHEMA, 'Target': build.TARGET, 'BuildPlan': native.ref(build_plan),
            'Passed': True, 'NativeWarningsReviewed': True, 'CriticalReductionCount': 4,
            'RetainedCriticalRecords': sum(len(v) for v in observed.values()), 'CounterProofs': rows,
            'NativeElaboratedParameters': {k: parsed[k] for k in required_params},
            'Warnings': warnings, 'WarningCounts': dict(Counter(r['Code'] for r in warnings)),
            'WarningReview': WARNING_REVIEW, 'ExternalACAccepted': False,
            'MappedCDCResetPinsStillRequireIndependentProof': True,
            'OriginalDiagnosticsUnmodified': True, 'HardwareAccessed': False,
            'InputSHA256': {str(p): h for p, h in watched.items()}}, watched


def verify(path):
    path = Path(path).resolve()
    saved = read(path)
    value, watched = derive(saved['BuildPlan']['Path'])
    require(saved == value, 'stored diagnostic review differs from full recomputation')
    native.add(watched, path)
    return value, watched


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-plan', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify:
        result, _ = verify(args.verify)
    else:
        result, _ = derive(args.build_plan)
        write(args.output, result)
    print(json.dumps({key: result[key] for key in ('Passed', 'NativeWarningsReviewed', 'CriticalReductionCount', 'RetainedCriticalRecords')}))
