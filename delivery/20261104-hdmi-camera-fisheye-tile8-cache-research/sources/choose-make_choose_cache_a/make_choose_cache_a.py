"""Replay the isolated registered slow-way choice, preserving frozen assoc b."""
from pathlib import Path
import hashlib,json
BASE=Path(__file__).resolve().parent
SOURCE=BASE.parent/'assoc2way256-a/rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_b.v'
TARGET=BASE/'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_choose_a.v'
PIN='745f4f2cbc26f733d991eca2998484542a131c47f2d747504194f8ecaca95f0b'
OLD='''                SLOW_LOOKUP:state<=CHECK;
                CHECK:begin
                        // Lock chosen physical line before AR and every RAM operation.
                        selected_line<=selected_choose_line;
                        selected_pixel_address<={selected_choose_way,selected_pixel_address[ADDRESS_BITS-2:0]};
                        if(selected_hit)begin
                            lru_way[selected_line[SET_BITS-1:0]]<=!selected_choose_way;
                            state<=LOAD;
                        end else begin
                            valid_lines[selected_choose_line]<=0;
                            miss_count<=miss_count+1'b1;fill_beat<=0;address_pending<=1;state<=AR;
                        end
                end
'''
NEW='''                SLOW_LOOKUP:state<=CHOOSE;
                CHOOSE:begin
                    // This state owns no DDR response. An illegal R must not
                    // commit a choice; the fault handler clears the old line.
                    if(!failed && !rvalid)begin
                        selected_line<=selected_choose_line;
                        selected_pixel_address<={selected_choose_way,selected_pixel_address[ADDRESS_BITS-2:0]};
                        selected_hit_q<=selected_hit;
                        state<=CHECK;
                    end
                end
                CHECK:begin
                        // Tags and way choice end at the preceding register.
                        if(selected_hit_q)begin
                            lru_way[selected_line[SET_BITS-1:0]]<=!selected_line[INDEX_BITS-1];
                            state<=LOAD;
                        end else begin
                            valid_lines[selected_line]<=0;
                            miss_count<=miss_count+1'b1;fill_beat<=0;address_pending<=1;state<=AR;
                        end
                end
'''
CHANGES=[
 ('FAULT=8,CHECK=9,SLOW_LOOKUP=10;','FAULT=8,CHECK=9,SLOW_LOOKUP=10,CHOOSE=11;'),
 ('    reg selected_parity;','    reg selected_parity;\n    reg selected_hit_q;'),
 ('wire [INDEX_BITS-1:0] fault_line=state==CHECK ? selected_choose_line:selected_line;','wire [INDEX_BITS-1:0] fault_line=selected_line;'),
 ('wire slow_hit_increment=state==CHECK && selected_hit;','wire slow_hit_increment=state==CHECK && selected_hit_q;'),
 ('selected_pixel_address<=0;selected_parity<=0;','selected_pixel_address<=0;selected_parity<=0;selected_hit_q<=0;'),
 (OLD,NEW)]
def derive():
 data=SOURCE.read_bytes();assert hashlib.sha256(data).hexdigest()==PIN
 text=data.decode()
 for old,new in CHANGES:
  assert text.count(old)==1,repr(old)
  text=text.replace(old,new)
 return text.encode()
if __name__=='__main__':
 data=derive();TARGET.parent.mkdir(parents=True,exist_ok=True)
 with TARGET.open('xb') as stream:stream.write(data)
 print(json.dumps(dict(Path=str(TARGET),SHA256=hashlib.sha256(data).hexdigest(),Bytes=len(data),OriginalSHA256=PIN,ExactTransformations=len(CHANGES))))
