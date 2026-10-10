"""Stage isolated host-angle board integration from the verified adaptive target."""
from pathlib import Path
import hashlib,json,re
root=Path(__file__).resolve().parents[1];lab=root/'results/lab-20261007'
proof=json.loads((lab/'host-control-simulation-check.json').read_text());assert proof['passed']
for rel,digest in proof['source_sha256'].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest().upper()==digest,rel
old,new='corrected_adaptive_seed2','corrected_host'
assert not (root/'build'/new/(new+'.pds')).exists(),'Preserve existing host board build'
top=(root/'board'/(old+'.v')).read_text().replace('module '+old+'(', 'module '+new+'(')
top=top.replace('input key0_n,clk_27m','input uart_rxd,key0_n,clk_27m')
start=top.index('    rotation_demo_control rotation_control(');end=top.index('    wire temp_valid',start)
top=top[:start]+'''    wire host_byte_valid,host_byte_error,host_command_valid,host_command_ready;
    wire [7:0] host_byte,host_opcode;wire [15:0] host_sequence,host_accepted_sequence;
    wire [31:0] host_argument,host_requested_phase,host_command_count;
    wire [31:0] host_parsed_count,host_rejected_count,host_duplicate_count;
    reg [31:0] host_framing_count=0;
    uart_rx_control host_receiver(.clk(core_clk),.rst_n(test_reset_sync[1]),.rx(uart_rxd),
        .valid(host_byte_valid),.data(host_byte),.framing_error(host_byte_error));
    rotation_command_parser host_parser(.clk(core_clk),.rst_n(test_reset_sync[1]),
        .byte_valid(host_byte_valid),.byte_data(host_byte),.byte_error(host_byte_error),
        .cmd_valid(host_command_valid),.cmd_ready(host_command_ready),.cmd_opcode(host_opcode),
        .cmd_seq(host_sequence),.cmd_argument(host_argument),.accepted(host_parsed_count),
        .rejected(host_rejected_count),.duplicates(host_duplicate_count));
    always @(posedge core_clk)
        if(!test_reset_sync[1])host_framing_count<=0;
        else if(host_byte_error)host_framing_count<=host_framing_count+1'b1;
    rotation_host_control rotation_control(.clk(core_clk),.rst_n(test_reset_sync[1]),.key_n(key0_n),
        .cmd_valid(host_command_valid),.cmd_ready(host_command_ready),.cmd_opcode(host_opcode),
        .cmd_seq(host_sequence),.cmd_argument(host_argument),.auto_mode(rotation_automatic),
        .cfg_valid(rotation_valid),.cfg_phase(rotation_phase),.cfg_cos(rotation_cos),.cfg_sin(rotation_sin),
        .accepted_seq(host_accepted_sequence),.requested_phase(host_requested_phase),.command_count(host_command_count));
    // Host acknowledgement joins the existing held-bus toggle snapshot. It
    // never samples a changing multi-bit bus directly in the 27MHz domain.
    reg [175:0] held_host=0,host_status=0,report_host=0;
'''+top[end:]
for a,b in [
    ('held_capture<=0;', 'held_capture<=0;held_host<=0;'),
    ('held_capture<={capture_overlap_cycles,', 'held_host<={host_accepted_sequence,host_requested_phase,host_command_count,host_rejected_count,host_duplicate_count,host_framing_count};\n                held_capture<={capture_overlap_cycles,'),
    ('capture_status<=0;', 'capture_status<=0;host_status<=0;'),
    ('capture_status<=held_capture;', 'capture_status<=held_capture;host_status<=held_host;'),
    ('report_capture<=0;', 'report_capture<=0;report_host<=0;'),
    ('report_capture<=capture_status;', 'report_capture<=capture_status;report_host<=host_status;')]:
    assert top.count(a)==1,a;top=top.replace(a,b)
cases=[];index=292
def literal(text):
    global index
    for char in text:
        cases.append(f'                {index}:message="{char}";');index+=1
def field(name,high,bits):
    global index
    literal(' '+name+'=')
    for n in range(high,high-bits,-4):
        cases.append(f'                {index}:message=hexchar(report_host[{n}:{n-3}]);');index+=1
literal(' HV=01');field('HQ',175,16)
for name,high in [('HR',159),('HC',127),('HX',95),('HD',63),('HE',31)]:field(name,high,32)
cases.extend([f'                {index}:message=13;',f'                {index+1}:message=10;'])
assert index+1<512
top=top.replace('                292:message=13;293:message=10;', '\n'.join(cases))
top=top.replace('report_index==293',f'report_index=={index+1}')
(root/'board'/(new+'.v')).write_text(top)
tcl=(root/'board'/('build-'+old+'.tcl')).read_text().replace(old,new)
replacement='\n'.join('add_design {D:/English/FPGA/distortion/rtl/experimental/'+name+'.v}' for name in ('uart_rx_control','rotation_command_parser','rotation_host_control'))
tcl=tcl.replace('add_design {D:/English/FPGA/distortion/rtl/rotation_demo_control.v}',replacement)
(root/'board'/('build-'+new+'.tcl')).write_text(tcl)
fdc=(root/'board'/(old+'.fdc')).read_text()
fdc=fdc.replace('# Small camera-ID / HDMI output build. No DDR or camera pixel clock.', '# Full adaptive corrected video with async host UART RX; inherited clock budgets unchanged.')
fdc+='''
# CP2102 FPGA_UART_RXD=B24, vendor hardware guide section 2.1.3.2.5.
define_attribute {p:uart_rxd} {PAP_IO_DIRECTION} {INPUT}
define_attribute {p:uart_rxd} {PAP_IO_LOC} {B24}
define_attribute {p:uart_rxd} {PAP_IO_VCCIO} {3.3}
define_attribute {p:uart_rxd} {PAP_IO_STANDARD} {LVCMOS33}
define_attribute {p:uart_rxd} {PAP_IO_NONE} {TRUE}
define_attribute {p:uart_rxd} {PAP_IO_PULLUP} {TRUE}
# Async external input is used only by the first receiver synchronizer flop.
# Synchronizer register-to-register paths remain timed at the core clock.
set_false_path -from [get_ports uart_rxd] -to [get_clocks ddrphy_sysclk]
'''
(root/'board'/(new+'.fdc')).write_text(fdc)
pins=json.loads((root/'board'/(old+'-pins.json')).read_text());assert 'B24' not in pins.values()
pins['uart_rxd']='B24';assert len(pins)==130
(root/'board'/(new+'-pins.json')).write_text(json.dumps(pins,indent=2)+'\n')
(root/'board'/('program-'+new+'.tcl')).write_text((root/'board'/('program-'+old+'.tcl')).read_text().replace(old,new))
sources=[p.replace(old,new) for p in json.loads((root/'board'/(old+'-sources.json')).read_text()) if p!='rtl\\rotation_demo_control.v']
sources+=['rtl\\experimental\\'+name+'.v' for name in ('uart_rx_control','rotation_command_parser','rotation_host_control')]
(root/'board'/(new+'-sources.json')).write_text(json.dumps(sources,indent=2)+'\n')
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    path=root/'tools'/name;text=path.read_text(encoding='utf-8-sig')
    text=re.sub(r"(?:@|ValidateSet)\(([^)\n]*'corrected_adaptive_seed2'[^)\n]*)\)",lambda m:m[0] if "'"+new+"'" in m[0] else m[0][:-1]+",'"+new+"')",text)
    path.write_text(text,encoding='utf-8-sig')
result={'target':new,'hardware_accessed':False,'prepared_at':__import__('datetime').datetime.now().astimezone().isoformat(),
    'clock_budgets_unchanged':True,'pins':130,'uart_rx_pin':'B24','baud':115200,
    'source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in sources},
    'telemetry_fields':{'HV':'protocol version 01','HQ':'controller accepted sequence','HR':'requested phase','HC':'controller command count','HX':'parser rejects','HD':'duplicate packets','HE':'framing faults','RA':'phase of completed video result'},
    'limits':'Board candidate only; arbitrary commands verified in isolated simulation, with full-frame arbitrary-angle and physical acknowledgement/display verification still pending.'}
(lab/'host-board-candidate.json').write_text(json.dumps(result,indent=2)+'\n')
print('Prepared isolated 130-pin host control board candidate with coherent acknowledgement telemetry.')
