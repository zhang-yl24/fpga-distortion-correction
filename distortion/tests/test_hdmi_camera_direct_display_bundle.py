"""Portable published bytes/scope and recorded-build source binding."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest

PACKAGE=Path(__file__).resolve().parents[1]/'results/hdmi-camera1080-direct-display-20261102-a'
spec=importlib.util.spec_from_file_location('direct_display_bundle_verifier',PACKAGE/'verify_bundle.py')
verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)


def test_original_package_verifies_without_pds_or_original_work_tree():
    value=verifier.verify(PACKAGE)
    assert value['Passed']and value['Resolution']==[1920,1080]and value['SignalFrameRateHz']==60
    assert value['UniqueOpticalFPSMeasured']is False and value['FlashWritten']is False
    assert value['NativePhysicalProofReexecuted']is False and value['HardwareAccessed']is False


@pytest.fixture
def package(tmp_path):
    out=tmp_path/'bundle';shutil.copytree(PACKAGE,out);return out


def update_inventory(package,manifest,name):
    path=package/name
    row=next(r for r in manifest['Files']if r['File']==name)
    row.update(Bytes=path.stat().st_size,SHA256=verifier.sha(path.read_bytes()))


@pytest.mark.parametrize('change',['optical_fps','flash','missing_origin','bit_bytes','rehashed_source'])
def test_changed_scope_missing_origin_and_even_rehashed_source_snapshots_are_rejected(package,change):
    path=package/'manifest.json';m=json.loads(path.read_text())
    if change=='optical_fps':m['UniqueOpticalFPSMeasured']=True
    elif change=='flash':m['FlashWritten']=True
    elif change=='missing_origin':
        origin=m['Roles']['ProgramReceipt']['OriginalPath']
        m['OriginIndex']=[r for r in m['OriginIndex']if r['OriginalPath']!=origin]
    elif change=='bit_bytes':
        target=package/'candidate/hdmi_camera_direct_top.sbit'
        data=bytearray(target.read_bytes());data[-1]^=1;target.write_bytes(data)
    else:
        row=next(r for r in m['SourceSnapshots']if r['Source'].endswith('hdmi_camera_pixel_sampler.v'))
        for field in ('OriginalFile','CompiledFile'):
            target=package/row[field];target.write_bytes(target.read_bytes()+b'\n// different source\n')
            update_inventory(package,m,row[field])
        row['OriginalSHA256']=verifier.sha((package/row['OriginalFile']).read_bytes())
        row['CompiledSHA256']=verifier.sha((package/row['CompiledFile']).read_bytes())
    path.write_text(json.dumps(m))
    with pytest.raises(ValueError):verifier.verify(package)


def test_package_paths_cannot_escape_even_if_the_external_file_exists(tmp_path):
    package=tmp_path/'bundle';package.mkdir();(tmp_path/'escape').write_text('not package evidence')
    with pytest.raises(ValueError):verifier.safe(package,'../escape')
    with pytest.raises(ValueError):verifier.safe(package,str((tmp_path/'escape').resolve()))


def test_staging_requires_a_new_ascii_path_outside_the_immutable_package(tmp_path):
    sys.path.insert(0,str(PACKAGE))
    from reproduce_build import stage
    with pytest.raises(ValueError):stage(PACKAGE,PACKAGE/'would_modify_release')
    destination=tmp_path/'existing';destination.mkdir()
    with pytest.raises(ValueError):stage(PACKAGE,destination)
