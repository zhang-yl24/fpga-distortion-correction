"""Preserve the independent power-cycle/replug V3 trial without editing history."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil
import struct
import zlib

ROOT=Path(r"D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction")
VIS=Path(__file__).resolve().parent
LIVE=ROOT/"distortion/results/hdmi-interval-live-20261030"
PROGRAM=ROOT/"distortion/build/offline-20261024/hdmi-interval-program-1030-b"
DEST=ROOT/"distortion/results/hdmi-interval-restart-20261031"
SUMMARY=DEST.with_suffix(".json")
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text(encoding="utf-8-sig"))

def save(path,value):
    with path.open("x",encoding="utf-8",newline="\n") as f:
        json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write("\n")

def decode(stem):
    wire=LIVE/(stem+".raw.bin");receipt=load(LIVE/(stem+".json"))
    data=wire.read_bytes();assert len(data)%64==0
    rows=[]
    for offset in range(0,len(data),64):
        p=data[offset:offset+64]
        assert p[:8]==b"PGHDMI01" and p[60:]==b"HM01"
        assert zlib.crc32(p[:56])==struct.unpack_from("<I",p,56)[0]
        assert struct.unpack_from("<I",p,48)[0]==0x48444903
        row=dict(sequence=struct.unpack_from("<I",p,8)[0],reference_ticks=struct.unpack_from("<I",p,12)[0],
            flags=struct.unpack_from("<H",p,16)[0],cfg_error=p[18],input_fault=p[19],
            width=struct.unpack_from("<H",p,20)[0],height=struct.unpack_from("<H",p,22)[0],
            pclk_edges=struct.unpack_from("<I",p,24)[0],good_frames=struct.unpack_from("<I",p,28)[0],
            bad_frames=struct.unpack_from("<I",p,32)[0],completed_transactions=struct.unpack_from("<I",p,40)[0],
            monitor_freshness_mask=p[52],vs_edge_count_ref=struct.unpack_from("<H",p,53)[0])
        assert all(receipt["frames"][len(rows)][k]==v for k,v in row.items())
        rows.append(row)
    assert receipt["accepted_packets"]==len(rows) and receipt["rejected_packets"]==0 and receipt["wire_sha256"]==sha(wire)
    for a,b in zip(rows,rows[1:]):
        assert (b["sequence"]-a["sequence"])&0xffffffff==1
        assert (b["reference_ticks"]-a["reference_ticks"])&0xffffffff==13500000
    return dict(IndependentParsePassed=True,Packets=len(rows),First=rows[0],Last=rows[-1],
        VSModuloIncrements=[(b["vs_edge_count_ref"]-a["vs_edge_count_ref"])&0xffff for a,b in zip(rows,rows[1:])],
        PCLKEdgesRange=[min(r["pclk_edges"] for r in rows),max(r["pclk_edges"] for r in rows)],
        ReferenceSeconds=((rows[-1]["reference_ticks"]-rows[0]["reference_ticks"])&0xffffffff)/27000000,
        WireSHA256=sha(wire),Rows=rows)

def main():
    assert not DEST.exists() and not SUMMARY.exists()
    program=load(PROGRAM/"receipt.json")
    assert program["Passed"] and program["DoneConfirmed"] and not program["FlashWritten"] and not program["CleanupErrors"]
    captures={key:decode(stem) for key,stem in (
        ("AfterPowerCycle","live-status-b-after-power-cycle"),
        ("AfterReplug","live-status-c-after-power-cycle-replug"),
        ("Stability","live-status-d-source-stability"))}
    windows=load(VIS/"windows-display-restart-20261031-a.json")
    hdmi=[p for p in windows["ActiveDisplayConfig"]["paths"] if p["outputTechnology"]==5]
    assert len(hdmi)==1
    hdmi_only=dict(Schema="windows-hdmi-target-extract-v1",SourceSHA256=sha(VIS/"windows-display-restart-20261031-a.json"),
        StartedUTC=windows["StartedUTC"],EndedUTC=windows["EndedUTC"],ReadOnly=True,DisplaySettingsChanged=False,
        Target={key:hdmi[0][key] for key in ("friendlyName","outputTechnology","pathActive","pathRefreshHz","targetSignal")})
    DEST.mkdir()
    for path in sorted(PROGRAM.iterdir()):
        if path.is_file():
            target=DEST/"program"/path.name;target.parent.mkdir(exist_ok=True)
            shutil.copyfile(path,target);assert sha(path)==sha(target)
    for stem in ("live-status-b-after-power-cycle","live-status-c-after-power-cycle-replug","live-status-d-source-stability",
                 "assessment-b-after-power-cycle","assessment-c-after-power-cycle-replug","assessment-d-source-stability"):
        for suffix in (".json",".raw.bin"):
            source=LIVE/(stem+suffix)
            if source.exists():shutil.copyfile(source,DEST/source.name)
    save(DEST/"independent-windows.json",captures)
    save(DEST/"windows-hdmi-target.json",hdmi_only)
    save(DEST/"user-observations.json",dict(Source="Explicit user messages",BoardPowerCycled=True,
        ReplugConfirmedAfterSRAMReload=True,SourceConnection="Computer HDMI port directly to FPGA HDMI IN"))
    shutil.copyfile(VIS/"restart_interval_after_power_cycle.py",DEST/"restart_interval_after_power_cycle.py")
    shutil.copyfile(Path(__file__),DEST/Path(__file__).name)
    files=[dict(File=p.relative_to(DEST).as_posix(),Bytes=p.stat().st_size,SHA256=sha(p)) for p in sorted(DEST.rglob("*")) if p.is_file()]
    save(DEST/"manifest.json",dict(Schema="hdmi-interval-restart-evidence-v1",CreatedUTC=datetime.now(timezone.utc).isoformat(),
        Files=files,FileCount=len(files),RawEvidenceUnmodified=True,HardwareAccessed=True))
    summary=dict(Schema="hdmi-interval-restart-progress-v1",CreatedUTC=datetime.now(timezone.utc).isoformat(),
        Target=program["Target"],BitstreamSHA256=program["Bitstream"]["SHA256"],SRAMProgrammed=True,DoneConfirmed=True,FlashWritten=False,
        ProgrammingStartedUTC=program["StartedUTC"],ProgrammingEndedUTC=program["EndedUTC"],
        WindowsConfiguredHDMITarget=hdmi_only["Target"],DirectHDMIConnectionConfirmed=True,
        Captures={key:{k:v for k,v in report.items() if k!="Rows"} for key,report in captures.items()},
        Observations="After reload VS=0 with nominal PCLK; after replug VS reaches43 and bad42 then both freeze; PCLK rises to~88MHz while Windows still configures74.25MHz. Source config is not a measurement of receiver lock or output.",
        QualifiedInputWindow=False,InputPixelPayloadVerified=False,HardwareReleaseAllowed=False,
        EvidenceManifestSHA256=sha(DEST/"manifest.json"),EvidenceFiles=len(files))
    save(SUMMARY,summary)
    assert all(sha(DEST/row["File"])==row["SHA256"] for row in files)
    print(json.dumps(dict(Passed=True,Files=len(files),Summary=str(SUMMARY),WindowsHz=hdmi[0]["targetSignal"]["pixelRateHz"],
        Captures={k:dict(Packets=v["Packets"],VSFirst=v["First"]["vs_edge_count_ref"],VSLast=v["Last"]["vs_edge_count_ref"],PCLKEdgesRange=v["PCLKEdgesRange"]) for k,v in captures.items()})))

if __name__=="__main__":main()
