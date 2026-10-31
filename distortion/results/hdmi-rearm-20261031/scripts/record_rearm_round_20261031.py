"""Seal rearm simulations, native implementation, SRAM event and raw captures."""
from datetime import datetime,timezone
from pathlib import Path
import gzip
import hashlib
import json
import struct
import zlib

ROOT=Path(r"D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction")
DIST=ROOT/"distortion";BASE=DIST/"build/hdmi-uart-diagnostic";VIS=Path(__file__).resolve().parent
SOURCE=BASE/"trained-pds-rearm-1031-a";REVIEW=BASE/"rearm-review-1031-a";BIT=BASE/"rearm-bit-1031-a"
PROGRAM=DIST/"build/offline-20261024/hdmi-rearm-program-1031-a";LIVE=DIST/"results/hdmi-rearm-live-20261031"
DEST=DIST/"results/hdmi-rearm-20261031";SUMMARY=DEST.with_suffix(".json")
digest=lambda data:hashlib.sha256(data).hexdigest()
sha=lambda path:digest(Path(path).read_bytes())
load=lambda path:json.loads(Path(path).read_text(encoding="utf-8-sig"))

def save(path,value):
    with path.open("x",encoding="utf-8",newline="\n") as f:
        json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write("\n")

def independent(path):
    receipt=load(path);wire=path.with_suffix(".raw.bin");data=wire.read_bytes()
    assert len(data)%64==0 and receipt["accepted_packets"]==len(data)//64 and receipt["rejected_packets"]==0
    rows=[]
    for i in range(0,len(data),64):
        p=data[i:i+64]
        assert p[:8]==b"PGHDMI01" and p[60:]==b"HM01" and zlib.crc32(p[:56])==struct.unpack_from("<I",p,56)[0]
        assert struct.unpack_from("<I",p,48)[0]==0x48444903 and p[52]&0xe0==0 and p[55]==0
        r=dict(sequence=struct.unpack_from("<I",p,8)[0],reference_ticks=struct.unpack_from("<I",p,12)[0],
            flags=struct.unpack_from("<H",p,16)[0],cfg_error=p[18],input_fault=p[19],width=struct.unpack_from("<H",p,20)[0],
            height=struct.unpack_from("<H",p,22)[0],pclk_edges=struct.unpack_from("<I",p,24)[0],
            good_frames=struct.unpack_from("<I",p,28)[0],bad_frames=struct.unpack_from("<I",p,32)[0],
            monitor_freshness_mask=p[52],vs_edge_count_ref=struct.unpack_from("<H",p,53)[0],
            last_address=struct.unpack_from("<H",p,44)[0],last_value=p[46])
        assert all(receipt["frames"][len(rows)][k]==v for k,v in r.items());rows.append(r)
    for a,b in zip(rows,rows[1:]):
        assert ((b["sequence"]-a["sequence"])&0xffffffff)==1
        assert ((b["reference_ticks"]-a["reference_ticks"])&0xffffffff)==13500000
    return dict(Passed=True,Packets=len(rows),WireSHA256=sha(wire),Rows=rows,First=rows[0],Last=rows[-1],
        PCLKEdgesRange=[min(r["pclk_edges"] for r in rows),max(r["pclk_edges"] for r in rows)],
        VSModuloIncrements=[(b["vs_edge_count_ref"]-a["vs_edge_count_ref"])&0xffff for a,b in zip(rows,rows[1:])],
        Status209EValues=sorted({r["last_value"] for r in rows if r["last_address"]==0x209e}))

def main():
    assert not DEST.exists() and not SUMMARY.exists()
    build=load(SOURCE/"build-plan.json");execution=load(SOURCE/"execution.json")
    scope=load(REVIEW/"scoped-cdc/scoped-cdc-review.json");final=load(REVIEW/"final-functional-export/connectivity-review.json")
    export=load(BIT/"export-result.json");program=load(PROGRAM/"receipt.json")
    ab=load(BASE/"ready-reentry-ab-1031-a/simulation-result.json");wire=load(BASE/"ready-reentry-wire-1031-b/simulation-result.json")
    assert execution["Passed"] and not execution["SourceDrift"] and export["Passed"] and scope["AuditPassed"] and final["AuditPassed"]
    assert program["Passed"] and program["DoneConfirmed"] and not program["FlashWritten"] and not program["CleanupErrors"]
    assert ab["Passed"] and not ab["SourceDrift"] and wire["Passed"] and not wire["SourceDrift"]
    assert all(sha(DIST/name)==h for name,h in build["InputSHA256"].items())
    assert all(sha(SOURCE/name)==h for name,h in build["FrozenInputSHA256"].items())
    captures={p.name:independent(p) for p in sorted(LIVE.glob("live-status-*.json"))}
    DEST.mkdir();files=[]
    def preserve(path,prefix):
        raw=path.read_bytes();compressed=path.suffix in (".adf",".rtr",".netlist",".sbit") or len(raw)>120000
        rel=prefix+(".gz" if compressed else "");stored=gzip.compress(raw,mtime=0) if compressed else raw
        target=DEST/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(stored)
        files.append(dict(File=rel,Encoding="gzip" if compressed else "identity",Bytes=len(stored),SHA256=digest(stored),
            Source=str(path),SourceBytes=len(raw),SourceSHA256=digest(raw)))
    suffixes={".py",".v",".sv",".json",".tcl",".fdc",".log",".prt",".rtr",".adf",".netlist",".bin",".sbit",".bgr",".csv",".hex"}
    for base,prefix in ((SOURCE,"source-build"),(REVIEW,"review"),(BIT,"bit-export"),(PROGRAM,"program"),(LIVE,"live"),
            (BASE/"ready-reentry-ab-1031-a","ab-simulation"),(BASE/"ready-reentry-wire-1031-a","wire-failed-bound"),
            (BASE/"ready-reentry-wire-1031-b","wire-simulation")):
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in suffixes and not any(n in p.parts for n in ("xsim.dir","__pycache__","logbackup")):
                preserve(p,prefix+"/"+p.relative_to(base).as_posix())
    for p in (VIS/"program_rearm.py",VIS/"run_rearm_bitstream.py",VIS/"run_rearm_program_live.py",Path(__file__),
            DIST/"tools/run_ms7200_ready_reentry_sim.py",DIST/"tools/run_ms72xx_rearm_wire_sim.py",
            DIST/"tests/tb_ms7200_ready_reentry.sv",DIST/"tests/tb_ms72xx_rearm_observed_e2e.sv",
            DIST/"tools/hdmi_status.py",DIST/"tools/assess_hdmi_input.py"):
        preserve(p,"scripts/"+p.name)
    save(DEST/"independent-captures.json",captures)
    files.append(dict(File="independent-captures.json",Encoding="identity",Bytes=(DEST/"independent-captures.json").stat().st_size,
        SHA256=sha(DEST/"independent-captures.json"),SourceSHA256=sha(DEST/"independent-captures.json")))
    save(DEST/"manifest.json",dict(Schema="hdmi-rearm-native-live-evidence-v1",CreatedUTC=datetime.now(timezone.utc).isoformat(),
        Files=files,FileCount=len(files),RawUARTUnmodified=True,HardwareAccessed=True))
    summary=dict(Schema="hdmi-rearm-progress-v1",CreatedUTC=datetime.now(timezone.utc).isoformat(),Target="hdmi_uart_rearm_diag",
        Bitstream=export["Bitstream"],SourceADFSHA256=final["OriginalADFSHA256"],ScopedADFSHA256=export["ADF_SHA256"],
        WorstSlackNS=scope["WorstSlackNS"],CellCount=final["CellCount"],VerifiedFFs=161,StageLinks=81,Pins=46,
        ABPassed=True,ABSummary=ab.get("Summary"),ABTransactionModelStub=True,
        WirePassed=True,WireTransactions=wire["WireTransactions"],SuccessfulTelemetryCompared=wire["SuccessfulTelemetryCompared"],
        NACKsSuppressed=wire["NACKsSuppressed"],ReentryTransactions=wire["ReentryScenarioTransactions"],
        SRAMProgrammed=True,DoneConfirmed=True,FlashWritten=False,ProgrammingStartedUTC=program["StartedUTC"],ProgrammingEndedUTC=program["EndedUTC"],
        Captures={n:{k:v for k,v in c.items() if k!="Rows"} for n,c in captures.items()},
        ImportantFindings=["Reentry branch fixed in isolation; all register/EDID values unchanged.",
            "30-second capture completed before user-confirmed replug and is not evidence of the replug transition.",
            "Confirmed-replug capture has VS1135 and bad1134 frozen, good0,1920x25,nominal74.249MHz PCLK.",
            "Raw byte19=07 is CRC-valid but not a defined source-monitor fault value; exact fault-path review pending. Do not decode07 as a known error category."],
        QualifiedInputWindow=False,InputPixelPayloadVerified=False,DDRAndDistortionVerified=False,HardwareReleaseAllowed=False,
        EvidenceManifestSHA256=sha(DEST/"manifest.json"),EvidenceFiles=len(files))
    save(SUMMARY,summary)
    for row in files:
        data=(DEST/row["File"]).read_bytes();assert digest(data)==row["SHA256"]
        raw=gzip.decompress(data) if row["Encoding"]=="gzip" else data;assert digest(raw)==row["SourceSHA256"]
    print(json.dumps(dict(Passed=True,Files=len(files),Summary=str(SUMMARY),WireTransactions=wire["WireTransactions"],
        Captures={n:dict(Packets=c["Packets"],VSFirst=c["First"]["vs_edge_count_ref"],VSLast=c["Last"]["vs_edge_count_ref"],
            Faults=sorted({r["input_fault"] for r in c["Rows"]})) for n,c in captures.items()})))

if __name__=="__main__":main()
