"""Prepare the separate CAM2 guarded target; never build or access hardware."""
from pathlib import Path
import argparse
import hashlib
import json
import re
from pds_source_manifest import expand_sources

ROOT = Path(__file__).resolve().parents[1]
TARGET = "raw_camera_capture_cam2_guarded"
REFERENCE = "raw_camera_capture_cam2_ref"


def prepare(*, refresh=False):
    baseline = json.loads((ROOT / f"board/{REFERENCE}-sources.json").read_text(encoding="utf-8"))
    for name, expected in baseline["SourceSHA256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest().upper() != expected.upper():
            raise ValueError(f"Original 97-source raw baseline changed: {name}")
    contract = json.loads((ROOT / "output/project/guarded-protocol-v2.json").read_text(encoding="utf-8"))["contract"]
    if contract["build_tag"] != 0x52473201 or contract["status_bytes"] != 128:
        raise ValueError("Guarded protocol identity changed")
    old_tcl = (ROOT / f"board/build-{REFERENCE}.tcl").read_text(encoding="utf-8")
    design = [Path(name).relative_to(ROOT).as_posix() for name in re.findall(r"add_design \{([^}]+)\}", old_tcl)]
    design.remove(f"board/{REFERENCE}.v")
    design += ["rtl/raw_capture_lease.v", "rtl/raw_camera_capture_guarded.v",
               "rtl/guarded_command_engine.v", "rtl/guarded_capture_controller.v",
               "rtl/guarded_temperature_cdc.v", "rtl/guarded_status_uart.v",
               "rtl/guarded_uart_arbiter.v", "rtl/experimental/uart_rx_control.v",
               "rtl/logos2_temperature_monitor.v", "rtl/adc_temperature_reader.v", f"board/{TARGET}.v"]
    fdc = (ROOT / f"board/{REFERENCE}.fdc").read_text(encoding="utf-8")
    fdc = fdc.replace("# Small camera-ID / HDMI output build. No DDR or camera pixel clock.",
                      "# Independent guarded raw + ADC candidate; no corrected-image datapath.")
    # Held-bus CDC must arrive well before the synchronized request is consumed.
    # Keep pixel-domain unrelated logic asynchronous, but bound BOTH directions
    # of the actual 27MHz/core status crossing instead of false-pathing the bus.
    old_group = "set_clock_groups -name ddr_user_async -asynchronous -group [get_clocks {clk_27m pixel_clk}] -group [get_clocks {ref_clk rst_clk ddrphy_sysclk phy_dq_clk_0 phy_dq_sysclk_0 phy_dq_clk_1 phy_dq_sysclk_1}]"
    camera_group = "set_clock_groups -name camera_async -asynchronous -group [get_clocks camera_pclk] -group [get_clocks {clk_27m pixel_clk}]"
    if fdc.count(old_group) != 1 or fdc.count(camera_group) != 1:
        raise ValueError("Reference clock-group lines differ; refusing a broad CDC constraint edit")
    fdc = fdc.replace(old_group, old_group.replace("{clk_27m pixel_clk}", "{pixel_clk}"), 1)
    if fdc.count(camera_group) != 1:
        raise ValueError("Original camera/27MHz asynchronous reset group was changed")
    fdc += """
# New RX pad crosses only via uart_rx_control's two-flop pin synchronizer.
define_attribute {p:uart_rxd} {PAP_IO_LOC} {B24}
define_attribute {p:uart_rxd} {PAP_IO_VCCIO} {3.3}
define_attribute {p:uart_rxd} {PAP_IO_STANDARD} {LVCMOS33}
set_false_path -from [get_ports uart_rxd] -to [get_clocks ddrphy_sysclk]
# 27MHz ADC/camera held snapshots plus req/ack and registered safety level.
set_max_delay -datapath_only -from [get_clocks clk_27m] -to [get_clocks ddrphy_sysclk] 8.0
set_max_delay -datapath_only -from [get_clocks ddrphy_sysclk] -to [get_clocks clk_27m] 8.0
set_min_delay -from [get_clocks clk_27m] -to [get_clocks ddrphy_sysclk] 0.0
set_min_delay -from [get_clocks ddrphy_sysclk] -to [get_clocks clk_27m] 0.0
"""
    pins = json.loads((ROOT / f"board/{REFERENCE}-pins.json").read_text(encoding="utf-8"))
    if pins["cam_data[5]"] != "AA23" or "B24" in pins.values():
        raise ValueError("CAM2 D5 or UART RX reference is inconsistent")
    pins["uart_rxd"] = "B24"
    tcl = "".join("add_design {" + (ROOT / name).as_posix() + "}\n" for name in design)
    tcl += old_tcl[old_tcl.index("add_constraint "):].replace(REFERENCE, TARGET)
    generated = {f"board/{TARGET}.fdc": fdc, f"board/{TARGET}-pins.json": json.dumps(pins, indent=2)+"\n",
                 f"board/build-{TARGET}.tcl": tcl}
    for name, content in generated.items():
        path = ROOT / name
        if path.exists() and path.read_text(encoding="utf-8") != content and not refresh:
            raise ValueError(f"Candidate differs; explicit --refresh-prepared required: {name}")
        path.write_text(content, encoding="utf-8")
    extra = list(generated) + ["rtl/video_crc32.vh", "board/ov5640_cadence_trial_commands.vh", "board/ms7210_commands.vh"]
    names = expand_sources(ROOT, design + extra)
    manifest = {"target": TARGET, "hardware_accessed": False, "physical_eye": None,
                "connector_slot_tag": 2, "reference_board_port": "CAM2 D5 AA23, UART RX B24",
                "RawCaptureContract": baseline["RawCaptureContract"], "GuardedControlContract": contract,
                "source_files": names, "SourceSHA256": {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper() for name in names},
                "limits": "Prepared guarded candidate only. ADC estimates are approximate. No optical, physical-eye, stereo, thermal-safety or unattended acceptance. Failed partial raw packet retains UART lock for host timeout/idle restoration. A stopped DDR/core clock can silence status; 27MHz ADC does not create an independent UART supervisor."}
    path = ROOT / f"board/{TARGET}-sources.json"
    content = json.dumps(manifest, indent=2)+"\n"
    if path.exists() and path.read_text(encoding="utf-8") != content and not refresh:
        raise ValueError("Prepared source binding differs; explicit --refresh-prepared required")
    path.write_text(content, encoding="utf-8")
    return {"target": TARGET, "source_files": len(names), "active_pins": len(pins), "hardware_accessed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-prepared", action="store_true", help="Refresh only this unprogrammed candidate's source binding")
    args = parser.parse_args()
    print(json.dumps(prepare(refresh=args.refresh_prepared)))
