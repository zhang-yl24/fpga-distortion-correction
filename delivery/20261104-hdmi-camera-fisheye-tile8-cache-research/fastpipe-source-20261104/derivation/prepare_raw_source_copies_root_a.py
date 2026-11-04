"""Copy only the pinned cache and engine into the independent raw namespace."""
import hashlib
import importlib.util
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
TARGET=ROOT/'distortion/work/hdmi-camera-fisheye-assoc2way256-fastpipe-20261104-a/source'
ROWS=((HERE/'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_fastpipe_a.v',
    'c769fa5b352794c83e655c44a1a295f79c71e43f475b43274158671e4e92e888'),
    (HERE.parent/'assoc2way256-fifo-a/rtl/hdmi_camera_fisheye_engine_index10_fifo_a.v',
    'd17d5659a8818427d55951d8b0e5807dd21bc9da1ca9d903a56e53f65977804e'))

def main():
    assert TARGET.resolve().is_relative_to(ROOT.resolve())
    generator=HERE/'make_fastpipe_cache_a.py'
    spec=importlib.util.spec_from_file_location('fastpipe_source_replay',generator)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.derive()==ROWS[0][0].read_bytes()
    TARGET.mkdir(parents=True,exist_ok=True)
    for source,pin in ROWS:
        data=source.read_bytes()
        assert hashlib.sha256(data).hexdigest()==pin
        target=TARGET/source.name
        if target.exists():assert target.read_bytes()==data
        else:
            with target.open('xb') as stream:stream.write(data)
        print(source.name+' '+pin)

if __name__=='__main__':main()
