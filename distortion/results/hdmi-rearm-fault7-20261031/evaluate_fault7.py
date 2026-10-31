"""Reproduce raw UART fault07 and the exact mapped one-hot fault decoder."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import struct
import sys
import zlib

ROOT=Path(__file__).resolve().parents[3]
DIST=ROOT/"distortion"
sys.path.insert(0,str(DIST/"tools"))
import audit_checked_io_netlist as n
OUT=Path(__file__).resolve().parent
REVIEW=DIST/"build/hdmi-uart-diagnostic/rearm-review-1031-a/final-functional-export"
NETLIST=REVIEW/"generate_netlist/hdmi_uart_rearm_diag_sim.v"
WIRE=DIST/"results/hdmi-rearm-live-20261031/live-status-c-after-confirmed-replug.raw.bin"
RECEIPT=WIRE.with_name("live-status-c-after-confirmed-replug.json")
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    proof=json.loads((REVIEW/"connectivity-review.json").read_text())
    assert proof["AuditPassed"] and proof["Target"]=="hdmi_uart_rearm_diag"
    assert proof["ScopedADFSHA256"]=="7ba58f239b6ee2054d728f1e6e74c123996bfbb2be5595b3a47c370e49c6dd85"
    assert proof["EvidenceSHA256"][str(NETLIST)]==sha(NETLIST)
    raw=NETLIST.read_text()
    cells,ports,drivers,libraries=n.parse(raw.replace("module hdmi_uart_rearm_diag","module board1080_top",1),n.LIBRARY)
    def expression(net,seen=()):
        c=n.constant(net)
        if c is not None:return ("constant",c)
        assert net not in seen
        if ports.get(net)=="input":return ("variable",net)
        matches=drivers[net];assert len(matches)==1,(net,matches)
        name,port=matches[0];cell=cells[name];ps=cell["Ports"];typ=cell["Type"];par=cell["Parameters"]
        child=lambda pin:expression(n.scalar(ps[pin]),seen+(net,))
        if typ in n.FFS:return ("variable",net)
        if typ in ("V_BUF","V_IBUF"):return child("I")
        if typ=="V_INV":return ("invert",child("I"))
        assert typ=="V_LUT6CARRY" and port in ("Z","Z5"),(name,typ,port)
        init=int(re.fullmatch(r"64'h([0-9a-fA-F_]+)",par["INIT"])[1].replace("_",""),16)
        inputs=[child("I"+str(i)) for i in range(5)]
        if port=="Z":inputs.append(child("I5" if par.get("I5_TO_LUT")=='"TRUE"' else "CIN"))
        return ("lut",init,inputs)
    def variables(e):
        if e[0]=="variable":return {e[1]}
        if e[0]=="constant":return set()
        if e[0]=="invert":return variables(e[1])
        return set.union(set(),*(variables(a) for a in e[2]))
    def evaluate(e,d):
        if e[0]=="constant":return e[1]
        if e[0]=="variable":return d[e[1]]
        if e[0]=="invert":return 1-evaluate(e[1],d)
        return (e[1]>>sum(evaluate(a,d)<<i for i,a in enumerate(e[2])))&1
    def qff(prefix,bit,trace=True):
        q=n.canonical("\\"+prefix+" ["+str(bit)+"]")
        matches=drivers[q];assert len(matches)==1
        name,port=matches[0];cell=cells[name];assert cell["Type"] in n.FFS
        return name,cell,expression(n.scalar(cell["Ports"]["D"])) if trace else None
    cones={bit-1:qff("input_status/geometry/held_snapshot",bit)[2] for bit in (1,2,3,5)}
    leaves=sorted(set.union(set(),*(variables(e) for e in cones.values())))
    state_bits=[n.canonical("\\input_status/geometry/source_fault_reg ["+str(k)+"]") for k in range(6)]
    assert leaves==sorted(state_bits)
    table=[]
    for state in range(64):
        values={name:(state>>k)&1 for k,name in enumerate(state_bits)}
        code=sum(evaluate(e,values)<<bit for bit,e in cones.items())
        table.append(dict(State=state,StateBits=format(state,"06b"),DecodedFault=code,DecodedFaultHex=f"0x{code:02x}",OneHot=state!=0 and state&(state-1)==0))
    assert [(r["State"],r["DecodedFault"]) for r in table if r["OneHot"]]==[(1,0),(2,17),(4,18),(8,19),(16,20),(32,21)]
    assert [r["State"] for r in table if r["DecodedFault"]==7]==[0]
    wire=WIRE.read_bytes();assert len(wire)==1280
    receipt=json.loads(RECEIPT.read_text());packets=[]
    for start in range(0,len(wire),64):
        packet=wire[start:start+64]
        assert packet[:8]==b"PGHDMI01" and packet[60:]==b"HM01"
        assert zlib.crc32(packet[:56])==struct.unpack_from("<I",packet,56)[0]
        assert struct.unpack_from("<I",packet,48)[0]==0x48444903
        row=dict(Sequence=struct.unpack_from("<I",packet,8)[0],RawFaultByte=packet[19],CRCValid=True)
        assert row["RawFaultByte"]==7 and receipt["frames"][len(packets)]["input_fault"]==7
        packets.append(row)
    fault_registers=[]
    for bit in range(6):
        name,cell,_=qff("input_status/geometry/source_fault_reg",bit,trace=False)
        fault_registers.append(dict(StateBit=bit,Name=name,Primitive=cell["Type"],Parameters=cell["Parameters"],Ports=cell["Ports"]))
    report=dict(Schema="hdmi-rearm-fault7-netlist-review-v1",Passed=True,CreatedUTC=datetime.now(timezone.utc).isoformat(),
        ScopedADFSHA256=proof["ScopedADFSHA256"],NetlistSHA256=sha(NETLIST),RawUARTSHA256=sha(WIRE),ReceiptSHA256=sha(RECEIPT),
        EvaluatorSHA256=sha(__file__),FinalProofSHA256=sha(REVIEW/"connectivity-review.json"),LibrarySHA256=libraries,
        RawPackets=packets,All64States=table,Decoded07States=[0],SourceFaultRegisters=fault_registers,
        HeldSnapshotDecodeCones=cones,DecoderLeaves=leaves,
        Interpretation="Raw byte19=07 in20 CRC-valid V3 packets. The exact mapped one-hot decoder produces07 only for illegal all-zero state000000; it is not a defined RTL fault code. This establishes decoder behavior, not the physical fault location. It does not distinguish persistent source-state corruption from invalid held-bus sampling without further observation.",
        HardwareAccessed=False,EDAExecuted=False,SourceModified=False,
        Limits="Static native primitive truth table plus independent struct/zlib UART verification. No clock waveform measurement or proof of the physical mechanism that produced the illegal code.")
    with (OUT/"review.json").open("x",encoding="utf-8",newline="\n") as f:json.dump(report,f,indent=2);f.write("\n")
    print(json.dumps(dict(Passed=True,RawPackets=len(packets),TruthTableRows=len(table),Decoded07States=[0],Output=str(OUT/"review.json"))))

if __name__=="__main__":main()
