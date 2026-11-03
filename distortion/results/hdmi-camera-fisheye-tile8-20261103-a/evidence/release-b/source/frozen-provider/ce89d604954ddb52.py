"""Seal the prepared closed group and actual tile8 audit/raw sources only."""
from pathlib import Path
import argparse,json,sys,xml.etree.ElementTree as ET
WORK=Path(__file__).resolve().parent;ROOT=WORK.parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT.parent/'.venv/Lib/site-packages')]
import hdmi_camera_fisheye_tile8_build as build
watched={}
def add(path,expected=None):
    path=Path(path).resolve();digest=build.sha(path)
    build.require(expected is None or digest==expected,'physical/release freeze SHA mismatch: '+str(path))
    build.require(str(path)not in watched or watched[str(path)]==digest,'conflicting exact source SHA')
    watched[str(path)]=digest;return build.ref(path)
def merge(rows):
    for path,digest in rows.items():add(path,digest)
def references(value):
    if isinstance(value,dict):
        if set(value)=={'Path','SHA256'}:add(value['Path'],value['SHA256'])
        else:
            for row in value.values():references(row)
    elif isinstance(value,list):
        for row in value:references(row)
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--peer-review',type=Path,required=True);args=parser.parse_args()
    output=WORK/'physical-release-provider-source-manifest-a.json'
    build.require(not output.exists(),'fresh immutable final provider manifest required')
    group_path=WORK/'physical-release-group-prebuild-freeze-a.json';group=build.read(group_path)
    build.require(group['Passed']is True and group['Tests']==348 and group['Failures']==group['Errors']==0,
                  'completed closed-group contracts required')
    merge(group['InputSHA256']);add(group_path);references(group['GroupModules'])
    add(group['FrozenOriginalTile8Scoped']['Path'],group['FrozenOriginalTile8Scoped']['SHA256'])
    add(group['BoundedBOriginal']['Path'],group['BoundedBOriginal']['SHA256'])
    audit_path=WORK/'audit-provider-source-manifest-a.json';audit=build.read(audit_path)
    build.require(audit['Passed']is True and audit['OldS3ProvidersUnchanged']is True and
                  audit['NativeAuditAcceptanceNotInherited']is True,'actual own audit provider closure required')
    add(audit_path,'69ed0e4bb696455286600483bc674e7635eeb9e2f8f209840585c7371b22b741')
    merge(audit['InputSHA256']);references(audit)
    warning=build.read(WORK/'source-warnings-a.json')
    build.require(warning['Passed']is True and warning['SourceDiagnosticReviewPassed']is True and
                  warning['BuildPlan']==build.ref(WORK/'build-a/plan.json'),'own actual source warnings must pass')
    add(WORK/'source-warnings-a.json','f8ba7b7fcdf4cbc9cba8891105ae3d588bd4a9fafc663f42c1477966b2421d8d')
    peer=build.read(args.peer_review)
    build.require(peer['Passed']is True,'independent closed group peer review required')
    peer_ref=add(args.peer_review);references(peer)
    closure=build.read(WORK/'build-provider-source-manifest-a.json');references(closure);add(WORK/'build-provider-source-manifest-a.json')
    for role in('build','native','scoped_native'):add(ROOT/'tools'/f'hdmi_camera_fisheye_tile8_{role}.py')
    handoff=build.read(WORK/'raw-native-completed-a.json')
    build.require(handoff['PriorWorkerEnded']is True and handoff['PDriveReleased']is True,'completed own raw handoff required')
    references(handoff);handoff_ref=add(WORK/'raw-native-completed-a.json')
    core=build.read(WORK/'raw-core-timing-a.json')
    build.require(core['Passed']is True and len(core['Rows'])==10 and all(
        r['FailingChecks']==0 and r['WorstSlackNS']>=0 and r['TotalNegativeSlackNS']==0 for r in core['Rows']),
        'all ten own ordinary core checks required')
    add(WORK/'raw-core-timing-a.json')
    selected=build.read(WORK/'system-binding-selected-v2-a.json')
    build.require(selected['Passed']is True and selected.get('InputDrift',selected.get('SourceDrift'))==[],
                  'actual selected tile8 bit-provider simulation binding required')
    selected_ref=add(WORK/'system-binding-selected-v2-a.json');references(selected)
    merge(selected['WatchedInputSHA256'])
    for path in('writer-unit-c/simulation.json','engine-unit-a/simulation.json','system-small-a/simulation.json','system-native-a/simulation.json'):
        value=build.read(WORK/path);build.require(value['Passed']is True,'actual writer/engine/system regression failed')
        add(WORK/path)
    add(__file__);add(WORK/'physical-release-closed-group-a.md')
    # Keep the established S3 closure immutable; it is provenance only.
    old_path=ROOT/'work/hdmi-camera-fisheye-fill8r3s3-20261103-a/provider-revision-v2-source-manifest-a.json'
    old=build.read(old_path);merge(old['InputSHA256']);old_ref=add(old_path,
        '5d6a03f264d445c36bb62ef51be20d015108b6b99d5180ea52b19480e0ba65fe')
    build.require(all(build.sha(path)==digest for path,digest in watched.items()),'final source closure drift while freezing')
    result={'Schema':'hdmi-camera-fisheye-tile8v2-provider-source-manifest-v1','ProviderRevision':'tile8v2-bounded-b',
        'Passed':True,'FrozenUTC':build.utc(),'ClosedGroupPrebuildManifest':build.ref(group_path),
        'AuditProviderManifest':build.ref(audit_path),'SourceWarningReview':build.ref(WORK/'source-warnings-a.json'),
        'IndependentClosedGroupReview':peer_ref,'RawNativeHandoff':handoff_ref,'SelectedSystemSimulationBinding':selected_ref,
        'InputSHA256':dict(sorted(watched.items())),'InputDrift':[],'ManifestSelfIncluded':False,
        'OriginalS3Frozen77Unchanged':True,'OriginalActiveTile8ScopedUnchanged':True,
        'OwnAllTenOrdinaryCoreChecksPassed':True,'OwnRawNativeReceiptsCompleted':True,
        'OriginalS3ProviderManifestProvenance':old_ref,'PriorPhysicalTimingOrAcceptanceInherited':False,
        'FreshFullAuditAndBoundedStartupReviewStillRequired':True,'OwnFinalPhysicalProofStillRequired':True,
        'RootGoPreparedByThisTool':False,'PhysicalStagePrepared':False,'BitStagePrepared':False,
        'PDriveAccessed':False,'EDAExecuted':False,'HardwareAccessed':False,'HardwareReleaseAllowed':False}
    build.write(output,result)
    print(json.dumps({'Passed':True,'Manifest':build.ref(output),'InputRows':len(watched),'EDAExecuted':False}),flush=True)
if __name__=='__main__':main()
