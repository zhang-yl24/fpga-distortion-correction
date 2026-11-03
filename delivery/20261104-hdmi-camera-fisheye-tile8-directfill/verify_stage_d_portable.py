"""CPU-only delivery entry for a completed D package; never reruns EDA/hardware.

This is prepared source, not a publication receipt. It refuses missing D results.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from types import ModuleType

BASE_C_SHA = 'ab2f88a9ef8fdc53b503ad74403f5869738ff2867c3525f7c2e1141baabfcbcc'
ADAPTER_SHA = 'df228ebd19c15ab4281f329bfb8c595d22e0595775f238fe24440be9837e319a'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    def unique(rows):
        value = {}
        for key, item in rows:
            require(key not in value, 'duplicate JSON key')
            value[key] = item
        return value
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique)


def inside(package, name):
    require(type(name) is str and '\\' not in name and ':' not in name, 'canonical package relative path required')
    rel = PurePosixPath(name)
    require(not rel.is_absolute() and '..' not in rel.parts and rel.parts and rel.as_posix() == name, 'package path escaped')
    path = package.joinpath(*rel.parts).resolve()
    require(path.is_relative_to(package) and path.is_file(), 'missing/escaped bundled file')
    return path


def verify(package):
    package = Path(package).resolve()
    manifest = read(package / 'portable-evidence-manifest-d.json')
    require(manifest['Schema'] == 'hdmi-camera-fisheye-tile8-portable-archive-v1' and
            manifest['ManifestSelfExcluded'] is True and manifest['LargePhysicalProofsBundled'] is False, 'D archive schema/scope differs')
    files = {}
    for row in manifest['BundledFiles']:
        name = row['Path']; identity = name.casefold()
        require(identity not in files, 'duplicate portable archive path')
        path = inside(package, name)
        require(path.stat().st_size == row['Bytes'] and digest(path) == row['SHA256'], 'bundled archive byte drift: ' + name)
        files[identity] = row
    actual = {p.relative_to(package).as_posix().casefold() for p in package.rglob('*') if p.is_file()}
    require(actual == set(files) | {'portable-evidence-manifest-d.json'}, 'unmanifested/missing archive file')
    old = package / 'portable-evidence-manifest-c.json'
    require(digest(old) == BASE_C_SHA, 'immutable published C identity differs')
    base = read(old)
    require(len(base['BundledFiles']) == 449, 'incomplete historical A/B/C package')
    for row in base['BundledFiles']:
        require(files.get(row['Path'].casefold()) == row, 'historical A/B/C bytes differ')
    receipt = read(package / 'copy-receipt-d.json')
    require(receipt['Schema'] == 'hdmi-camera-fisheye-tile8-evidence-archive-receipt-v1' and
            receipt['Passed'] is True and receipt['Candidate'] == 'df8' and receipt['HistoricalABCBytesPreserved'] is True and
            receipt['ProviderVerificationInvoked'] is False and receipt['EDAExecuted'] is False and receipt['HardwareAccessed'] is False,
            'missing completed D saved-byte receipt or exceeded replay scope')
    replay = receipt['PortableReplay']
    require(replay['Map'] == 'source-contract-map-d.json', 'explicit stage D source-contract map required')
    mapping = inside(package, replay['Map'])
    require(digest(mapping) == receipt['PortableSourceContractMap']['SHA256'], 'D portable map differs')
    adapter = inside(package, replay['Adapter'])
    require(digest(adapter) == ADAPTER_SHA, 'frozen portable adapter differs before execution')
    module = ModuleType('frozen_stage_d_portable'); module.__file__ = str(adapter)
    exec(compile(adapter.read_bytes(), str(adapter), 'exec'), module.__dict__)
    facts, watched = module.review(package, mapping)
    require(facts['Candidate'] == 'df8' and facts['PortableSourceContractVerified'] is True and facts['PublicationComplete'] is False,
            'finite portable source replay differs')
    return {'ArchiveBytesVerified': True, 'HistoricalABCBytesPreserved': True,
            'BundledFilesVerified': len(files), 'PortableSourceContractFacts': facts,
            'NewRTLRunExecuted': False, 'NativePhysicalAcceptanceRecomputed': False,
            'BitstreamOrBoardAcceptanceRecomputed': False, 'EDAExecuted': False, 'HardwareAccessed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.package), indent=2))


if __name__ == '__main__':
    main()
