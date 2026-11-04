"""Assemble source, reproducible dependencies and evidence into a verified ZIP."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, sys, zipfile
from export_standalone import export
from prepare_candidate import HERE, REPO, BASELINE


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package(prepared, stage, archive):
    prepared,stage,archive=map(lambda p:Path(p).resolve(),(prepared,stage,archive))
    if stage.exists() or archive.exists():raise ValueError('Choose fresh stage and archive paths')
    stage.mkdir(parents=True)
    excluded=shutil.ignore_patterns('__pycache__','*.pyc','.git')
    for source in (HERE,BASELINE,REPO/'distortion'):
        target=stage/source.relative_to(REPO)
        shutil.copytree(source,target,ignore=excluded)
    export(prepared,stage/'native-source')
    entry='delivery/20261103-hdmi-camera-fisheye-60'
    start=f'''# 1080p60 鱼眼校正集成候选

功能、最终验证状态和复现方法见 [{entry}/README.md]({entry}/README.md)。
上板状态以 [{entry}/VALIDATION_STATUS.json]({entry}/VALIDATION_STATUS.json) 为准。
原 C 基线和本候选各自保留在 delivery 目录；本包包含原始依赖源码、测试与证据。
当前候选物理时序尚未收敛，未生成新的 60 FPS 位流。包内原 C 位流对应约 4.28 FPS 的已上板基线。

运行 README 中的 tools 命令前，进入 `{entry}` 目录。
独立冻结工程则从压缩包根目录运行：

```powershell
python native-source/rebuild.py --verify-only
python native-source/rebuild.py --output D:/f60-rebuild
```

选择新的短路径，按 native-source/README.md 调用已安装的 PDS。
本包的实板新校正帧率尚待同学测量；完整验收步骤见候选 docs/BOARD_ACCEPTANCE.md。
'''
    (stage/'START_HERE.md').write_text(start,encoding='utf-8')
    # Verify the repository-style preparation path after copying all inputs.
    verify=subprocess.run([sys.executable,str(stage/BASELINE.relative_to(REPO)/'verify_source.py')],
                          capture_output=True,text=True,check=True)
    (stage/'baseline-verification.json').write_text(verify.stdout,encoding='utf-8')
    files={p.relative_to(stage).as_posix():digest(p.read_bytes()) for p in stage.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    plan=json.loads((prepared/'candidate-plan.json').read_text())
    manifest={'schema':'fisheye60-delivery-v1','source_identity':plan['source_identity'],
              'build_id':plan['build_id'],'profile_id':plan['profile_id'],
              'hardware_tested':False,'files':files}
    (stage/'delivery-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    archive.parent.mkdir(parents=True,exist_ok=True)
    prefix='fpga-fisheye60-20261103/'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in sorted([*files,'delivery-manifest.json']):z.write(stage/name,prefix+name)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,expected in files.items():assert digest(z.read(prefix+name))==expected,name
    result={'archive':str(archive),'bytes':archive.stat().st_size,'sha256':digest(archive.read_bytes()),
            'file_count':len(files)+1,'source_identity':plan['source_identity'],
            'build_id':plan['build_id'],'zip_verified':True,'hardware_tested':False}
    archive.with_suffix(archive.suffix+'.sha256').write_text(result['sha256']+'  '+archive.name+'\n',encoding='ascii')
    archive.with_suffix(archive.suffix+'.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepared',type=Path,required=True);p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--archive',type=Path,required=True);a=p.parse_args()
    print(json.dumps(package(a.prepared,a.stage,a.archive),indent=2))
