"""Verify and freeze planning/assessment artifacts without hardware access."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,shutil,re
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/project'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()

def main():
    register=read(OUT/'evidence-register.json');sfr=read(OUT/'sfr-validation.json')
    if not sfr['passed'] or sfr['host_tests']!=10 or sfr['optical_acceptance_complete']:
        raise ValueError('Need completed diagnostic tool checks without false optical acceptance')
    for obj in (register,sfr):
        for name,digest in obj['source_sha256'].items():
            if sha(ROOT/name)!=digest:raise ValueError('Generated report source changed')
    for row in register['evidence']:
        if sha(ROOT/row['file'])!=row['sha256']:raise ValueError('Inventory evidence changed')
    docs=list(OUT.glob('*.md'))
    if len(docs)!=4:raise ValueError('Need the four project documents')
    for doc in docs:
        text=doc.read_text(encoding='utf-8')
        if '\ufffd' in text:raise ValueError('Corrupted document text')
        for target in re.findall(r'\]\(([^)]+)\)',text):
            if target.startswith('D:/') and not Path(target).is_file():raise ValueError('Broken local document link: '+target)
    status=read(ROOT/'status.json')
    if status['current_sram_target']!='heartbeat':raise ValueError('Board no longer recorded idle')
    files=[p for p in OUT.iterdir() if p.is_file()]
    names=('tools/slanted_edge_analysis.py','tools/validate-slanted-edge.py','tests/test_slanted_edge_analysis.py',
        'tools/build-project-evidence.py','tools/seal-project-planning.py','README.md',
        'vendor/competition/pango-topic-guide-2026.pdf')
    files += [ROOT/name for name in names]
    archive=ROOT/'results/verified'/('project-plan-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    archive.mkdir()
    for source in files:
        source=source.resolve();dest=archive/source.relative_to(ROOT)
        if not source.is_relative_to(ROOT) or not dest.resolve().is_relative_to(archive):raise ValueError('Archive escaped workspace')
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        if sha(source)!=sha(dest):raise ValueError('Copy differs')
    release={'recorded_utc':datetime.now(timezone.utc).isoformat(),'hardware_accessed':False,
        'stable_bitstream_sha256':register['stable_bitstream_sha256'],'previous_physical_release':register['verified_release'],
        'previous_release_verified_files':register['verified_release_files'],'new_sfr_host_tests':10,
        'last_known_board_target':'heartbeat','last_actual_idle_confirmation':status['current_connection']['checked_on'],
        'documents':4,'limits':'Project targets are planned milestones, not achieved award level. SFR validation is synthetic only. Board state is the last verified idle transfer, not a new hardware observation.'}
    (archive/'release.json').write_text(json.dumps(release,indent=2)+'\n')
    hashes={p.relative_to(archive).as_posix():sha(p) for p in archive.rglob('*') if p.is_file()}
    (archive/'files-sha256.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if not all(sha(archive/name)==digest for name,digest in read(archive/'files-sha256.json').items()):raise ValueError('Final hashes changed')
    print(json.dumps({'archive':str(archive),'verified_files':len(hashes),'documents':4,'new_tests':10,'hardware_accessed':False}))

if __name__=='__main__':main()
