"""Split adjacent-pixel reads into even/odd banks, retaining cache protocol."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
NEW='rtl/experimental/ddr_pipeline_parity_cache.v'

def main():
    text=(ROOT/'rtl/experimental/ddr_pipeline_hit_cache.v').read_text()
    text=text.replace('// Isolated four-read replica experiment. Hits enter an elastic two-stage\n// pipeline; misses drain it and use the proven serial short-burst engine.\n// Four replicas cost 32KiB in addition to the 8KiB fallback at INDEX_BITS=5.\n// No board timing/resource or DDR-controller performance claim.',
        '// Isolated even/odd pixel bank experiment, two row-read replicas.\n// Four 128-bit memories cost 16KiB plus the unchanged 8KiB fallback.\n// Hits retain the same elastic two-stage protocol. Board resources and\n// timing require separate measurement; no hardware claim from this RTL.')
    begin=text.index('    genvar n;')
    end=text.index('    ddr_serial_neighbour_cache',begin)
    text=text[:begin]+'''    wire [127:0] bank_q[0:3];
    genvar n,lane;
    generate for(n=0;n<4;n=n+1) begin: neighbour
        wire signed [16:0] nx=x0+(n%2);
        wire signed [16:0] ny=y0+(n/2);
        assign in_bounds[n]=nx>=0 && nx<WIDTH && ny>=0 && ny<HEIGHT;
        assign pixel_number[n]=ny*WIDTH+nx;
        assign line_number[n]=pixel_number[n][7 +: INDEX_BITS];
        assign word_number[n]=pixel_number[n][4 +: INDEX_BITS+3];
        assign line_hit[n]=!in_bounds[n] || (valid_lines[line_number[n]] &&
            tags[line_number[n]]==pixel_number[n][31:7]);
        wire [127:0] chosen=lane0[n][0] ? bank_q[2*(n/2)+1]:bank_q[2*(n/2)];
        always @(posedge clk)
            if(rst_n && stage1_ready && v0)
                pixels1[n]<=bounds0[n] ? expand565(chosen[lane0[n][3:1]*16 +:16]):24'd0;
    end
    for(n=0;n<4;n=n+1) begin: parity_bank
        // Horizontally adjacent pixels always occupy opposite parity banks,
        // including word/line boundaries. Top/bottom use independent copies.
        localparam LEFT=2*(n/2);
        wire [INDEX_BITS+2:0] address=(pixel_number[LEFT][0]==(n%2)) ? word_number[LEFT]:word_number[LEFT+1];
        wire [127:0] fill_data;
        for(lane=0;lane<8;lane=lane+1) begin: fill_lane
            assign fill_data[lane*16 +:16]=rdata[(2*lane+(n%2))*16 +:16];
        end
        reg [127:0] memory[0:LINES*8-1];
        reg [127:0] q;
        assign bank_q[n]=q;
        always @(posedge clk) begin
            if(read_active && rvalid && !failed && rid==0 && rlast==(fill_beat==7))
                memory[{fill_line,fill_beat}]<=fill_data;
            if(accept_fast) q<=memory[address];
        end
    end endgenerate
'''+text[end:]
    (ROOT/NEW).write_text(text)
    suite={}
    for kind,oldwork,newwork,runner in (
        ('query','pipeline_hit_query_sim','pipeline_parity_v2001_query_sim','run-pipeline-hit-query-sim.ps1'),
        ('stream','pipeline_hit_stream_sim','pipeline_parity_v2001_stream_sim','run-pipeline-hit-stream-sim.ps1'),
        ('native','pipeline_twelve_native_sim','pipeline_parity_v2001_native_sim','run-pipeline-twelve-native-sim.ps1')):
        work=ROOT/'build'/newwork
        if (work/'simulation.log').exists():raise ValueError('Existing parity simulation; do not regenerate')
        work.mkdir(exist_ok=True)
        for src in (ROOT/'build'/oldwork).iterdir():
            if src.is_file() and src.suffix in ('.mem','.json','.vh'):
                shutil.copy2(src,work/src.name)
        script=(ROOT/'tools'/runner).read_text(encoding='utf-8-sig').replace(oldwork,newwork).replace("'ddr_pipeline_hit_cache'","'ddr_pipeline_parity_cache'")
        if kind=='query':
            tb=(ROOT/'tests/tb_pipeline_hit_query.sv').read_text().replace(oldwork,newwork)
            (ROOT/'tests/tb_pipeline_parity_v2001_query.sv').write_text(tb)
            script=script.replace("'tests\\tb_pipeline_hit_query.sv'","'tests\\tb_pipeline_parity_v2001_query.sv'")
        newrunner='tools/run-pipeline-parity-v2001-'+kind+'-sim.ps1'
        (ROOT/newrunner).write_text(script,encoding='utf-8-sig')
        suite[kind]={'work_directory':str(work),'runner':newrunner}
    all_files=[NEW,'rtl/experimental/ddr_pipeline_serial_cache.v','rtl/experimental/pipeline_hit_frame_engine.v',
        'rtl/experimental/ddr_adaptive_result_writer.v','tests/tb_pipeline_parity_v2001_query.sv','tests/tb_pipeline_hit_stream.sv',
        'tests/tb_pipeline_twelve_native_regression.sv','board/calibration-trial.vh','board/rotation-domain.vh','rtl/cordic-constants.vh']
    all_files+=['rtl/'+n+'.v' for n in ('bilinear_rgb','ddr_remap_sample','mul32_pipe','pixel_inverse_rotation','bounded_brown_inverse_mapper','rotated_remap_core')]
    for s in suite.values():
        all_files.append(s['runner'])
        all_files+=[p.relative_to(ROOT).as_posix() for p in Path(s['work_directory']).iterdir() if p.suffix in ('.mem','.json','.vh')]
    evidence={'hardware_accessed':False,'suite':suite,'source_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest().upper() for n in all_files},
        'logical_fast_cache_bytes_before':32768,'logical_fast_cache_bytes_after':16384,'serial_cache_bytes':8192,
        'physical_resources_verified':False}
    (ROOT/'results/lab-20261008/pipeline-parity-inputs.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('Prepared isolated parity cache and unchanged query/stream/native oracle inputs')

if __name__=='__main__':main()
