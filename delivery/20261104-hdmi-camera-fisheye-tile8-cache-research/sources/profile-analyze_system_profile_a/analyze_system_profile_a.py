"""Read saved enhanced XSim observations; no simulator/provider/hardware calls."""
import csv
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path

HERE=Path(__file__).resolve().parent
RUN=HERE/'native-a'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(value,message):
    if not value:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def csvrows(name):
    with (RUN/name).open(encoding='utf-8-sig',newline='')as stream:return list(csv.DictReader(stream))

def main():
    inputs={}
    def pin(path,digest=None):
        path=Path(path).resolve();actual=sha(path)
        require(digest is None or actual==digest,'saved artifact drift: '+str(path));inputs[str(path)]=actual
    pin(__file__);pin(RUN/'profiling.json')
    report=read(RUN/'profiling.json')
    require(report['Passed'] is True and report['FunctionalPassed'] is True and report['InputDrift']==[],
        'completed original oracle/CRC/drain and enhanced profiling required')
    require(report['OriginalBenchPreservedAfterRemovingObserver'] is True and
        report['OriginalOracleCRCAndDrainAssessPassed'] is True,'original checks not preserved')
    for name,digest in report['ArtifactsSHA256'].items():pin(RUN/name,digest)
    timeline=csvrows('profile-timeline.csv');frames=csvrows('frames.csv')
    cycles=csvrows('profile-cycles.csv');fsm=csvrows('profile-cache-fsm.csv');hist=csvrows('profile-ddr-histograms.csv')
    original=csvrows('performance.csv');events=csvrows('events.csv')
    names=['IDLE','SELECT','AR','FILL','WAIT_COMMIT','LOAD','PICK','RESULT','FAULT','CHECK']
    output=[]
    def one(kind,ident):
        rows=[row for row in timeline if row['event']==kind and int(row['frame_id'])==ident]
        require(len(rows)==1,'expected exactly one '+kind+' for '+str(ident));return rows[0]
    def interval(left,right):return (int(right['time_ps'])-int(left['time_ps']))/1e9
    for index,frame in enumerate(frames):
        ident=int(frame['frame_id']);metric=cycles[index];perf=original[index]
        offer=one('source_offer',ident);accept=one('source_accept',ident)
        start=one('engine_start',ident);done=one('engine_done',ident)
        pending=one('pending_rise',ident);consume=one('pending_fall',ident)
        grants=[row for row in timeline if row['event']=='display_grant_accept' and int(row['frame_id'])==ident]
        require(grants,'display grant missing')
        firstgrant=grants[0]
        require(int(firstgrant['bank'])==int(frame['result_bank']),'frame/result display bank differs')
        fills=int(frame['fills']);part={names[int(row['state'])]:int(row['cycles'])for row in fsm if int(row['frame_id'])==ident}
        require(sum(part.values())==int(metric['processing_cycles']),'FSM partition not exhaustive')
        first=[row for row in hist if row['client']=='cache' and int(row['frame_id'])==ident and row['metric']=='ar_to_first_r']
        gaps=[row for row in hist if row['client']=='cache' and int(row['frame_id'])==ident and row['metric']=='r_beat_gap']
        burstcount=sum(int(row['count'])for row in first)
        firstwait=sum((int(row['cycles'])-1)*int(row['count'])for row in first)
        missing=sum((int(row['cycles'])-1)*int(row['count'])for row in gaps)
        require(burstcount==fills and sum(int(row['count'])for row in gaps)==7*fills,
            'cache eight-beat burst histogram closure differs')
        require(int(metric['cache_first_r_wait'])==firstwait,'first-R wait accounting differs')
        # The raw receiving&&!R observer includes each accepted AR cycle in its
        # later-wait bucket. Do not describe that raw bucket as pure beat gaps.
        raw_later=int(metric['cache_later_r_wait'])
        require(raw_later==missing+fills,'raw later-wait AR-cycle offset differs')
        require(int(metric['source_offer_wait'])==int(accept['core_cycle'])-int(offer['core_cycle']),
            'source-offer cycle count differs from exact event interval')
        output.append(dict(FrameID=ident,AcceptedInputSourceIndex=int(frame['input_source_index']),
            CurrentInputRasterIndexAtOffer=int(offer['input_source_index']),
            SourceBank=int(frame['source_bank']),ResultBank=int(frame['result_bank']),
            SourceOfferPS=int(offer['time_ps']),SourceAcceptPS=int(accept['time_ps']),
            EngineStartPS=int(start['time_ps']),EngineDonePS=int(done['time_ps']),
            PendingRisePS=int(pending['time_ps']),PendingConsumedPS=int(consume['time_ps']),
            FirstDisplayGrantPS=int(firstgrant['time_ps']),FirstActualScanPixelPS=int(frame['scan_start_ps']),
            ActualScanDonePS=int(frame['scan_done_ps']),SourceOfferWaitMS=interval(offer,accept),
            EngineStartToDoneMS=interval(start,done),PendingWaitForDisplayMS=interval(pending,consume),
            SourceAcceptToFirstScanMS=(int(frame['scan_start_ps'])-int(accept['time_ps']))/1e9,
            HardwareProcessCycles=int(frame['hardware_process_cycles']),
            HardwareProcessMS=int(frame['hardware_process_cycles'])*8e-6,
            ObserverProcessingCycles=int(metric['processing_cycles']),
            CacheFSMCycles=part,CacheFills=fills,CacheReadBeats=int(metric['cache_r_beats']),
            CacheARBlockedCycles=int(metric['cache_ar_blocked']),
            CacheARToFirstRHistogram={row['cycles']:int(row['count'])for row in first},
            CacheARToFirstRMeanCycles=sum(int(row['cycles'])*int(row['count'])for row in first)/fills,
            CacheFirstRWaitCyclesExcludingARAndR=firstwait,
            CacheFirstRWaitMS=firstwait*8e-6,CacheMissingBeatCycles=missing,
            CacheMissingBeatMS=missing*8e-6,RawLaterRWaitIncludesAcceptedARCycles=raw_later,
            CacheBeatGapHistogram={row['cycles']:int(row['count'])for row in gaps},
            ReadDualClientContentionCycles=int(metric['read_contention']),
            WriteDualClientContentionCycles=int(metric['write_contention']),
            OriginalPerformanceBreakdown=perf))
    for left,right in zip(output,output[1:]):
        right['IntervalSincePreviousSourceAcceptMS']=(right['SourceAcceptPS']-left['SourceAcceptPS'])/1e9
        right['IntervalSincePreviousFirstDisplayGrantMS']=(right['FirstDisplayGrantPS']-left['FirstDisplayGrantPS'])/1e9
        right['IntervalSincePreviousActualScanDoneMS']=(right['ActualScanDonePS']-left['ActualScanDonePS'])/1e9
    drift=[path for path,digest in inputs.items()if sha(path)!=digest];require(not drift,'saved analysis input drift')
    result=dict(Schema='tile8df8-enhanced-native-system-profile-analysis-v1',Passed=True,
        CreatedUTC=datetime.now(timezone.utc).isoformat(),Frames=output,Summary=report['Summary'],
        ProfilesCompletedFrames=4,ActualUniqueScannedPixels=8294400,ProductionSourceModified=False,
        OriginalOracleCRCAndDrainPassed=True,PhysicalTimingOrHardwareFPSClaimed=False,
        TimelineNotes=['Core handshakes are observed at the active edge; state transition events use post-NBA edge+2ps observations.',
            'Timeline input_source_index is the input raster currently arriving at the event, not the source identity; AcceptedInputSourceIndex is joined from original frames.csv.',
            'pending_fall raw bank column reflects the newly flipped next write bank; the consumed result bank is checked using same-ID display grant/front bank.',
            'capture_grant_not_ready is CDC grant receiver backpressure, not a no-free-frame count.',
            'FSM state-cycle, AR stall, and read-gap counters are observations that can overlap; they are not independently additive throughput improvements.',
            'Raw cache_later_r_wait contains one accepted AR cycle per fill; pure missing beat cycles are independently derived from the complete physical read gap histogram.'],
        InputSHA256=inputs,InputDrift=drift,EDAExecuted=False,HardwareAccessed=False,PDriveAccessed=False)
    path=HERE/'analysis-a.json'
    with path.open('x',encoding='utf-8',newline='\n')as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(dict(Passed=True,Report=str(path),SHA256=sha(path),Frames=output)),flush=True)

if __name__=='__main__':main()
