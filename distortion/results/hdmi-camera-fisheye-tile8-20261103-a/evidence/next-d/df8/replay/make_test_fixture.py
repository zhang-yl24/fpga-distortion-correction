"""Copy an explicit small LOCAL TEST FIXTURE; never make a release receipt.

This temporary input map binds current saved unit/collision evidence and110
production source bytes. It does not assemble real bit/physical/FPS stage D.
"""
from pathlib import Path
import argparse
import json
import shutil

import portable_source_contract as portable


def prepare(repo, output, candidate='df9tp'):
    repo, output = Path(repo).resolve(), Path(output).resolve()
    portable.require(candidate in portable.CANDIDATES and not output.exists(), 'fresh temporary fixture directory required')
    portable.require(not output.is_relative_to(repo / 'distortion/results'), 'test fixture must not masquerade as released results')
    root = repo / 'distortion'; config = portable.CANDIDATES[candidate]
    manifest_path = root / f'board/hdmi-camera-fisheye-tile8{candidate}-build-sources.json'
    roles = {name: root / config[name] for name in ('Source', 'Baseline', 'Helper', 'HelperTests')}
    roles.update(ProductionManifest=manifest_path, UnitReceipt=root / config['UnitWork'] / 'simulation.json',
                 CollisionReceipt=root / config['CollisionWork'] / 'simulation.json')
    sources = {}

    def add(path, expected=None):
        path = Path(path).resolve(strict=True)
        portable.require(path.is_relative_to(repo) and path.is_file(), 'fixture input must be an actual repository file')
        h = portable.sha(path)
        portable.require(expected is None or h == expected, 'fixture source SHA drift: ' + str(path))
        key = portable.windows_identity(str(path))
        if key in sources:
            portable.require(sources[key]['SHA256'] == h, 'conflicting fixture identity')
            return
        sources[key] = {'OriginalPath': str(path), 'BundlePath': 'payload/' + path.relative_to(repo).as_posix(),
                        'SHA256': h, 'Bytes': path.stat().st_size}

    for name, path in roles.items(): add(path, config[name + 'SHA256'])
    manifest = portable.load_json(manifest_path)
    for name, h in manifest['SourceSHA256'].items(): add(root / name, h)
    for name in ('UnitReceipt', 'CollisionReceipt'):
        path = roles[name]; value = portable.load_json(path)
        for original, h in value['SourceSHA256'].items(): add(original, h)
        for artifact, h in value['ArtifactsSHA256'].items():
            parts = portable.relative_artifact(artifact).parts
            add(path.parent.joinpath(*parts), h)
    # Validate the whole input inventory before any copy. No source is changed.
    for row in sources.values():
        source = Path(row['OriginalPath'])
        portable.require(portable.sha(source) == row['SHA256'] and source.stat().st_size == row['Bytes'], 'fixture input changed')
    output.mkdir(parents=True)
    for row in sources.values():
        target = output / row['BundlePath']; target.parent.mkdir(parents=True, exist_ok=True)
        with Path(row['OriginalPath']).open('rb') as src, target.open('xb') as dst:
            shutil.copyfileobj(src, dst)
    mapping = {'Schema': portable.SCHEMA, 'Candidate': candidate,
               'Roles': {name: str(path) for name, path in roles.items()}, 'Files': list(sources.values())}
    mapping_path = output / 'source-contract-map.json'
    with mapping_path.open('x', encoding='utf-8') as stream:
        json.dump(mapping, stream, indent=2); stream.write('\n')
    return mapping_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate', choices=sorted(portable.CANDIDATES), default='df9tp')
    args = parser.parse_args(argv)
    path = prepare(args.repo, args.output, args.candidate)
    print(json.dumps({'TemporaryFixtureInputMap': str(path), 'PublicationReceiptWritten': False,
                      'EDAExecuted': False, 'HardwareAccessed': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
