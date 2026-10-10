from pathlib import Path
import re,json
root=Path(__file__).resolve().parents[1];board=root/'board'
vendor=root/'platform/video_base'
v=(vendor/'source/rtl/HDMI_IN_DDR3_HDMI_OUT_top.v').read_text(encoding='utf-8-sig')
ports=v[v.index('//DDR'):v.index('    output reg                           heart_beat_led')]
ports=ports.replace('//DDR','').rstrip().rstrip(',')
for a,b in {'MEM_ROW_ADDR_WIDTH':'15','MEM_BADDR_WIDTH':'3','MEM_DQ_WIDTH/8':'4','MEM_DQ_WIDTH':'32'}.items():ports=ports.replace(a,b)
t=(board/'preview.v').read_text().replace('module preview(', 'module ddr_check(')
t=t.replace('    output [7:0] r_out,g_out,b_out);','    output [7:0] r_out,g_out,b_out, input clk_p,clk_n,\n'+ports+');')
ip=v[v.index('        ddr3_test u_ddr3_test_h ('):v.index('//心跳信号')]
ip=ip.replace('(pll_lock ', '(ddr_pll_lock ')
extra='''
    wire clk_125Mhz, core_clk, ddr_init_done,ddr_pll_lock;
    wire phy_pll_lock,gpll_lock,rst_gpll_lock,ddrphy_cpd_lock;
    GTP_INBUFGDS #(.IOSTANDARD("DEFAULT"),.TERM_DIFF("ON")) u_gtp(
        .O(clk_125Mhz),.I(clk_p),.IB(clk_n));
    wire [27:0] axi_awaddr,axi_araddr;
    wire [3:0] axi_awlen,axi_arlen,axi_rid;
    wire [3:0] axi_awuser_id=0,axi_aruser_id=0;
    wire axi_awready,axi_awvalid,axi_wready,axi_wusero_last;
    wire axi_arready,axi_arvalid,axi_rlast,axi_rvalid;
    wire [255:0] axi_wdata,axi_rdata;
    wire [31:0] axi_wstrb;
    (* async_reg="true" *) reg [1:0] ddr_reset_sync=0;
    always @(posedge core_clk or negedge rst_n)
        if(!rst_n) ddr_reset_sync<=0;
        else ddr_reset_sync<={ddr_reset_sync[0],1'b1};
    reg [1:0] test_reset_sync=0;
    always @(posedge core_clk)
        if(!ddr_reset_sync[1] || !ddr_init_done) test_reset_sync<=0;
        else test_reset_sync<={test_reset_sync[0],1'b1};
    wire [3:0] test_state;
    wire test_done,test_failed;
    wire [7:0] test_fault,test_passes;
    wire [31:0] test_written,test_read,test_errors;
    wire [27:0] test_first_bad;
    ddr_integrity_test memory_test(.clk(core_clk),.rst_n(test_reset_sync[1]),
        .awaddr(axi_awaddr),.araddr(axi_araddr),.awlen(axi_awlen),.arlen(axi_arlen),
        .awvalid(axi_awvalid),.arvalid(axi_arvalid),.awready(axi_awready),.arready(axi_arready),
        .wdata(axi_wdata),.wstrb(axi_wstrb),.wready(axi_wready),.wlast(axi_wusero_last),
        .rdata(axi_rdata),.rvalid(axi_rvalid),.rlast(axi_rlast),.rid(axi_rid),
        .state(test_state),.done(test_done),.failed(test_failed),.fault(test_fault),
        .written_beats(test_written),.read_beats(test_read),.errors(test_errors),
        .first_bad_address(test_first_bad),.completed_passes(test_passes));
    // Request/ack held-bus CDC: source snapshot remains stable until next request.
    reg snapshot_request=0,snapshot_ack=0;
    (* async_reg="true" *) reg [1:0] request_sync=0,ack_sync=0;
    (* async_reg="true" *) reg [1:0] init_sync=0,ddr_pll_sync=0;
    reg [145:0] held_status=0,ddr_status=0;
    reg ack_seen=0;
    always @(posedge core_clk) begin
        if(!ddr_reset_sync[1]) begin request_sync<=0;snapshot_ack<=0;held_status<=0;end
        else begin
            request_sync<={request_sync[0],snapshot_request};
            if(request_sync[1]!=snapshot_ack) begin
                held_status<={test_state,test_done,test_failed,test_fault,test_written,test_read,test_errors,test_first_bad,test_passes};
                snapshot_ack<=request_sync[1];
            end
        end
    end
    always @(posedge clk_27m) begin
        if(!rst_n) begin ack_sync<=0;ack_seen<=0;ddr_status<=0;init_sync<=0;ddr_pll_sync<=0;end
        else begin
            ack_sync<={ack_sync[0],snapshot_ack};
            init_sync<={init_sync[0],ddr_init_done};
            ddr_pll_sync<={ddr_pll_sync[0],ddr_pll_lock};
            if(ack_sync[1]!=ack_seen) begin ddr_status<=held_status;ack_seen<=ack_sync[1];end
        end
    end
    reg [145:0] report_ddr_status;
    reg report_ddr_init,report_ddr_pll;
'''
t=t.replace('    wire [15:0] sensor_id;',extra+ip+'\n    wire [15:0] sensor_id;')
t=t.replace("assign led={1'b0,preview_ready,", "assign led={ddr_status[141],preview_ready,")
t=t.replace('input [6:0] idx;', 'input [7:0] idx;').replace('reg [6:0] report_index;', 'reg [7:0] report_index;')
# Existing message terminates at 113; extend without altering known camera fields.
items=[(' D=',('bit','report_ddr_init')),(' K=',('bit','report_ddr_pll')),
       (' Q=',('hex','report_ddr_status[145:142]',1)),
       (' OK=',('bit','report_ddr_status[141]')),(' FAIL=',('bit','report_ddr_status[140]')),
       (' X=',('hex','report_ddr_status[139:132]',2)),
       (' WB=',('hex','report_ddr_status[131:100]',8)),
       (' RB=',('hex','report_ddr_status[99:68]',8)),
       (' BAD=',('hex','report_ddr_status[67:36]',8)),
       (' BA=',('hex','report_ddr_status[35:8]',7)),
       (' PASS=',('hex','report_ddr_status[7:0]',2))]
entries=[];i=113
for label,spec in items:
    for c in label:entries.append(f'                {i}:message="{c}";');i+=1
    if spec[0]=='bit':entries.append(f'                {i}:message={spec[1]} ? "1":"0";');i+=1
    else:
        expr,n=spec[1:];m=re.match(r'(.+)\[(\d+):(\d+)\]',expr);base,hi,lo=m.group(1),int(m.group(2)),int(m.group(3))
        for nib in reversed(range(n)):
            entries.append(f'                {i}:message=hexchar({base}[{lo+nib*4+3}:{lo+nib*4}]);');i+=1
entries.append(f'                {i}:message=13;{i+1}:message=10;')
assert i+1<256
t=t.replace('                113:message=13;114:message=10;', '\n'.join(entries))
t=t.replace('if(report_index==114)',f'if(report_index=={i+1})')
t=t.replace('            report_sum<=0;', '            snapshot_request<=0;report_ddr_status<=0;report_ddr_init<=0;report_ddr_pll<=0;\n            report_sum<=0;')
t=t.replace('                    report_sum<=dvp_sum;', '                    snapshot_request<=!snapshot_request;report_ddr_status<=ddr_status;report_ddr_init<=init_sync[1];report_ddr_pll<=ddr_pll_sync[1];\n                    report_sum<=dvp_sum;')
(board/'ddr_check.v').write_text(t)
original=(vendor/'HDMI_IN_DDR3_HDMI_OUT_top.fdc').read_text()
portlines=[line for line in original.splitlines() if re.match(r'define_attribute \{p:(mem_|clk_p|clk_n)',line)]
pins=json.loads((board/'preview-pins.json').read_text())
for line in portlines:
    m=re.match(r'define_attribute \{p:([^}]+)\} \{PAP_IO_LOC\} \{([^}]+)\}',line)
    if m:pins[m[1]]=m[2]
assert len(pins.values())==len(set(pins.values())),'Pin collision'
(board/'ddr_check-pins.json').write_text(json.dumps(pins,indent=2)+'\n')
clocks=original[original.index('create_clock -name {ref_clk}'):original.index('###==== END "Generated Clocks"')]
clocks='\n'.join(l for l in clocks.splitlines() if 'set_clock_groups -name sys_clk' not in l)
logical=[l for l in original.splitlines() if l.startswith('define_attribute {i:u_ddr3_test_h.')]
fdc=(board/'preview.fdc').read_text()+'\n# Verified supplier DDR pins, placement and internal PHY clock relationships.\n'+'\n'.join(portlines)+'\n'+clocks+'\n'+'\n'.join(logical)
fdc+='\n# User logic crosses only through synchronized reset, flags and held-bus snapshots.\nset_clock_groups -name ddr_user_async -asynchronous -group [get_clocks {clk_27m pixel_clk camera_pclk}] -group [get_clocks {ref_clk rst_clk ddrphy_sysclk phy_dq_clk_0 phy_dq_sysclk_0 phy_dq_clk_1 phy_dq_sysclk_1}]\n'
(board/'ddr_check.fdc').write_text(fdc)
build=(board/'build-preview.tcl').read_text().replace('/board/preview.v}', '/board/ddr_check.v}').replace('/board/preview.fdc}', '/board/ddr_check.fdc}').replace('top_module preview','top_module ddr_check')
build='add_design {D:/English/FPGA/distortion/rtl/ddr_integrity_test.v}\nadd_design {D:/English/FPGA/distortion/platform/video_base/ipcore/ddr3_test/ddr3_test.idf}\n'+build
(board/'build-ddr_check.tcl').write_text(build)
(board/'program-ddr_check.tcl').write_text((board/'program-preview.tcl').read_text().replace('preview','ddr_check'))
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    p=root/'tools'/name;s=p.read_text(encoding='utf-8-sig');lines=s.splitlines(keepends=True)
    lines[0]=lines[0].replace("'preview')", "'preview','ddr_check')");s=''.join(lines)
    s=s.replace("'camera2','preview')", "'camera2','preview','ddr_check')")
    if name=='build-pds.ps1' and "throw 'DDR source is newer than bitstream'" not in s:
        s=s.replace("    if($Target -eq 'camera_diag') {",'''    if($Target -eq 'ddr_check') {
        foreach($src in @('board\\ddr_check.v','board\\ddr_check.fdc','board\\build-ddr_check.tcl','rtl\\camera_preview.v','rtl\\ddr_integrity_test.v','platform\\video_base\\ipcore\\ddr3_test\\ddr3_test.idf')) {
            if((Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'DDR source is newer than bitstream'}
        }
    }
    if($Target -eq 'camera_diag') {''')
    p.write_text(s,encoding='utf-8-sig')
print(f'Prepared ddr_check: {len(pins)} unique verified pins, {i+2} UART bytes; preview retained plus four-pass DDR integrity test.')
