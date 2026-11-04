"""Derive the isolated two-entry whole-pixel queue; no production edits."""
from pathlib import Path
import hashlib,json
BASE=Path(__file__).resolve().parent
SOURCE=BASE.parent/'assoc2way256-a/rtl/hdmi_camera_fisheye_engine_index10_a.v'
TARGET=BASE/'rtl/hdmi_camera_fisheye_engine_index10_fifo_a.v'
PIN='f5cacc66d2f51a273ed947a107380805461c7ef823b49c46a3c628ebdd027bd8'
OLD='''    // One elastic whole-pixel stage isolates cache interpolation/tag control
    // from the writer's burst enables. No pixel/tag can advance separately.
    reg buffer_valid;
    reg [23:0] buffer_rgb,buffer_tag;
    wire writer_input_ready;
    assign result_ready=!buffer_valid || writer_input_ready;
    always @(posedge clk)begin
        if(!rst_n || failed)begin buffer_valid<=0;buffer_rgb<=0;buffer_tag<=0;end
        else if(result_ready)begin
            buffer_valid<=result_valid;
            if(result_valid)begin
                buffer_rgb<=result_masked ? 24'd0:result_rgb;
                buffer_tag<=result_tag;
            end
        end
    end
'''
NEW='''    // A two-entry whole-pixel queue cuts the writer-ready combinational path.
    // At full occupancy a simultaneous writer pop reopens admission next cycle.
    reg [1:0] buffer_count;
    reg buffer_read,buffer_write;
    reg [23:0] buffer_rgb_queue[0:1],buffer_tag_queue[0:1];
    wire buffer_valid=buffer_count!=0;
    wire [23:0] buffer_rgb=buffer_rgb_queue[buffer_read];
    wire [23:0] buffer_tag=buffer_tag_queue[buffer_read];
    wire writer_input_ready;
    assign result_ready=buffer_count<2;
    wire buffer_push=result_valid && result_ready;
    wire buffer_pop=buffer_valid && writer_input_ready && !failed;
    always @(posedge clk)begin
        if(!rst_n || failed)begin
            buffer_count<=0;buffer_read<=0;buffer_write<=0;
            buffer_rgb_queue[0]<=0;buffer_rgb_queue[1]<=0;
            buffer_tag_queue[0]<=0;buffer_tag_queue[1]<=0;
        end else begin
            case({buffer_push,buffer_pop})
                2'b10:buffer_count<=buffer_count+1'b1;
                2'b01:buffer_count<=buffer_count-1'b1;
                default:buffer_count<=buffer_count;
            endcase
            if(buffer_push)begin
                buffer_rgb_queue[buffer_write]<=result_masked ? 24'd0:result_rgb;
                buffer_tag_queue[buffer_write]<=result_tag;
                buffer_write<=!buffer_write;
            end
            if(buffer_pop)buffer_read<=!buffer_read;
        end
    end
'''
def derive():
    data=SOURCE.read_bytes()
    assert hashlib.sha256(data).hexdigest()==PIN
    text=data.decode()
    assert text.count(OLD)==1
    assert text.count('&& !buffer_valid && !failed;')==1
    return text.replace(OLD,NEW).replace('&& !buffer_valid && !failed;','&& buffer_count==0 && !failed;').encode()
if __name__=='__main__':
    result=derive();TARGET.parent.mkdir(parents=True,exist_ok=True)
    with TARGET.open('xb') as stream:stream.write(result)
    print(json.dumps(dict(Path=str(TARGET),SHA256=hashlib.sha256(result).hexdigest(),Bytes=len(result),OriginalSHA256=PIN)))
