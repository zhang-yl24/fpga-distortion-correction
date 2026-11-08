"""Apply/check parameter facts in an independently licensed GUI-created IDF.

Usage: python configure_ddr_idf.py new/ddr3_test.idf [--csv DDR3_PARAMETERS.csv]
       python configure_ddr_idf.py generated/ddr3_test.idf --check
Does not invoke IP Compiler, write RTL, or supply vendor implementation files.
"""
from pathlib import Path
import argparse
import csv
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('idf', type=Path)
    ap.add_argument('--csv', type=Path, default=Path(__file__).with_name('DDR3_PARAMETERS.csv'))
    ap.add_argument('--check', action='store_true', help='Read only; require all371 saved values to match')
    args = ap.parse_args()
    with args.csv.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        require(reader.fieldnames == ['parameter', 'value'], 'Unexpected CSV columns')
        rows = list(reader)
    expected = {}
    for row in rows:
        name, value = row['parameter'], row['value']
        require(name and value is not None and name not in expected, 'Empty/duplicate CSV parameter')
        expected[name] = value
    require(len(expected) == 371, 'Expected exactly371 CSV parameters')
    original = args.idf.read_bytes()
    text = original.decode('utf-8-sig')
    root = ET.fromstring(text)
    require(root.tag == 'ip_inst', 'Expected ip_inst root')
    headers = root.findall('header')
    require(len(headers) == 1, 'Missing/duplicate header')
    header = headers[0]
    for name, value in {'vendor':'Pango', 'id':'042003', 'display_name':'DDR3 Interface',
                        'name':'Logos2 HMIC_S', 'version':'1.10', 'instance':'ddr3_test',
                        'family':'Logos2', 'device':'PG2L100H', 'package':'FBG676',
                        'speedgrade':'-6'}.items():
        fields = header.findall(name)
        require(len(fields) == 1 and fields[0].text == value, 'Header mismatch: '+name)
    lists = root.findall('param_list')
    require(len(lists) == 1, 'Missing/duplicate param_list')
    current = {}
    for param in lists[0]:
        require(param.tag == 'param', 'Unexpected param_list child')
        names, values = param.findall('name'), param.findall('value')
        require(len(names) == 1 and len(values) == 1, 'Missing/duplicate name/value')
        name = names[0].text
        require(name and name not in current, 'Empty/duplicate IDF parameter')
        require(not list(values[0]), 'Nested XML in parameter value')
        current[name] = values[0].text or ''
    require(set(expected) <= set(current), 'Missing required IDF parameter(s): '+','.join(sorted(set(expected)-set(current))))
    mismatch = [name for name in expected if current[name] != expected[name]]
    if args.check:
        require(not mismatch, 'Parameter mismatch: '+','.join(mismatch))
        print('PASS:371 parameters and exact model/device header match; read only.')
        return
    # Patch only value text in the one param_list, leaving all other XML bytes,
    # including header, file lists, GUI choices, comments and line endings intact.
    pattern = re.compile(r'(<param_list\s*>)(.*?)(</param_list\s*>)', re.S)
    blocks = list(pattern.finditer(text))
    require(len(blocks) == 1, 'Unsupported param_list serialization')
    seen = set()
    def patch_param(match):
        raw = match.group(0)
        parsed = ET.fromstring(raw)
        name = parsed.findtext('name')
        if name not in expected:
            return raw
        require(name not in seen, 'Duplicate serialized parameter')
        seen.add(name)
        vp = re.compile(r'(<value\s*>)([^<]*)(</value\s*>)', re.S)
        require(len(list(vp.finditer(raw))) == 1, 'Unsupported value serialization: '+name)
        return vp.sub(lambda m: m[1]+escape(expected[name])+m[3], raw)
    body = re.sub(r'<param\s*>.*?</param\s*>', patch_param, blocks[0][2], flags=re.S)
    require(seen == set(expected), 'Could not locate every parameter without rewriting XML')
    updated = text[:blocks[0].start(2)]+body+text[blocks[0].end(2):]
    payload = (b'\xef\xbb\xbf' if original.startswith(b'\xef\xbb\xbf') else b'')+updated.encode('utf-8')
    check = ET.fromstring(payload)
    values = {p.findtext('name'):p.findtext('value') or '' for p in check.find('param_list')}
    require(all(values[k] == v for k,v in expected.items()), 'Internal post-update verification failed')
    if payload != original:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=args.idf.parent, prefix='.idf-parameters-', delete=False) as f:
                temporary = Path(f.name)
                f.write(payload)
            os.replace(temporary, args.idf)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
    print('PASS:371 parameters set; changed values='+str(len(mismatch))+'; other XML preserved. Generate this instance in the licensed GUI next.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, UnicodeError, ET.ParseError) as exc:
        print('STOP: '+str(exc), file=sys.stderr)
        sys.exit(2)
