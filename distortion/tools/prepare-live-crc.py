from pathlib import Path
import re
root=Path(__file__).resolve().parents[1]
targets = [root/f'rtl/{name}.v' for name in
           ('camera_live_bridge', 'ddr_video_writer', 'ddr_video_reader', 'ddr_video_output')]
converted = ['video_crc32.vh' in p.read_text() for p in targets]
if all(converted):
    print('Live CRC32 conversion already applied; sources unchanged.')
    raise SystemExit(0)
if any(converted):
    raise SystemExit('Mixed CRC conversion state; inspect the sources before regeneration.')
p=root/'rtl/camera_live_bridge.v';s=p.read_text()
s=re.sub(r'    function \[31:0\] checksum_beat;.*?    endfunction', '    `include "D:/English/FPGA/distortion/rtl/video_crc32.vh"',s,flags=re.S)
s=s.replace('checksum_beat(beat_first ? 0:checksum,beat_data)', "video_crc32_beat(beat_first ? 32'hFFFFFFFF:checksum,beat_data)")
s=s.replace('checksum_held<=checksum;', 'checksum_held<=~checksum;')
p.write_text(s)
for name in ('ddr_video_writer','ddr_video_reader'):
    p=root/f'rtl/{name}.v';s=p.read_text()
    s=re.sub(r'    function \[31:0\] checksum_beat;.*?    endfunction', '    `include "D:/English/FPGA/distortion/rtl/video_crc32.vh"',s,flags=re.S)
    s=s.replace('checksum_beat(', 'video_crc32_beat(')
    if name.endswith('writer'):
        s=s.replace('write_checksum<=0;', "write_checksum<=32'hFFFFFFFF;")
        s=s.replace('source_checksum!=write_checksum', 'source_checksum!=~write_checksum')
    else:
        s=s.replace('checksum<=0;', "checksum<=32'hFFFFFFFF;")
        s=s.replace('last_checksum<=checksum;', 'last_checksum<=~checksum;')
        s=s.replace('checksum!=expected', '~checksum!=expected')
    p.write_text(s)
p=root/'rtl/ddr_video_output.v';s=p.read_text()
s=s.replace('    localparam WX=', '    `include "D:/English/FPGA/distortion/rtl/video_crc32.vh"\n    localparam WX=')
s=s.replace("wire [31:0] next_checksum={checksum[30:0],checksum[31]} ^ {16'b0,pixel};", 'wire [31:0] next_checksum=video_crc32_pixel(checksum,pixel);')
s=s.replace('checksum<=0;', "checksum<=32'hFFFFFFFF;")
s=s.replace('last_checksum<=next_checksum;', 'last_checksum<=~next_checksum;')
s=s.replace('next_checksum!=expected', '~next_checksum!=expected')
p.write_text(s)
print('Live path uses IEEE CRC32 across source, DDR read, and displayed pixel streams; original proven targets unchanged.')
