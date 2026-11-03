"""Build an isolated, hash-bound source tree; never execute EDA or hardware."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / '20261103-hdmi1080-demo-source'
PREFIX = 'source/build/offline-20261024/'
SELECTOR = PREFIX + 'boardtop-penn-prep-20261029-a/frame_ab_control.v'
TOP = PREFIX + 'cfg100-independent-20261030-a/candidate/board1080_cfg100_top.v'
WRITER = 'source/rtl/experimental/ddr_adaptive_result_writer.v'
CACHE = 'source/rtl/experimental/ddr_compact_neighbour_cache_scatter4.v'
INCLUDE = re.compile(rb'`include\s+"([^"\r\n]+)"')
MODES = {'raw': 0, 'corrected': 1, 'demo': 2}


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def frozen_manifest():
    spec = importlib.util.spec_from_file_location('frozen_verifier', BASE / 'tools/verify_package.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.verify()
    return json.loads((BASE / 'manifests/source-manifest.json').read_text(encoding='utf-8'))


def candidate_sources(variant='both', mode='corrected'):
    if variant not in ('baseline', 'writer', 'cache', 'both') or mode not in MODES:
        raise ValueError('Unknown variant or mode')
    manifest = frozen_manifest()
    sources = {}
    for row in manifest['files']:
        if row['disposition'] == 'included_source':
            sources[row['path']] = (BASE / 'native' / row['path']).read_bytes()
    overlays = {SELECTOR: ROOT / 'rtl/frame_ab_control.v'}
    if variant in ('writer', 'both'):
        overlays[WRITER] = ROOT / 'rtl/ddr_adaptive_result_writer.v'
    if variant in ('cache', 'both'):
        overlays[CACHE] = ROOT / 'rtl/ddr_compact_neighbour_cache_scatter4.v'
    for rel, path in overlays.items():
        sources[rel] = path.read_bytes()
    token = b'parameter integer MODE=1'
    if sources[SELECTOR].count(token) != 1:
        raise ValueError('Selector default changed; review mode substitution')
    sources[SELECTOR] = sources[SELECTOR].replace(token, f'parameter integer MODE={MODES[mode]}'.encode())
    identity = {'variant': variant, 'mode': mode,
                'sources': {rel: sha(blob) for rel, blob in sorted(sources.items())},
                'frozen_manifest_sha256': sha((BASE / 'manifests/source-manifest.json').read_bytes())}
    identity_hash = sha(json.dumps(identity, sort_keys=True).encode())
    param_id = identity_hash[:8]
    old = b".telemetry_param_id(32'he5ccceb0)"
    if sources[TOP].count(old) != 1:
        raise ValueError('Frozen top telemetry identity changed')
    sources[TOP] = sources[TOP].replace(old, f".telemetry_param_id(32'h{param_id})".encode())
    return manifest, sources, {'variant': variant, 'mode': mode, 'param_id_hex': param_id,
                              'candidate_identity_sha256': identity_hash}


def prepare(dependency_native, run_name, variant='both', mode='corrected', output_root=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', run_name):
        raise ValueError('Run name must be a short identifier')
    work = (Path(output_root) if output_root is not None else ROOT / '_build').resolve() / run_name
    if work.exists():
        raise FileExistsError('Use a fresh run name')
    manifest, sources, identity = candidate_sources(variant, mode)
    longest = max(len(str(work / 'native' / row['path'])) for row in manifest['files'])
    if longest > 240:
        raise ValueError('Prepared source path exceeds 240 characters; use --output-root C:/fpga-build')
    deps = Path(dependency_native).resolve()
    external = {}
    for row in manifest['files']:
        if row['disposition'] != 'included_source':
            path = (deps / row['path']).resolve()
            if not path.is_relative_to(deps) or not path.is_file():
                raise ValueError('Missing exact dependency: ' + row['path'])
            blob = path.read_bytes()
            if len(blob) != row['bytes'] or sha(blob) != row['sha256']:
                raise ValueError('Dependency hash mismatch: ' + row['path'])
            external[row['path']] = blob
    sources.update(external)
    native = work / 'native'
    changes, files, prepared = [], [], {}
    # Validate/rewrite the entire closure in memory before creating output.
    for rel, original in sources.items():
        blob = original
        if Path(rel).suffix.lower() in ('.v', '.sv', '.vh', '.vp'):
            def replace(match):
                inc = match.group(1).decode('ascii').replace('\\', '/')
                if not re.match(r'^[A-Za-z]:/', inc) and not inc.startswith('/'):
                    target = (Path(rel).parent / inc).as_posix()
                    if target in sources or 'b4/rtl/' + inc in sources:
                        return match.group(0)
                    if rel == WRITER and inc == 'video_crc32.vh':
                        target = 'source/rtl/video_crc32.vh'
                    else:
                        raise ValueError('Unbound include: ' + inc)
                else:
                    if '/native/' not in inc:
                        raise ValueError('Unknown include prefix: ' + inc)
                    target = inc.split('/native/', 1)[1]
                if target not in sources:
                    raise ValueError('Include outside closure: ' + target)
                dest = (native / target).resolve().as_posix()
                if any(c in dest for c in '{}\n\r"'):
                    raise ValueError('Unsupported path')
                changes.append({'file': rel, 'original': inc, 'compiled': dest})
                return ('`include "' + dest + '"').encode('utf-8')
            blob = INCLUDE.sub(replace, blob)
        prepared[rel] = blob
        files.append({'path': rel, 'input_sha256': sha(original), 'compile_sha256': sha(blob)})
    recipe = json.loads((BASE / 'manifests/build-recipe.json').read_text(encoding='utf-8'))
    def tclpath(path):
        value = path.resolve().as_posix()
        if any(c in value for c in '{}\n\r'):
            raise ValueError('Unsupported Tcl path')
        return '{' + value + '}'
    lines = ['# Independent throughput candidate. New PNR/STA/CDC/IO review required.',
             'proc checked {command} {',
             '  set rc [catch {uplevel 1 $command} result]',
             '  if {$rc != 0} { puts stderr $result; exit 1 }',
             '  puts $result', '}', 'cd ' + tclpath(work)]
    lines += ['checked [list add_design ' + tclpath(native / rel) + ']' for rel in recipe['designs']]
    lines += ['checked [list add_constraint ' + tclpath(native / rel) + ']' for rel in recipe['constraints']]
    lines += ['checked [list set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676]',
              'checked [list compile -top_module board1080_top -include_path ' + tclpath(native / 'b4/rtl') + ']',
              'checked [list synthesize -ads -selected_syn_tool_opt 2]',
              'checked [list dev_map]', 'puts {THROUGHPUT_MAP_COMPLETE_NOT_TIMING_SIGNOFF}']
    # Recheck inputs before writing to guard against concurrent source edits.
    if candidate_sources(variant, mode)[2] != identity:
        raise ValueError('Candidate inputs changed during preparation')
    work.mkdir(parents=True, exist_ok=False)
    for rel, blob in prepared.items():
        dest = native / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
    (work / 'map.tcl').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    result = dict(identity, schema='hdmi1080-throughput-source-v1', source_count=len(sources),
                  work_directory=str(work), include_changes=changes, files=files,
                  eda_executed=False, hardware_accessed=False,
                  map_script_sha256=sha((work / 'map.tcl').read_bytes()))
    (work / 'preparation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dependency-native', type=Path, required=True)
    parser.add_argument('--run-name', required=True)
    parser.add_argument('--variant', choices=['baseline', 'writer', 'cache', 'both'], default='both')
    parser.add_argument('--mode', choices=list(MODES), default='corrected')
    parser.add_argument('--output-root', type=Path, help='Short output directory, e.g. C:/fpga-build')
    args = parser.parse_args()
    result = prepare(args.dependency_native, args.run_name, args.variant, args.mode, args.output_root)
    print(json.dumps({k: result[k] for k in ('variant', 'mode', 'param_id_hex', 'work_directory', 'source_count')}, indent=2))
