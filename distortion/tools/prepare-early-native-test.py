from pathlib import Path
import zlib
root=Path(__file__).resolve().parents[1];work=root/'build/early_native_sim';work.mkdir(parents=True,exist_ok=True)
raw=(root/'captures/corrected-pairs/20261006-155846/pair00000004/raw-source.rgb565').read_bytes()
assert len(raw)==640*480*2
(work/'source.mem').write_text(''.join(f'{int.from_bytes(raw[i:i+32],"little"):064x}\n' for i in range(0,len(raw),32)))
(work/'checksum.vh').write_text(f"localparam [31:0] EXPECTED_CRC=32'h{zlib.crc32(raw):08x};\n")
print('Prepared actual 640x480 camera source and independent zlib CRC.')
