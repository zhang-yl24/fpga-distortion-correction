"""Use vendor primitive declaration with an explicitly digital APB stub."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[1];work=root/'build/temperature_monitor_sim';work.mkdir(parents=True,exist_ok=True)
library=Path('E:/Pango/PDS_2022.2-SP6.4/arch/vendor/pango/logos2/common/lib/gtp_lib.v')
text=library.read_text();declaration=re.search(r'module GTP_ADC_E2\b(.*?)endmodule',text,re.S)[0]
declaration=declaration.replace(') /* pragma PAP_LIB_IS_TECH_CELL */ ;',');')
body='''
    // Digital protocol/configuration fixture only. No ADC analog model.
    reg [15:0] data_word=0;reg response=0,conversion=0;
    reg injected_over=0;reg [4:0] injected_alarm=0;
    integer ticks=0,delay_count=0;reg active=0;
    assign DO=data_word;assign DRDY=response;assign LOGIC_DONE_A=conversion;
    assign LOGIC_DONE_B=0;assign ADC_CLK_OUT=0;assign DMODIFIED=0;
    assign OVER_TEMP=injected_over;assign ALARM=injected_alarm;
    initial begin
        if(CREG_00H!==16'h1003 || CREG_01H!==16'h5020 || CREG_02H!==16'h0008 ||
            CREG_03H!==16'h0004 || CREG_07H!==16'h0004 || CREG_05H!==0 ||
            CREG_20H!==12'hB7A || CREG_21H!==12'hAAD || CREG_2AH!==12'hCC2 || CREG_2BH!==12'hA5B)
            $fatal(1,"Temperature primitive configuration differs from reviewed values");
    end
    always @(posedge DCLK) begin
        if(!RST_N) begin ticks<=0;conversion<=0;response<=0;active<=0;data_word<=0;end
        else begin
            ticks<=ticks+1;conversion<=ticks%8==0;
            if(SECEN && !active) begin
                if(!DEN || DWE || DADDR!==8'h40) $fatal(1,"Primitive APB read misuse");
                active<=1;delay_count<=5;
            end else if(active && SECEN && !response) begin
                if(delay_count>0) delay_count<=delay_count-1;
                else begin response<=1;data_word<=16'hB007;end
            end
            if(active && !SECEN) begin response<=0;active<=0;end
        end
    end
'''
declaration=declaration.replace('endmodule',body+'endmodule')
(work/'digital-adc-stub.sv').write_text('`timescale 1ns/1ps\n'+declaration)
print('Generated vendor-interface digital ADC stub; no physical temperature accuracy simulated.')
