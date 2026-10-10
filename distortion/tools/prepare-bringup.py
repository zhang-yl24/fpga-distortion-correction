"""Generate a small board build from audited vendor pin and MS7210 tables."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "platform/video_base"
board = ROOT / "board"
vendor_ctl = (BASE / "source/hdmi/ms7210_ctl.v").read_text(errors="replace")
entries = re.findall(r"6'd(\d+)\s*:\s*cmd_data\s*=\s*\{16'h([0-9a-fA-F]+),8'h([0-9a-fA-F]+)\}", vendor_ctl)
assert len(entries) == 49 and [int(e[0]) for e in entries] == list(range(49))
rom = "// Register settings retained from vendor ms7210_ctl.v; not an original algorithm.\n"
rom += "function [23:0] hdmi_command;\ninput [5:0] index;\nbegin\ncase(index)\n"
rom += "\n".join(f"6'd{i}: hdmi_command=24'h{a.zfill(4)}{v.zfill(2)};" for i, a, v in entries)
rom += "\ndefault: hdmi_command=24'h000000;\nendcase\nend\nendfunction\n"
(board / "ms7210_commands.vh").write_text(rom)
# Keep the vendor PLL VCO and feedback parameters; double output divider
# 7 -> 14 for 74.25MHz (720p60). Compile the explicit primitive wrapper.
pll_text=(BASE / "ipcore/pll/pll.v").read_text()
assert "STATIC_RATIO0    = 7.0" in pll_text and "STATIC_DUTY0     = 7;" in pll_text
pll_text=pll_text.replace("module pll (", "module bringup_pll (")
pll_text=pll_text.replace("STATIC_RATIO0    = 7.0", "STATIC_RATIO0    = 14.0")
pll_text=pll_text.replace("STATIC_DUTY0     = 7;", "STATIC_DUTY0     = 14;")
(board / "bringup_pll.v").write_text(pll_text)
pins = {"clk_27m": "D18", "uart_txd": "C24", "cam_rst_n": "T20", "cam_scl": "W21", "cam_sda": "U14"}
pins.update({f"led[{i}]": p for i, p in enumerate(["A20","C18","C19","E18","A17","A18","C17","B17"])})
fdc = (BASE / "HDMI_IN_DDR3_HDMI_OUT_top.fdc").read_text(errors="replace")
selected = {"pix_clk", "vs_out", "hs_out", "de_out", "rstn_out", "hd_scl", "hd_sda"}
selected.update(f"{c}_out[{i}]" for c in "rgb" for i in range(8))
for port, pin in re.findall(r"define_attribute\s+\{p:([^}]+)\}\s+\{PAP_IO_LOC\}\s+\{([^}]+)\}", fdc):
    if port in selected:
        pins[port] = pin
assert selected <= pins.keys()
assert len(set(pins.values())) == len(pins), "Pin collision"
lines = ["# Small camera-ID / HDMI output build. No DDR or camera pixel clock.",
         "create_clock -name clk_27m -period 37.037 [get_ports clk_27m]",
         # Bringup PLL takes 27MHz and outputs 74.25MHz (ratio 11/4).
         "create_generated_clock -name pixel_clk -source [get_ports clk_27m] -multiply_by 11 -divide_by 4 [get_pins video_pll/clkout0]",
         # External buses: only cuts to explicit first synchronizer stages.
         "set_false_path -from [get_ports {cam_scl cam_sda hd_scl hd_sda}] -to [get_cells -hierarchical {*scl_meta* *sda_meta*}]",
         "set_false_path -from [get_pins video_pll/lock] -to [get_cells -hierarchical {*pixel_reset_sync*}]",
         # Initial external budget, not a measured chip/PCB timing value.
         "set_output_delay -clock pixel_clk -max 2.0 [get_ports {r_out[*] g_out[*] b_out[*] de_out hs_out vs_out}]",
         "set_output_delay -clock pixel_clk -min -2.0 [get_ports {r_out[*] g_out[*] b_out[*] de_out hs_out vs_out}]",
]
for port, pin in pins.items():
    lines += [f"define_attribute {{p:{port}}} {{PAP_IO_LOC}} {{{pin}}}",
              f"define_attribute {{p:{port}}} {{PAP_IO_VCCIO}} {{3.3}}",
              f"define_attribute {{p:{port}}} {{PAP_IO_STANDARD}} {{LVCMOS33}}"]
    if port != "clk_27m":
        video_port = port in selected and port not in {"rstn_out", "hd_scl", "hd_sda"}
        lines += [f"define_attribute {{p:{port}}} {{PAP_IO_DRIVE}} {{{8 if video_port else 4}}}",
                  f"define_attribute {{p:{port}}} {{PAP_IO_SLEW}} {{{'FAST' if video_port else 'SLOW'}}}"]
(board / "bringup.fdc").write_text("\n".join(lines) + "\n")
(board / "bringup-pins.json").write_text(json.dumps(pins, indent=2) + "\n")
sources = [ROOT / "rtl/reg16_i2c.v", ROOT / "rtl/uart_tx.v", ROOT / "rtl/camera_id_probe.v",
           board / "hdmi_tx_init.v", ROOT / "rtl/video_pattern.v", board / "bringup.v",
           board / "bringup_pll.v"]
tcl = [f"add_design {{{p.as_posix()}}}" for p in sources]
tcl += [f"add_constraint {{{(board / 'bringup.fdc').as_posix()}}}",
        "set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676",
        "compile -top_module bringup", "synthesize -ads -selected_syn_tool_opt 2", "dev_map", "pnr",
        "report_timing -from [get_clocks pixel_clk] -to [get_ports {r_out[*] g_out[*] b_out[*] de_out hs_out vs_out}] -max_path 2",
        "gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED"]
(board / "build-bringup.tcl").write_text("\n".join(tcl) + "\n")
print(f"Prepared {len(pins)} audited ports; 49 vendor HDMI commands.")
