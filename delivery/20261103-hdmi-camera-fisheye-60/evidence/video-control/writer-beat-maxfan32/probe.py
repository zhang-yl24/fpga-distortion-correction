from pathlib import Path
import hashlib,json,re,subprocess,time

ROOT=Path('D:/f60-work/video/writer-beat-fanout-probe-r2')
ROOT.mkdir(exist_ok=False)
P=Path('D:/f60/delivery/20261103-hdmi-camera-fisheye-60')
live=P/'rtl/ddr_adaptive_result_writer.v'
crc=Path('D:/f60/distortion/rtl/video_crc32.vh')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source=live.read_text()
source=source[source.index('module ddr_raster_result_writer_pingpong'):]
(ROOT/'video_crc32.vh').write_bytes(crc.read_bytes())
source=source.replace('`include "video_crc32.vh"','`include "'+(ROOT/'video_crc32.vh').as_posix()+'"')
wrapper='''module writer_probe(
input clk,rst_n,abort,frame_valid,
input [27:0] frame_base,input [31:0] frame_id,
input in_valid,input [23:0] in_rgb,input [23:0] in_tag,
input awready,wready,wlast,input [2:0] probe_slice,input [1:0] probe_status,
output frame_ready,in_ready,awvalid,done,failed,
output [27:0] awaddr,output [7:0] fault,
output [31:0] data_slice,status_slice
);
wire [3:0] awlen;wire [255:0] wdata;wire [31:0] wstrb;
wire [31:0] accepted_pixels,written_beats,last_checksum,completed_id;
ddr_raster_result_writer_pingpong #(.WIDTH(1920),.HEIGHT(440)) writer(
.clk(clk),.rst_n(rst_n),.abort(abort),.frame_valid(frame_valid),.frame_ready(frame_ready),
.frame_base(frame_base),.frame_id(frame_id),.in_valid(in_valid),.in_ready(in_ready),
.in_rgb(in_rgb),.in_tag(in_tag),.awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
.wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),.done(done),.failed(failed),.fault(fault),
.accepted_pixels(accepted_pixels),.written_beats(written_beats),.last_checksum(last_checksum),.completed_id(completed_id));
assign data_slice=wdata[probe_slice*32+:32];
assign status_slice=probe_status==0?accepted_pixels:probe_status==1?written_beats:probe_status==2?last_checksum:completed_id;
endmodule
'''
(ROOT/'wrapper.v').write_text(wrapper,encoding='utf-8')
tool=Path('E:/PDS_2025.2-ads-win64/pango/PDS_2025.2-ads/bin/pds_shell.exe')
manifest={'scope':'Isolated unchanged raster writer, native compile/synthesis/device-map only; live source frozen. The single variant adds the documented register syn_maxfan=32 attribute. No placement, routing or timing pass claimed.',
          'live_source_sha256':sha(live),'crc_sha256':sha(crc),'wrapper_sha256':sha(ROOT/'wrapper.v'),
          'wrapper_scope':'All 256 WDATA bits remain observable through a dynamic 32-bit slice; all four statistics through a dynamic 32-bit mux. These top-level observation muxes reduce package IO demand. Actual lane-1 dimensions 1920x440. No writer behavior is changed.',
          'initial_probe_note':'The direct 569-IO module probe synthesized successfully but device-map rejected the 300-IO package limit. The r2 wrapper removes only package IO width; initial failed artifacts remain intact.',
          'runs':[]}
for kind in ['baseline','maxfan32']:
    d=ROOT/kind;d.mkdir()
    s=source if kind=='baseline' else source.replace('reg [3:0] beat;','reg [3:0] beat /* synthesis syn_maxfan = 32 */;')
    assert kind=='baseline' or s!=source
    (d/'writer.v').write_text(s,encoding='utf-8')
    (d/'clock.fdc').write_text('create_clock -period 8.000 -name writer_clk [get_ports clk]\n')
    (d/'build.tcl').write_text('\n'.join([
        'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676',
        'set_option max_threads 2',
        'add_design {'+(d/'writer.v').as_posix()+'}',
        'add_design {'+(ROOT/'wrapper.v').as_posix()+'}',
        'add_constraint {'+(d/'clock.fdc').as_posix()+'}',
        'compile -top_module writer_probe',
        'synthesize -ads -selected_syn_tool_opt 2','dev_map','exit','']))
    cmd=[str(tool),'-file',str(d/'build.tcl'),'-work_dir',str(d)]
    start=time.monotonic()
    with (d/'console.log').open('w',encoding='utf-8') as f:
        r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=480)
    item={'variant':kind,'returncode':r.returncode,'seconds':time.monotonic()-start,'source_sha256':sha(d/'writer.v'),'console_sha256':sha(d/'console.log')}
    manifest['runs'].append(item)
    (ROOT/'run-results.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(item),flush=True)
    if r.returncode:raise RuntimeError(f'{kind} failed; inspect console')
assert sha(live)==manifest['live_source_sha256'],'Live source drifted during read-only probe'
print('DONE native writer attribute probe',flush=True)
