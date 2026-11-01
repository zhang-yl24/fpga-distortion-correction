"""Candidate-bound CPU-only camera CDC inventory and native query planner.

Counts and placement come from the final functional export. This bounded
checker does not certify universal CDC coverage, analog MTBF or board release.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import re

import audit_camera_vga_physical as physical

FINAL_SHA = 'daa2a9221238d09398ba325acef561b604dcb5643571301ba8831f76736dfd9f'
PROJECT = Path(__file__).resolve().parents[1]
CAP = 'system/input_link/input_dma/capture/'
FF_TYPES = {'V_FFASYN', 'V_FFSYN'}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def canon(value):
    return value.replace('\\', '').replace(' ', '')


def one(values, label):
    require(len(values) == 1, label + ' must resolve exactly once: ' + str(values))
    return values[0]


def native_parent(name):
    return re.sub(r'/(?:FFAPP?\d*|FF\d+)/FF$', '', name)


class Graph:
    def __init__(self, graph):
        self.g = graph
        self.cells = graph['Cells']
        self.ff = {n: c for n, c in self.cells.items() if c['Primitive'] in FF_TYPES}
        self.refs, self.outputs = defaultdict(list), defaultdict(list)
        for name, cell in self.cells.items():
            kind, ports = cell['Primitive'], cell['Ports']
            pins = ({'Q'} if kind in FF_TYPES else
                    {'Z', 'Z5', 'COUT'} if kind == 'V_LUT6CARRY' else
                    {'Z'} if kind in ('V_BUF', 'V_INV') else
                    {'O'} if kind in ('V_IBUF', 'V_INBUFG', 'V_INBUFGDS') else
                    {'CLKOUT'} if kind == 'V_USCM' else
                    {'CLKOUT0', 'CLKOUT1', 'CLKOUT2', 'CLKOUT3', 'LOCK'} if kind == 'V_GPLL' else set())
            for pin, net in ports.items():
                if net:
                    self.refs[net].append((name, pin))
                    if pin in pins:
                        self.outputs[net].append((name, pin))
        self.clock_cache = {}

    def by_q(self, value):
        return one([n for n, c in self.ff.items() if canon(c['Ports']['Q']) == value], value)

    def first_prefix(self, prefix):
        return one([n for n in self.ff if n.startswith(prefix) and '/FFAPP' not in n], prefix)

    def driver(self, net):
        return one(self.outputs[net], 'driver of ' + net)

    def clock(self, net, visited=()):
        if net in self.clock_cache:
            return self.clock_cache[net]
        require(net not in visited, 'clock cycle')
        if net in ('clk_27m', 'cam_pclk'):
            result = {'Domain': {'clk_27m':'board27', 'cam_pclk':'camera_pclk'}[net], 'Root':net, 'Trace':[]}
        else:
            name, pin = self.driver(net)
            cell = self.cells[name]
            kind, ports = cell['Primitive'], cell['Ports']
            row = {'Cell':name, 'Primitive':kind, 'Pin':pin, 'Net':net}
            if kind == 'V_GPLL' and pin == 'CLKOUT0':
                domain = 'pixel_clk' if name.startswith('video_pll/') else ('ddrphy_sysclk' if '/ddrphy_gpll/' in name else None)
                require(domain is not None, 'unreviewed PLL clock ' + name)
                result = {'Domain':domain, 'Root':name + '/' + pin, 'Trace':[row]}
            else:
                if kind == 'V_USCM':
                    require(cell['Parameters']['USCM_MODE'] == '"BUF_A"' and pin == 'CLKOUT', 'dynamic clock mux')
                    upstream = ports['CLK0']
                elif kind == 'V_BUF' and pin == 'Z':
                    upstream = ports['I']
                elif kind in ('V_IBUF', 'V_INBUFG') and pin == 'O':
                    upstream = ports['I']
                else:
                    raise ValueError('unreviewed clock driver ' + name + ' ' + kind)
                parent = self.clock(upstream, visited + (net,))
                result = {**parent, 'Trace':[row] + parent['Trace']}
        self.clock_cache[net] = result
        return result

    def clear_expression(self, net, visited=()):
        require(net not in visited, 'clear buffer cycle')
        if net in ("1'b0", "1'b1"):
            return ('constant', int(net[-1]))
        ds = self.outputs.get(net, [])
        if len(ds) == 1:
            name, pin = ds[0]
            c = self.cells[name]
            if c['Primitive'] in ('V_BUF', 'V_INV') and pin == 'Z':
                e = self.clear_expression(c['Ports']['I'], visited + (net,))
                return e if c['Primitive'] == 'V_BUF' else ('not', e)
        return ('net', net)

    def constant_one(self, net, visited=()):
        require(net not in visited, 'constant source cycle')
        if net == "1'b1":
            return True
        if net == "1'b0":
            return False
        name, pin = self.driver(net)
        c = self.cells[name]
        if c['Primitive'] == 'V_BUF' and pin == 'Z':
            return self.constant_one(c['Ports']['I'], visited + (net,))
        return c['Primitive'] == 'V_LUT6CARRY' and pin in ('Z', 'Z5') and c['Parameters'].get('INIT') == "64'hFFFFFFFFFFFFFFFF"

    def lut_gate(self, name, output, first, release):
        c = self.cells[name]
        require(c['Primitive'] == 'V_LUT6CARRY' and output in ('Z', 'Z5'), 'unsupported interstage cell')
        p = c['Ports']
        names = sorted({p['I' + str(i)] for i in range(6)} - {"1'b0", "1'b1"})
        require(first in names and release in names, 'first stage/local release absent from LUT')
        init = int(c['Parameters']['INIT'][4:], 16)
        def evaluate(port, values):
            size = 5 if port == 'Z5' else 6
            return (init >> sum(values[p['I' + str(i)]] << i for i in range(size))) & 1
        for bits in itertools.product((0, 1), repeat=len(names)):
            values = dict(zip(names, bits)); values.update({"1'b0":0, "1'b1":1})
            require(evaluate(output, values) == values[first] & values[release], 'interstage LUT differs from first AND release')
            for other in ('Z', 'Z5'):
                if other != output and p.get(other):
                    changed = dict(values); changed[first] ^= 1
                    require(evaluate(other, values) == evaluate(other, changed), 'first stage escapes via shared LUT output')
            require(not p.get('COUT'), 'unreviewed interstage carry fanout')
        return {'Cell':name, 'Output':output, 'Truth':'first_stage AND local_release',
                'ReleaseNet':release, 'ExhaustiveAssignments':2 ** len(names),
                'FirstStageInputPins':[p0 for p0, n in p.items() if n == first]}

    def chain(self, first, second, label, release=None, replicated=False):
        a, b = self.ff[first], self.ff[second]
        pa, pb = a['Ports'], b['Ports']
        ca, cb = self.clock(pa['CK']), self.clock(pb['CK'])
        require(first != second and ca['Domain'] == cb['Domain'] and ca['Root'] == cb['Root'], 'different stage clock domains')
        require(pa['CE'] == pb['CE'] == "1'b1", 'nonconstant synchronizer CE')
        require(self.clear_expression(pa['SR']) == self.clear_expression(pb['SR']), 'different stage clear functions')
        require(a['Primitive'] == b['Primitive'] and a['Parameters'] == b['Parameters'], 'different stage initial/reset values')
        logic = None
        if pb['D'] == pa['Q']:
            allowed = {(first, 'Q'), (second, 'D')}
        else:
            require(release is not None, 'interstage combinational logic without approved local release')
            n, pin = self.driver(pb['D'])
            logic = self.lut_gate(n, pin, pa['Q'], release)
            allowed = {(first, 'Q')} | {(n, p) for p in logic['FirstStageInputPins']}
            require(set(self.refs[pb['D']]) == {(n, pin), (second, 'D')}, 'interstage LUT output has extra fanout')
        if not replicated:
            require(set(self.refs[pa['Q']]) == allowed, 'first-stage functional fanout escapes: ' + label)
        la, lb = self.g['FFPlacement'][first], self.g['FFPlacement'][second]
        query = []
        if la != lb:
            endpoints = ([logic['Cell'].rsplit('/', 2)[0] + '/' + pin for pin in logic['FirstStageInputPins']]
                         if logic else [native_parent(second) + '/D'])
            for endpoint in endpoints:
                query.append({'Label':label, 'Source':native_parent(first) + '/CLK', 'Endpoint':endpoint,
                              'Clock':ca['Domain'], 'ExpectedKind':['setup','hold'], 'ExpectedCorners':['slow','fast'],
                              'Purpose':'ordinary first-to-second-stage interstage timing; not analog MTBF',
                              'EndpointResolutionRequired':True})
        return {'Label':label, 'First':first, 'Second':second, 'FirstPorts':pa, 'SecondPorts':pb,
                'FirstPlacement':la, 'SecondPlacement':lb, 'SameSite':la['Site']==lb['Site'], 'SameBLE':la==lb,
                'DestinationClock':ca['Domain'], 'ClockRootsIdentical':True, 'ClearFunctionsEquivalent':True,
                'FirstStageOnlyFeedsSecondStage':not replicated, 'InterstageLogic':logic, 'NativeQueries':query}


def gray_structures(g):
    groups = defaultdict(dict)
    for name in g.ff:
        m = re.match(r'(.+/)(rd_gray_w1|wr_gray_r1)\[(\d+)\]/', name)
        if m and '/FFAPP' not in name:
            key = (m[1], m[2]); bit = int(m[3])
            require(bit not in groups[key], 'duplicate Gray first stage')
            groups[key][bit] = name
    require(groups and {k[0] for k in groups} == {'system/display_fifo/', CAP+'pixels/'}, 'unexpected/missing FIFO hierarchy')
    result = []
    for (prefix, stage), bits in sorted(groups.items()):
        width = max(bits)+1
        require(set(bits)==set(range(width)), 'noncontiguous Gray pointer bits')
        second_stage = stage[:-1] + '2'
        direction = 'rd' if stage.startswith('rd') else 'wr'
        for bit, first in sorted(bits.items()):
            second = g.by_q(prefix+second_stage+f'[{bit}]')
            row = g.chain(first, second, prefix+stage+f'[{bit}]')
            require(row['SameBLE'], 'Gray stages not packed into same native BLE')
            source, pin = g.driver(g.ff[first]['Ports']['D'])
            require(source in g.ff and pin=='Q', 'Gray origin not registered')
            expected = prefix+direction+('_binary' if bit==width-1 else '_gray')+f'[{bit}]'
            require(canon(g.ff[first]['Ports']['D'])==expected, 'Gray bit source identity mismatch')
            source_clock = g.clock(g.ff[source]['Ports']['CK'])['Domain']
            require(source_clock!=row['DestinationClock'], 'Gray chain not crossing clocks')
            row.update(Source=source, SourcePorts=g.ff[source]['Ports'], SourceClock=source_clock, Width=width, Bit=bit,
                       Group=prefix+stage, NativeEndpoint=native_parent(first)+'/D')
            result.append(row)
    return result


def scalar_structures(g):
    rows = []
    direct = [('board_failed_core[0]/','board_failed_core[1]')]
    for p in ('camera_configuration/bus/', 'hdmi_configuration/bus/'):
        direct += [(p+x+'_meta/',p+x+'_sampled') for x in ('scl','sda')]
    direct += [('system/'+x+'[0]/','system/'+x+'[1]') for x in
               ('done_sync','grant_ack_sync','request_sync','scan_abort_sync','scan_failed_sync')]
    direct += [('system/scan_enable_sync[1]/','system/scan_enable_sync[1]')]
    direct += [('system/output_video/'+x+'[0]/','system/output_video/'+x+'[1]') for x in ('done_ack_sync','grant_sync')]
    for prefix, q in direct:
        rows.append(g.chain(g.first_prefix(prefix),g.by_q(q),q))
    gated = [('ddr_ready_ref[0]','nt_led[1]','ref_reset[1]'),
             ('video_lock_ref[0]','nt_led[2]','ref_reset[1]'),
             ('system_failed_ref[0]','system_failed_ref[1]','ref_reset[1]'),
             ('processed_bit_ref[0]','nt_led[6]','ref_reset[1]'),
             ('captured_bit_ref[0]','nt_led[5]','ref_reset[1]')]
    gated += [(CAP+x+'[0]',CAP+x+'[1]',CAP+'cam_reset[1]') for x in ('ack_sync','grant_sync','enable_cam')]
    gated += [(CAP+'done_sync[0]',CAP+'done_sync[1]','system/input_link/input_dma/sys_reset[1]')]
    for first_q, second_q, release in gated:
        reset = g.by_q(release)
        rows.append(g.chain(g.by_q(first_q),g.by_q(second_q),first_q,g.ff[reset]['Ports']['Q']))
    return rows


def reset_structures(g):
    rows, replicated = [], []
    for first in sorted(g.ff):
        if first.startswith('u_ddr3_test_h/') or '/FFAPP' in first or not re.search(r'reset(?:_sync)?\[0\]/',first):
            continue
        a = g.ff[first]; pa = a['Ports']
        require(g.constant_one(pa['D']), 'reset release first stage does not shift one')
        require(a['Primitive']=='V_FFASYN' and a['Parameters'].get('INIT')=="1'b0" and a['Parameters'].get('SET_RESET')=='"RESET"', 'reset stage not async clear')
        loads = [(n,p) for n,p in g.refs[pa['Q']] if (n,p)!=(first,'Q')]
        require(loads and all(n in g.ff and p=='D' for n,p in loads),'reset first stage has non-second-stage fanout')
        chain_rows = [g.chain(first,n,first.rsplit('/',3)[0],replicated=len(loads)>1) for n,p in loads]
        if len(loads)==1:
            rows.extend(chain_rows)
        else:
            require(first.startswith('system/bank_core/engine/core/reset_sync[0]/'),'unexpected replicated reset family')
            replicated.append({'First':first,'SecondStageCount':len(chain_rows),'FirstStageOnlyFeedsSecondStages':True,
                               'SeparateReleaseEdgesPossible':True,'Chains':chain_rows})
    require(rows and replicated,'missing reset release structures')
    return rows, replicated


def constraint_inventory(path):
    text = Path(path).read_text(encoding='utf-8-sig')
    lines=[]; periods={}
    for i,line in enumerate(text.splitlines(),1):
        if line.startswith(('create_clock','create_generated_clock','set_max_delay','set_min_delay','set_false_path','set_input_delay')):
            lines.append({'Line':i,'Text':line})
        m=re.fullmatch(r'create_clock -name (board27|camera_pclk) -period ([\d.]+) \[get_ports (\w+)\]',line)
        if m:periods[m[1]]=float(m[2])
    require(set(periods)=={'board27','camera_pclk'},'board/camera clock constraints absent')
    require('create_generated_clock -name pixel_clk -source [get_ports clk_27m] -multiply_by 11 -divide_by 4 [get_pins video_pll/clkout0]' in text,'pixel clock ratio changed')
    require('create_clock -name {ref_clk} [get_ports {clk_p}] -period {8.0}' in text,'DDR reference period changed')
    periods.update(pixel_clk=periods['board27']*4/11,ddrphy_sysclk=8.0)
    pairs={}
    for row in lines:
        m=re.fullmatch(r'set_max_delay -datapath_only -from \[get_clocks \{(\w+)\}\] -to \[get_clocks \{(\w+)\}\] ([\d.]+)',row['Text'])
        if m:pairs[(m[1],m[2])]={'BoundNS':float(m[3]),'Line':row['Line']}
    return {'Path':str(Path(path).resolve()),'SHA256':sha(path),'RelevantStatements':lines,'PeriodsNS':periods},pairs


def max_delay_paths(path, endpoints):
    selected=[]; section=None; block=[]; line0=0; counts=Counter(); maxima={}
    def finish():
        if not block or section!='set_max_delay(setup)':return
        t=''.join(block)
        if 'Timing Exception  :  MaxDelay Path' not in t:return
        def field(pattern,label):return one(re.findall(pattern,t,re.M),label)
        corner=field(r'^Path Type\s*:\s*max \((slow|fast) corner\)\s*$','max corner')
        endpoint=field(r'^Endpoint\s*:\s*(\S+)\s*$','max endpoint')
        slack=field(r'^ Slack \((MET|VIOLATED)\)\s+([-+]?\d+(?:\.\d+)?)\s*$','max slack')
        arrival=float(field(r'^ Data arrival time\s+([-+]?\d+(?:\.\d+)?)\s+Logic Levels:.*$','max arrival'))
        bound=float(field(r'^Timing Exception\s*:\s*MaxDelay Path ([-+]?\d+(?:\.\d+)?)ns -datapath_only\s*$','max bound'))
        require(slack[0]=='MET' and float(slack[1])>=0,'reported max-delay violation')
        counts[corner]+=1; maxima[corner]=max(maxima.get(corner,0),arrival)
        if endpoint in endpoints:
            selected.append({'Source':field(r'^Startpoint\s*:\s*(\S+)\s*$','max source'),'Endpoint':endpoint,'Corner':corner,
                             'BoundNS':bound,'SlackNS':float(slack[1]),'ArrivalNS':arrival,'ReportLine':line0,
                             'PathSHA256':hashlib.sha256(t.encode()).hexdigest()})
    with Path(path).open(encoding='gb18030',errors='strict') as stream:
        for line_number,line in enumerate(stream,1):
            m=re.fullmatch(r'\| Exception type\s*:\s*(\S+)\s*\n?',line)
            if m:finish();block=[];section=m[1]
            elif line.startswith('Startpoint'):finish();block=[line];line0=line_number
            elif block:block.append(line)
    finish()
    require(counts and set(counts)=={'slow','fast'},'no two-corner max-delay report')
    return selected,{'ReportedMaxDelayPathsPerCorner':dict(counts),'MaximumReportedArrivalNS':maxima,'ReportedChecksNonnegative':True}


def audit(export_dir, final_dir, output_dir):
    export_dir,final_dir,output_dir=map(lambda p:Path(p).resolve(),(export_dir,final_dir,output_dir))
    netlist=export_dir/'generate_netlist/camera_vga_output_top_sim.v'
    er=export_dir/'result.json';fr=final_dir/'result.json'
    export=json.loads(er.read_text(encoding='utf-8-sig'));final=json.loads(fr.read_text(encoding='utf-8-sig'))
    for stage,receipt in ((export_dir,export),(final_dir,final)):
        require(receipt['ExecutionPassed'] and receipt['ExitCode']==0 and receipt['InputDrift']==[] and receipt['Diagnostics']==[],'native receipt failed')
        require(receipt['SourceADFSHA256']==receipt['ResultADFSHA256']==sha(stage/'input.adf')==FINAL_SHA,'wrong final candidate ADF')
    require(sha(netlist)==export['Netlist']['SHA256'],'functional export receipt differs')
    exceptions=final_dir/'camera_vga_output_top_exception.rtr'
    require(sha(exceptions)==final['Artifacts'][exceptions.name],'exception report receipt differs')
    fdc=PROJECT/'work/camera-vga-output/pds-20261031-a/compiled/board/camera-vga-output-diagnostic.fdc'
    inputs=[netlist,er,fr,exceptions,fdc,Path(__file__),Path(physical.__file__),
            PROJECT/'board/camera_vga_output_top.v',PROJECT/'rtl/video_async_fifo.v',
            PROJECT/'rtl/experimental/dvp_rgb565_capture_cdc.v',PROJECT/'rtl/experimental/camera_vga_input_dma.v',
            PROJECT/'rtl/experimental/camera_vga_video_system.v',PROJECT/'rtl/experimental/ddr_video_output_1080_board.v']
    watched={str(p.resolve()):sha(p) for p in inputs}
    for path,digest in watched.items():
        if path in export['InputSHA256']:require(export['InputSHA256'][path]==digest,'source differs from final export closure')
    graph=Graph(physical.functional(netlist))
    gray=gray_structures(graph);scalar=scalar_structures(graph);resets,replicas=reset_structures(graph)
    constraints,pairs=constraint_inventory(fdc)
    paths,stats=max_delay_paths(exceptions,{r['NativeEndpoint'] for r in gray})
    gray_groups=[];missing=[]
    for group in sorted({r['Group'] for r in gray}):
        bits=[r for r in gray if r['Group']==group]
        require(len({(r['SourceClock'],r['DestinationClock']) for r in bits})==1,'Gray bus crosses inconsistent domains')
        source,dest=bits[0]['SourceClock'],bits[0]['DestinationClock']
        require((source,dest) in pairs,'Gray crossing lacks max-delay constraint')
        required={r['NativeEndpoint'] for r in bits}
        for corner in ('slow','fast'):
            records=[p for p in paths if p['Corner']==corner and p['Endpoint'] in required]
            seen=Counter(p['Endpoint'] for p in records)
            missing += [{'Group':group,'Corner':corner,'Endpoint':p} for p in sorted(required-set(seen))]
            require(all(n==1 for n in seen.values()),'ambiguous Gray endpoint timing paths')
            for record in records:
                bit=one([r for r in bits if r['NativeEndpoint']==record['Endpoint']],'Gray target bit')
                require(record['Source']==native_parent(bit['Source'])+'/CLK','Gray native source differs from registered origin')
                require(record['BoundNS']==pairs[(source,dest)]['BoundNS'] and 0<=record['ArrivalNS']<constraints['PeriodsNS'][source],'Gray delay exceeds source period')
            gray_groups.append({'Group':group,'Width':len(bits),'Corner':corner,'SourceClock':source,'DestinationClock':dest,
                                'SourcePeriodNS':constraints['PeriodsNS'][source],'Constraint':pairs[(source,dest)],
                                'CoverageComplete':set(seen)==required,'MaximumArrivalNS':max([p['ArrivalNS'] for p in records],default=None),
                                'ConservativeSkewUpperBoundNS':max([p['ArrivalNS'] for p in records],default=None),'Paths':records})
    queries=[q for row in scalar+resets+[c for r in replicas for c in r['Chains']] for q in row['NativeQueries']]
    # Query every non-BLE-local stage pair separately; union reports may suppress sources.
    unique={ (q['Source'],q['Endpoint']):q for q in queries }
    queries=[unique[k] for k in sorted(unique)]
    gray_queries=[]
    for endpoint in sorted({r['Endpoint'] for r in missing}):
        bit=one([r for r in gray if r['NativeEndpoint']==endpoint],'missing Gray bit')
        gray_queries.append({'Label':bit['Label'],'Source':native_parent(bit['Source'])+'/CLK',
                             'Endpoint':endpoint,'SourceClock':bit['SourceClock'],
                             'DestinationClock':bit['DestinationClock'],
                             'ExpectedCorners':['slow','fast'],'ExpectedException':'MaxDelay Path 8ns -datapath_only',
                             'Purpose':'fill missing actual Gray path coverage; inspect normal and exception reports'})
    query={'Schema':'camera-vga-cdc-query-plan-v1','InputADFSHA256':FINAL_SHA,'SourceADF':str(final_dir/'input.adf'),
           'Queries':queries,'GrayCoverageQueries':gray_queries,'MissingGrayCases':missing,'RequiresExactPairReports':True,
           'ExpectedCasesPerQuery':4,'EDAExecuted':False,'HardwareAccessed':False}
    result={'Schema':'camera-vga-cdc-structural-v1','AuditPassed':True,'AuditedUTC':datetime.now(timezone.utc).isoformat(),
            'CandidateADFSHA256':FINAL_SHA,'InputSHA256':watched,'GrayBitSynchronizers':gray,'ScalarSynchronizers':scalar,
            'ResetReleaseStructure':{'PackedOrSingleSecondStageChains':resets,'ReplicatedSecondStageTrees':replicas},
            'ClockTopology':graph.clock_cache,'ConstraintInventory':constraints,'GrayPhysicalGroups':gray_groups,
            'Summary':{'GrayBits':len(gray),'ScalarChains':len(scalar),'ScalarSameSite':sum(r['SameSite'] for r in scalar),
                       'ScalarSameBLE':sum(r['SameBLE'] for r in scalar),'ResetChains':len(resets),
                       'ReplicatedResetTrees':len(replicas),'ReplicatedResetSecondStages':sum(r['SecondStageCount'] for r in replicas),
                       'GrayPhysicalCoverageComplete':not missing,'NativeInterstageQueryCount':len(queries),
                       'NativeGrayCoverageQueryCount':len(gray_queries),**stats},
            'StartupReview':{'Evidence':'Current candidate source closure, actual two-stage nets and clear/clock topology',
                'PowerRelease':'20-bit power_count terminal detection registered into power_ready after key_reset_sync; global reset=reset_n AND power_ready.',
                'PipelineRelease':'8-second continuous camera_ready AND !camera_failed AND synchronized DDR/video ready AND TX ready; sticky pipeline_release.',
                'RuntimeFault':'Sticky board_failed/board_fault stops new admissions after board_failed_core; common pipeline reset does not reassert on runtime faults.',
                'DDRReady':'First-stage D is combinational ddr_init_done AND ddr_pll_lock gated by local release; two-stage synchronization does not prove freedom from all upstream glitches.',
                'BoardFaultBundle':'board_fault changes with sticky board_failed, then remains stable; core consumes after two-stage flag. Physical bundle bound alone is not universal protocol proof.',
                'CameraClock':'External camera_pclk; absent/stopped clock holds local release and capture idle. Independent clock-stop recovery is not claimed.',
                'UnusedTelemetry':'no_grant_s1/s2 counter outputs may be optimized away; no binary multi-bit coherence claim.'},
            'Scope':{'NativeInterstageTimingComplete':False,'AnalogMTBFProven':False,'AllCDCUniversallyProven':False,
                     'GrayDatapathBoundComplete':not missing,'HeldMailboxProtocol':'Static current RTL review; source/destination handshake simulation remains separate evidence.',
                     'DDRIPResetScope':'Existing candidate-specific reset proof remains separate; this inventory covers application reset chains.'},
            'HardwareAccessed':False,'EDAExecuted':False,'HardwareReleaseAllowed':False}
    require(all(sha(p)==digest for p,digest in watched.items()),'audit input drift')
    output_dir.mkdir(parents=True,exist_ok=True)
    for name,value in (('cdc-structure.json',result),('query-plan.json',query)):
        with (output_dir/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2);f.write('\n')
    body=['# Query fragment only; parent runner must bind final ADF and initialize native STA.']
    for i,q in enumerate(queries+gray_queries,1):
        body += [f'# {i}: {q["Label"]}',
                 'report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {'+q['Source']+'} -to {'+q['Endpoint']+'}']
    with (output_dir/'interstage-query-body.tcl').open('x',encoding='utf-8') as f:f.write('\n'.join(body)+'\n')
    print(json.dumps({'Output':str(output_dir),'AuditPassed':True,**result['Summary']}))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export-dir',type=Path,default=PROJECT/'work/camera-vga-output/export-final-20261031-a')
    p.add_argument('--final-dir',type=Path,default=PROJECT/'work/camera-vga-output/physical-final-report-20261031-a')
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();audit(a.export_dir,a.final_dir,a.output_dir)


if __name__=='__main__':main()
