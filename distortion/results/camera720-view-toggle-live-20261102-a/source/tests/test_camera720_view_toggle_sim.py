"""Reject mixed-mode/epoch results in the switching regression's output audit."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import run_camera720_view_toggle_sim as sim


def test_profile_mux_changes_wait_for_mapper_frame_boundary(tmp_path):
    """Fast RTL proof alongside the long full-frame DDR/scan regression."""
    work = tmp_path.resolve()
    n = 64
    current, guard = sim.corrected.parse_header(sim.PROFILE.read_text(encoding='ascii'))
    raw, _ = sim.corrected.parse_header((sim.ROOT / sim.RAW).read_text(encoding='ascii'))
    points = [(x, y) for y in (0, 1, 120, 359, 360, 600, 718, 719)
              for x in (0, 1, 160, 639, 640, 1120, 1278, 1279)]
    rows = []
    for config in (current, raw, current):
        u = np.array([p[0] * 256 for p in points], dtype=np.int64)
        v = np.array([p[1] * 256 for p in points], dtype=np.int64)
        x, y, bad, radius = sim.cpu.project_integer(u, v, config)
        for i in range(n):
            black = bool(bad[i] or radius[i] > guard)
            px, py = (-(1 << 23),) * 2 if black else (int(x[i]), int(y[i]))
            word = (int(u[i]) << 73) | (int(v[i]) << 49) | (int(black) << 48) | ((px & 0xffffff) << 24) | (py & 0xffffff)
            rows.append(f'{word:025x}')
    (work / 'vectors.mem').write_text('\n'.join(rows) + '\n', encoding='ascii')
    (work / 'config.vh').write_bytes(sim.PROFILE.read_bytes())
    (work / 'camera720-view-select.vh').write_bytes((sim.ROOT / sim.SELECT).read_bytes())
    ports = ','.join(f'.cfg_{name.lower()}(view_{name.lower()})' for name in sim.cpu.NAMES)
    bench = r'''
`timescale 1ns/1ps
module tb_view_mapper;
    `include "config.vh"
    reg corrected_requested=1;
    `include "camera720-view-select.vh"
    reg clk=0,rst=1,cfg_valid=0,in_valid=0,out_ready=0;
    always #4 clk=~clk;
    wire cfg_ready,in_ready,out_valid,out_black;
    reg signed [23:0] in_u=0,in_v=0;
    reg [23:0] in_tag=0;
    wire signed [23:0] out_x,out_y;
    wire [23:0] out_tag;
    bounded_brown_inverse_mapper #(.MAX_RADIUS_Q22(C720_RADIUS_Q22)) dut(
        .clk(clk),.rst(rst),.cfg_valid(cfg_valid),.cfg_ready(cfg_ready),__PORTS__,
        .in_black(1'b0),.in_valid(in_valid),.in_ready(in_ready),.in_u(in_u),.in_v(in_v),.in_tag(in_tag),
        .out_valid(out_valid),.out_ready(out_ready),.out_x(out_x),.out_y(out_y),.out_black(out_black),.out_tag(out_tag));
    reg [96:0] vectors[0:191];
    reg held=0;reg [72:0] held_data;
    integer ticks=0,received=0,phase,q,blocked_config=0;
    always @(posedge clk)if(!rst)begin
        ticks<=ticks+1;
        if(held && (!out_valid || {out_black,out_tag,out_x,out_y}!==held_data))
            $fatal(1,"view mapper output changed during backpressure");
        held<=out_valid && !out_ready;held_data<={out_black,out_tag,out_x,out_y};
        if(cfg_valid && !cfg_ready)blocked_config<=blocked_config+1;
        if(out_valid && out_ready)begin
            if(out_tag!==received || {out_black,out_x,out_y}!==vectors[received][48:0])
                $fatal(1,"view mapper changed mode midframe tag=%0d expected=%0d",out_tag,received);
            received<=received+1;
        end
    end
    always @(negedge clk)out_ready=!rst && ticks%11>=4;
    task configure;
        begin
            @(negedge clk);cfg_valid=1;
            do @(posedge clk);while(!cfg_ready);
            @(negedge clk);cfg_valid=0;
        end
    endtask
    task send(input integer index);
        begin
            @(negedge clk);in_valid=1;in_u=vectors[index][96:73];in_v=vectors[index][72:49];in_tag=index;
            if(index==16)corrected_requested=0;
            if(index==80)corrected_requested=1;
            if(index==144)corrected_requested=0;
            do @(posedge clk);while(!in_ready);
        end
    endtask
    initial begin
        $readmemh("vectors.mem",vectors);
        repeat(6)@(posedge clk);@(negedge clk);rst=0;
        for(phase=0;phase<3;phase=phase+1)begin
            configure;
            for(q=phase*64;q<(phase+1)*64;q=q+1)send(q);
            @(negedge clk);in_valid=0;
        end
        wait(received==192);
        if(blocked_config==0)$fatal(1,"no pending configuration during old frame drain");
        $display("VIEW_MAPPER_PASS rays=192 corrected/raw/corrected midframe requests and output stalls");
        $finish;
    end
    initial begin #1000000;$fatal(1,"view mapper deadline");end
endmodule
'''.replace('__PORTS__', ports)
    tb = work / 'tb_view_mapper.sv'
    tb.write_text(bench, encoding='ascii')
    sources = (sim.ROOT / 'rtl/mul32_pipe.v', sim.ROOT / 'rtl/bounded_brown_inverse_mapper.v', tb)
    iverilog, vvp = shutil.which('iverilog'), shutil.which('vvp')
    if iverilog and vvp:
        compiled = subprocess.run([iverilog, '-g2012', '-s', 'tb_view_mapper', '-o', str(work / 'sim.vvp'),
                                   *map(str, sources)], cwd=work, capture_output=True, text=True, timeout=60)
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr
        result = subprocess.run([vvp, str(work / 'sim.vvp')], cwd=work, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr
        log = result.stdout + result.stderr
    else:
        from simulation_tools import resolve_vivado_bin
        binary = resolve_vivado_bin(sim.ROOT.parent).resolve()
        if os.name != 'nt' or not all((binary / n).is_file() for n in ('xvlog.bat', 'xelab.bat', 'xsim.bat')):
            pytest.skip('mapper RTL test requires Icarus or configured local XSim')
        deadline = time.monotonic() + 120
        sim.tool(binary, 'xvlog.bat', ['--sv', *map(str, sources)], work, deadline, 'compile')
        sim.tool(binary, 'xelab.bat', ['tb_view_mapper', '-s', 'view_mapper_tb', '--timescale', '1ns/1ps'], work, deadline, 'elaborate')
        sim.tool(binary, 'xsim.bat', ['view_mapper_tb', '-runall', '-log', 'simulation.log'], work, deadline, 'simulate')
        log = (work / 'simulation.log').read_text(encoding='utf-8', errors='replace')
    assert log.count('VIEW_MAPPER_PASS rays=192') == 1, log
    assert not re.search(r'(?im)^\s*(?:fatal|error):', log), log


class ViewOutputAuditTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='view-toggle-audit-')
        self.addCleanup(self.scratch.cleanup)
        self.work = Path(self.scratch.name)
        self.frames = [np.arange(8, dtype=np.uint16).reshape(2, 4) + i * 10 for i in range(3)]
        self.records = [{'FrameID': i + 1, 'Mode': mode, 'SourceCRC32': sim.crc(frame ^ np.uint16(i != 1)),
                         'CorrectedCRC32': sim.crc(frame)}
                        for i, (frame, mode) in enumerate(zip(self.frames, ('corrected', 'raw', 'corrected')))]
        self.summary = {'repeat_scans': 1}
        self.write_scans((1, 1, 2, 3))
        rows = ['event,id,core_cycle,crc32']
        for i, record in enumerate(self.records):
            rows += [f"commit,{i+1},{i*10+1},{record['SourceCRC32']}",
                     f"release,{i+1},{i*10+2},{record['CorrectedCRC32']}"]
        (self.work / 'events.csv').write_text('\n'.join(rows) + '\n', encoding='ascii')

    def write_scans(self, ids):
        (self.work / 'scan-pixels.mem').write_text(''.join(
            f'{fid} {int(v):04x}\n' for fid in ids for v in self.frames[fid - 1].ravel()), encoding='ascii')

    def verify(self):
        return sim.validate_outputs(self.work, self.frames, self.records, self.summary)

    def test_corrected_raw_corrected_and_repeat_retain_distinct_crc(self):
        result = self.verify()
        self.assertEqual([r['Mode'] for r in result], ['corrected', 'corrected', 'raw', 'corrected'])
        self.assertEqual([r['Pixels'] for r in result], [8] * 4)

    def test_one_raw_pixel_replaced_by_corrected_pixel_is_rejected(self):
        path = self.work / 'scan-pixels.mem'
        rows = path.read_text().splitlines()
        rows[18] = '2 0000'
        path.write_text('\n'.join(rows) + '\n', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'per-frame independent view oracle'):
            self.verify()

    def test_mode_or_epoch_change_inside_display_is_rejected(self):
        path = self.work / 'scan-pixels.mem'
        rows = path.read_text().splitlines()
        rows[18] = '3 ' + rows[18].split()[1]
        path.write_text('\n'.join(rows) + '\n', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'epoch changed'):
            self.verify()

    def test_old_frame_repeating_cannot_substitute_for_new_raw_frame(self):
        self.write_scans((1, 1, 1, 3))
        with self.assertRaisesRegex(ValueError, 'not every source epoch'):
            self.verify()

    def test_raw_crc_cannot_substitute_corrected_result_crc(self):
        path = self.work / 'events.csv'
        path.write_text(path.read_text().replace(self.records[0]['CorrectedCRC32'], self.records[0]['SourceCRC32']), encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'view result completion CRC'):
            self.verify()

    def test_missing_and_extra_pixels_are_rejected(self):
        path = self.work / 'scan-pixels.mem'
        original = path.read_text()
        path.write_text('\n'.join(original.splitlines()[:-1]) + '\n', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'incomplete actual scan'):
            self.verify()
        path.write_text(original + '3 0000\n', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'extra HDMI pixels'):
            self.verify()

    def test_default_preparation_never_launches_simulator(self):
        work = self.work.resolve() / 'prepared'
        with mock.patch.object(sim, 'BASE', self.work.resolve()), \
             mock.patch.object(sim, 'fixtures', return_value=(self.frames, self.records, {})), \
             mock.patch.object(sim, 'resolve_vivado_bin', side_effect=AssertionError('unexpected simulator lookup')), \
             mock.patch.object(sim, 'tool', side_effect=AssertionError('unexpected simulator launch')):
            self.assertEqual(sim.run(work), 0)
        result = json.loads((work / sim.REPORT).read_text())
        self.assertTrue(result['Prepared'])
        self.assertFalse(result['Passed'])
        self.assertFalse(result['SimulationExecuted'])
        self.assertFalse(result['HardwareAccessed'])
        self.assertEqual(result['InputSHA256'], result['InputSHA256After'])


if __name__ == '__main__':
    unittest.main()
