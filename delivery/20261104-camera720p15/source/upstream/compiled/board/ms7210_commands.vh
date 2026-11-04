// Register settings retained from vendor ms7210_ctl.v; not an original algorithm.
function [23:0] hdmi_command;
input [5:0] index;
begin
case(index)
6'd0: hdmi_command=24'h128104;
6'd1: hdmi_command=24'h001604;
6'd2: hdmi_command=24'h000901;
6'd3: hdmi_command=24'h000709;
6'd4: hdmi_command=24'h0008F0;
6'd5: hdmi_command=24'h000AF0;
6'd6: hdmi_command=24'h000611;
6'd7: hdmi_command=24'h053184;
6'd8: hdmi_command=24'h090020;
6'd9: hdmi_command=24'h090147;
6'd10: hdmi_command=24'h090409;
6'd11: hdmi_command=24'h092307;
6'd12: hdmi_command=24'h092444;
6'd13: hdmi_command=24'h092544;
6'd14: hdmi_command=24'h090F80;
6'd15: hdmi_command=24'h091F07;
6'd16: hdmi_command=24'h09201E;
6'd17: hdmi_command=24'h001820;
6'd18: hdmi_command=24'h05c0FE;
6'd19: hdmi_command=24'h000B00;
6'd20: hdmi_command=24'h050706;
6'd21: hdmi_command=24'h090604;
6'd22: hdmi_command=24'h09205E;
6'd23: hdmi_command=24'h0926DD;
6'd24: hdmi_command=24'h09270D;
6'd25: hdmi_command=24'h092888;
6'd26: hdmi_command=24'h092908;
6'd27: hdmi_command=24'h091001;
6'd28: hdmi_command=24'h000B11;
6'd29: hdmi_command=24'h050E00;
6'd30: hdmi_command=24'h050A82;
6'd31: hdmi_command=24'h050902;
6'd32: hdmi_command=24'h050B0D;
6'd33: hdmi_command=24'h050D06;
6'd34: hdmi_command=24'h050D11;
6'd35: hdmi_command=24'h050D58;
6'd36: hdmi_command=24'h050D00;
6'd37: hdmi_command=24'h050D00;
6'd38: hdmi_command=24'h050D00;
6'd39: hdmi_command=24'h050D00;
6'd40: hdmi_command=24'h050D00;
6'd41: hdmi_command=24'h050D00;
6'd42: hdmi_command=24'h050D00;
6'd43: hdmi_command=24'h050D00;
6'd44: hdmi_command=24'h050D00;
6'd45: hdmi_command=24'h050D00;
6'd46: hdmi_command=24'h050D00;
6'd47: hdmi_command=24'h050E40;
6'd48: hdmi_command=24'h050700;
default: hdmi_command=24'h000000;
endcase
end
endfunction
