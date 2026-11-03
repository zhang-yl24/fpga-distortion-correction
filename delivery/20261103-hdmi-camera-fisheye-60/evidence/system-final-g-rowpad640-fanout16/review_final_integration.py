"""Read-only closure and ANSI-port inventory for the frozen candidate snapshot."""
from pathlib import Path
import hashlib, json, re

WORK = Path('D:/f60-work/system-final-g-rowpad640-fanout16')
REPO = Path('D:/f60')
PACKAGE = REPO/'delivery/20261103-hdmi-camera-fisheye-60'
plan = json.loads((WORK/'candidate-plan.json').read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def paren(text, start):
    assert text[start] == '('
    depth = 0
    for i in range(start, len(text)):
        depth += (text[i] == '(') - (text[i] == ')')
        if depth == 0:
            return text[start+1:i], i+1
    raise ValueError('Unclosed header')

def interfaces(path):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', path.read_text(encoding='utf-8-sig'), flags=re.S)
    modules = {}
    for match in re.finditer(r'\bmodule\s+(\w+)\s*', text):
        cursor = match.end()
        if text[cursor] == '#':
            _, cursor = paren(text, text.index('(', cursor))
        ports, _ = paren(text, text.index('(', cursor))
        result, direction, width = {}, None, ''
        for item in ports.split(','):
            direct = re.search(r'\b(input|output|inout)\b', item)
            if direct:
                direction, width = direct[1], ''
            bits = re.search(r'\[[^\]]+\]', item)
            if bits:
                width = re.sub(r'\s+', '', bits[0])
            name = re.findall(r'\b\w+\b', item)[-1]
            result[name] = [direction, width]
        modules[match[1]] = result
    return modules

build_text = (WORK/'build.tcl').read_text()
designs = [Path(p) for p in re.findall(r'^add_design\s+\{([^}]+)\}', build_text, re.M)]
constraints = [Path(p) for p in re.findall(r'^add_constraint\s+\{([^}]+)\}', build_text, re.M)]
module_owners = {}
for design in designs:
    if design.suffix == '.v':
        for module in interfaces(design):
            module_owners.setdefault(module, []).append(str(design.relative_to(WORK/'compiled')))
changes = []
for row in plan['overlays']:
    if not row['compiled'].endswith('.v'):
        continue
    current = WORK/'compiled'/row['compiled']
    original = REPO/'distortion'/row['compiled']
    new_modules = interfaces(current)
    old_modules = interfaces(original) if original.exists() else {}
    diff = {'file': row['source'], 'new_modules': sorted(set(new_modules)-set(old_modules)),
            'removed_modules': sorted(set(old_modules)-set(new_modules)), 'port_differences': {}}
    for module in set(new_modules) & set(old_modules):
        old, new = old_modules[module], new_modules[module]
        details = {name: {'baseline': old.get(name), 'candidate': new.get(name)}
                   for name in old.keys() | new.keys() if old.get(name) != new.get(name)}
        if details:
            diff['port_differences'][module] = details
    changes.append(diff)
report = {
    'source_identity': plan['source_identity'], 'build_id': plan['build_id'],
    'scope': 'Build closure paths, SHA256 and ANSI port inventory; runtime interfaces are elaborated by the real system regression. Vendor physical timing is a separate check.',
    'design_count': len(designs), 'constraint_count': len(constraints),
    'missing_designs_or_constraints': [str(p) for p in designs+constraints if not p.is_file()],
    'duplicate_design_entries': sorted({str(p) for p in designs if designs.count(p)>1}),
    'duplicate_plain_verilog_modules': {m:p for m,p in module_owners.items() if len(p)>1},
    'changed_snapshot_files': [p for p,h in plan['source_files'].items() if sha(WORK/'compiled'/p) != h],
    'changed_live_overlays': [r['source'] for r in plan['overlays'] if sha(PACKAGE/r['source']) != r['source_sha256']],
    'missing_overlay_build_entries': [r['compiled'] for r in plan['overlays'] if r['compiled'].endswith('.v') and WORK/'compiled'/r['compiled'] not in designs],
    'interface_inventory': changes,
}
(WORK/'integration-review.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))



