`timescale 1ns/1ps
module tb_video_crc32;
    `include "D:/English/FPGA/distortion/rtl/video_crc32.vh"
    reg [287:0] vectors[0:255];reg [31:0] beat_crc,pixel_crc;
    integer i,lane;
    initial begin
        $readmemh("vectors.hex",vectors);
        for(i=0;i<256;i=i+1) begin
            if(i%4==0) begin beat_crc=32'hFFFFFFFF;pixel_crc=32'hFFFFFFFF;end
            beat_crc=video_crc32_beat(beat_crc,vectors[i][255:0]);
            for(lane=0;lane<16;lane=lane+1)
                pixel_crc=video_crc32_pixel(pixel_crc,vectors[i][lane*16+:16]);
            if(~beat_crc!==vectors[i][287:256] || ~pixel_crc!==vectors[i][287:256])
                $fatal(1,"CRC32 vs Python mismatch index=%d beat=%h pixel=%h expected=%h",i,~beat_crc,~pixel_crc,vectors[i][287:256]);
        end
        $display("PASS IEEE CRC32: 256 Python binascii prefix vectors, 64 four-beat streams, pixel and 256-bit updates match little-endian RGB565 order.");
        $finish;
    end
endmodule
