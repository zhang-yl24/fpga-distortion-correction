"""The new namespace must retain the approved exact bounded native parser."""
import ast
from pathlib import Path
import importlib
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT.parent/'.venv/Lib/site-packages')]

def test_exact_approved_bounded_b_native_cell_function_ast_and_namespace():
    old=importlib.import_module('hdmi_camera_fisheye_fill8r3s3_vendor_startup_bounded_b')
    new=importlib.import_module('hdmi_camera_fisheye_tile8df8_vendor_startup_bounded_b')
    def node(path):
        return next(n for n in ast.parse(Path(path).read_text(encoding='utf-8-sig')).body
                    if isinstance(n,ast.FunctionDef)and n.name=='native_route_cell')
    assert ast.dump(node(old.__file__),include_attributes=False)==ast.dump(node(new.__file__),include_attributes=False)
    assert new.protocol.__name__=='hdmi_camera_fisheye_tile8df8_protocol'
    assert new.build.__name__=='hdmi_camera_fisheye_tile8df8_build'
    assert new.native.__name__=='hdmi_camera_fisheye_tile8df8_native'
    assert new.SCHEMA=='hdmi-camera-fisheye-tile8df8-vendor-startup-isolation-v2-bounded-b'
