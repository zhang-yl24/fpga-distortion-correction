"""Read-only comparison of a GUI-generated PLL wrapper against saved facts.

python check_pll_parameters.py cfg_pll generated/cfg_pll.v
python check_pll_parameters.py bringup_pll generated/bringup_pll.v
Only literal numeric/string localparams are accepted. Expressions mean UNKNOWN.
"""
from pathlib import Path
import argparse
import csv
from decimal import Decimal, InvalidOperation
import re
import sys


def literal(value, from_csv=False):
    value = value.strip()
    if re.fullmatch(r'"[^"\r\n]*"', value):
        return ('string', value[1:-1])
    if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', value):
        return ('number', Decimal(value))
    # CSV stores unquoted enum/string values.
    if from_csv and re.fullmatch(r'[A-Za-z_]\w*', value):
        return ('string', value)
    raise ValueError('UNKNOWN nonliteral expression')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('instance', choices=['cfg_pll','bringup_pll'])
    ap.add_argument('wrapper', type=Path)
    ap.add_argument('--csv', type=Path, default=Path(__file__).with_name('PLL_PARAMETERS.csv'))
    args = ap.parse_args()
    with args.csv.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ['instance','parameter','value']:
            raise ValueError('Unexpected CSV columns')
        rows = [r for r in reader if r['instance'] == args.instance]
    expected = {}
    for row in rows:
        if not row['parameter'] or row['parameter'] in expected:
            raise ValueError('Empty/duplicate CSV parameter')
        expected[row['parameter']] = literal(row['value'], from_csv=True)
    if not expected:
        raise ValueError('No expected parameters')
    text = args.wrapper.read_text(encoding='utf-8-sig')
    # Strip comments without stripping comment characters inside quoted strings.
    text = re.sub(r'"[^"\r\n]*"|/\*.*?\*/|//[^\r\n]*', lambda m: m[0] if m[0].startswith('"') else ' ', text, flags=re.S)
    modules = list(re.finditer(r'\bmodule\s+(\w+)\b(.*?)\bendmodule\b', text, re.S))
    selected = [m for m in modules if m[1] == args.instance]
    if len(selected) != 1:
        raise ValueError('Missing/duplicate expected module')
    params = {}
    declarations = list(re.finditer(r'\blocalparam\s+(?:(?:real|integer)\s+)?(\w+)\s*=\s*([^;]+);', selected[0][2]))
    if len(declarations) != len(re.findall(r'\blocalparam\b', selected[0][2])):
        raise ValueError('UNKNOWN unsupported localparam declaration')
    for m in declarations:
        if m[1] in params:
            raise ValueError('Duplicate localparam: '+m[1])
        params[m[1]] = m[2].strip()
    missing = set(expected)-set(params)
    if missing:
        raise ValueError('Missing/UNKNOWN localparams: '+','.join(sorted(missing)))
    if set(params)-set(expected):
        raise ValueError('UNKNOWN additional localparams: '+','.join(sorted(set(params)-set(expected))))
    for name,value in expected.items():
        if literal(params[name]) != value:
            raise ValueError('Mismatch: '+name)
    print('PASS: '+args.instance+' '+str(len(expected))+' literal parameters match. Read only; connectivity/clock/timing still require independent verification.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, UnicodeError, InvalidOperation) as exc:
        print('STOP: '+str(exc), file=sys.stderr)
        sys.exit(2)
