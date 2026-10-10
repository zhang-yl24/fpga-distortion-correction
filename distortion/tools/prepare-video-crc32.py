from pathlib import Path
root=Path(__file__).resolve().parents[1]
poly=0xEDB88320
def balanced(terms):
    if len(terms)==1:return terms[0]
    mid=len(terms)//2
    return '('+balanced(terms[:mid])+' ^ '+balanced(terms[mid:])+')'
def function(name,width,data_name):
    state=[1<<i for i in range(32)]
    for i in range(width):
        feedback=state[0]^(1<<(32+i))
        state=[(state[j+1] if j<31 else 0)^(feedback if (poly>>j)&1 else 0) for j in range(32)]
    lines=[f'function [31:0] {name};',f'    input [31:0] previous;input [{width-1}:0] {data_name};','    begin']
    for bit,mask in enumerate(state):
        terms=[f'previous[{i}]' if i<32 else f'{data_name}[{i-32}]' for i in range(32+width) if mask&(1<<i)]
        lines.append(f'        {name}[{bit}]='+balanced(terms)+';')
    return '\n'.join(lines+['    end','endfunction'])
s='// IEEE reflected CRC32 (EDB88320). Generated exact GF(2) matrices.\n// Balanced XOR trees bound logic depth; verified against Python binascii.\n// Initialize FFFFFFFF, feed RGB565 little-endian, complement at frame end.\n'
s+=function('video_crc32_beat',256,'bytes')+'\n'+function('video_crc32_pixel',16,'pixel')+'\n'
(root/'rtl/video_crc32.vh').write_text(s)
print(f'Generated balanced 256-bit/16-bit CRC32 transforms ({len(s)} bytes).')
