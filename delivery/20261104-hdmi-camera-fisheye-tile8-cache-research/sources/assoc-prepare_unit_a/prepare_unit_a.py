"""Prepare new associative tests without modifying the frozen direct tests."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ROOT = REPO / 'distortion'


def main():
    original = ROOT / 'tests/tb_directfill_tagpipe_cache.sv'
    text = original.read_text().replace('\r\n', '\n')
    # Add a third line before the existing miss/younger/stalled RESULT test.
    text = text.replace('        query(0,0,7,11,25\'h10e0000);drain();',
                        '        new_frame(0);\n'
                        '        query(0,0,7,11,25\'h10e0000);drain();\n'
                        '        query((2*conflict_number)%WIDTH,(2*conflict_number)/WIDTH,13,17,25\'h10e0001);drain();')
    start = text.index('module tb_directfill_tagpipe_cache;')
    text = text[:start] + '''module tb_directfill_tagpipe_cache;
    wire small16_done,small32_done,native_done;
    directfill_tagpipe_cache_case #(.WIDTH(2048),.HEIGHT(480),.INDEX_BITS(5)) small16(small16_done);
    directfill_tagpipe_cache_case #(.WIDTH(639),.HEIGHT(480),.INDEX_BITS(6)) small32(small32_done);
    directfill_tagpipe_cache_case #(.WIDTH(1920),.HEIGHT(1080),.INDEX_BITS(10)) native1024(native_done);
    initial begin wait(small16_done&&small32_done&&native_done);
        $display("PASS TAGPIPE complete independent cache regression");$finish;end
    initial begin #20000000;$fatal(1,"associative regression timeout");end
endmodule
'''
    marker = '    task automatic reset_case;'
    extra = '''    // Second-way metadata is a complete peer of the frozen way0 monitor.
    reg [24:0] held_way1_tag[0:3],refresh_way1_tag[0:3];
    reg [3:0] held_way1_valid,refresh_way1_valid;
    always @(posedge clk)if(rst_n&&checking&&!failed)begin
        held_way1_valid=dut.inner.query_cached_valid_way1;
        for(integer n=0;n<4;n=n+1)begin
            held_way1_tag[n]=dut.inner.query_cached_tag_way1[n];
            refresh_way1_tag[n]=dut.inner.tags[(1<<(INDEX_BITS-1))+dut.inner.query_line_index[n]];
            refresh_way1_valid[n]=dut.inner.valid_lines[(1<<(INDEX_BITS-1))+dut.inner.query_line_index[n]];
        end
        #1;
        if(monitor_stall)begin
            if(dut.inner.query_cached_valid_way1!==held_way1_valid)$fatal(1,"stalled way1 valid changed");
            for(integer n=0;n<4;n=n+1)
                if(dut.inner.query_cached_tag_way1[n]!==held_way1_tag[n])$fatal(1,"stalled way1 tag changed");
        end
        if(monitor_refresh)begin
            if(dut.inner.query_cached_valid_way1!==refresh_way1_valid)$fatal(1,"way1 refresh valid mismatch");
            for(integer n=0;n<4;n=n+1)
                if(dut.inner.query_cached_tag_way1[n]!==refresh_way1_tag[n])$fatal(1,"way1 refresh tag mismatch");
        end
    end
    // Independent replacement oracle: full block IDs, serial demand order,
    // invalid-first selection and one-bit LRU. Does not use DUT cached tags.
    localparam SETS=LINES/2;
    reg [LINES-1:0] oracle_valid=0;
    reg [24:0] oracle_tag[0:LINES-1];
    reg [SETS-1:0] oracle_lru=0;
    integer oracle_set,oracle_way,oracle_line,oracle_block;
    integer oracle_checks=0,way0_fills=0,way1_fills=0,fast_way1_touches=0;
    integer invalid0_choices=0,invalid1_choices=0,lru0_choices=0,lru1_choices=0;
    reg oracle_hit;
    always @(posedge clk)begin
        if(!rst_n || (frame_valid&&frame_ready))begin oracle_valid=0;oracle_lru=0;end
        else if(checking&&!failed)begin
            if(dut.inner.accept_fast)begin
                for(integer n=0;n<4;n=n+1)if(dut.inner.in_bounds[n])begin
                    oracle_block=dut.inner.pixel_number[n]>>7;oracle_set=oracle_block&(SETS-1);
                    if(oracle_valid[oracle_set]&&oracle_tag[oracle_set]==oracle_block)oracle_way=0;
                    else if(oracle_valid[oracle_set+SETS]&&oracle_tag[oracle_set+SETS]==oracle_block)oracle_way=1;
                    else $fatal(1,"DUT fast hit absent from independent full-tag cache");
                    if(dut.inner.query_hit_way[n]!==oracle_way[0])$fatal(1,"fast hit selected wrong physical way");
                    if(dut.inner.pixel_address[n]!==((oracle_way*SETS+oracle_set)*64+((dut.inner.pixel_number[n]&127)>>1)))
                        $fatal(1,"fast physical pixel address disagrees with full-tag oracle");
                    oracle_lru[oracle_set]=!oracle_way[0];
                    if(oracle_way)fast_way1_touches=fast_way1_touches+1;
                end
            end
            if(dut.inner.state==9)begin
                oracle_block=dut.inner.selected_block;oracle_set=oracle_block&(SETS-1);oracle_hit=1;
                if(oracle_valid[oracle_set]&&oracle_tag[oracle_set]==oracle_block)oracle_way=0;
                else if(oracle_valid[oracle_set+SETS]&&oracle_tag[oracle_set+SETS]==oracle_block)oracle_way=1;
                else begin
                    oracle_hit=0;
                    if(!oracle_valid[oracle_set])begin oracle_way=0;invalid0_choices=invalid0_choices+1;end
                    else if(!oracle_valid[oracle_set+SETS])begin oracle_way=1;invalid1_choices=invalid1_choices+1;end
                    else begin oracle_way=oracle_lru[oracle_set];
                        if(oracle_way)lru1_choices=lru1_choices+1;else lru0_choices=lru0_choices+1;end
                end
                oracle_line=oracle_way*SETS+oracle_set;oracle_checks=oracle_checks+1;
                if(dut.inner.selected_hit!==oracle_hit || dut.inner.selected_choose_line!==oracle_line[INDEX_BITS-1:0])
                    $fatal(1,"independent invalid-first/LRU choice mismatch block%0d wantedline%0d gotline%0d",oracle_block,oracle_line,dut.inner.selected_choose_line);
                if(oracle_hit)oracle_lru[oracle_set]=!oracle_way[0];
                else oracle_valid[oracle_line]=0;
            end
            if(dut.inner.state==4&&dut.inner.write_commit_last)begin
                oracle_line=dut.inner.write_commit_line;oracle_set=oracle_line&(SETS-1);
                oracle_tag[oracle_line]=dut.inner.fill_write_block;oracle_valid[oracle_line]=1;
                oracle_lru[oracle_set]=!(oracle_line>=SETS);
                if(oracle_line>=SETS)way1_fills=way1_fills+1;else way0_fills=way0_fills+1;
            end
            #1;
            if(!failed && (dut.inner.valid_lines!==oracle_valid || dut.inner.lru_way!==oracle_lru))
                $fatal(1,"published metadata/LRU differs from independent ordered-demand oracle");
        end
    end
'''
    if text.count(marker) != 1:
        raise ValueError('nonunique task marker')
    text = text.replace(marker, extra + marker)
    text = text.replace('        summary=$fopen($sformatf(',
                        '        if(oracle_checks<10||way0_fills==0||way1_fills==0||fast_way1_touches==0||invalid0_choices==0||invalid1_choices==0||lru0_choices+lru1_choices==0)\n'
                        '            $fatal(1,"associative replacement coverage was vacuous");\n'
                        '        $display("ASSOC_ORACLE WIDTH%0d INDEX%0d checks%0d fillways%0d/%0d fastway1%0d invalid%0d/%0d lru%0d/%0d",WIDTH,INDEX_BITS,oracle_checks,way0_fills,way1_fills,fast_way1_touches,invalid0_choices,invalid1_choices,lru0_choices,lru1_choices);\n'
                        '        summary=$fopen($sformatf(')
    bench = HERE / 'tests/tb_assoc2_cache_a.sv'
    bench.parent.mkdir(parents=True, exist_ok=True)
    with bench.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)
    base_runner = ROOT / 'tools/run_directfill_tagpipe_cache_sim.py'
    runner = base_runner.read_text().replace('\r\n', '\n')
    runner = runner.replace('from run_fill8_rowpipe_cache_sim import run_tool',
                            'import sys\nsys.path.insert(0,str(Path(__file__).resolve().parents[3]/\'distortion/tools\'))\nfrom run_fill8_rowpipe_cache_sim import run_tool')
    runner = runner.replace("ROOT = Path(__file__).resolve().parents[1]", "ROOT = Path(__file__).resolve().parents[3]/'distortion'")
    runner = runner.replace("BASE = ROOT / 'work/hdmi-camera-fisheye-tile8df9-tagpipe-20261103-a'", 'BASE = Path(__file__).resolve().parent')
    runner = runner.replace("SOURCE = ROOT / 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill_tagpipe.v'", "SOURCE = BASE / 'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_a.v'")
    runner = runner.replace("BENCH = ROOT / 'tests/tb_directfill_tagpipe_cache.sv'", "BENCH = BASE / 'tests/tb_assoc2_cache_a.sv'")
    runner = runner.replace('CASES = ((639, 480, 3), (1920, 1080, 7), (1920, 1080, 8), (1920, 1080, 9))',
                            'CASES = ((2048, 480, 5), (639, 480, 6), (1920, 1080, 10))')
    runner = runner.replace("output.name.startswith('cache-unit-')", "output.name.startswith('unit-')")
    runner = runner.replace("'tile8-directfill-tagpipe-independent-cache-simulation-v1'", "'tile8-assoc2-tagpipe-independent-cache-simulation-v1'")
    runner = runner.replace("'SingleRegisteredBeatPerWrite': True", "'Ways':2,'IndexBitsMeansTotalLines':True,'LRUOracleChecked':True,'BothWayHeldMetadataChecked':True,'SingleRegisteredBeatPerWrite': True")
    destination = HERE / 'run_unit_a.py'
    with destination.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(runner)
    print(json.dumps(dict(Bench=str(bench), SHA256=hashlib.sha256(bench.read_bytes()).hexdigest(), Runner=str(destination))))


if __name__ == '__main__':
    main()
