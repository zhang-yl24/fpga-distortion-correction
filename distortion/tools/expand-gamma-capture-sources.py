from pathlib import Path
import json
from pds_source_manifest import expand_sources
root=Path(__file__).resolve().parents[1]
manifest=root/'board/gamma_capture-sources.json'
names=json.loads(manifest.read_text(encoding='utf-8-sig'))
expanded=expand_sources(root,names)
if 'board/gamma_capture-sources.json' not in expanded:
    expanded.append('board/gamma_capture-sources.json')
manifest.write_text(json.dumps(expanded,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'sources_before':len(names),'sources_after':len(expanded),'idf_synthesis_sources_bound':True}))
