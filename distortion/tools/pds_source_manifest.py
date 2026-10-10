"""Expand local PDS IP synthesis sources for complete build-time hash binding."""
from pathlib import Path
import xml.etree.ElementTree as ET


def expand_sources(root, names):
    root = Path(root).resolve()
    expanded = []
    for name in names:
        path = (root/name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f'Missing or non-project design source: {name}')
        rel = path.relative_to(root).as_posix()
        if rel not in expanded:
            expanded.append(rel)
        if path.suffix.lower() == '.idf':
            source_nodes = ET.parse(path).findall('./file_list/source/file')
            if not source_nodes:
                raise ValueError(f'IP has no explicit synthesis sources: {name}')
            for node in source_nodes:
                dependency = (path.parent/node.attrib['pathname']).resolve()
                if not dependency.is_relative_to(root) or not dependency.is_file():
                    raise ValueError(f'Missing or non-project IP source: {node.attrib["pathname"]}')
                rel = dependency.relative_to(root).as_posix()
                if rel not in expanded:
                    expanded.append(rel)
    return expanded
