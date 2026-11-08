// UI address units are 4B. Keep the 10 column bits intact.
// Interchange bank bits and three low row/page bits; an involutive bijection.
function [27:0] ddr_bank_page_interleave;
 input [27:0] logical_address;
 begin ddr_bank_page_interleave={logical_address[12:10],logical_address[24:13],logical_address[27:25],logical_address[9:0]};end
endfunction
