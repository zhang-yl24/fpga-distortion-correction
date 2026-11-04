from pathlib import Path
import argparse, datetime as dt, hashlib, json, time
from decode_runtime_diag import decode

def main():
    a=argparse.ArgumentParser(description="Passive PGIQ0001 receiver. Start before SRAM programming; this tool never programs the board or transmits UART bytes.")
    a.add_argument("--port",required=True)
    a.add_argument("--seconds",type=float,default=100)
    a.add_argument("--outdir",type=Path,required=True)
    a.add_argument("--bit-sha256",required=True)
    a.add_argument("--source",choices=("pc","camera","unknown"),default="unknown")
    x=a.parse_args()
    if not (0<x.seconds<=180):a.error("seconds must be in (0,180]")
    bit=x.bit_sha256.lower()
    if len(bit)!=64 or any(c not in "0123456789abcdef" for c in bit):a.error("invalid declared bit SHA256")
    out=x.outdir.resolve()
    if out.exists():a.error("output directory already exists; preserve prior evidence")
    out.mkdir(parents=True)
    st={"state":"OPENING_PORT","started":dt.datetime.now().astimezone().isoformat(),"port":x.port,"baud":115200,"source_declared":x.source,"bit_sha256_declared":bit,"bit_load_verified_by_this_tool":False,"requested_seconds":x.seconds,"tx_bytes":0,"DTR":False,"RTS":False,"raw_file":"uart.raw.bin","board_60fps_proven":False}
    def save():
        tmp=out/"capture.json.tmp";tmp.write_text(json.dumps(st,indent=2)+"\n",encoding="utf-8");tmp.replace(out/"capture.json")
    raw=bytearray();port=None;save();code=0
    try:
        import serial
        port=serial.Serial(port=None,baudrate=115200,timeout=.1,write_timeout=1,xonxoff=False,rtscts=False,dsrdtr=False)
        port.dtr=False;port.rts=False;port.port=x.port
        start=time.monotonic();port.open();st["state"]="CAPTURING_RX_ONLY";st["opened"]=dt.datetime.now().astimezone().isoformat();save()
        due=start+x.seconds
        with (out/"uart.raw.bin").open("xb") as f:
            while time.monotonic()<due:
                b=port.read(4096)
                if b:
                    if len(raw)+len(b)>4*1024*1024:raise RuntimeError("4MiB receive budget exceeded")
                    raw.extend(b);f.write(b);f.flush()
        st["elapsed_seconds"]=time.monotonic()-start
    except BaseException as exc:
        st["error"]=repr(exc);code=2
    finally:
        if port is not None:port.close()
        st["port_closed"]=(port is None or not port.is_open)
        if not (out/"uart.raw.bin").exists():(out/"uart.raw.bin").write_bytes(raw)
        result=decode(bytes(raw));(out/"decoded.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        st.update(raw_bytes=len(raw),raw_sha256=hashlib.sha256(raw).hexdigest(),valid_packets=len(result["packets"]),decode_errors=result["errors"],finished=dt.datetime.now().astimezone().isoformat())
        st["state"]="CAPTURE_ERROR" if code else "CAPTURED_WITH_DECODE_ERRORS" if result["errors"] else "CAPTURED"
        if not result["packets"]:code=2
        save()
    print(json.dumps({k:st.get(k)for k in ("state","raw_bytes","raw_sha256","valid_packets","decode_errors","port_closed","error")}))
    return code

if __name__=="__main__":raise SystemExit(main())
