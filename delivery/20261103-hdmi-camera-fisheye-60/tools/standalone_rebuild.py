"""Verify and relocate an exported FPGA source bundle using Python only."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import xml.etree.ElementTree as ET

TEXT_SOURCES = {'.v', '.vh', '.sv', '.svh'}
ADDITIONS = re.compile(r'^add_(?:design|constraint)\s+\{([^}]+)\}\s*$', re.M)
INCLUDES = re.compile(r'`include\s+"([^"\r\n]+)"')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bound(root, relative):
    name = PurePosixPath(relative)
    require(bool(relative) and not name.is_absolute() and '..' not in name.parts and
            ':' not in relative and '\\' not in relative and relative != '.',
            'Invalid manifest path: ' + relative)
    path = root.joinpath(*name.parts)
    require(path.resolve().is_relative_to(root.resolve()), 'Path escapes source root: ' + relative)
    return path


def inventory(root):
    require(root.is_dir() and not root.is_symlink(), 'Compiled source directory missing or linked')
    paths = list(root.rglob('*'))
    require(not any(p.is_symlink() for p in paths), 'Source closure must not contain symbolic links')
    return {p.relative_to(root).as_posix(): digest(p.read_bytes()) for p in paths if p.is_file()}


def infer_compiled_root(tcl, sources):
    names = ADDITIONS.findall(tcl)
    require(names, 'No explicit source or constraint entries in build.tcl')
    roots = set()
    for name in names:
        matches = [s for s in sources if name.endswith('/' + s)]
        require(matches, 'Tcl input is outside the source manifest: ' + name)
        relative = max(matches, key=len)
        roots.add(name[:-len(relative)-1])
    require(len(roots) == 1, 'Tcl input roots are inconsistent')
    return roots.pop()


def check_references(compiled, tcl, original_root, sources):
    """Resolve virtual original paths against the files physically in this bundle."""
    prefix = original_root.rstrip('/') + '/'
    for name in ADDITIONS.findall(tcl):
        require(name.startswith(prefix), 'Unbound Tcl input: ' + name)
        relative = name[len(prefix):]
        require(relative in sources and bound(compiled, relative).is_file(), 'Missing Tcl input: ' + relative)
    for relative in sources:
        path = bound(compiled, relative)
        if path.suffix.lower() in TEXT_SOURCES:
            for include in INCLUDES.findall(path.read_text(encoding='utf-8-sig')):
                normalized = include.replace('\\', '/')
                if PureWindowsPath(normalized).is_absolute() or PurePosixPath(normalized).is_absolute():
                    require(normalized.startswith(prefix), 'Unbound absolute include in ' + relative)
                    target = bound(compiled, normalized[len(prefix):])
                else:
                    target = (path.parent / normalized).resolve()
                    require(target.is_relative_to(compiled.resolve()), 'Relative include escapes closure')
                require(target.is_file(), 'Missing include in ' + relative + ': ' + include)
        if path.suffix.lower() == '.idf':
            for node in ET.fromstring(path.read_bytes()).findall('./file_list/source/file'):
                target = (path.parent / node.attrib['pathname']).resolve()
                require(target.is_relative_to(compiled.resolve()) and target.is_file(),
                        'Missing/outside IDF dependency: ' + node.attrib['pathname'])


def inspect_prepared(prepared):
    plan_bytes = (prepared / 'candidate-plan.json').read_bytes()
    plan = json.loads(plan_bytes.decode('utf-8-sig'))
    require(plan.get('schema') == 'fisheye60-candidate-v1', 'Unexpected candidate manifest schema')
    sources = plan['source_files']
    for name in sources:
        bound(prepared / 'compiled', name)
    require(inventory(prepared / 'compiled') == sources, 'Compiled source SHA256/inventory differs from candidate-plan.json')
    require(digest(json.dumps(sources, sort_keys=True).encode()) == plan['source_identity'],
            'Candidate source identity differs')
    tcl_bytes = (prepared / 'build.tcl').read_bytes()
    require(digest(tcl_bytes) == plan['build_tcl_sha256'], 'build.tcl SHA256 differs from candidate manifest')
    root = infer_compiled_root(tcl_bytes.decode('utf-8-sig'), sources)
    check_references(prepared / 'compiled', tcl_bytes.decode('utf-8-sig'), root, sources)
    return plan, plan_bytes, tcl_bytes, root


def verify_bundle(bundle):
    record = json.loads((bundle / 'bundle-manifest.json').read_text(encoding='utf-8-sig'))
    require(record.get('schema') == 'fisheye60-standalone-bundle-v1', 'Unexpected bundle schema')
    for name, expected in record['bound_files'].items():
        path = bound(bundle, name)
        require(path.is_file() and not path.is_symlink() and digest(path.read_bytes()) == expected,
                'Bundle file SHA256 differs: ' + name)
    plan, plan_bytes, tcl_bytes, root = inspect_prepared(bundle)
    require(root == record['original_compiled_root'] and plan['source_identity'] == record['source_identity'],
            'Bundle provenance differs')
    return record, plan, plan_bytes, tcl_bytes, root


def new_directory(path, compiled_names=()):
    path = Path(path).resolve()
    require(not path.exists(), 'Output already exists; choose a new directory')
    require(not any(c in path.as_posix() for c in '{}\r\n\x00'), 'Output path cannot be represented safely in Tcl')
    if __import__('os').name == 'nt':
        require(all(len(str(path / 'compiled' / n)) < 260 for n in compiled_names),
                'Output path exceeds Windows/PDS MAX_PATH; choose a shorter directory')
    return path


def relocate(bundle, output):
    bundle = Path(bundle).resolve()
    record, plan, plan_bytes, tcl_bytes, original_root = verify_bundle(bundle)
    output = new_directory(output, plan['source_files'])
    require(not output.is_relative_to(bundle / 'compiled'), 'Output cannot be inside the frozen compiled sources')
    new_root = (output / 'compiled').as_posix()
    new_tcl = tcl_bytes.replace(original_root.encode(), new_root.encode())
    relocated, changes = {}, []
    # Validate every source and transformation before creating the output.
    for name in plan['source_files']:
        data = bound(bundle / 'compiled', name).read_bytes()
        updated = data
        if Path(name).suffix.lower() in TEXT_SOURCES:
            def replace_include(match):
                include = match.group(1)
                normalized = include.replace('\\', '/')
                if normalized.startswith(original_root + '/'):
                    return match.group(0).replace(include, new_root + normalized[len(original_root):])
                return match.group(0)
            updated = INCLUDES.sub(replace_include, data.decode('utf-8')).encode('utf-8')
        relocated[name] = updated
        if updated != data:
            changes.append({'path': name, 'original_sha256': digest(data), 'relocated_sha256': digest(updated),
                            'change': 'absolute include root relocation'})
    output.mkdir(parents=True)
    for name, data in relocated.items():
        target = bound(output / 'compiled', name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (output / 'build.tcl').write_bytes(new_tcl)
    (output / 'source-candidate-plan.json').write_bytes(plan_bytes)
    sources = inventory(output / 'compiled')
    require(sources == {n: digest(d) for n, d in relocated.items()}, 'Relocated output verification failed')
    check_references(output / 'compiled', new_tcl.decode('utf-8-sig'), new_root, sources)
    receipt = {'schema': 'fisheye60-standalone-rebuild-v1', 'verified': True,
               'original_source_identity': plan['source_identity'],
               'source_identity': digest(json.dumps(sources, sort_keys=True).encode()),
               'baseline_commit': plan['baseline_commit'], 'baseline_bitstream': plan['baseline_bitstream'],
               'build_id': plan['build_id'], 'profile_id': plan['profile_id'],
               'candidate_plan_sha256': digest(plan_bytes), 'source_files': sources,
               'original_compiled_root': original_root, 'relocated_compiled_root': new_root,
               'build_tcl_sha256': digest(new_tcl), 'relocations': changes,
               'hardware_tested': False, 'physical_timing_verified': False, 'eda_executed': False,
               'command_template': ['<PDS-install>/bin/pds_shell.exe', '-file', (output / 'build.tcl').as_posix(),
                                    '-work_dir', output.as_posix(), '-project_name', 'hdmi_camera_fisheye_top']}
    (output / 'rebuild-plan.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--verify-only', action='store_true')
    action.add_argument('--output', type=Path)
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent
    if args.verify_only:
        _, plan, _, _, _ = verify_bundle(bundle)
        print(json.dumps({'verified': True, 'source_files': len(plan['source_files']),
                          'source_identity': plan['source_identity'], 'eda_executed': False}))
    else:
        receipt = relocate(bundle, args.output)
        print(json.dumps({'verified': True, 'source_files': len(receipt['source_files']),
                          'output': str(args.output.resolve()), 'eda_executed': False}))


if __name__ == '__main__':
    main()
