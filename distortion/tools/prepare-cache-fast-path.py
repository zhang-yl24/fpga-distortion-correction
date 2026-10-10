"""Generate an isolated candidate; production DDR cache is preserved for routing."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parents[1]
src = root / 'rtl/ddr_neighbour_cache.v'
text = src.read_text()
old = '''                    if(neighbour==3) state<=RESULT;
                    else begin neighbour<=neighbour+1'b1;state<=SELECT;end'''
new = '''                    if(neighbour==3) state<=RESULT;
                    // A left neighbour already fetched this synchronous RAM
                    // beat. Its right neighbour may use it on the next cycle.
                    // Do not cross RGB565 lane 15 or the image's right border.
                    else if(!neighbour[0] && nx<WIDTH-1 && pixel_lane!=15) begin
                        neighbour<=neighbour+1'b1;pixel_lane<=pixel_lane+1'b1;
                        hits<=hits+1'b1;state<=PICK;
                    end else begin neighbour<=neighbour+1'b1;state<=SELECT;end'''
assert text.count(old) == 1
text = '// Experimental build selection only: same public module, isolated file.\n' + text.replace(old, new)
out = root / 'rtl/experimental/ddr_neighbour_cache_fast.v'
out.parent.mkdir(exist_ok=True)
out.write_text(text)
record = {'baseline_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
          'candidate_sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
          'scope': 'Reuses one fetched 256-bit beat for adjacent horizontal RGB565 neighbours; avoids SELECT/LOOKUP/LOAD on that neighbour. No change to DDR burst ownership, miss handling, memory capacity, border zeroing, or fault quarantine. Candidate is not selected in board targets.'}
(root / 'results/cache-fast-path-source-20261006.json').write_text(json.dumps(record, indent=2) + '\n')
print('Generated isolated adjacent-beat cache reuse candidate.')
