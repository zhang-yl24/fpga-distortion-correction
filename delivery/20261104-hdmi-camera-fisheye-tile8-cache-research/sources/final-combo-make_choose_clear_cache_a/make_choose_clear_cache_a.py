"""Isolate frame-wide clear after drained frame admission; no reset retiming."""
from pathlib import Path
import hashlib,json
BASE=Path(__file__).resolve().parent
SOURCE=BASE.parent/'assoc2way256-choose-a/rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_choose_a.v'
TARGET=BASE/'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_choose_clear_a.v'
PIN='ea561f9e487e1f03141f13139a8f7ccbb338c2b8e256a4ca81ed73298e6e69d1'
CHANGES=[
 ('    reg frame_loaded;\n    reg [1:0] queue_count;','    reg frame_loaded,frame_loading;\n    reg [1:0] queue_count;'),
 ('assign frame_ready=queue_empty && inner_frame_ready && !failed;','assign frame_ready=queue_empty && inner_frame_ready && !frame_loading && !failed;'),
 ('frame_loaded<=0;queue_count<=0;read_pointer<=0;write_pointer<=0;','frame_loaded<=0;frame_loading<=0;queue_count<=0;read_pointer<=0;write_pointer<=0;'),
 ('frame_loaded<=1;queue_count<=0;read_pointer<=0;write_pointer<=0;','frame_loaded<=0;frame_loading<=1;queue_count<=0;read_pointer<=0;write_pointer<=0;'),
 ('''            end else begin
                case({push,pop})''','''            end else begin
                // This edge is the private FRAME_CLEAR commit edge. Admission
                // remains closed during clear and opens only after its NBA.
                if(frame_loading)begin frame_loaded<=1;frame_loading<=0;end
                case({push,pop})'''),
 ('CHOOSE=11;','CHOOSE=11,FRAME_CLEAR=12;'),
 ('if(accept_frame)begin base<=frame_base;valid_lines<=0;lru_way<=0;frame_loaded<=1;end',
  'if(accept_frame)begin base<=frame_base;frame_loaded<=0;state<=FRAME_CLEAR;end'),
 ('                SELECT:begin','''                FRAME_CLEAR:begin
                    // Frame admission already proved every old-frame stage
                    // empty. Wide clear depends only on this registered state.
                    valid_lines<=0;lru_way<=0;frame_loaded<=1;state<=IDLE;
                end
                SELECT:begin''')]
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
