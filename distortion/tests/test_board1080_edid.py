from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import board1080_edid as tool


def test_profile_corrects_real_reference_preferred_mode_and_preserves_only_edid_scope():
    audit=tool.audit_controller()
    assert audit['ReferencePreferredMode']['Width']==3840
    assert audit['ReferencePreferredMode']['PixelClockHz']==297000000
    assert audit['OnlyEDIDBytesChanged'] and audit['RegisterCommandCount']==311
    assert audit['EDIDWritesIncludingHeaderRepeat']==264
    assert audit['Profile']['PreferredMode']=={
        'PixelClockHz':74250000,'Width':1920,'Height':1080,'HTotal':2200,'VTotal':1125,
        'HFrontPorch':88,'HSync':44,'VFrontPorch':4,'VSync':5,'Interlaced':False,
        'HSyncPositive':True,'VSyncPositive':True,'FrameHz':30.0}
    assert audit['Profile']['Checksums']==[0,0]
    assert audit['Profile']['CTAVideoCodes']==[34]
    assert audit['Profile']['MaximumTMDSMHz']==75
    assert tool.build_edid()[23]==tool.extract_edid(tool.REFERENCE)[23]==0x78
    assert audit['HardwareAccessed'] is False and audit['PhysicalI2CVerified'] is False


def checksum(data):
    for start in (0,128):data[start+127]=(-sum(data[start:start+127]))&255
    return bytes(data)


@pytest.mark.parametrize('index,value',[(0,1),(18,2),(35,128),(38,129),(54,2),(71,158),
    (72,1),(126,0),(128,3),(130,4),(131,64),(133,144),(135,4),(139,48),(141,60)])
def test_even_rechecksummed_unsupported_capabilities_are_rejected(index,value):
    bad=bytearray(tool.build_edid());bad[index]=value
    with pytest.raises(ValueError):tool.audit_edid(checksum(bad))


def test_corrupt_checksum_and_length_reject():
    data=tool.build_edid()
    with pytest.raises(ValueError,match='checksum'):tool.audit_edid(data[:-1]+bytes([data[-1]^1]))
    with pytest.raises(ValueError,match='two128'):tool.audit_edid(data[:128])


def test_non_edid_register_or_fsm_edits_are_rejected(tmp_path):
    text=tool.CANDIDATE.read_text(encoding='utf-8')
    for index,(old,new) in enumerate((("16'h0204, 8'h02","16'h0204, 8'h03"),
                                     ("dri_cnt == 9'd299","dri_cnt == 9'd298"))):
        target=tmp_path/f'changed{index}.v';target.write_text(text.replace(old,new,1),encoding='utf-8')
        with pytest.raises(ValueError,match='beyond isolated EDID'):tool.audit_controller(target)


def test_duplicate_edid_header_cannot_disagree_with_final_ram_contents(tmp_path):
    text=tool.CANDIDATE.read_text(encoding='utf-8').replace("16'h0D00, 8'h00","16'h0D00, 8'h01",1)
    target=tmp_path/'bad.v';target.write_text(text,encoding='utf-8')
    with pytest.raises(ValueError,match='repeated EDID header'):tool.extract_edid(target)


def test_non_edid_initial_and_setting_writes_match_vendor_exactly():
    original=tool.command_rows(tool.REFERENCE);candidate=tool.command_rows(tool.CANDIDATE)
    assert [(i,a,d) for i,a,d in original if not 0xD00<=a<0xE00] == [
        (i,a,d) for i,a,d in candidate if not 0xD00<=a<0xE00]
    assert original[294:]==candidate[294:]


def test_video_blocks_are_only_native_vic34_and_minimal_hdmi_vsdb():
    data=tool.build_edid();cta=data[128:]
    assert cta[:4]==bytes([2,3,14,0])
    assert cta[4:6]==bytes([0x41,0xa2])
    assert cta[6:14]==bytes([0x67,3,12,0,0x10,0,0,15])
    assert cta[14:127]==bytes(113)
    assert data[72:90]==b'\0\0\0\xfc\0FPGA1080P30\n '
