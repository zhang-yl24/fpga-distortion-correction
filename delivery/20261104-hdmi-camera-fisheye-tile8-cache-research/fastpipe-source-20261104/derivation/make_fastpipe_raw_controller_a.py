"""Create the isolated raw timing recipe; never execute EDA from this generator."""
import argparse
import hashlib
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
DIST=REPO/'distortion'
OLDWORK=DIST/'work/hdmi-camera-fisheye-assoc2way256-choose-clear-20261104-a'
WORK=DIST/'work/hdmi-camera-fisheye-assoc2way256-fastpipe-20261104-a'
OLDNAME='ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_choose_clear_a.v'
NEWNAME='ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_fastpipe_a.v'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cache-sha',required=True)
    args=parser.parse_args()
    original=DIST/'tools/hdmi_camera_fisheye_assoc2way256_choose_clear_build.py'
    body=original.read_bytes()
    assert hashlib.sha256(body).hexdigest()=='a6167f2ea85732fea613dfc586a9d712c8b503b62fd92ccb683623eb2b7af6a0'
    text=body.decode().replace('\r\n','\n').replace('assoc2way256chooseclear','assoc2way256fastpipe')
    text=text.replace('assoc2way256-choose-clear','assoc2way256-fastpipe').replace(OLDNAME,NEWNAME)
    build_path=DIST/'tools/hdmi_camera_fisheye_assoc2way256_fastpipe_build.py'
    if build_path.exists():
        assert build_path.read_text()==text
    else:
        with build_path.open('xb') as stream:stream.write(text.encode())
    body=(OLDWORK/'run_raw_research_a.py').read_bytes()
    assert hashlib.sha256(body).hexdigest()=='d5fb1a9d364dc49de4729933d80eb482d3106964cf2782a28c8396524cd5056c'
    text=body.decode().replace('\r\n','\n')
    text=text.replace('import hdmi_camera_fisheye_assoc2way256_choose_clear_build as build',
                      'import hdmi_camera_fisheye_assoc2way256_fastpipe_build as build')
    assert text.count("CACHE_SHA='62225f2694f1c7441ec8c37b219d20643fce5b3847897d4ec590d3a306a4d728'")==1
    text=text.replace("CACHE_SHA='62225f2694f1c7441ec8c37b219d20643fce5b3847897d4ec590d3a306a4d728'",'CACHE_SHA='+repr(args.cache_sha))
    anchor='import make_choose_clear_cache_a as clear_source\n'
    assert text.count(anchor)==1
    text=text.replace(anchor,anchor+"FAST_PROBE=REPO/'output/new-next-probe-20261104/assoc2way256-fastpipe-a'\nsys.path.insert(0,str(FAST_PROBE))\nimport make_fastpipe_cache_a as fast_source\n")
    start=text.index('def source_review():')
    end=text.index('\n\ndef finite_checks():',start)
    replacement='''def source_review():
    original=ROOT/'tools/hdmi_camera_fisheye_assoc2way256_choose_clear_build.py'
    require(build.sha(original)=='a6167f2ea85732fea613dfc586a9d712c8b503b62fd92ccb683623eb2b7af6a0','prior build changed')
    expected=original.read_text().replace('assoc2way256chooseclear','assoc2way256fastpipe')
    expected=expected.replace('assoc2way256-choose-clear','assoc2way256-fastpipe')
    expected=expected.replace('''+repr(OLDNAME)+''','''+repr(NEWNAME)+''')
    actual=Path(build.__file__).read_text()
    require(actual==expected,'build differs beyond namespace and cache path')
    require(ast.dump(ast.parse(actual),include_attributes=False)==ast.dump(ast.parse(expected),include_attributes=False),'whole build AST differs')
    require(build.WORK==WORK and build.STAGES==['Compile','Synthesize','Device Map','Place','Route','Route Optimize','Report Timing'],'scope/stages differ')
    candidate=FAST_PROBE/'''+repr('rtl/'+NEWNAME)+'''
    require(candidate.read_bytes()==fast_source.derive() and build.sha(candidate)==CACHE_SHA,'fast pipeline exact source replay failed')
    require((FIFO_PROBE/'rtl/hdmi_camera_fisheye_engine_index10_fifo_a.v').read_bytes()==fifo_source.derive(),'FIFO engine changed')
    return dict(ExactSourceReplayPassed=True,WholeModuleASTPassed=True,OriginalBuild=ref(original),NewBuild=ref(build.SELF),
        RelativeToFrameClearCandidateOnlyCacheBytesChanged=True,EngineFIFOUnchanged=True,
        CacheFastPipelineGenerator=ref(fast_source.__file__),AllOtherProductionBytesMustEqualOriginal=True,
        AllowedConstraintChanges='FDC filename only; exact original FDC/RCF bytes retained',
        UnchangedExecutionBudgetSeconds=1800,UnchangedSeed=3,UnchangedReportMaxPath=10000,UnchangedReportNWorst=4)
'''
    text=text[:start]+replacement+text[end:]
    old="build.sha(CLEAR_PROBE/'rtl/"+OLDNAME+"')==CACHE_SHA"
    assert text.count(old)==1
    text=text.replace(old,"build.sha(FAST_PROBE/'rtl/"+NEWNAME+"')==CACHE_SHA")
    old="files=[CLEAR_PROBE/'unit-a/simulation.json',CLEAR_PROBE/'boundary-a/simulation.json',\n           CLEAR_PROBE/'system-normal-small-a/simulation.json',CLEAR_PROBE/'system-sustained-small-a/simulation.json']"
    assert text.count(old)==1
    text=text.replace(old,"files=[FAST_PROBE/'unit-a/simulation.json',FAST_PROBE/'boundary-a/simulation.json',\n           FAST_PROBE/'system-normal-small-a/simulation.json',FAST_PROBE/'system-sustained-small-a/simulation.json']")
    text=text.replace("'tile8-assoc2-choose-clear-tagpipe-independent-cache-simulation-v1'","'tile8-assoc2-fastpipe-independent-cache-simulation-v1'")
    text=text.replace("'tile8-assoc2-choose-clear-tagpipe-independent-boundary-simulation-v1'","'tile8-assoc2-fastpipe-independent-boundary-simulation-v1'")
    old="and value.get('TotalIndependentBoundaryCases')==7,'all seven current boundary cases required')"
    assert text.count(old)==1
    text=text.replace(old,"and value.get('TotalIndependentBoundaryCases',0)>=8 and value.get('FastPipelineBoundary',{}).get('Passed')is True,'original seven plus real fast-pipeline boundary required')")
    anchor="    helpers=local_import_sources([Path(__file__),build.SELF,Path(timing.__file__)])"
    assert text.count(anchor)==1
    text=text.replace(anchor,"    fast_peer_path=FAST_PROBE/'fastpipe-independent-source-peer-a.json';add(watched,fast_peer_path)\n    fast_peer=build.read(fast_peer_path)\n    require(fast_peer.get('Passed')is True and fast_peer.get('Independent')is True and fast_peer.get('InputDrift')==[],'actual independent fast pipeline source/gate review required')\n    for name,digest in fast_peer['InputSHA256'].items():add(watched,name,digest)\n    add(watched,fast_source.__file__)\n"+anchor)
    text=text.replace('assoc2way256chooseclear-raw','assoc2way256fastpipe-raw')
    WORK.mkdir(parents=True,exist_ok=True)
    path=WORK/'run_raw_research_a.py'
    with path.open('xb') as stream:stream.write(text.encode())
    print('BuildSHA256='+hashlib.sha256(build_path.read_bytes()).hexdigest())
    print('ControllerSHA256='+hashlib.sha256(path.read_bytes()).hexdigest())

if __name__=='__main__':main()
