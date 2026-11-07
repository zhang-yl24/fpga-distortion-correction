"""Derive complete-query metadata FIFO; only new experimental output is written."""
from pathlib import Path
import hashlib,json
BASE=Path(__file__).resolve().parent
SOURCE=BASE.parent/'assoc2way256-choose-clear-a/rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_choose_clear_a.v'
TARGET=BASE/'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_fastpipe_a.v'
PIN='62225f2694f1c7441ec8c37b219d20643fce5b3847897d4ec590d3a306a4d728'

DECL='''    // Four complete metadata slots plus a synchronous-read reservation.
    // Reserved count includes the read in flight: no current pop lookahead.
    reg [2:0] metadata_count,metadata_reserved_count;
    reg [1:0] metadata_read,metadata_write;
    reg metadata_read_valid;
    reg signed [16:0] metadata_x[0:3],metadata_y[0:3];
    reg [7:0] metadata_fx[0:3],metadata_fy[0:3];
    reg [TAG_W-1:0] metadata_tag[0:3];
    reg [127:0] metadata_numbers[0:3];
    reg [3:0] metadata_bounds[0:3],metadata_hitway[0:3];
    reg [4*SET_BITS-1:0] metadata_indices[0:3];
    reg metadata_all_hit[0:3];
    reg signed [16:0] metadata_read_x,metadata_read_y;
    reg [7:0] metadata_read_fx,metadata_read_fy;
    reg [TAG_W-1:0] metadata_read_tag;
    reg [127:0] metadata_read_numbers;
    reg [3:0] metadata_read_bounds;
    reg [4*SET_BITS-1:0] metadata_read_indices;
    wire [3:0] metadata_return_hitway,metadata_return_line_hit;
    reg [3:0] query_hitway_q;
    reg query_all_hit_q;
    reg meta_refresh_active,meta_refresh_phase;
    reg [2:0] meta_refresh_slot;
    wire meta_refresh_issue=meta_refresh_active && !meta_refresh_phase && !failed;
    wire meta_refresh_return=meta_refresh_active && meta_refresh_phase && !failed;
    wire metadata_fetch=decoded_count!=0 && metadata_reserved_count<4 &&
        !failed && state==IDLE && !meta_refresh_active;
'''

OLDGEN='''        wire hit0=query_cached_valid[n] && query_cached_tag[n]==pixel_number[n][31:7];
        wire hit1=query_cached_valid_way1[n] && query_cached_tag_way1[n]==pixel_number[n][31:7];
        assign query_hit_way[n]=!hit0 && hit1;
        assign pixel_address[n]={query_hit_way[n],query_line_index[n],pixel_number[n][6:1]};
        assign line_hit[n]=!in_bounds[n] || hit0 || hit1;
        // A younger query may be looked up on its predecessor's miss edge.
        // Fill can replace the same index; refresh only after slow RESULT is
        // consumed, when all real final commits and publications have drained.
        // RESULT selects a fixed held index even while out_ready is stalled.
        wire refresh_query=consume_slow && query_valid;
        wire [SET_BITS-1:0] metadata_index=state==RESULT ? query_line_index[n]:
            decoded_index_head[n*SET_BITS+:SET_BITS];
        always @(posedge clk)begin
            if(pre_to_query || refresh_query)begin
                query_cached_tag[n]<=tags[{1'b0,metadata_index}];
                query_cached_valid[n]<=valid_lines[{1'b0,metadata_index}];
                query_cached_tag_way1[n]<=tags[{1'b1,metadata_index}];
                query_cached_valid_way1[n]<=valid_lines[{1'b1,metadata_index}];
            end
        end
'''
NEWGEN='''        // The retained aliases permit independent snapshot/oracle checking.
        wire hit0=query_cached_valid[n] && query_cached_tag[n]==pixel_number[n][31:7];
        wire hit1=query_cached_valid_way1[n] && query_cached_tag_way1[n]==pixel_number[n][31:7];
        assign query_hit_way[n]=query_hitway_q[n];
        assign pixel_address[n]={query_hit_way[n],query_line_index[n],pixel_number[n][6:1]};
        assign line_hit[n]=!in_bounds[n] || hit0 || hit1;
        reg [24:0] metadata_read_tag0,metadata_read_tag1;
        reg metadata_read_valid0,metadata_read_valid1;
        reg [24:0] metadata_slot_tag0[0:3],metadata_slot_tag1[0:3];
        reg metadata_slot_valid0[0:3],metadata_slot_valid1[0:3];
        wire [31:0] return_number=metadata_read_numbers[n*32+:32];
        wire return_hit0=metadata_read_valid0 && metadata_read_tag0==return_number[31:7];
        wire return_hit1=metadata_read_valid1 && metadata_read_tag1==return_number[31:7];
        assign metadata_return_hitway[n]=!return_hit0 && return_hit1;
        assign metadata_return_line_hit[n]=!metadata_read_bounds[n] || return_hit0 || return_hit1;
        wire [SET_BITS-1:0] refresh_index=meta_refresh_slot==4 ? query_line_index[n]:
            metadata_indices[meta_refresh_slot[1:0]][n*SET_BITS+:SET_BITS];
        wire [SET_BITS-1:0] metadata_index=meta_refresh_active ? refresh_index:
            decoded_index_head[n*SET_BITS+:SET_BITS];
        always @(posedge clk)begin
            // No accept_query, accept_fast or downstream-ready term drives
            // either tag-RAM read enable. Capacity and refresh are registered.
            if(metadata_fetch || meta_refresh_issue)begin
                metadata_read_tag0<=tags[{1'b0,metadata_index}];
                metadata_read_valid0<=valid_lines[{1'b0,metadata_index}];
                metadata_read_tag1<=tags[{1'b1,metadata_index}];
                metadata_read_valid1<=valid_lines[{1'b1,metadata_index}];
            end
            if(metadata_read_valid && !failed)begin
                metadata_slot_tag0[metadata_write]<=metadata_read_tag0;
                metadata_slot_valid0[metadata_write]<=metadata_read_valid0;
                metadata_slot_tag1[metadata_write]<=metadata_read_tag1;
                metadata_slot_valid1[metadata_write]<=metadata_read_valid1;
            end
            if(pre_to_query)begin
                query_cached_tag[n]<=metadata_slot_tag0[metadata_read];
                query_cached_valid[n]<=metadata_slot_valid0[metadata_read];
                query_cached_tag_way1[n]<=metadata_slot_tag1[metadata_read];
                query_cached_valid_way1[n]<=metadata_slot_valid1[metadata_read];
            end
            if(meta_refresh_return)begin
                if(meta_refresh_slot==4)begin
                    query_cached_tag[n]<=metadata_read_tag0;
                    query_cached_valid[n]<=metadata_read_valid0;
                    query_cached_tag_way1[n]<=metadata_read_tag1;
                    query_cached_valid_way1[n]<=metadata_read_valid1;
                end else begin
                    metadata_slot_tag0[meta_refresh_slot[1:0]]<=metadata_read_tag0;
                    metadata_slot_valid0[meta_refresh_slot[1:0]]<=metadata_read_valid0;
                    metadata_slot_tag1[meta_refresh_slot[1:0]]<=metadata_read_tag1;
                    metadata_slot_valid1[meta_refresh_slot[1:0]]<=metadata_read_valid1;
                end
            end
        end
'''

OLDQUERY='''            if(pre_to_query)begin
                decoded_read<=!decoded_read;
                query_valid<=1;query_x<=decoded_x[decoded_read];query_y<=decoded_y[decoded_read];
                query_fx<=decoded_fx[decoded_read];query_fy<=decoded_fy[decoded_read];
                query_tag<=decoded_tag[decoded_read];in_bounds<=decoded_bound_queue[decoded_read];
                for(i=0;i<4;i=i+1)begin
                    pixel_number[i]<=decoded_numbers[decoded_read][i*32+:32];
                    query_line_index[i]<=decoded_index_head[i*SET_BITS+:SET_BITS];
                end
            end else if(accept_query)query_valid<=0;
'''
NEWQUERY='''            // The synchronous metadata return is compared and registered
            // before it can reach the actual issue head or replacement logic.
            metadata_read_valid<=metadata_fetch;
            case({metadata_read_valid,pre_to_query})
                2'b10:metadata_count<=metadata_count+1'b1;
                2'b01:metadata_count<=metadata_count-1'b1;
                default:metadata_count<=metadata_count;
            endcase
            case({metadata_fetch,pre_to_query})
                2'b10:metadata_reserved_count<=metadata_reserved_count+1'b1;
                2'b01:metadata_reserved_count<=metadata_reserved_count-1'b1;
                default:metadata_reserved_count<=metadata_reserved_count;
            endcase
            if(metadata_fetch)begin
                decoded_read<=!decoded_read;
                metadata_read_x<=decoded_x[decoded_read];metadata_read_y<=decoded_y[decoded_read];
                metadata_read_fx<=decoded_fx[decoded_read];metadata_read_fy<=decoded_fy[decoded_read];
                metadata_read_tag<=decoded_tag[decoded_read];metadata_read_bounds<=decoded_bound_queue[decoded_read];
                metadata_read_numbers<=decoded_numbers[decoded_read];metadata_read_indices<=decoded_index_head;
            end
            if(metadata_read_valid)begin
                metadata_x[metadata_write]<=metadata_read_x;metadata_y[metadata_write]<=metadata_read_y;
                metadata_fx[metadata_write]<=metadata_read_fx;metadata_fy[metadata_write]<=metadata_read_fy;
                metadata_tag[metadata_write]<=metadata_read_tag;metadata_bounds[metadata_write]<=metadata_read_bounds;
                metadata_numbers[metadata_write]<=metadata_read_numbers;metadata_indices[metadata_write]<=metadata_read_indices;
                metadata_hitway[metadata_write]<=metadata_return_hitway;
                metadata_all_hit[metadata_write]<=&metadata_return_line_hit;
                metadata_write<=metadata_write+1'b1;
            end
            if(pre_to_query)begin
                metadata_read<=metadata_read+1'b1;
                query_valid<=1;query_x<=metadata_x[metadata_read];query_y<=metadata_y[metadata_read];
                query_fx<=metadata_fx[metadata_read];query_fy<=metadata_fy[metadata_read];
                query_tag<=metadata_tag[metadata_read];in_bounds<=metadata_bounds[metadata_read];
                query_hitway_q<=metadata_hitway[metadata_read];query_all_hit_q<=metadata_all_hit[metadata_read];
                for(i=0;i<4;i=i+1)begin
                    pixel_number[i]<=metadata_numbers[metadata_read][i*32+:32];
                    query_line_index[i]<=metadata_indices[metadata_read][i*SET_BITS+:SET_BITS];
                end
            end else if(accept_query)query_valid<=0;
            // No fetch is possible during a slow transaction. The one read
            // issued on its acceptance edge returns before SELECT completes.
            // Refresh every physical queue slot and the held issue head only
            // after the complete slow RESULT is consumed. Invalid slots stay
            // unobservable through the registered occupancy masks.
            if(consume_slow)begin
                meta_refresh_active<=1;meta_refresh_phase<=0;meta_refresh_slot<=0;
            end else if(meta_refresh_active)begin
                if(!meta_refresh_phase)begin
                    if(meta_refresh_slot==4)begin
                        metadata_read_bounds<=in_bounds;
                        for(i=0;i<4;i=i+1)metadata_read_numbers[i*32+:32]<=pixel_number[i];
                    end else begin
                        metadata_read_bounds<=metadata_bounds[meta_refresh_slot[1:0]];
                        metadata_read_numbers<=metadata_numbers[meta_refresh_slot[1:0]];
                    end
                    meta_refresh_phase<=1;
                end else begin
                    if(meta_refresh_slot==4)begin
                        query_hitway_q<=metadata_return_hitway;query_all_hit_q<=&metadata_return_line_hit;
                        meta_refresh_active<=0;meta_refresh_phase<=0;
                    end else begin
                        metadata_hitway[meta_refresh_slot[1:0]]<=metadata_return_hitway;
                        metadata_all_hit[meta_refresh_slot[1:0]]<=&metadata_return_line_hit;
                        meta_refresh_slot<=meta_refresh_slot+1'b1;meta_refresh_phase<=0;
                    end
                end
            end
            if(failed)begin
                metadata_count<=0;metadata_reserved_count<=0;metadata_read_valid<=0;
                meta_refresh_active<=0;query_valid<=0;
            end
'''

def derive():
 data=SOURCE.read_bytes();assert hashlib.sha256(data).hexdigest()==PIN
 text=data.decode()
 def change(old,new):
  nonlocal text
  assert text.count(old)==1,repr(old[:100])
  text=text.replace(old,new)
 change('    wire all_hit=&line_hit;','    wire all_hit=query_all_hit_q;')
 change('    wire accept_query;','    wire accept_query;\n'+DECL)
 change('!query_valid && !failed;','!query_valid && metadata_reserved_count==0 && !metadata_read_valid && !meta_refresh_active && !failed;')
 change('wire pre_to_query=decoded_count!=0 && !failed && state==IDLE &&\n        (!query_valid || accept_query);','wire pre_to_query=metadata_count!=0 && !failed && state==IDLE && !meta_refresh_active &&\n        (!query_valid || accept_query);')
 change('state==IDLE && all_hit && stage0_ready;','state==IDLE && !meta_refresh_active && all_hit && stage0_ready;')
 change('state==IDLE && !all_hit && empty;','state==IDLE && !meta_refresh_active && !all_hit && empty;')
 change(OLDGEN,NEWGEN)
 change('case({pre_to_decoded,pre_to_query})','case({pre_to_decoded,metadata_fetch})')
 change('if(pre_to_query && decoded_count==2)','if(metadata_fetch && decoded_count==2)')
 change('if(decoded_count==0 || pre_to_query)','if(decoded_count==0 || metadata_fetch)')
 change(OLDQUERY,NEWQUERY)
 change('            decoded_index_head<=0;decoded_index_tail<=0;', '''            decoded_index_head<=0;decoded_index_tail<=0;
            metadata_count<=0;metadata_reserved_count<=0;metadata_read<=0;metadata_write<=0;
            metadata_read_valid<=0;query_hitway_q<=0;query_all_hit_q<=0;
            meta_refresh_active<=0;meta_refresh_phase<=0;meta_refresh_slot<=0;''')
 return text.encode()
if __name__=='__main__':
 data=derive();TARGET.parent.mkdir(parents=True,exist_ok=True)
 with TARGET.open('xb')as stream:stream.write(data)
 print(json.dumps(dict(Path=str(TARGET),SHA256=hashlib.sha256(data).hexdigest(),Bytes=len(data),OriginalSHA256=PIN)))
