"""Exact RGB HDMI 1080p30 EDID for the isolated board1080 controller.

The existing reference EDID advertises a 297 MHz 3840x2160 preferred mode.
This profile advertises only the 74.25 MHz progressive mode the RTL admits.
Timing encoding follows the distributed VESA EDID layout and Linux drm_edid
CTA VIC 34 timing (1920,2008,2052,2200 / 1080,1084,1089,1125, +/+).
No I2C ACK, receiver register readback, host behavior or hardware is proved.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'platform/video_base/source/hdmi/ms7200_ctl.v'
CANDIDATE = ROOT / 'rtl/experimental/ms7200_1080p30_ctl.v'
REFERENCE_SHA256 = '501521c4cceecd48de5741d3116eb7062c93a70a606a386682e1d8756a494199'
PROLOGUE = ('// Isolated board1080 HDMI30 profile: only the 256 EDID bytes differ.\n'
            '// Compile instead of platform/video_base/source/hdmi/ms7200_ctl.v.\n'
            '// Reference identity/chromaticity retained; capability is RGB1080p30 only.\n'
            '// I2C ACK/readback, actual receiver format and board timing remain unverified.\n')
ROW = re.compile(r"(?P<index>\d+)'d(?P<n>\d+)\s*:\s*cmd_data\s*=\s*\{16'h(?P<addr>[0-9a-fA-F]+),\s*8'h(?P<data>[0-9a-fA-F]+)\}")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def command_rows(path):
    text = Path(path).read_text(encoding='utf-8')
    rows = [(int(m['n']), int(m['addr'],16), int(m['data'],16)) for m in ROW.finditer(text)]
    require([i for i,_,_ in rows] == list(range(311)), 'exact 311 unique command rows required')
    return rows


def extract_edid(path):
    rows = command_rows(path)
    writes = [(addr,data) for _,addr,data in rows if 0x0D00 <= addr < 0x0E00]
    require(len(writes) == 264, 'eight repeated header plus 256 EDID writes required')
    require([addr for addr,_ in writes] == list(range(0x0D00,0x0D08))+list(range(0x0D00,0x0E00)),
            'EDID address ordering changed')
    require(writes[:8] == writes[8:16], 'repeated EDID header differs')
    return bytes(data for _,data in writes[8:])


def detailed_timing(data):
    require(len(data)==18, 'DTD needs18 bytes')
    clock = int.from_bytes(data[:2], 'little') * 10000
    require(clock > 0, 'not a detailed timing descriptor')
    ha=data[2]+((data[4]&0xF0)<<4); hb=data[3]+((data[4]&15)<<8)
    va=data[5]+((data[7]&0xF0)<<4); vb=data[6]+((data[7]&15)<<8)
    hfront=data[8]+((data[11]&0xC0)<<2); hs=data[9]+((data[11]&0x30)<<4)
    vfront=(data[10]>>4)+((data[11]&0x0C)<<2); vs=(data[10]&15)+((data[11]&3)<<4)
    return {'PixelClockHz':clock,'Width':ha,'Height':va,'HTotal':ha+hb,'VTotal':va+vb,
            'HFrontPorch':hfront,'HSync':hs,'VFrontPorch':vfront,'VSync':vs,
            'Interlaced':bool(data[17]&0x80),'HSyncPositive':bool(data[17]&2),
            'VSyncPositive':bool(data[17]&4),'FrameHz':clock/((ha+hb)*(va+vb))}


def build_edid(reference=REFERENCE):
    original=extract_edid(reference)
    base=bytearray(original[:128])
    # EDID1.3 RGB digital input; preserve supplied identity/chromaticity only.
    base[18:25]=bytes([1,3,0x80,0,0,original[23],0x02])
    base[35:38]=bytes(3)             # No established timings.
    base[38:54]=bytes([1,1])*8       # No standard timings.
    # 7425*10 kHz; 1920+280 x1080+45; 88/44 and4/5 sync; +/+.
    dtd=bytes.fromhex('01 1d 80 18 71 38 2d 40 58 2c 45 00 00 00 00 00 00 1e')
    base[54:72]=dtd
    base[72:90]=b'\x00\x00\x00\xfc\x00FPGA1080P30\n '
    dummy=bytes([0,0,0,0x10,0])+bytes(13)
    base[90:108]=dummy; base[108:126]=dummy
    base[126]=1
    base[127]=(-sum(base[:127]))&0xFF
    extension=bytearray(128)
    # CTA3, no audio/YUV/deep-color capabilities; one native VIC34.
    # HDMI VSDB OUI03-0c-00, physical1.0.0.0, no optional features,75 MHz max.
    blocks=bytes([0x41,0xA2,0x67,0x03,0x0C,0x00,0x10,0x00,0x00,0x0F])
    extension[:4]=bytes([0x02,0x03,4+len(blocks),0x00])
    extension[4:4+len(blocks)]=blocks
    extension[127]=(-sum(extension[:127]))&0xFF
    return bytes(base+extension)


def audit_edid(data, reference=REFERENCE):
    require(len(data)==256, 'exact two128-byte EDID blocks required')
    require(data[:8]==bytes.fromhex('00 ff ff ff ff ff ff 00'), 'EDID header differs')
    require(data[126]==1, 'one CTA extension required')
    require(sum(data[:128])%256==sum(data[128:])%256==0, 'EDID checksum mismatch')
    require(data[35:38]==bytes(3) and data[38:54]==bytes([1,1])*8,
            'unsupported established or standard mode')
    require(data[54:56]!=b'\0\0' and all(data[i:i+2]==b'\0\0' for i in (72,90,108)),
            'exact one preferred DTD required')
    require(data==build_edid(reference), 'EDID differs from exact RGB1080p30 capability profile')
    mode=detailed_timing(data[54:72])
    require(mode['FrameHz']==30 and mode['PixelClockHz']==74250000 and not mode['Interlaced'],
            'unsupported preferred mode')
    return {'PreferredMode':mode,'CTAVideoCodes':[34],'NativeVideoCode':34,
            'Blocks':2,'Checksums':[sum(data[:128])%256,sum(data[128:])%256],
            'HDMIVendorOUI':'000C03','PhysicalAddress':'1.0.0.0','MaximumTMDSMHz':75,
            'AudioAdvertised':False,'YCbCrAdvertised':False,'DeepColorAdvertised':False,
            'EDIDSHA256':hashlib.sha256(data).hexdigest()}


def render_controller(reference=REFERENCE):
    original=Path(reference).read_text(encoding='utf-8')
    data=build_edid(reference)
    def replace(match):
        address=int(match['addr'],16)
        if not 0x0D00<=address<0x0E00:
            return match.group()
        start,end=match.span('data')
        offset=match.start()
        return match.group()[:start-offset]+f'{data[address-0x0D00]:02X}'+match.group()[end-offset:]
    return PROLOGUE+ROW.sub(replace,original)


def audit_controller(candidate=CANDIDATE, reference=REFERENCE):
    candidate,reference=Path(candidate),Path(reference)
    require(sha(reference)==REFERENCE_SHA256, 'vendor reference differs from bound source')
    actual=candidate.read_text(encoding='utf-8')
    require(actual==render_controller(reference), 'controller differs beyond isolated EDID replacement')
    profile=audit_edid(extract_edid(candidate),reference)
    old=extract_edid(reference)
    return {'Schema':'board1080-hdmi30-edid-audit-v1','AuditPassed':True,
            'Controller':str(candidate),'ControllerSHA256':sha(candidate),
            'Reference':str(reference),'ReferenceSHA256':sha(reference),
            'OnlyEDIDBytesChanged':True,'RegisterCommandCount':311,'InitialWriteCount':300,
            'EDIDWritesIncludingHeaderRepeat':264,'Profile':profile,
            'ReferencePreferredMode':detailed_timing(old[54:72]),
            'HardwareAccessed':False,'PhysicalI2CVerified':False,'HostModeSelectionVerified':False,
            'Limitations':['Reference identity and chromaticity bytes remain; this is a capability profile, not an actual display identity.',
                'No audio, YCbCr, HDR or deep color is advertised; host/receiver interoperability still needs hardware.',
                'The inherited I2C driver does not report ACK failures; this change only corrects advertised video modes.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate',type=Path,default=CANDIDATE)
    parser.add_argument('--reference',type=Path,default=REFERENCE)
    args=parser.parse_args()
    print(json.dumps(audit_controller(args.candidate,args.reference),indent=2))


if __name__=='__main__':main()
