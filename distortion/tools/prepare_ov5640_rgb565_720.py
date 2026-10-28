"""Source-bound 84/4 RGB565720 register candidate, never a board-ready claim.

Only new files; --stage creates its ROM and action manifest once. Common ISP
bytes come from the frozen RGB baseline. All legacy clock, wake, geometry and
banding writes are removed before inserting the reviewed conditional sequence.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import ov5640_clock_sequence_audit as clock

ROOT=Path(__file__).resolve().parents[1]
ROM="board/ov5640_rgb565_720_commands.vh"
MANIFEST="board/ov5640_rgb565_720_sequence.json"
BASE="board/ov5640_cadence_trial_commands.vh"
PROPOSAL="build/offline-20261024/guarded-720-source-review-20261025/proposed-720-register-order.json"
WRITE,RMW,READ,RESET_WRITE=1,2,3,5
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def expected():
    if sha(ROOT/BASE)!="53428872aa14e6120eed93d876c889ef5155b3c196c014db77c4578b2bd50674":
        raise ValueError("frozen RGB common source changed")
    if sha(ROOT/PROPOSAL)!="c31b5d46ea7a4eb11b812016603e9baa4930049f45d83c7a262e64d2136dc30a":
        raise ValueError("reviewed720 geometry source changed")
    proposal=json.loads((ROOT/PROPOSAL).read_text(encoding="utf-8-sig"))
    rows=proposal["ordered_proposed_writes"]
    actions=[]
    def add(op,address,mask,value,delay=0,source=""):
        actions.append(dict(index=len(actions),op=op,address=address,mask=mask,value=value,delay_ms=delay,source=source))
    # Source delay20ms is the existing documented software-reset/wake delay,
    # not a newly claimed PLL lock/settling guarantee.
    add(RESET_WRITE,0x3008,0,0x82,20,"RGB software reset; final-data NACK cannot be verified as a self-clearing reset")
    add(READ,0x300a,255,0x56,source="silicon ID high")
    add(READ,0x300b,255,0x40,source="silicon ID low")
    clock_actions=clock.proposed_actions()
    checked=clock.audit_sequence(clock_actions)
    if not checked["static_model_passed"]:raise ValueError("reviewed84/4 clock sequence failed")
    for action in clock_actions[1:]:
        add(READ if action["op"]=="read_check" else RMW if action["op"]=="rmw" else WRITE,
            action["address"],action["mask"],action.get("expected",action.get("value")),source="reviewed conditional84/4 clock action")
    # Take only the sourced720 geometry/analog-mode patch, never its PLL values.
    mode={int(row["address"],16):int(row["value"],16) for row in rows[266:307]}
    for row in rows:
        a=int(row["address"],16)
        if 0x3810<=a<=0x3812:mode.setdefault(a,int(row["value"],16))
    mode.update({0x300e:0x58,0x4300:0x6f,0x501f:1,0x3017:0x7f,0x3018:0xf0,0x4740:0x23,
                 0x3a08:0,0x3a09:110,0x3a0a:0,0x3a0b:91,0x3a0e:6,0x3a0d:8})
    if mode[0x380c]*256+mode[0x380d]!=1892 or mode[0x380e]*256+mode[0x380f]!=740:
        raise ValueError("source720 HTS/VTS differs")
    excluded=set(clock.MASKS)|set(mode)|set(range(0x3800,0x3816))|{0x3008}
    common=[];removed=[]
    baseline=(ROOT/BASE).read_text(encoding="utf-8")
    for index,a,v,delay in re.findall(r"9'd(\d+): camera_command=32'h([0-9a-f]{4})([0-9a-f]{2})([0-9a-f]{2});",baseline):
        a,v,delay=int(a,16),int(v,16),int(delay,16)
        if a in excluded:removed.append(int(index));continue
        common.append(int(index));add(WRITE,a,0,v,delay,"unchanged RGB common index"+index)
    for a,v in mode.items():add(WRITE,a,255,v,source="sourced720 geometry/mode; RGB formatter/pads from measured baseline; banding computed at nominal24MHz")
    finals={a:(clock.MASKS[a],v) for a,v in clock.FINAL.items()}
    finals.update({a:(255,v) for a,v in mode.items()})
    preflight=len(actions)
    for a,(mask,v) in finals.items():add(READ,a,mask,v,source="complete controlled pre-wake read check")
    wake=len(actions);add(RMW,0x3008,0x40,0,20,"unique final stream wake after preflight; no PLL lock claim")
    postflight=len(actions)
    for a,(mask,v) in finals.items():add(READ,a,mask,0 if a==0x3008 else v,source="complete controlled post-wake read check")
    if len(actions)>=1024:raise ValueError("action index width exceeded")
    for a in actions:
        if a["op"] in (WRITE,RMW) and a["address"]==0x3036 and a["value"]!=84:raise ValueError("legacy multiplier escaped filtering")
    lines=["// Independent84/4 RGB565720 register candidate. No hardware/mode admission.",
           "// Common ISP bytes retain STMicroelectronics BSD-3-Clause provenance; see vendor/reference/st-ov5640/LICENSE.md.",
           f"localparam MODE_ACTIONS={len(actions)}, MODE_PREFLIGHT={preflight}, MODE_WAKE={wake}, MODE_POSTFLIGHT={postflight};",
           "function [47:0] mode_action; input [9:0] index; begin case(index)"]
    for a in actions:
        word=(a["op"]<<44)|(a["address"]<<28)|(a["mask"]<<20)|(a["value"]<<12)|a["delay_ms"]
        lines.append(f"10'd{a['index']}:mode_action=48'h{word:012x};")
    lines.extend(["default:mode_action=0;","endcase end endfunction",""])
    report={"Target":"ov5640_rgb565_720_register_candidate","ImageSize":[1280,720],"CompleteOrderedRegisterSequence":True,
            "NominalXVCLKHz":24000000,"XVCLKMeasured":False,"NominalPCLKModelHz":42000000,"UpperPCLKModelHzAt27MHz":47250000,
            "NominalFPSModel":42000000/(1892*740*2),"MeasuredFPS":None,"HardwareReleaseAllowed":False,
            "ConfiguredIsNotModeReady":True,"ClockActivityAndLineFreshnessMonitorImplemented":False,
            "MissingModeAdmissionGate":"PCLK-domain activity/CDC plus exact2560 bytes x720 lines and freshness; no raw grant may depend on configured alone",
            "ClockActionAudit":checked,"ClockActions":clock_actions,"Actions":actions,"CommonBaseIndices":common,"RemovedLegacyIndices":removed,
            "SourceSHA256":{n:sha(ROOT/n) for n in [BASE,PROPOSAL,"tools/ov5640_clock_sequence_audit.py",
                "output/project/ov5640-720p-bounded-clock-source-plan-20261025.json"]},
            "FinalModeBytes":{f"{a:04X}":v for a,v in mode.items()},
            "BandingNominal24MHz":{"step50":110,"step60":91,"max50":6,"max60":8,"SCLKModelHz":21000000,"HTS":1892,"VTS":740},
            "Limits":"Engineering RGB mode adaptation, not an OEM board recipe. Static controlled PLL model only; reset/default interval, transients, low VCO lock and actual XVCLK/PCLK remain unmeasured. No guessed PLL lock bit/delay. Full critical mode/clock read checks; common undocumented ISP bytes use ACK, with data-high accepted only after exact full readback. No mode admission, pixels, PDS, hardware, optical or30fps claim."}
    return {ROM:"\n".join(lines).encode(),MANIFEST:(json.dumps(report,indent=2,allow_nan=False)+"\n").encode()}


def verify():
    for n,payload in expected().items():
        if (ROOT/n).read_bytes()!=payload:raise ValueError("720 source/action ROM changed: "+n)
    return json.loads((ROOT/MANIFEST).read_text(encoding="utf-8"))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--stage",action="store_true");args=parser.parse_args()
    if args.stage:
        files=expected()
        if any((ROOT/n).exists() for n in files):raise ValueError("new candidate only; no overwrite")
        for n,payload in files.items():
            with (ROOT/n).open("xb") as out:out.write(payload)
    result=verify();print(json.dumps({"verified":True,"actions":len(result["Actions"]),"hardware_release_allowed":False}))
