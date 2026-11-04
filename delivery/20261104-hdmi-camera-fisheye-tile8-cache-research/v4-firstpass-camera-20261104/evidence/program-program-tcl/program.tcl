cfg_set_tcl_break -flag true
cfg_connect -ip 127.0.0.1 -port 65420
cfg_set_cable_property -index 0 -freq 1MHz
cfg_scan_chain
cfg_assign_file -file {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/hdmi-camera-fisheye-assoc2way256-fastpipe-20261104-a/bit-v4-a/generate_bitstream/hdmi_camera_fisheye_top.sbit} -device_index 0
cfg_program -device_index 0
cfg_scan_chain
cfg_read_device_property -mode 3 -device_index 0
cfg_disconnect
cfg_close
