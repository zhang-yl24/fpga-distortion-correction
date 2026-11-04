"""Verify finite saved bytes only, including decoded split gzip; never replay hardware."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import zlib

MAX_PART = 8 * 1024 * 1024
MAX_LOGICAL = 1024 * 1024 * 1024


def require(ok, message):
    if not ok:
        raise ValueError(message)


def local(path):
    path = Path(path).absolute()
    value = str(path)
    return Path('\\\\?\\' + value) if os.name == 'nt' and not value.startswith('\\\\?\\') else path


def relative(name):
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name, 'relative POSIX path required')
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.as_posix() == name and all(part not in ('','.','..') and part.casefold() != '.git' for part in path.parts), 'unsafe path')
    return path


def identity(row, maximum):
    require(type(row.get('Bytes')) is int and 0 <= row['Bytes'] <= maximum and
            isinstance(row.get('SHA256'),str) and re.fullmatch('[0-9a-f]{64}',row['SHA256']), 'invalid byte identity')


def safe_path(root, name):
    path = root.joinpath(*relative(name).parts)
    require(path.resolve().is_relative_to(root) and path == path.resolve(), 'payload escaped or traverses link')
    for item in (path,*path.parents):
        if item == root:
            break
        require(not item.is_symlink(), 'symlink payload forbidden')
    return local(path)


def digest(path):
    hashed = hashlib.sha256()
    length = 0
    with local(path).open('rb') as stream:
        for data in iter(lambda:stream.read(65536),b''):
            length += len(data);hashed.update(data)
    return length,hashed.hexdigest()


def decoded_digest(root, row, indexed):
    parts = row['Parts']
    require(isinstance(parts,list) and parts and len(parts) == len(set(parts)), 'nonempty unique ordered parts required')
    require(all(name in indexed for name in parts), 'logical payload references unlisted bytes')
    if row['Encoding'] == 'identity':
        require(len(parts) == 1, 'identity payload must have one part')
        item = indexed[parts[0]]
        return item['Bytes'], item['SHA256']
    require(row['Encoding'] == 'gzip', 'unsupported stored encoding')
    decoder = zlib.decompressobj(31)
    hashed = hashlib.sha256();count = 0
    for name in parts:
        with safe_path(root,name).open('rb') as stream:
            for chunk in iter(lambda:stream.read(65536),b''):
                require(not decoder.eof, 'trailing compressed bytes forbidden')
                pending = chunk
                while pending:
                    data = decoder.decompress(pending,65536)
                    pending = decoder.unconsumed_tail
                    count += len(data);hashed.update(data)
                    require(count <= row['Bytes'], 'decoded payload exceeds declared size')
                    require(not decoder.unused_data, 'multiple members or trailing data forbidden')
    require(decoder.eof and not decoder.unconsumed_tail and not decoder.unused_data, 'incomplete gzip payload')
    return count,hashed.hexdigest()


def review(root):
    root = Path(root).resolve()
    manifest = json.loads(local(root/'sha-manifest.json').read_text(encoding='utf-8'))
    require(manifest.get('Schema') == 'tile8-fastpipe-board-saved-byte-manifest-v1' and
            manifest.get('SavedEvidenceOnly') is True and all(manifest.get(key) is False for key in
            ('HDLReexecuted','STAReexecuted','HardwareAccessed')), 'saved-byte scope required')
    indexed = {};folded = set()
    for row in manifest['Files']:
        name = row['BundlePath'];relative(name);identity(row,MAX_PART)
        require(name.casefold() not in folded and name != 'sha-manifest.json','duplicate or recursive manifest payload')
        folded.add(name.casefold());indexed[name] = row
        path = safe_path(root,name)
        require(path.is_file() and digest(path) == (row['Bytes'],row['SHA256']), 'saved part SHA/size mismatch: '+name)
    require(indexed, 'empty saved inventory')
    for name in indexed:
        for parent in relative(name).parents:
            require(parent.as_posix() not in indexed, 'file is another payload parent')
    logical = manifest['LogicalPayloads'];roles = set();used = set()
    require(logical, 'empty logical inventory')
    for row in logical:
        require(isinstance(row.get('Role'),str) and row['Role'] and row['Role'] not in roles, 'unique evidence roles required')
        roles.add(row['Role']);identity(row,MAX_LOGICAL)
        require(decoded_digest(root,row,indexed) == (row['Bytes'],row['SHA256']), 'logical payload identity mismatch: '+row['Role'])
        used.update(row['Parts'])
    require(used == set(indexed), 'unmapped or unlisted stored payload')
    return dict(Schema='tile8-fastpipe-board-saved-byte-review-v1',Passed=True,
        FilesVerified=len(indexed),LogicalPayloadsVerified=len(logical),SavedEvidenceOnly=True,
        HDLReexecuted=False,STAReexecuted=False,HardwareAccessed=False,
        FullSystemOrBoardAcceptanceConferred=False,
        Scope='Exact saved file and decoded gzip SHA/size only. Historical result fields are not re-executed proofs.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=Path(__file__).resolve().parent)
    print(json.dumps(review(parser.parse_args().bundle),indent=2))
