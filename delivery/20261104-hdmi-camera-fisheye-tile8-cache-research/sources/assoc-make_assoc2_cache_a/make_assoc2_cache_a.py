"""Derive an isolated two-way full-tag prototype from frozen tagpipe bytes."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SOURCE = REPO / 'distortion/rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill_tagpipe.v'
PIN = 'cc47c00bf2458491c1def0c5be3a2f8d209269a57dc2259d46ce7ce1054486a1'
DESTINATION = HERE / 'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_a.v'


def main():
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PIN:
        raise ValueError('frozen tagpipe bytes differ')
    text = raw.decode('utf-8').replace('\r\n', '\n')
    changes = []

    def change(old, new, role, count=1):
        nonlocal text
        if text.count(old) != count:
            raise ValueError('nonexact transformation ' + role + ': ' + str(text.count(old)))
        text = text.replace(old, new)
        changes.append(role)

    change('    localparam LINES=1<<INDEX_BITS,ADDRESS_BITS=INDEX_BITS+6,WORD_ADDRESS_BITS=INDEX_BITS+4;',
           '    localparam LINES=1<<INDEX_BITS,SETS=LINES/2,SET_BITS=INDEX_BITS-1,ADDRESS_BITS=INDEX_BITS+6,WORD_ADDRESS_BITS=INDEX_BITS+4;\n'
           '    // INDEX_BITS is TOTAL physical lines: {way,set}. Full DDR block tags remain 25 bits.\n'
           '    reg [SETS-1:0] lru_way; // 0 => evict way0; touch way0 sets 1, touch way1 sets 0.', 'equal-capacity two-way geometry')
    change('    reg [4*INDEX_BITS-1:0] decoded_index_head,decoded_index_tail;',
           '    reg [4*SET_BITS-1:0] decoded_index_head,decoded_index_tail;', 'decoded set indices')
    change('    reg [INDEX_BITS-1:0] query_line_index[0:3];',
           '    reg [SET_BITS-1:0] query_line_index[0:3];\n'
           '    reg [24:0] query_cached_tag_way1[0:3];\n'
           '    reg [3:0] query_cached_valid_way1;\n'
           '    wire [3:0] query_hit_way;', 'both-way complete held query metadata')
    change('    reg selected_cached_valid;',
           '    reg selected_cached_valid;\n'
           '    reg [24:0] selected_cached_tag_way1;\n'
           '    reg selected_cached_valid_way1,selected_cached_lru;\n'
           '    wire selected_hit0=selected_cached_valid && selected_cached_tag==selected_block;\n'
           '    wire selected_hit1=selected_cached_valid_way1 && selected_cached_tag_way1==selected_block;\n'
           '    wire selected_hit=selected_hit0 || selected_hit1;\n'
           '    wire selected_choose_way=selected_hit0 ? 1\'b0:selected_hit1 ? 1\'b1:\n'
           '        !selected_cached_valid ? 1\'b0:!selected_cached_valid_way1 ? 1\'b1:selected_cached_lru;\n'
           '    wire [INDEX_BITS-1:0] selected_choose_line={selected_choose_way,selected_line[SET_BITS-1:0]};', 'synchronous slow hit/invalid/LRU choice')
    change('        assign pixel_address[n]=pixel_number[n][1 +: ADDRESS_BITS];\n'
           '        assign line_hit[n]=!in_bounds[n] || (query_cached_valid[n] &&\n'
           '            query_cached_tag[n]==pixel_number[n][31:7]);',
           '        wire hit0=query_cached_valid[n] && query_cached_tag[n]==pixel_number[n][31:7];\n'
           '        wire hit1=query_cached_valid_way1[n] && query_cached_tag_way1[n]==pixel_number[n][31:7];\n'
           '        assign query_hit_way[n]=!hit0 && hit1;\n'
           '        assign pixel_address[n]={query_hit_way[n],query_line_index[n],pixel_number[n][6:1]};\n'
           '        assign line_hit[n]=!in_bounds[n] || hit0 || hit1;', 'per-neighbour full-tag way and physical RAM address')
    change('        wire [INDEX_BITS-1:0] metadata_index=state==RESULT ? query_line_index[n]:\n'
           '            decoded_index_head[n*INDEX_BITS+:INDEX_BITS];',
           '        wire [SET_BITS-1:0] metadata_index=state==RESULT ? query_line_index[n]:\n'
           '            decoded_index_head[n*SET_BITS+:SET_BITS];', 'fixed held set on stalled RESULT')
    change('                query_cached_tag[n]<=tags[metadata_index];\n'
           '                query_cached_valid[n]<=valid_lines[metadata_index];',
           '                query_cached_tag[n]<=tags[{1\'b0,metadata_index}];\n'
           '                query_cached_valid[n]<=valid_lines[{1\'b0,metadata_index}];\n'
           '                query_cached_tag_way1[n]<=tags[{1\'b1,metadata_index}];\n'
           '                query_cached_valid_way1[n]<=valid_lines[{1\'b1,metadata_index}];', 'both-way read-old-safe refresh after slow consumption')
    change('            selected_cached_tag<=tags[selected_line];\n'
           '            selected_cached_valid<=valid_lines[selected_line];',
           '            selected_cached_tag<=tags[{1\'b0,selected_line[SET_BITS-1:0]}];\n'
           '            selected_cached_valid<=valid_lines[{1\'b0,selected_line[SET_BITS-1:0]}];\n'
           '            selected_cached_tag_way1<=tags[{1\'b1,selected_line[SET_BITS-1:0]}];\n'
           '            selected_cached_valid_way1<=valid_lines[{1\'b1,selected_line[SET_BITS-1:0]}];\n'
           '            selected_cached_lru<=lru_way[selected_line[SET_BITS-1:0]];', 'slow both-way tag and replacement snapshot')
    change('    wire slow_hit_increment=state==CHECK && selected_cached_valid &&\n'
           '        selected_cached_tag==selected_block;',
           '    wire slow_hit_increment=state==CHECK && selected_hit;', 'preserve hit event timing across both ways')
    change('state<=IDLE;frame_loaded<=0;address_pending<=0;base<=0;valid_lines<=0;',
           'state<=IDLE;frame_loaded<=0;address_pending<=0;base<=0;valid_lines<=0;lru_way<=0;', 'common reset invalidates both ways and LRU')
    change('decoded_index_head[i*INDEX_BITS+:INDEX_BITS]<=decoded_number[i][7 +: INDEX_BITS];',
           'decoded_index_head[i*SET_BITS+:SET_BITS]<=decoded_number[i][7 +: SET_BITS];', 'head set decode')
    change('decoded_index_tail[i*INDEX_BITS+:INDEX_BITS]<=decoded_number[i][7 +: INDEX_BITS];',
           'decoded_index_tail[i*SET_BITS+:SET_BITS]<=decoded_number[i][7 +: SET_BITS];', 'tail set decode')
    change('query_line_index[i]<=decoded_index_head[i*INDEX_BITS+:INDEX_BITS];',
           'query_line_index[i]<=decoded_index_head[i*SET_BITS+:SET_BITS];', 'held set follows numbers and payload')
    change('                for(i=0;i<4;i=i+1)parity0[i]<=pixel_number[i][0];',
           '                // Neighbour 00,10,01,11 order. Last assignment for a repeated set wins;\n'
           '                // each bit is !touched_way, independent of the old LRU bit.\n'
           '                for(i=0;i<4;i=i+1)begin\n'
           '                    parity0[i]<=pixel_number[i][0];\n'
           '                    if(in_bounds[i])lru_way[query_line_index[i]]<=!query_hit_way[i];\n'
           '                end', 'one-bit LRU sequential-neighbour fast demand order')
    change('if(accept_frame)begin base<=frame_base;valid_lines<=0;frame_loaded<=1;end',
           'if(accept_frame)begin base<=frame_base;valid_lines<=0;lru_way<=0;frame_loaded<=1;end', 'frame epoch invalidates both ways')
    change('selected_block<=selected_number[31:7];selected_line<=selected_number[7 +: INDEX_BITS];\n'
           '                        selected_pixel_address<=selected_number[1 +: ADDRESS_BITS];selected_parity<=selected_number[0];',
           'selected_block<=selected_number[31:7];selected_line<={1\'b0,selected_number[7 +: SET_BITS]};\n'
           '                        selected_pixel_address<={1\'b0,selected_number[7 +: SET_BITS],selected_number[6:1]};selected_parity<=selected_number[0];', 'slow block/set/offset lock before metadata read')
    change('                        if(selected_cached_valid && selected_cached_tag==selected_block)begin\n'
           '                            state<=LOAD;\n'
           '                        end else begin\n'
           '                            valid_lines[selected_line]<=0;',
           '                        // Lock chosen physical line before AR and every RAM operation.\n'
           '                        selected_line<=selected_choose_line;\n'
           '                        selected_pixel_address<={selected_choose_way,selected_pixel_address[ADDRESS_BITS-2:0]};\n'
           '                        if(selected_hit)begin\n'
           '                            lru_way[selected_line[SET_BITS-1:0]]<=!selected_choose_way;\n'
           '                            state<=LOAD;\n'
           '                        end else begin\n'
           '                            valid_lines[selected_choose_line]<=0;', 'hit/invalid/LRU victim line chosen once before owned refill')
    change('                        tags[write_commit_line]<=fill_write_block;\n'
           '                        state<=LOAD;',
           '                        tags[write_commit_line]<=fill_write_block;\n'
           '                        lru_way[write_commit_line[SET_BITS-1:0]]<=!write_commit_line[INDEX_BITS-1];\n'
           '                        state<=LOAD;', 'LRU insertion only on last actual RAM commit')
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    with DESTINATION.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write('// EXPERIMENT ONLY: two-way capacity model candidate; no native/board acceptance.\n' + text)
    value = dict(Schema='tile8-two-way-tagpipe-prototype-source-v1', ResearchOnly=True,
                 Baseline=dict(Path=str(SOURCE), SHA256=PIN),
                 Variant=dict(Path=str(DESTINATION), SHA256=hashlib.sha256(DESTINATION.read_bytes()).hexdigest()),
                 Transformations=changes, IndexBitsIsTotalPhysicalLines=True, Ways=2,
                 FullBlockTagBits=25, PublicInterfaceUnchanged=True,
                 NoNewOutstandingOwner=True, EDAExecuted=False, HardwareAccessed=False,
                 PhysicalOrReleaseAccepted=False)
    with (HERE / 'source-a.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    print(json.dumps(value))


if __name__ == '__main__':
    main()
