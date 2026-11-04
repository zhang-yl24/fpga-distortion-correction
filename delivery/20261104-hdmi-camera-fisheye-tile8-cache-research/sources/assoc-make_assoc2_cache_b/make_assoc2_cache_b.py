"""Replay the one fault-priority correction; accepts only identical saved bytes."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
A = HERE / 'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_a.v'
B = HERE / 'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_b.v'
A_SHA = 'ffb8712d7eee8b3e0fdddec1405a5a835ed1b9e4542eb63caec05e1fbcfeded6'
B_SHA = '745f4f2cbc26f733d991eca2998484542a131c47f2d747504194f8ecaca95f0b'


def main():
    raw = A.read_bytes()
    if hashlib.sha256(raw).hexdigest() != A_SHA:
        raise ValueError('original prototype bytes differ')
    text = raw.decode('utf-8')
    marker = '    wire [INDEX_BITS-1:0] selected_choose_line={selected_choose_way,selected_line[SET_BITS-1:0]};'
    if text.count(marker) != 1 or text.count('valid_lines[selected_line]<=0;') != 3:
        raise ValueError('fault-priority anchors differ')
    text = text.replace(marker, marker + '\n    wire [INDEX_BITS-1:0] fault_line=state==CHECK ? selected_choose_line:selected_line;')
    text = text.replace('valid_lines[selected_line]<=0;', 'valid_lines[fault_line]<=0;')
    data = text.encode('utf-8')
    if hashlib.sha256(data).hexdigest() != B_SHA:
        raise ValueError('derived variant SHA differs')
    if B.exists():
        if B.read_bytes() != data:
            raise ValueError('refuse overwriting different prototype bytes')
    else:
        with B.open('xb') as stream:
            stream.write(data)
    print(json.dumps(dict(Source=str(A), SourceSHA256=A_SHA, Variant=str(B), VariantSHA256=B_SHA,
                          OnlyChange='CHECK same-edge fault invalidates the newly selected physical line; other states retain the owned selected line',
                          NormalPathUnchanged=True, RTLOrHardwareExecuted=False)))


if __name__ == '__main__':
    main()
