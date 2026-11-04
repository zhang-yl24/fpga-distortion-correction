// Exact function extracted from guarded_status_uart.v; see source manifest.
    function [31:0] crc_byte;
        input [31:0] previous;input [7:0] value;integer i;reg [31:0] c;
        begin c=previous^{24'b0,value};for(i=0;i<8;i=i+1)
            c=(c>>1)^(c[0]?32'hEDB88320:0);crc_byte=c;end
    endfunction
