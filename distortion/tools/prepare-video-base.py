"""Import the vendor video platform into an editable working copy.

Original archives/reference files remain unchanged. This is a platform baseline,
not the competition correction implementation and not a tested camera design.
"""
from pathlib import Path
import re
import shutil
import json
import hashlib

def main():
    root=Path(__file__).resolve().parents[2]
    matches=list((root/'vendor'/'reference'/'video').rglob('HDMI_IN_DDR3_HDMI_OUT.pds'))
    if len(matches)!=1:raise ValueError('Expected one extracted vendor video project')
    original=matches[0].parent
    dest=root/'distortion'/'platform'/'video_base'
    dest.mkdir(parents=True,exist_ok=True)
    for folder in ('source','ipcore'):
        if not (dest/folder).exists():
            shutil.copytree(original/folder,dest/folder,ignore=shutil.ignore_patterns('pnr','logbackup','sim','sim_lib'))
    constraint='HDMI_IN_DDR3_HDMI_OUT_top.fdc'
    if not (dest/constraint).exists():shutil.copy2(original/constraint,dest/constraint)
    text=matches[0].read_text(encoding='utf-8')
    section=text.split('(_widget wgt_my_design_src',1)[1].split('(_widget wgt_my_ips_src',1)[0]
    sources=re.findall(r'\(_file "([^"]+)"',section)
    ips=re.findall(r'\(_ip "([^"]+)"',text)
    lines=[]; records=[]
    for relative in sources+ips:
        target=(dest/relative).resolve()
        if not target.is_relative_to(dest.resolve()) or not target.is_file():
            raise ValueError(f'Invalid/missing vendor source: {relative}')
        lines.append('add_design {'+target.as_posix()+'}')
        records.append({'file':relative,'original_sha256':hashlib.sha256((original/relative).read_bytes()).hexdigest()})
    lines+=['add_constraint {'+(dest/constraint).as_posix()+'}',
            'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676',
            'compile -top_module HDMI_IN_DDR3_HDMI_OUT_top',
            'synthesize -ads -selected_syn_tool_opt 2', 'dev_map']
    (dest/'synthesize.tcl').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (dest/'provenance.json').write_text(json.dumps({'source_project':str(matches[0]),
        'role':'Vendor DDR/HDMI platform baseline; correction logic is project-owned',
        'source_files':records,'constraints':constraint},indent=2,ensure_ascii=False),encoding='utf-8')
    print(f'Prepared {len(sources)} RTL sources and {len(ips)} IP descriptors in {dest}')

if __name__=='__main__':main()
