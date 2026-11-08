"""Offline source-closure check. Never launches EDA, network, or hardware."""
from pathlib import Path
import argparse
import re
import sys
import xml.etree.ElementTree as ET


def check(root, spec=None):
    root = Path(root).resolve()
    spec = Path(spec or Path(__file__).parent)
    expected = [s for s in (spec / 'expected_source_files.txt').read_text().splitlines() if s]
    imports = [s for s in (spec / 'design_imports.txt').read_text().splitlines() if s]
    required = expected + [
        'constraints/KEY1_ONLY.fdc', 'constraints/uart_bound.pcf',
        'constraints/vendor-ca-debug-priority.rcf',
    ]
    missing = sorted({s for s in required if not (root / s).is_file()})
    errors = []
    if len(expected) != 155 or len(imports) != 68 or len(set(imports)) != 68:
        errors.append('Expected 155 source files and 68 unique direct imports.')
    for relative in expected + imports:
        p = Path(relative)
        if p.is_absolute() or '..' in p.parts or not relative.startswith('native/'):
            errors.append('Unsafe source reference: ' + relative)
    native = root / 'native'
    for relative in expected:
        p = root / relative
        if not p.is_file():
            continue
        text = p.read_text(encoding='utf-8', errors='replace')
        if p.suffix.lower() in ('.v', '.sv', '.vh', '.svh'):
            for name in re.findall(r'`include\s+"([^"]+)"', text):
                if re.match(r'^[A-Za-z]:[\\/]|^[/\\]', name):
                    errors.append(relative + ': absolute include; relocate to native search root')
                elif not any(q.is_file() for q in (p.parent / name, native / name, native / 'b4/rtl' / name)):
                    errors.append(relative + ': missing include ' + name)
        if p.suffix.lower() == '.idf':
            try:
                for entry in ET.fromstring(text).findall('./file_list/source/file'):
                    name = entry.attrib['pathname']
                    q = p.parent / name
                    if not q.is_file():
                        errors.append(relative + ': missing IDF synthesis source ' + name)
            except (ET.ParseError, KeyError) as exc:
                errors.append(relative + ': invalid IDF: ' + str(exc))
    pcf = root / 'constraints/uart_bound.pcf'
    if pcf.is_file():
        text = pcf.read_text()
        pins = dict(re.findall(r'def_port\s+\{([^}]+)\}\s+LOC=(\w+)', text))
        if len(pins) != 145:
            errors.append('Paired PCF must assign exactly 145 unique ports.')
        for port, pin in [('telemetry_tx', 'C24'), ('telemetry_rx', 'B24'), ('key1_n', 'C23')]:
            if pins.get(port) != pin:
                errors.append('Paired PCF pin mismatch: ' + port + ' must use ' + pin)
    top = root / 'native/source/build/offline-20261024/cfg100-independent-20261030-a/candidate/board1080_cfg100_top.v'
    if top.is_file():
        text = re.sub(r'\s+', '', top.read_text())
        required_top = [
            'moduleboard1080_top#(', 'RATIONAL_BROWN_PROFILE=1', 'R34_ENABLE_GAMMA=0',
            'TILE8_GROUP_WIDTH=64', '.STARTUP_SCAN_ALIGN(1)', '.STARTUP_SCAN_GUARD_CYCLES(0)',
            '.STARTUP_PRIME_NEXT_SOURCE(1)', '.RESULT_BANKS(2)', '.STATS_ENABLE(1)',
            '.STATS_CORE_HZ(125000000)', '.MACRO_TILE_HEIGHT(RATIONAL_BROWN_PROFILE?32:8)',
            '.CACHE_INDEX_BITS(RATIONAL_BROWN_PROFILE?7:6)',
            '.PREFETCH_QUERY_DEPTH(RATIONAL_BROWN_PROFILE?4096:0)',
            '.CORE_PRIORITY(RATIONAL_BROWN_PROFILE?1:0)',
        ]
        for token in required_top:
            if token not in text:
                errors.append('Critical AA source configuration changed: ' + token)
    rcf = root / 'constraints/vendor-ca-debug-priority.rcf'
    if rcf.is_file():
        nets = re.findall(r'def_route\s+-prior_net\s+\{([^}]+)\}', rcf.read_text())
        wanted = [
            'u_ddr3_test_h/u_ddrphy_top/ddrphy_ioclk_gate [0]',
            'u_ddr3_test_h/u_ddrphy_top/ddrphy_ioclk_gate [1]',
            'u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/all_group_ca_dly',
            'u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/debug_data [273]',
        ]
        if nets != wanted:
            errors.append('Physical route priority list differs from the four original nets.')
    return missing, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    missing, errors = check(args.root)
    for name in missing:
        print('MISSING ' + name)
    for error in errors:
        print('ERROR ' + error)
    if missing or errors:
        print('STOP: source closure incomplete. Legally generate/restore required vendor IP first; no EDA was launched.')
        return 2
    print('FILE_CLOSURE_READY: 155 required source files, 68 direct imports, include/IDF synthesis references present.')
    print('This is a file-closure check, not synthesis, timing, license, or byte-identical implementation proof.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
