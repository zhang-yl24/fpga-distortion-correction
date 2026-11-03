"""New root handoffs retain their exact manifest rows before any stage executes."""
from pathlib import Path
import importlib.util
import json
import sys
import pytest
WORK=Path(__file__).resolve().parents[1];ROOT=WORK.parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT.parent/'.venv/Lib/site-packages')]

@pytest.mark.parametrize('filename',['run_physical_v2_a.py','run_release_v2_a.py'])
@pytest.mark.parametrize('case',['valid_then_source_drift','wrong_schema','manifest_drift'])
def test_exact_approved_revision_rows(filename,case,tmp_path):
    spec=importlib.util.spec_from_file_location('isolated_'+filename.replace('.','_'),WORK/filename)
    driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
    driver.WORK=tmp_path
    api=driver.build if hasattr(driver,'build')else driver.bit
    source=tmp_path/'provider.py';source.write_text('approved')
    path=tmp_path/'physical-release-provider-source-manifest-a.json'
    manifest={'Schema':'hdmi-camera-fisheye-tile8df8v2-provider-source-manifest-v1',
              'ProviderRevision':'tile8df8v2-bounded-b','InputSHA256':{str(source):api.sha(source)}}
    if case=='wrong_schema':manifest['Schema']='old-provider-revision'
    path.write_text(json.dumps(manifest))
    record=api.ref(path)
    if case=='wrong_schema':
        with pytest.raises(ValueError,match='exact complete isolated revision'):driver.verify_revision(record)
        return
    driver.verify_revision(record)
    if case=='valid_then_source_drift':
        source.write_text('changed')
        with pytest.raises(ValueError,match='approved revision input changed'):driver.verify_revision()
    else:
        path.write_text(json.dumps({**manifest,'Unexpected':True}))
        with pytest.raises(ValueError,match='approved revision manifest drift'):driver.verify_revision()
