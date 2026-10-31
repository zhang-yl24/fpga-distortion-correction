"""Preserve the new V3 implementation, exact download and raw counter window."""
from datetime import datetime, timezone
from pathlib import Path
import gzip
import hashlib
import json
import struct
import zlib

ROOT=Path(r"D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion")
VIS=Path(__file__).resolve().parent
BASE=ROOT/"build/hdmi-uart-diagnostic"
SOURCE=BASE/"trained-pds-interval-1030-a"
REVIEW=BASE/"interval-review-1030-a"
BIT=BASE/"interval-bit-1030-a"
PROGRAM=ROOT/"build/offline-20261024/hdmi-interval-program-1030-a"
LIVE=ROOT/"results/hdmi-interval-live-20261030"
DEST=ROOT/"results/hdmi-interval-20261030"
SUMMARY=ROOT/"results/hdmi-interval-20261030.json"
sha=lambda data:hashlib.sha256(data).hexdigest()
load=lambda path:json.loads(Path(path).read_text(encoding="utf-8-sig"))

def write(path,value):
    with path.open("x",encoding="utf-8",newline="\n") as f:
        json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False)
        f.write("\n")

def main():
    assert not DEST.exists() and not SUMMARY.exists()
    build=load(SOURCE/"build-plan.json")
    export=load(BIT/"export-result.json")
    program=load(PROGRAM/"receipt.json")
    assess=load(LIVE/"assessment-a.json")
    capture=load(LIVE/"live-status-a.json")
    assert export["Passed"] and program["Passed"] and program["DoneConfirmed"]
    assert not program["FlashWritten"] and program["CleanupErrors"]==[]
    assert all(sha((ROOT/name).read_bytes())==wanted for name,wanted in build["InputSHA256"].items())
    assert all(sha((SOURCE/name).read_bytes())==wanted for name,wanted in build["FrozenInputSHA256"].items())
    raw=(LIVE/"live-status-a.raw.bin").read_bytes()
    assert len(raw)==1280 and capture["accepted_packets"]==20 and capture["rejected_packets"]==0
    rows=[]
    for offset in range(0,len(raw),64):
        p=raw[offset:offset+64]
        assert p[:8]==b"PGHDMI01" and p[60:]==b"HM01"
        assert zlib.crc32(p[:56])==struct.unpack_from("<I",p,56)[0]
        assert struct.unpack_from("<I",p,48)[0]==0x48444903 and p[52]&0xe0==0 and p[55]==0
        row=dict(sequence=struct.unpack_from("<I",p,8)[0],reference_ticks=struct.unpack_from("<I",p,12)[0],
                 vs_edge_count_ref=struct.unpack_from("<H",p,53)[0],monitor_freshness_mask=p[52],input_fault=p[19],
                 width=struct.unpack_from("<H",p,20)[0],height=struct.unpack_from("<H",p,22)[0],
                 good_frames=struct.unpack_from("<I",p,28)[0],bad_frames=struct.unpack_from("<I",p,32)[0])
        assert all(capture["frames"][len(rows)][k]==v for k,v in row.items())
        rows.append(row)
    increments=[(b["vs_edge_count_ref"]-a["vs_edge_count_ref"])&0xffff for a,b in zip(rows,rows[1:])]
    assert all(((b["sequence"]-a["sequence"])&0xffffffff)==1 and ((b["reference_ticks"]-a["reference_ticks"])&0xffffffff)==13500000 for a,b in zip(rows,rows[1:]))
    independent=dict(Passed=True,Packets=len(rows),Rows=rows,VSModuloIncrements=increments,
                     Interpretation="Synchronized normalized VS counter is zero at all twenty reports, with PCLK/DE/snapshot fresh. No VS rising edge has been counted since this observer epoch. A 16-bit modulo counter cannot exclude aliasing by exact multiples of 65536 events; such activity would not be admitted 1080p30 timing.",
                     WireSHA256=sha(raw),ReferenceSpanSeconds=9.5,HardwareReleaseAllowed=False)
    write(LIVE/"independent-a.json",independent)
    DEST.mkdir()
    files=[]
    extensions={".py",".v",".sv",".json",".tcl",".fdc",".log",".prt",".rtr",".adf",".netlist",".bin",".sbit",".bgr",".csv"}
    for base,prefix in ((SOURCE,"source-build"),(REVIEW,"review"),(BIT,"bit-export"),(PROGRAM,"program"),(LIVE,"live"),(BASE/"interval-uart-sim-1030-a","uart-simulation")):
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix not in extensions or any(s in path.parts for s in ("__pycache__","xsim.dir","logbackup")):
                continue
            data=path.read_bytes()
            zipped=path.suffix in (".adf",".rtr",".netlist",".sbit") or len(data)>120000
            rel=prefix+"/"+path.relative_to(base).as_posix()+(".gz" if zipped else "")
            dest=DEST/rel
            dest.parent.mkdir(parents=True,exist_ok=True)
            stored=gzip.compress(data,mtime=0) if zipped else data
            dest.write_bytes(stored)
            files.append(dict(File=rel,Encoding="gzip" if zipped else "identity",Bytes=len(stored),SHA256=sha(stored),Source=str(path),SourceBytes=len(data),SourceSHA256=sha(data)))
    for path in (VIS/"run_interval_bitstream.py",VIS/"program_interval.py",Path(__file__),
                 ROOT/"tools/hdmi_status.py",ROOT/"tools/assess_hdmi_input.py",ROOT/"tools/run_hdmi_uart_sim.py",
                 ROOT/"tests/test_hdmi_status.py",ROOT/"tests/test_assess_hdmi_input.py"):
        data=path.read_bytes();rel="scripts/"+path.name
        dest=DEST/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        files.append(dict(File=rel,Encoding="identity",Bytes=len(data),SHA256=sha(data),Source=str(path),SourceBytes=len(data),SourceSHA256=sha(data)))
    write(DEST/"manifest.json",dict(Schema="hdmi-interval-native-live-evidence-v1",Files=files,FileCount=len(files),CreatedUTC=datetime.now(timezone.utc).isoformat(),RawEvidencePreserved=True))
    scope=load(REVIEW/"scoped-cdc/scoped-cdc-review.json")
    final=load(REVIEW/"final-functional-export/connectivity-review.json")
    summary=dict(Schema="hdmi-interval-progress-v1",Target="hdmi_uart_interval_diag",CreatedUTC=datetime.now(timezone.utc).isoformat(),
        SourceBuildPassed=True,NativeSTAAndMappingPassed=True,ScopedADFSHA256=export["ADF_SHA256"],Bitstream=export["Bitstream"],
        SRAMProgrammed=True,DoneConfirmed=True,FlashWritten=False,CPUProtocolChecksPassed=150,UARTV3WireSimulationPassed=True,
        WorstSlackNS=scope["WorstSlackNS"],VerifiedSynchronizerFFs=161,StageLinks=81,Pins=46,CellCount=final["CellCount"],
        CapturedPackets=20,CRCRejected=0,VSFirst=rows[0]["vs_edge_count_ref"],VSLast=rows[-1]["vs_edge_count_ref"],VSModuloIncrements=increments,
        FreshnessMasks=sorted({hex(row["monitor_freshness_mask"]) for row in rows}),Faults=sorted({hex(row["input_fault"]) for row in rows}),
        QualifiedInputWindow=assess["passed"],EvidenceManifestSHA256=sha((DEST/"manifest.json").read_bytes()),EvidenceFiles=len(files),
        NextAction="Keep board powered; user requested to replug HDMI IN, then capture V3 cumulative VS count while preserving UART connection.",
        InputPixelPayloadVerified=False,DDRAndDistortionVerified=False,HardwareReleaseAllowed=False,
        Limits="Digital timing only. Count is observed after polarity training in the existing monitor enable epoch, not a separate raw-pin sampler. No external AC/complete CDC/PHY lock/pixels/stability acceptance.")
    write(SUMMARY,summary)
    for row in files:
        data=(DEST/row["File"]).read_bytes()
        assert sha(data)==row["SHA256"]
        source=gzip.decompress(data) if row["Encoding"]=="gzip" else data
        assert sha(source)==row["SourceSHA256"]
    print(json.dumps(dict(Passed=True,Files=len(files),Summary=str(SUMMARY),VSIncrements=increments,InputPassed=assess["passed"])))

if __name__=="__main__":main()
