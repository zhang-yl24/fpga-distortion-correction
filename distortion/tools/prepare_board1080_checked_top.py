"""Derive and audit the isolated checked-I2C board top; no manifest changes.

This is a source transformation contract, not PDS/STA or a hardware release.
The DDR/data pipeline and all reset/clock constants remain byte-identical to
the bound rowpipe top outside the explicit replacements below.
"""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "board/board1080_rowpipe_top.v"
CANDIDATE = "board/board1080_checked_top.v"
BASELINE_SHA256 = "28cba7652a01f4eaef7f7edbc19ff63b12176aaa355c13e68a6d74bf2905d6da"
SOURCE_REPLACEMENTS = {
    BASELINE: CANDIDATE,
    "platform/video_base/source/hdmi/ms72xx_ctl.v": "rtl/experimental/ms72xx_checked_ctl.v",
    "platform/video_base/source/hdmi/ms7210_ctl.v": "rtl/experimental/ms7210_checked_ctl.v",
    "platform/video_base/source/hdmi/iic_dri.v": "rtl/experimental/iic_dri_checked.v",
    "platform/video_base/source/hdmi/ms7200_ctl.v": "rtl/experimental/ms7200_1080p30_ctl.v",
}
REPLACEMENTS = (
    ("// Independent row-product pipeline integration; same board interfaces and reset logic.",
     "// Isolated checked-I2C board integration; SCL is open drain and faults latch A7."),
    ("    output hd_scl,inout hd_sda,output rstn_out,output [7:0] led,",
     "    inout hd_scl,inout hd_sda,output rstn_out,output [7:0] led,"),
    ("    wire rx_init_done,tx_init_done;\n"
     "    ms72xx_ctl hdmi_configuration(.clk(cfg_clk),.rst_n(global_reset_n),\n"
     "        .init_over_rx(rx_init_done),.init_over(tx_init_done),.iic_scl(hd_scl),.iic_sda(hd_sda));",
     "    wire rx_init_done,tx_init_done,hdmi_init_failed;\n"
     "    wire [3:0] hdmi_init_error; // Held by checked driver until common reset.\n"
     "    ms72xx_checked_ctl hdmi_configuration(.clk(cfg_clk),.rst_n(global_reset_n),\n"
     "        .init_over_rx(rx_init_done),.init_over(tx_init_done),\n"
     "        .init_failed(hdmi_init_failed),.error_code(hdmi_init_error),.iic_scl(hd_scl),.iic_sda(hd_sda));"),
    ("    // init_over only means the reference sequencer completed. It is not an",
     "    // init_over only means checked register transactions completed. It is not an"),
    ("    (* async_reg=\"true\" *) reg [1:0] system_failed_ref,processed_bit_ref;",
     "    (* async_reg=\"true\" *) reg [1:0] system_failed_ref,processed_bit_ref;\n"
     "    (* async_reg=\"true\" *) reg [1:0] hdmi_failed_ref;"),
    ("            system_failed_ref<=0;processed_bit_ref<=0;\n        end else if(!ref_reset[1])begin",
     "            system_failed_ref<=0;processed_bit_ref<=0;hdmi_failed_ref<=0;\n        end else if(!ref_reset[1])begin"),
    ("            system_failed_ref<=0;processed_bit_ref<=0;\n        end else begin",
     "            system_failed_ref<=0;processed_bit_ref<=0;hdmi_failed_ref<=0;\n        end else begin"),
    ("            system_failed_ref<={system_failed_ref[0],system_failed};processed_bit_ref<={processed_bit_ref[0],processed_frames[4]};",
     "            system_failed_ref<={system_failed_ref[0],system_failed};processed_bit_ref<={processed_bit_ref[0],processed_frames[4]};\n"
     "            hdmi_failed_ref<={hdmi_failed_ref[0],hdmi_init_failed};"),
    ("            if(!pipeline_release && !board_failed && cfg_lock_ref[1] && video_lock_ref[1] &&",
     "            if(!pipeline_release && !board_failed && !hdmi_failed_ref[1] && cfg_lock_ref[1] && video_lock_ref[1] &&"),
    ("            if(pipeline_release && !board_failed)begin",
     "            // A7 applies before AND after startup; fault wins simultaneous readiness.\n"
     "            // Keep pipeline_release monotonic; runtime recovery uses the existing drain path.\n"
     "            if(!board_failed && hdmi_failed_ref[1])begin board_failed<=1;board_fault<=8'ha7;end\n"
     "            else if(pipeline_release && !board_failed)begin"),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render(source):
    raw = Path(source).read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASELINE_SHA256:
        raise ValueError("rowpipe baseline differs from the bound source")
    # Preserve the baseline CRLF convention, including every untouched byte.
    for before, after in REPLACEMENTS:
        old = before.replace("\n", "\r\n").encode("ascii")
        new = after.replace("\n", "\r\n").encode("ascii")
        if raw.count(old) != 1:
            raise ValueError("exact top transformation anchor differs")
        raw = raw.replace(old, new, 1)
    return raw


def audit(root=ROOT):
    root = Path(root)
    expected = render(root / BASELINE)
    if (root / CANDIDATE).read_bytes() != expected:
        raise ValueError("checked top differs outside exact allowed transformation")
    return {"Baseline": BASELINE, "BaselineSHA256": BASELINE_SHA256,
            "Candidate": CANDIDATE, "CandidateSHA256": sha(root / CANDIDATE),
            "SourceReplacements": SOURCE_REPLACEMENTS,
            "Edits": len(REPLACEMENTS), "SCLInout": True,
            "StartupFailureBlocksRelease": True, "RuntimeFailureUsesExistingDrainPath": True,
            "DDRAndPipelineBodyUnchanged": True, "ProductionManifestChanged": False,
            "PDSExecuted": False, "HardwareReleaseAllowed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create", action="store_true", help="create missing candidate only")
    args = parser.parse_args(argv)
    if args.create:
        with (ROOT / CANDIDATE).open("xb") as stream:
            stream.write(render(ROOT / BASELINE))
    print(json.dumps(audit(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
