from pathlib import Path
import argparse,hashlib,json
p=argparse.ArgumentParser(description="Create a guarded UTF-8/LF four-file patch base from a legal cf9 native source copy; never modify that source.")
p.add_argument("--source-root",type=Path,required=True)
p.add_argument("--output",type=Path,required=True)
a=p.parse_args()
identity=json.loads((Path(__file__).resolve().parents[1]/"SOURCE_DELTA_IDENTITY.json").read_text(encoding="utf-8"))
src=a.source_root.resolve();out=a.output.resolve()
assert src.is_dir(),"source root missing"
assert not out.exists(),"output must be new; inspect an existing output instead of overwriting it"
assert not out.is_relative_to(src),"output must be outside source root"
prepared=[]
for f in identity["changed_files"]:
    rel=Path(f["relative_path"]);assert not rel.is_absolute() and ".." not in rel.parts
    b=(src/rel).read_bytes()
    assert hashlib.sha256(b).hexdigest()==f["original_sha256"],str(rel)+": original SHA mismatch"
    normalized=b.decode(f["original_encoding"]).replace("\r\n","\n").replace("\r","\n").encode("utf-8")
    assert hashlib.sha256(normalized).hexdigest()==f["patch_base_sha256"],str(rel)+": normalized SHA mismatch"
    prepared.append((rel,normalized))
for rel,b in prepared:
    target=out/"native"/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b)
print("PASS_GUARDED_PATCH_BASE",len(prepared),"source unchanged; apply PHASE_CONTRACT_UTF8.patch to this new output")
