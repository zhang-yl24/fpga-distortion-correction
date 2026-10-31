"""Source-bound offline Gamma/parity integration; no PDS or hardware access."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

import numpy as np
import prepare_gamma_pipeline_d5 as candidate

ROOT = candidate.ROOT
APPROVED = ROOT / "build/offline-20261024"
NEW_TESTS = ("tests/tb_gamma_pipeline_native.sv", "tests/tb_gamma_pipeline_small.sv",
             "tests/tb_ddr_gamma_pipeline_video.sv")
TOOLS = ("tools/prepare_gamma_pipeline_d5.py", "tools/run_gamma_pipeline_d5_sim.py")
FIXED = ("bilinear_rgb", "ddr_remap_sample", "mul32_pipe", "pixel_inverse_rotation",
         "bounded_brown_inverse_mapper", "dvp_rgb565_capture", "video_async_fifo",
         "ddr_video_writer", "ddr_video_reader", "ddr_video_output", "ddr_read_arbiter", "ddr_write_arbiter")
EXPERIMENTAL = ("ddr_pipeline_parity_cache", "ddr_pipeline_serial_cache", "pipeline_gamma_frame_engine",
                "ddr_adaptive_result_writer", "ddr_gamma_pipeline_video", "rotated_remap_core_gamma",
                "adaptive_gamma_stream", "adaptive_gamma_tagged", "rgb565_burst_pack_early", "camera_live_bridge_early")
COMPILE = ["rtl/" + n + ".v" for n in FIXED] + ["rtl/experimental/" + n + ".v" for n in EXPERIMENTAL]


def compile_sources(prepared):
    """Choose the verified public implementation; never mutate global COMPILE."""
    layout = prepared.get("CacheLayout")
    if layout not in candidate.CACHE_FILES:
        raise ValueError("Simulation needs an explicit verified cache layout")
    cache = candidate.CACHE_FILES[layout]
    contract = prepared["IntegrationContract"]
    if contract.get("cache") != cache or contract.get("index_bits") != 5:
        raise ValueError("Simulation cache/layout/INDEX5 contract differs")
    names = [cache if name == candidate.PARITY else name for name in COMPILE]
    if any(name not in prepared["SourceSHA256"] for name in names):
        raise ValueError("Compiled RTL is absent from the verified source closure")
    if sum(names.count(name) for name in candidate.CACHE_FILES.values()) != 1:
        raise ValueError("Multiple public neighbour-cache implementations selected")
    return names


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def verify_reference_manifest() -> dict:
    path = ROOT / "build/corrected_gamma_d5/validated-build.json"
    record = read_json(path)
    for name, digest in record["SourceSHA256"].items():
        if sha(ROOT / name) != digest.lower():
            raise ValueError("Stable routed baseline source drift: " + name)
    return {"Path": str(path), "SHA256": sha(path), "SourceCount": len(record["SourceSHA256"]),
            "SourceSHA256": record["SourceSHA256"]}


def copy_fixtures(source_dir: str, destination: Path, filenames: tuple[str, ...], proof_path: str) -> dict:
    proof = read_json(ROOT / proof_path)
    if proof.get("passed") is not True:
        raise ValueError("Historical oracle proof did not pass")
    pinned = {n.replace("\\", "/"): h.lower() for n, h in proof["source_sha256"].items()}
    report = {"Proof": proof_path, "ProofSHA256": sha(ROOT / proof_path), "Inputs": {}}
    for filename in filenames:
        name = source_dir + "/" + filename
        source = ROOT / name
        digest = sha(source)
        if pinned.get(name) != digest:
            raise ValueError("Historical fixture is absent from its proof or changed: " + name)
        shutil.copyfile(source, destination / filename)
        if sha(destination / filename) != digest:
            raise ValueError("Fixture copy mismatch")
        report["Inputs"][name] = digest
    return report


def read_words(path: Path, width: int = 32) -> bytes:
    return b"".join(int(line, 16).to_bytes(width, "little") for line in path.read_text().splitlines())


def write_words(path: Path, payload: bytes) -> None:
    with path.open("x", encoding="ascii") as out:
        for offset in range(0, len(payload), 32):
            out.write(f"{int.from_bytes(payload[offset:offset + 32], 'little'):064x}\n")


def native_gamma_oracle(work: Path) -> dict:
    """Tone independent historical native pixels; derive mask from integer math.

    Uses old measured-lens parameters, never estimates the new module's K/D.
    The historical rotation/interpolation output is SHA-pinned, not new RTL.
    """
    import zlib
    c = []
    for bits, value in re.findall(r"CAL_\w+=(\d+)'sh([0-9a-f]+);", (ROOT / "board/calibration-trial.vh").read_text()):
        bits = int(bits); value = int(value, 16)
        c.append(value - (1 << bits) if value & (1 << (bits - 1)) else value)
    if len(c) != 13:
        raise ValueError("Cannot bind all historical integer calibration parameters")
    bound = int(re.search(r"ROT_MAX_R2_Q22=(\d+)", (ROOT / "board/rotation-domain.vh").read_text())[1])
    source = ROOT / "build/pipeline_parity_v2001_native_sim/result.mem"
    pixels = np.frombuffer(read_words(source), dtype="<u2").reshape(12, 480, 640)
    rotations = [int(v, 16) for v in (work / "rotations.mem").read_text().splitlines()]
    y, x = np.indices((480, 640), dtype=np.int64)
    rs = lambda v, n: (v + (1 << (n - 1))) >> n
    tables = {bits: [np.array([round((v / ((1 << bits) - 1)) ** g * ((1 << bits) - 1))
                                       for v in range(1 << bits)]) for g in (1, .65, 1.45)] for bits in (5, 6)}
    previous = next_mode = 0
    frames = []; modes = []; crcs = []; output = bytearray()
    mask_path = work / "masks.mem"
    with mask_path.open("x", encoding="ascii") as mask_file:
        for phase, rotation in enumerate(rotations):
            co, si = rotation >> 32, rotation & 0xffffffff
            co = co - (1 << 32) if co & (1 << 31) else co
            si = si - (1 << 32) if si & (1 << 31) else si
            u = rs(co * (x * 256 - 81792) + si * (y * 256 - 61312), 30) + 81792
            v = rs(-si * (x * 256 - 81792) + co * (y * 256 - 61312), 30) + 61312
            nx = rs((u-c[0])*c[6], 16); ny = rs((v-c[1])*c[7], 16)
            xx = rs(nx*nx, 22); yy = rs(ny*ny, 22); xy = rs(nx*ny, 22); r2 = xx+yy
            radial = 2**22 + rs((c[8] + rs((c[9] + rs(c[10]*r2, 22))*r2, 22))*r2, 22)
            tx = rs(2*c[11]*xy+c[12]*(r2+2*xx), 22); ty = rs(c[11]*(r2+2*yy)+2*c[12]*xy, 22)
            sx = rs((rs(nx*radial, 22)+tx)*c[4], 22)+c[2]
            sy = rs((rs(ny*radial, 22)+ty)*c[5], 22)+c[3]
            mask = (r2 > bound) | (sx <= -256) | (sy <= -256) | (sx >= 640*256) | (sy >= 480*256)
            p = pixels[phase]
            r = (p >> 11).astype(np.int64); g = ((p >> 5) & 63).astype(np.int64); b = (p & 31).astype(np.int64)
            luminance = (77*((r << 3)|(r >> 2))+150*((g << 2)|(g >> 4))+29*((b << 3)|(b >> 2))) >> 8
            mode = next_mode; modes.append(mode)
            toned = ((tables[5][mode][r] << 11) | (tables[6][mode][g] << 5) | tables[5][mode][b]).astype("<u2")
            toned[mask] = 0
            samples = luminance[~mask]; count = len(samples)
            decision = 0 if count < 307200//4 else 1 if int((samples < 64).sum()) >= (count+1)//2 else 2 if int((samples >= 192).sum()) >= (count+1)//2 else 0
            if decision == previous:
                next_mode = decision
            previous = decision
            payload = toned.tobytes(); output.extend(payload); crc = zlib.crc32(payload); crcs.append(crc)
            # One bit per line, as expected by the independently asserted TB.
            mask_file.write("".join("1\n" if bit else "0\n" for bit in mask.ravel()))
            frames.append({"angle_deg": phase*30, "gamma_mode": mode, "decision": decision,
                           "masked_pixels": int(mask.sum()), "pixels": 307200, "crc32": f"{crc:08X}"})
    write_words(work / "result.mem", bytes(output))
    (work / "modes.mem").write_text("".join(f"{v:x}\n" for v in modes), encoding="ascii")
    (work / "crcs.mem").write_text("".join(f"{v:08x}\n" for v in crcs), encoding="ascii")
    reference = {"frames": frames, "pixels": 3686400, "integer_config": c, "radius_q22": bound,
                 "scope": "Historical real-camera raw and same-source integer remap oracle plus independently computed tone/mask. Not a new lens calibration or physical performance result."}
    (work / "gamma-reference.json").write_text(json.dumps(reference, indent=2)+"\n")
    return reference


def real_native_oracle(work: Path, binding, metadata_paths) -> dict:
    """Generate new independent fixed-point/interpolation/tone pixels from RAW.

    Uses the calibrator's existing PNG/raw/metadata validation. Never relabels
    replay, synthetic or sensor-internal test patterns as new-lens evidence.
    """
    import cv2
    import zlib
    sys.path.insert(0, str(ROOT))
    from tools.calibrate_fisheye_profile import _decode_bound_capture
    from tools.stereo_fisheye_calibrate import _file
    from tools.wideangle_mapping_audit import _fixed_project
    from model.rotation import cordic, phase_from_degrees, inverse_rotate
    from model.reference import remap_fixed
    import importlib.util
    spec=importlib.util.spec_from_file_location("profile_brown_scalar",ROOT/"tools/generate-brown-vectors.py")
    brown=importlib.util.module_from_spec(spec);spec.loader.exec_module(brown)
    profile=read_json(Path(binding["Profile"]))
    captures=[]
    for path in metadata_paths:
        path=Path(path).resolve();meta=read_json(path)
        if meta.get("calibration_scene_eligible") is False or meta.get("input_origin")=="ov5640_internal_pre_isp_test_pattern":
            raise ValueError("internal bars are not a real calibration-scene source")
        image_path=_file(path.parent,meta.get("image_path"),"native PNG")
        image=cv2.imdecode(np.fromfile(image_path,dtype=np.uint8),cv2.IMREAD_COLOR)
        if image is None:raise ValueError("native PNG cannot be decoded")
        view={"metadata_path":str(path),"metadata_sha256":sha(path),"sha256":sha(image_path)}
        record=_decode_bound_capture(view,profile,path.parent,image,image_path)
        if record["physical_capture_record"] is not True:
            raise ValueError("real branch requires source-bound physical native capture, not replay/synthetic")
        payload=Path(record["raw_path"]).read_bytes()
        captures.append({"record":record,"image_path":str(image_path),"image_sha256":sha(image_path),"payload":payload})
    if not captures:raise ValueError("one or more real --source-metadata files required")
    c=binding["IntegerConfig"];guard=binding["RadiusGuardQ22"]
    y,x=np.indices((480,640),dtype=np.int64);rs=lambda v,n:(v+(1<<(n-1)))>>n
    tables={bits:[np.array([round((v/((1<<bits)-1))**g*((1<<bits)-1)) for v in range(1<<bits)]) for g in (1,.65,1.45)] for bits in (5,6)}
    previous=next_mode=0;source_bytes=bytearray();out_bytes=bytearray();modes=[];crcs=[];rotations=[];frames=[]
    with (work/"masks.mem").open("x",encoding="ascii") as mask_file:
        for phase,angle in enumerate(range(0,360,30)):
            capture=captures[phase%len(captures)];source_bytes.extend(capture["payload"])
            raw=np.frombuffer(capture["payload"],dtype="<u2").reshape(480,640)
            rr=(raw>>11).astype(np.uint16);gg=((raw>>5)&63).astype(np.uint16);bb=(raw&31).astype(np.uint16)
            rgb=np.stack(((rr<<3)|(rr>>2),(gg<<2)|(gg>>4),(bb<<3)|(bb>>2)),axis=-1).astype(np.uint8)
            co,si=cordic(phase_from_degrees(angle));rotations.append(((co&0xffffffff)<<32)|(si&0xffffffff))
            u=rs(co*(x*256-81792)+si*(y*256-61312),30)+81792
            v=rs(-si*(x*256-81792)+co*(y*256-61312),30)+61312
            sx,sy,bad,r2=_fixed_project(u,v,c)
            for index in np.unique(np.linspace(0,307199,33).astype(int)):
                yy,xx=divmod(int(index),640);pu,pv,rb=inverse_rotate(xx*256,yy*256,81792,61312,co,si)
                px,py,pb=brown.project(pu,pv,c)
                if (px,py,bool(pb or rb))!=(int(sx[yy,xx]),int(sy[yy,xx]),bool(bad[yy,xx])):
                    raise ValueError("new-profile scalar/vector oracle disagreement")
            mask=bad|(r2>guard)|(sx<=-256)|(sy<=-256)|(sx>=640*256)|(sy>=480*256)
            mapped=remap_fixed(rgb,np.where(mask,-(1<<23),sx)/256,np.where(mask,-(1<<23),sy)/256).astype(np.uint16)
            p=((mapped[...,0]>>3)<<11)|((mapped[...,1]>>2)<<5)|(mapped[...,2]>>3)
            rr=(p>>11).astype(np.int64);gg=((p>>5)&63).astype(np.int64);bb=(p&31).astype(np.int64)
            luminance=(77*((rr<<3)|(rr>>2))+150*((gg<<2)|(gg>>4))+29*((bb<<3)|(bb>>2)))>>8
            mode=next_mode;modes.append(mode)
            toned=((tables[5][mode][rr]<<11)|(tables[6][mode][gg]<<5)|tables[5][mode][bb]).astype("<u2");toned[mask]=0
            samples=luminance[~mask];count=len(samples)
            decision=0 if count<307200//4 else 1 if int((samples<64).sum())>=(count+1)//2 else 2 if int((samples>=192).sum())>=(count+1)//2 else 0
            if decision==previous:next_mode=decision
            previous=decision;payload=toned.tobytes();out_bytes.extend(payload);crc=zlib.crc32(payload);crcs.append(crc)
            mask_file.write("".join("1\n" if bit else "0\n" for bit in mask.ravel()))
            frames.append({"angle_deg":angle,"gamma_mode":mode,"decision":decision,"masked_pixels":int(mask.sum()),
                           "pixels":307200,"crc32":f"{crc:08X}","source_metadata":capture["record"]["metadata_path"]})
    write_words(work/"source.mem",bytes(source_bytes));write_words(work/"result.mem",bytes(out_bytes))
    for name,values,digits in (("crcs.mem",crcs,8),("modes.mem",modes,1),("rotations.mem",rotations,16)):
        (work/name).write_text("".join(f"{v:0{digits}x}\n" for v in values),encoding="ascii")
    tb=(ROOT/NEW_TESTS[0]).read_text()
    for old,new in candidate.PARAMETER_MOVES.items():
        if tb.count("/"+old+'"')!=1:raise ValueError("native TB private-include insertion differs")
        tb=tb.replace("/"+old+'"',"/"+new+'"')
    (work/"tb_gamma_pipeline_profile.sv").write_text(tb,encoding="utf-8")
    records=[{**v["record"],"image_path":v["image_path"],"image_sha256":v["image_sha256"]} for v in captures]
    reference={"frames":frames,"pixels":3686400,"integer_config":c,"radius_q22":guard,"SourceCaptures":records,
               "scope":"Actual raw/PNG/metadata bound source, real profile, independent integer remap/interpolation/Gamma oracle. Reusing a source at multiple angles is not multiple calibration poses. Not measured optical acceptance or hardware fps."}
    (work/"gamma-reference.json").write_text(json.dumps(reference,indent=2)+"\n")
    return reference


def tool(bin_dir: Path, name: str, arguments: list[str], work: Path, deadline: float, stem: str) -> None:
    tokens = [str(bin_dir / name), *arguments]
    if not Path(tokens[0]).is_file() or any(re.search(r'["\r\n&|<>^%!]', t) for t in tokens):
        raise ValueError("Invalid fixed simulation tool/argument")
    comspec = os.environ.get("ComSpec", "cmd.exe")
    if re.search(r'["\r\n&|<>^%!]', comspec):
        raise ValueError("Invalid command interpreter path")
    line = '"'+comspec+'" /d /s /c "' + " ".join('"'+t+'"' for t in tokens) + '"'
    process = None
    with (work/(stem+"-stdout.log")).open("wb") as out, (work/(stem+"-stderr.log")).open("wb") as err:
        try:
            process = subprocess.Popen(line, cwd=work, stdout=out, stderr=err,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Whole offline simulation bound exhausted")
            code = process.wait(timeout=remaining)
            if code:
                raise RuntimeError(name+" failed, exit="+str(code)+"; see "+str(work/(stem+"-stdout.log")))
        finally:
            if process is not None and process.poll() is None:
                # Only this owned PID and its children; never search/kill PDS or other jobs.
                result = subprocess.run([str(Path(os.environ["SystemRoot"])/"System32/taskkill.exe"),
                                         "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=15)
                (work/(stem+"-owned-stop.log")).write_bytes(result.stdout+result.stderr)
                process.wait(timeout=15)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maximum-seconds", type=int, default=900)
    parser.add_argument("--profile-binding", type=Path)
    parser.add_argument("--source-metadata", type=Path, nargs="+")
    args = parser.parse_args()
    if not 60 <= args.maximum_seconds <= 1800 or not APPROVED.is_dir():
        parser.error("Need existing approved scratch and whole-run bound 60..1800 seconds")
    if bool(args.profile_binding)!=bool(args.source_metadata):
        parser.error("real branch requires both --profile-binding and --source-metadata")
    prepared = candidate.verify_clone(args.profile_binding)
    compile_names = compile_sources(prepared)
    baseline = verify_reference_manifest()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    work = APPROVED / ("gamma-pipeline-sim-"+stamp+"-"+uuid.uuid4().hex[:6])
    work.mkdir(exist_ok=False)
    suites = {name: work/name for name in ("native", "small", "video")}
    for directory in suites.values():
        directory.mkdir(exist_ok=False)
    watched = dict(prepared["SourceSHA256"])
    watched.update({name: sha(ROOT/name) for name in (*NEW_TESTS, *TOOLS)})
    report = {"Passed": False, "Target": candidate.TARGET, "HardwareAccessed": False, "PDSAccessed": False,
              "StartedUtc": datetime.now(timezone.utc).isoformat(), "OutputDirectory": str(work),
              "CacheLayout": prepared["CacheLayout"], "IntegrationContract": prepared["IntegrationContract"],
              "CompileSources": {name: watched[name] for name in compile_names}, "SourceSHA256": watched,
              "BaselineReference": baseline, "Suites": {},
              "Limits": "Historical parameter integration and synthetic-stall simulation only. No new lens K/D, optics, physical fps/temperature/resources, final timing, bitstream, or hardware acceptance. Existing baseline input/host/Gamma/ownership code retained; not guarded raw mode."}
    report_path = work/"gamma-pipeline-integration.json"
    if args.profile_binding:
        report["ProfileBinding"] = prepared["ProfileBinding"]
        report["Limits"] = "Real calibrated-profile same-source digital integration, not hardware/optical acceptance. Native goldens regenerated from bound actual raw/PNG/metadata; small/video fixtures remain explicitly synthetic control regressions."
    deadline = time.monotonic()+args.maximum_seconds
    try:
        report["HistoricalFixtures"] = {
            "small": copy_fixtures("build/gamma_frame_sim", suites["small"],
                                    ("config.vh", "source.mem", "result.mem", "rotations.mem", "crcs.mem", "modes.mem", "masks.mem"),
                                    "results/lab-20261007/gamma-frame-simulation-check.json"),
            "video": copy_fixtures("build/pipeline_hit_video_sim", suites["video"],
                                    ("source.mem", "result.mem", "rotations.mem", "crcs.mem", "phases.mem"),
                                    "results/lab-20261007/pipeline-hit-native-check.json"),
        }
        if args.profile_binding:
            report["NativeReference"] = real_native_oracle(suites["native"],prepared["ProfileBinding"],args.source_metadata)
        else:
            report["HistoricalFixtures"]["native"] = copy_fixtures("build/pipeline_parity_v2001_native_sim",suites["native"],
                ("source.mem","rotations.mem"),"results/lab-20261008/pipeline-parity-regression.json")
            historical=read_json(ROOT/"results/lab-20261008/pipeline-parity-regression.json")["source_sha256"]
            key="build/pipeline_parity_v2001_native_sim/result.mem"
            if historical.get(key,"").lower()!=sha(ROOT/key):raise ValueError("Historical native golden changed")
            report["HistoricalFixtures"]["native"]["Inputs"][key]=sha(ROOT/key)
            report["NativeReference"] = native_gamma_oracle(suites["native"])
        generated = {str(p.relative_to(work)): sha(p) for directory in suites.values() for p in directory.iterdir() if p.is_file()}
        report["FixtureSHA256"] = generated
        config_path = ROOT.parent/"team-config.local.json"
        config = read_json(config_path) if config_path.exists() else {}
        bin_dir = Path(os.environ.get("FPGA_VIVADO_BIN") or config.get("vivado_bin") or r"E:\Vivado\Vivado\2017.4\bin")
        tests = (("small", "tb_gamma_pipeline_small", NEW_TESTS[1], "PASS Gamma parity small regression:"),
                 ("video", "tb_ddr_gamma_pipeline_video", NEW_TESTS[2], "PASS Gamma parity DDR video:"),
                 ("native", "tb_gamma_pipeline_native", NEW_TESTS[0], "PASS Gamma parity twelve native regression:"))
        for name, top, tb, required in tests:
            directory = suites[name]
            compiled_tb = directory/"tb_gamma_pipeline_profile.sv" if name=="native" and args.profile_binding else ROOT/tb
            tool(bin_dir, "xvlog.bat", ["--sv", *[str(ROOT/p) for p in compile_names], str(compiled_tb)], directory, deadline, "compile")
            tool(bin_dir, "xelab.bat", [top, "-s", top], directory, deadline, "elaborate")
            tool(bin_dir, "xsim.bat", [top, "-runall", "-log", "simulation.log"], directory, deadline, "simulate")
            log = directory/"simulation.log"
            text = log.read_text(encoding="utf-8", errors="replace")
            if required not in text or re.search(r"(?im)^\s*(?:fatal|error):", text):
                raise ValueError("Missing suite success or simulation failure: "+name)
            report["Suites"][name] = {"Passed": True, "Top": top, "LogSHA256": sha(log)}
        rows = list(csv.DictReader((suites["native"]/"cycles.csv").open(newline="")))
        if len(rows) != 12 or any(int(row["phase"]) != i or int(row["pixels"]) != 307200 or
                                  row["crc32"].upper() != report["NativeReference"]["frames"][i]["crc32"]
                                  for i, row in enumerate(rows)):
            raise ValueError("Incomplete native frame CRC/order/count")
        report["NativeCycles"] = rows
        report["NativeCyclesSHA256"] = sha(suites["native"]/"cycles.csv")
        report["SourceSHA256After"] = {n: sha(ROOT/n) for n in watched}
        if report["SourceSHA256After"] != watched:
            raise ValueError("Integration input source changed during simulation")
        for name, digest in generated.items():
            if sha(work/name) != digest:
                raise ValueError("Fixture changed during simulation: "+name)
        if candidate.verify_clone(args.profile_binding)!=prepared:
            raise ValueError("prepared profile/identity/source binding changed during simulation")
        verify_reference_manifest()
        for record in report["NativeReference"].get("SourceCaptures",[]):
            for path_key,hash_key in (("metadata_path","metadata_sha256"),("raw_path","raw_sha256"),("image_path","image_sha256")):
                if sha(Path(record[path_key]))!=record[hash_key]:raise ValueError("actual native source changed during simulation")
        report["Passed"] = True
    except Exception as exc:
        report["Error"] = str(exc)
        print(str(exc), file=sys.stderr)
    finally:
        report["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
        print(str(report_path))
    return 0 if report["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
