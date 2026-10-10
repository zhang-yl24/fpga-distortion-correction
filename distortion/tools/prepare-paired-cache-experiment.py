"""Isolated cache-hit cycle experiment; active board and prior tests unchanged."""
from pathlib import Path
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[1]
cache = (root / 'rtl/experimental/ddr_short_burst_cache.v').read_text()

def replace(old, new):
    global cache
    assert cache.count(old) == 1, old
    cache = cache.replace(old, new)

replace('    wire [15:0] pixel=cache_q[pixel_lane*16 +:16];', '''    wire [15:0] pixel=cache_q[pixel_lane*16 +:16];
    wire [3:0] right_lane=pixel_lane+4'd1;
    wire [15:0] right_pixel=cache_q[right_lane*16 +:16];
    wire [23:0] right_rgb={right_pixel[15:11],right_pixel[15:13],right_pixel[10:5],right_pixel[10:9],right_pixel[4:0],right_pixel[4:2]};''')
replace('beat_index<=pixel_index[6:4];pixel_lane<=pixel_index[3:0];state<=LOOKUP;', '''beat_index<=pixel_index[6:4];pixel_lane<=pixel_index[3:0];
                        // Check the computed line while latching its address.
                        // LOAD remains synchronous; no asynchronous RAM read.
                        if(valid_lines[pixel_index[7 +: INDEX_BITS]] &&
                            tags[pixel_index[7 +: INDEX_BITS]]==pixel_index[31:7]) begin
                            hits<=hits+1'b1;state<=LOAD;
                        end else begin
                            valid_lines[pixel_index[7 +: INDEX_BITS]]<=0;
                            misses<=misses+1'b1;fill_beat<=0;address_pending<=1;state<=AR;
                        end''')
begin = cache.index('                LOOKUP: begin')
end = cache.index('                AR:', begin)
cache = cache[:begin] + cache[end:]
begin = cache.index('                PICK: begin')
end = cache.index('                RESULT:', begin)
cache = cache[:begin] + '''                PICK: begin
                    // Both horizontal neighbours can use the same fetched beat.
                    // Cross-beat lane 15 and right-border cases retain the
                    // original per-neighbour path and independent zero fill.
                    if(!neighbour[0] && nx<WIDTH-1 && pixel_lane!=15) begin
                        if(neighbour==0) begin p00<=rgb;p10<=right_rgb;neighbour<=2;state<=SELECT;end
                        else begin p01<=rgb;p11<=right_rgb;state<=RESULT;end
                        hits<=hits+1'b1;
                    end else begin
                        case(neighbour) 0:p00<=rgb;1:p10<=rgb;2:p01<=rgb;3:p11<=rgb;endcase
                        if(neighbour==3) state<=RESULT;
                        else begin neighbour<=neighbour+1'b1;state<=SELECT;end
                    end
                end
''' + cache[end:]
cache = '// Isolated paired-neighbour and direct tag-check experiment; no board timing proof.\n' + cache
cache_path = root / 'rtl/experimental/ddr_paired_cache.v'
cache_path.write_text(cache)
engine = (root / 'rtl/experimental/short_burst_frame_engine.v').read_text().replace('short_burst_frame_engine', 'paired_cache_frame_engine')
engine_path = root / 'rtl/experimental/paired_cache_frame_engine.v'
engine_path.write_text(engine)
for kind in ('native', 'query'):
    old_work = root / ('build/short_burst_' + kind + '_sim')
    work = root / ('build/paired_cache_' + kind + '_sim')
    work.mkdir(parents=True, exist_ok=True)
    for src in old_work.glob('*.mem'):
        shutil.copy2(src, work / src.name)
    for name in ('counts.vh', 'reference.json'):
        if (old_work / name).exists():
            shutil.copy2(old_work / name, work / name)
    tb_path = root / ('tests/tb_short_burst_native_regression.sv' if kind == 'native' else 'tests/tb_short_burst_query.sv')
    tb = tb_path.read_text().replace('short_burst', 'paired_cache').replace('short burst', 'paired cache')
    (root / 'tests' / tb_path.name.replace('short_burst', 'paired_cache')).write_text(tb)
    runner = (root / ('tools/run-short-burst-' + kind + '-sim.ps1')).read_text(encoding='utf-8-sig')
    runner = runner.replace('short_burst', 'paired_cache').replace('short burst', 'paired cache')
    runner = runner.replace('ddr_paired_cache_cache', 'ddr_paired_cache')
    # Original module file names are ddr_short_burst_cache / short_burst_frame_engine.
    (root / ('tools/run-paired-cache-' + kind + '-sim.ps1')).write_text(runner, encoding='utf-8-sig')
    snapshot = work / 'source-snapshot'
    snapshot.mkdir(exist_ok=True)
    files = [cache_path, engine_path, root / 'rtl/experimental/ddr_adaptive_result_writer.v']
    hashes = {}
    for p in files:
        shutil.copy2(p, snapshot / p.name)
        hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    (snapshot / 'files-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
print('Prepared paired cache native/query tests with sealed inputs; board sources unchanged.')
