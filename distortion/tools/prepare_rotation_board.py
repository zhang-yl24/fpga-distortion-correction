"""Board composition generator. No modification to the proven baseline target."""
def integrate(root,top,tcl):
    top=top.replace('input clk_27m,cam_pclk', 'input key0_n,clk_27m,cam_pclk',1)
    top=top.replace('// First calibration trial: matched input/output K, bounded radial surrogate, no rotation.', '// KEY0 rotation demo and internal ADC temperature telemetry; optical model remains bounded.')
    controller='''
    `include "D:/English/FPGA/distortion/board/rotation-domain.vh"
    wire rotation_valid,rotation_automatic;
    wire [31:0] rotation_phase,result_phase;
    wire signed [31:0] rotation_cos,rotation_sin;
    rotation_demo_control rotation_control(.clk(core_clk),.rst_n(test_reset_sync[1]),.key_n(key0_n),
        .auto_mode(rotation_automatic),.cfg_valid(rotation_valid),.cfg_phase(rotation_phase),
        .cfg_cos(rotation_cos),.cfg_sin(rotation_sin));
    wire temp_valid,temp_failed,temp_over,temp_pulse;wire [4:0] temp_alarm;
    wire [7:0] temp_fault;wire [15:0] temp_raw;wire [11:0] temp_code;
    wire [31:0] temp_age,temp_conversions,temp_samples;
    logos2_temperature_monitor temperature(.clk(clk_27m),.rst_n(rst_n),
        .sample_valid(temp_valid),.sample_pulse(temp_pulse),.failed(temp_failed),.fault(temp_fault),
        .raw_word(temp_raw),.code12(temp_code),.sample_age(temp_age),.conversions(temp_conversions),.samples(temp_samples),
        .over_temp(temp_over),.alarm(temp_alarm));
    reg [32:0] held_rotation=0,rotation_status=0,report_rotation=0;
    reg [63:0] report_temperature=0;
'''
    top=top.replace('    ddr_corrected_video pipeline(',controller+'    ddr_rotated_video #(.MAX_RADIUS_Q22(ROT_MAX_R2_Q22)) pipeline(',1)
    top=top.replace('        .processed_frames(corrected_frames),', "        .cfg_rotation_valid(rotation_valid),.cfg_rotation_phase(rotation_phase),.result_phase(result_phase),\n        .cfg_rot_cx(24'sd81792),.cfg_rot_cy(24'sd61312),.cfg_rot_cos(rotation_cos),.cfg_rot_sin(rotation_sin),\n        .processed_frames(corrected_frames),",1)
    top=top.replace('pixel_snapshot_request<=0;held_engine<=0;', 'pixel_snapshot_request<=0;held_engine<=0;held_rotation<=0;')
    top=top.replace('held_engine<={corrected_frames,process_cycles,cache_hits,cache_misses,result_crc};', 'held_engine<={corrected_frames,process_cycles,cache_hits,cache_misses,result_crc};held_rotation<={rotation_automatic,result_phase};')
    top=top.replace('ack_seen<=0;engine_status<=0;', 'ack_seen<=0;engine_status<=0;rotation_status<=0;')
    top=top.replace('engine_status<=held_engine;', 'engine_status<=held_engine;rotation_status<=held_rotation;')
    top=top.replace('snapshot_request<=0;report_checksums<=0;', 'snapshot_request<=0;report_rotation<=0;report_temperature<=0;report_checksums<=0;')
    top=top.replace('snapshot_request<=!snapshot_request;report_engine<=engine_status;', 'snapshot_request<=!snapshot_request;report_rotation<=rotation_status;report_temperature<={temp_valid,temp_failed,temp_over,temp_alarm,temp_fault,temp_raw,temp_age};report_engine<=engine_status;')
    # Extend the existing human-readable line; keep total below 256 bytes so
    # the original eight-bit byte index remains sufficient.
    entries=[];index=190
    def literal(text):
        nonlocal index
        for ch in text:entries.append(f'                {index}:message="{ch}";');index+=1
    def hex_bus(bus,hi,bits):
        nonlocal index
        for b in range(hi,hi-bits,-4):entries.append(f'                {index}:message=hexchar({bus}[{b}:{b-3}]);');index+=1
    literal(' RA=');hex_bus('report_rotation',31,32)
    literal(' AU=');entries.append(f"                {index}:message=hexchar({{3'b0,report_rotation[32]}});");index+=1
    literal(' TV=');entries.append(f"                {index}:message=hexchar({{3'b0,report_temperature[63]}});");index+=1
    literal(' TR=');hex_bus('report_temperature',47,16)
    literal(' TF=');hex_bus('report_temperature',55,8)
    literal(' TA=');hex_bus('report_temperature',31,32)
    literal(' AL=');hex_bus('report_temperature',63,8)
    entries.append(f'                {index}:message=13;{index+1}:message=10;')
    assert index+1<256
    top=top.replace('                190:message=13;191:message=10;', '\n'.join(entries))
    top=top.replace('if(report_index==191)',f'if(report_index=={index+1})')
    for old,new in (('ddr_corrected_video','ddr_rotated_video'),('remap_frame_engine','rotated_frame_engine'),('brown_remap_core','rotated_remap_core'),('brown_inverse_mapper','bounded_brown_inverse_mapper')):
        tcl=tcl.replace('/rtl/'+old+'.v}', '/rtl/'+new+'.v}')
    extra=('pixel_inverse_rotation','cordic_sincos','rotation_demo_control','adc_temperature_reader','logos2_temperature_monitor')
    tcl=''.join('add_design {'+(root/'rtl'/ (name+'.v')).as_posix()+'}\n' for name in extra)+tcl
    return top,tcl
