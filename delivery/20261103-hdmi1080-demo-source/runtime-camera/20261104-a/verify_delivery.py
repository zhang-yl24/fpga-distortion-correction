from pathlib import Path
import json,hashlib,importlib.util,struct,zlib
ROOT=Path(__file__).resolve().parent
def project_bytes(row):
    p=(ROOT/row['package_ref']).resolve()
    assert p.is_relative_to(ROOT.parents[1].resolve())
    b=p.read_bytes()
    if row['disposition']=='reuse_published_OP':
        assert hashlib.sha256(b).hexdigest()==row['reference_sha256']
        if row['reference_transform']=='CRLF_to_LF':b=b.replace(b'\r\n',b'\n')
    assert hashlib.sha256(b).hexdigest()==row['export_sha256']
    return b
def verify():
    for row in json.loads((ROOT/'PACKAGE_FILES.json').read_text(encoding='utf-8')):
        b=(ROOT/row['path']).read_bytes()
        assert len(b)==row['bytes']and hashlib.sha256(b).hexdigest()==row['sha256'],row['path']
    m=json.loads((ROOT/'SOURCE_BINDING.json').read_text(encoding='utf-8'))
    assert m['native_input_count']==151 and len(m['files'])==151
    projects=[r for r in m['files']if r['disposition']!='external_dependency_not_published']
    for r in projects:project_bytes(r)
    assert len(projects)==69
    s=json.loads((ROOT/'SUMMARY.json').read_text(encoding='utf-8'))
    assert s['runtime_pixels']==24576 and s['runtime_frames']==6
    assert not s['new_board_bit_or_physical60_accepted']and not s['actual_UART_waveform_or_HDMI_scan_tested']
    spec=importlib.util.spec_from_file_location('offline_camera_encoder',ROOT/'scripts/encode_rotation.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    r=mod.encode(13.37,0x708006b9,1);b=bytes.fromhex(r['packet_hex'])
    assert r['param_id']=='91066c87'and len(b)==36 and b[:4]==b'SGR1'
    assert zlib.crc32(b[:32])==int.from_bytes(b[32:],'little')
    return {'project_sources_bound':69,'deltas':11,'OP_reused':58,'vendor_dependencies_excluded':82,'offline_encoder_CRC':True,'new_HDL_EDA_hardware':False}
if __name__=='__main__':print(json.dumps(verify()))
