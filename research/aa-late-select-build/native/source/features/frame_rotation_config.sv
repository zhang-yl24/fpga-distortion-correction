`timescale 1ns/1ps
// A single outstanding config crosses via the EXISTING held-bundle module.
// All config outputs use the same pending-vs-active mux. The real bank snapshots
// them AND parameter_id on the SAME source_valid&&source_ready edge. The
// registered source_commit pulse is deliberately NOT the apply event.
module frame_rotation_config(
    input wire ctrl_clk,core_clk,rst_n,
    input wire config_valid,output wire config_ready,input wire [127:0] config_data,
    input wire [31:0] default_param_id,
    input wire signed [31:0] default_cos,default_sin,
    input wire frame_accept,input wire [31:0] source_frame_id,
    output wire [31:0] selected_param_id,selected_phase,
    output wire signed [31:0] selected_cos,selected_sin,
    output reg applied_pulse,output reg [31:0] applied_source_id,applied_param_id
);
    wire pending_valid;wire [127:0] pending_data;
    (* PAP_ASYNC_REG=1 *) reg [1:0] core_release=0;
    always @(posedge core_clk or negedge rst_n)
        if(!rst_n)core_release<=0;else core_release<={core_release[0],1'b1};
    reg [31:0] active_param_id,active_phase;
    reg signed [31:0] active_cos,active_sin;
    held_bundle_cdc #(.WIDTH(128)) config_cdc(
        .s_clk(ctrl_clk),.d_clk(core_clk),.rst_n(rst_n),
        .s_valid(config_valid),.s_ready(config_ready),.s_data(config_data),
        .d_valid(pending_valid),.d_ready(frame_accept && core_release[1]),.d_data(pending_data));
    assign selected_param_id=pending_valid ? pending_data[127:96]:active_param_id;
    assign selected_phase=pending_valid ? pending_data[95:64]:active_phase;
    assign selected_cos=pending_valid ? $signed(pending_data[63:32]):active_cos;
    assign selected_sin=pending_valid ? $signed(pending_data[31:0]):active_sin;
    always @(posedge core_clk or negedge rst_n)begin
        if(!rst_n)begin
            active_param_id<=default_param_id;active_phase<=0;
            active_cos<=default_cos;active_sin<=default_sin;
            applied_pulse<=0;applied_source_id<=0;applied_param_id<=0;
        end else if(!core_release[1])begin
            active_param_id<=default_param_id;active_phase<=0;
            active_cos<=default_cos;active_sin<=default_sin;
            applied_pulse<=0;applied_source_id<=0;applied_param_id<=0;
        end else begin
            applied_pulse<=0;
            if(frame_accept && pending_valid)begin
                {active_param_id,active_phase,active_cos,active_sin}<=pending_data;
                applied_pulse<=1;applied_source_id<=source_frame_id;
                applied_param_id<=pending_data[127:96];
            end
        end
    end
endmodule
