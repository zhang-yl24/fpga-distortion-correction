"""Archive full-frame simulation and verify its entire prepared source closure."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalize(data, root):
    # Preparation rewrites only Verilog include roots. Compare all other bytes.
    marker = b'`include "'
    if marker not in data:
        return data
    prefix = root.resolve().as_posix().encode() + b'/compiled/'
    lines = data.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if marker in line:
            lines[i] = line.replace(prefix, b'<COMPILED>/')
    return b''.join(lines)


def archive(tested, physical, output):
    tested, physical, output = [Path(x).resolve() for x in (tested, physical, output)]
    assert not output.exists(), 'Choose a new evidence directory'
    plans = [json.loads((root/'candidate-plan.json').read_text()) for root in (tested, physical)]
    for key in ('build_id', 'profile_id', 'cache_configuration', 'tile_width', 'tile_height'):
        assert plans[0][key] == plans[1][key], key
    assert set(plans[0]['source_files']) == set(plans[1]['source_files'])
    normalized = {}
    for name in sorted(plans[0]['source_files']):
        values = []
        for root, plan in zip((tested, physical), plans):
            data = (root/'compiled'/name).read_bytes()
            assert sha(data) == plan['source_files'][name], (str(root), name)
            values.append(normalize(data, root))
        assert values[0] == values[1], name
        normalized[name] = sha(values[0])
    report = json.loads((tested/'engine-report.json').read_text())
    assert report['passed'] and report['crc_matches'] and report['mismatched_pixels'] == 0
    assert report['source_identity'] == plans[0]['source_identity']
    for name, expected in report['sources'].items():
        assert sha(Path(name).read_bytes()) == expected, name
    output.mkdir(parents=True)
    copied = {}
    for relative in ('candidate-plan.json', 'engine-report.json', 'sim/engine_full.sv',
                     'sim/engine-result.json', 'sim/xvlog.bat.log', 'sim/xelab.bat.log', 'sim/xsim.bat.log'):
        source = tested/relative
        shutil.copy2(source, output/source.name)
        copied[source.name] = sha(source.read_bytes())
    binding = dict(passed=True, source_files=len(normalized),
                   physical_source_identity=plans[1]['source_identity'],
                   tested_source_identity=plans[0]['source_identity'],
                   normalization='Only absolute compiled include roots',
                   normalized_source_sha256=normalized, evidence_sha256=copied)
    (output/'physical-source-binding.json').write_text(json.dumps(binding, indent=2)+'\n')
    return dict(passed=True, files=len(normalized), output=str(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('tested', 'physical', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(archive(args.tested, args.physical, args.output), indent=2))
