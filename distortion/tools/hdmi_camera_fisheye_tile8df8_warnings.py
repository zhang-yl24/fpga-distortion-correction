"""Exact current fisheye source warnings and limited vendor compiler disposition.

Three readable source counters have independent proofs; unchanged protected
vendor IP has only the explicitly limited diagnostic acceptance. Native DDR,
pins/reset/CDC/ROM semantics/timing and actual display remain separate.
"""
import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

# Match the already bound producer runtime, without changing any verifier.
SITE=Path(__file__).resolve().parents[2]/'.venv/Lib/site-packages'
sys.path.insert(0,str(SITE))
import hdmi_camera_fisheye_tile8df8_build as build
import hdmi_camera_fisheye_tile8df8_protocol as protocol
import importlib

SELF=Path(__file__).resolve()
SCHEMA='hdmi-camera-fisheye-tile8df8-source-warning-review-v1'
INVENTORY=build.WORK/'source-warning-inventory-a.json'
INVENTORY_SHA='1c9a8e9abdb9afed3dc088f5888c3d19fa739d1f8e9d0ca94d550d3014802e97'
DRIVER='rtl/experimental/iic_dri_checked.v'
CONTROL='rtl/experimental/ms72xx_rearm_observed_ctl.v'
DDR_PARAMETERS_SHA='95e39e516343108c06d7ff878606f0f5a0bca8af96bee6eb0cf4434197775857'
VENDOR_BASIS='unchanged official vendor IP and compiler optimization, diagnostic SRAM experiment'
REDUCTIONS=((build.TOP,47,'cfg_wait_count',32,22),(build.TOP,172,'pclk_age',32,22),
    (DRIVER,93,'watchdog',32,17),
    (build.IP+'/rtl/mcdq_ctrl/ips2l_mcdq_dcp_buf_v1_2.vp',541,'cnt',7,6),
    (build.IP+'/rtl/ddrphy/ips2l_ddrphy_data_slice_wrcal_v1_10.vp',614,'delay_cnt',4,2))
require,sha,read,ref=build.require,build.sha,build.read,build.ref


def add(watched,path,expected=None):
    """Keep canonical identity and exact hashes for opaque compiled paths."""
    path=Path(path).absolute();require(path==path.resolve() and build.local_io(path).is_file(),'canonical build input required: '+str(path))
    actual=sha(path);require(expected is None or actual==expected,'fisheye input SHA differs: '+str(path))
    require(str(path) not in watched or watched[str(path)]==actual,'conflicting fisheye input SHA')
    watched[str(path)]=actual;return path


PUBLIC={
    'cfg_wait_count':{'Source':build.TOP,'Parameter':'CFG_SETTLE_CYCLES','Value':2700000,
        'Maximum':2699999,'Old':32,'New':22,'TokenCount':5,'Assignments':['0',"cfg_wait_count+1'b1"],
        'Uses':[
            'reg[31:0]cfg_wait_count=0;',
            'if(!global_reset_n)begincfg_wait_count<=0;cfg_ready<=0;end',
            "if(cfg_wait_count<CFG_SETTLE_CYCLES-1)cfg_wait_count<=cfg_wait_count+1'b1;"],
        'Guard':"elseif(!cfg_ready)beginif(cfg_wait_count<CFG_SETTLE_CYCLES-1)cfg_wait_count<=cfg_wait_count+1'b1;elsecfg_ready<=1;end"},
    'pclk_age':{'Source':build.TOP,'Parameter':'PCLK_STALE_REF_CYCLES','Value':2700000,
        'Maximum':2700000,'Old':32,'New':22,'TokenCount':8,'Assignments':['0','0','0',"pclk_age+1'b1"],
        'Uses':[
            'reg[31:0]pclk_age;',
            'if(!global_reset_n)beginpclk_activity_seen<=0;pclk_observed<=0;pclk_age<=0;end',
            'elseif(!ref_reset[1])beginpclk_activity_seen<=0;pclk_observed<=0;pclk_age<=0;end',
            'pclk_activity_seen<=pclk_activity_ref[1];pclk_observed<=1;pclk_age<=0;',
            "endelseif(pclk_age<PCLK_STALE_REF_CYCLES)pclk_age<=pclk_age+1'b1;",
            'wirepclk_stale=pclk_age>=PCLK_STALE_REF_CYCLES;'],
        'Guard':"elseif(pclk_activity_ref[1]!=pclk_activity_seen)beginpclk_activity_seen<=pclk_activity_ref[1];pclk_observed<=1;pclk_age<=0;endelseif(pclk_age<PCLK_STALE_REF_CYCLES)pclk_age<=pclk_age+1'b1;"},
    'watchdog':{'Source':DRIVER,'Parameter':'TIMEOUT_CYCLES','Value':100000,
        'Maximum':99999,'Old':32,'New':17,'TokenCount':6,'Assignments':['0','0','watchdog+1'],
        'Uses':[
            'reg[31:0]divider,watchdog,complete_count;',
            'scl_low<=0;sda_low<=0;divider<=0;watchdog<=0;complete_count<=0;',
            'busy<=0;divider<=0;watchdog<=0;scl_low<=0;sda_low<=0;',
            'endelseif(watchdog>=TIMEOUT_CYCLES-1)begin',
            'watchdog<=watchdog+1;'],
        'Guard':"endelseif(watchdog>=TIMEOUT_CYCLES-1)beginscl_low<=0;sda_low<=0;busy<=0;transaction_failed<=1;error_code<=4'hf;state<=IDLE;endelsebeginwatchdog<=watchdog+1;"}}


def uncomment(text):
    return re.sub(r'/\*.*?\*/|//[^\r\n]*',lambda m:'\n'*m[0].count('\n'),text,flags=re.S)


def compact(text):return re.sub(r'\s+','',uncomment(text))


def parameters(text):
    """Preserve every elaborated value, including vendor strings/reals/bitvectors."""
    rows={};name=None;values=[]
    for line in text.splitlines()+['']:
        match=re.fullmatch(r'I: Module instance \{([^}]+)\} parameter value:',line)
        if name is not None and (not line.startswith('    ') or match):
            require(name not in rows and values,'duplicate/empty elaborated parameter block')
            require(len(values)==len({v.split(' = ',1)[0] for v in values}),'duplicate elaborated parameter')
            rows[name]=values;name=None;values=[]
        if match:name=match[1]
        elif name is not None:
            require(re.fullmatch(r'    \w+ = .+',line) is not None,'unparsed elaborated parameter')
            values.append(line.strip())
    return rows


def integer_parameters(block):
    result={}
    for row in block:
        match=re.fullmatch(r"(\w+) = (\d+)'b([01]+) \((\d+)'d(\d+)\)",row)
        require(match is not None,'integer parameter encoding differs')
        key,bits,binary,decimal_bits,decimal=match.groups()
        require(int(bits)==int(decimal_bits)==len(binary) and int(binary,2)==int(decimal),
                'elaborated binary/decimal parameter mismatch')
        result[key]=int(decimal)
    return result


def counter_contract(source,name):
    spec=PUBLIC[name];text=uncomment(source);flat=compact(source)
    uses=[{'Line':i,'Text':line.strip()}for i,line in enumerate(text.splitlines(),1)
          if re.search(r'\b'+name+r'\b',line)]
    require([re.sub(r'\s+','',r['Text']) for r in uses]==spec['Uses'],
            'counter assignment/use inventory differs: '+name)
    require(len(re.findall(r'\b'+name+r'\b',text))==spec['TokenCount'],
            'additional counter use: '+name)
    assignments=re.findall(re.escape(name)+r'<=([^;]+);',flat)
    require(assignments==spec['Assignments'] and flat.count(spec['Guard'])==1,
            'counter guarded next-state differs: '+name)
    if name=='watchdog':
        require(flat.count('if(state==IDLE)beginbusy<=0;divider<=0;watchdog<=0;')==1
            and flat.count('elseif(state==SUCCESS_HOLD)begin')==1,
            'watchdog idle reset or success hold priority differs')
    return {'AllAssignmentAndUseSites':uses,'NonblockingAssignmentRHS':assignments,
        'TokenOccurrences':spec['TokenCount'],'GuardedIncrementVerified':True,
        'DeclarationBits':spec['Old'],'ResetValue':0,'ImplicitHoldReviewed':True,
        'ResetAssumption':'Coordinated reset has asserted; no claim about an unreset unknown RTL state.'}


@lru_cache(maxsize=16)
def enumerate_bound(maximum,old_bits,new_bits):
    """Exhaust all reachable values with a conservative reset/hold/increment relation.

    At every value every reset and hold choice is allowed, and an increment is
    allowed iff below maximum. These choices overapproximate the reviewed RTL
    control states; no input traffic or eventual reset assumption is required.
    Both threshold comparisons and all three successor values are compared in
    original and reduced unsigned arithmetic. The terminal value is included.
    """
    require(type(maximum)is int and type(old_bits)is int and type(new_bits)is int
        and 0<=maximum<(1<<new_bits) and 0<new_bits<old_bits<=64,
        'terminal sentinel does not fit reduction')
    original_mask=(1<<old_bits)-1;reduced_mask=(1<<new_bits)-1
    for current in range(maximum+1):
        wide=current&original_mask;narrow=current&reduced_mask
        require(wide==narrow and (wide<maximum)==(narrow<maximum)
            and (wide>=maximum)==(narrow>=maximum),'comparison differs after reduction')
        advanced=wide+1 if wide<maximum else wide
        reduced_advanced=(narrow+1)&reduced_mask if narrow<maximum else narrow
        require(advanced==reduced_advanced and 0<=advanced<=maximum
            and (wide&original_mask)==(narrow&reduced_mask),'reachable successor overflows')
        # Reset successor is 0 at both widths; hold is checked above. Advancing
        # from every value below maximum also proves reachability from reset 0.
    return {'ReachableMinimum':0,'ReachableMaximum':maximum,'RequiredBits':max(1,maximum.bit_length()),
        'ReducedUnsignedMaximum':reduced_mask,'ReachableValuesEnumerated':maximum+1,
        'ResetHoldAdvanceTransitionsChecked':3*(maximum+1),
        'ThresholdComparisonsChecked':2*(maximum+1),'TerminalSentinelIncluded':True,
        'AllReachableUnsignedValuesEqualAtBothWidths':True,
        'InductiveClosureAndResetBaseVerified':True,'IndependentSourceRangeProof':True}


def source_binding(plan,work,name,watched,original_sha=None,compiled_sha=None):
    rows=[r for r in plan['CompiledInputs'] if r['Source']==name]
    require(len(rows)==1,'unique frozen/compiled source required: '+name)
    row=rows[0];source=build.ROOT/name;compiled=work/'compiled'/name
    require(row['CompiledPath']==str(compiled),'compiled source path differs')
    add(watched,source,row['OriginalSHA256']);add(watched,compiled,row['CompiledSHA256'])
    require(original_sha is None or row['OriginalSHA256']==original_sha,'reviewed original source SHA differs: '+name)
    require(compiled_sha is None or row['CompiledSHA256']==compiled_sha,'reviewed compiled source SHA differs: '+name)
    expected,changes=build.compiled_source(name,build.local_io(source).read_bytes(),work,plan['RepoAlias'])
    require(build.local_io(compiled).read_bytes()==expected and row['Changes']==changes,
            'compiled transformation differs from frozen original: '+name)
    return {'Source':name,'Original':ref(source),'Compiled':ref(compiled),'Changes':changes}


def vendor_basis(plan,work,blocks,compile_text,watched):
    base_path=build.ROOT/build.BASE_MANIFEST;add(watched,base_path,build.BASE_MANIFEST_SHA)
    base=read(base_path);build.source_names(base)
    idf_sha=base['SourceSHA256'].get(build.IDF)
    require(idf_sha is not None,'DDR IDF absent from checked baseline')
    source_binding(plan,work,build.IDF,watched,idf_sha,idf_sha)
    idf=build.ROOT/build.IDF;root=ET.fromstring(idf.read_bytes());node=root.find('file_list/source')
    require(node is not None,'vendor IDF source list absent')
    names=[build.IP+'/'+build.paths.relative_name(f.get('pathname')) for f in node.findall('file')]
    require(len(names)==len(set(names))==74 and set(names)==set(plan['SourceRoles']['IDFExpandedSources']),
            'vendor expanded source inventory differs')
    rows=[]
    for name in [build.IDF]+names:
        expected=base['SourceSHA256'].get(name)
        require(expected is not None,'vendor body missing from checked baseline manifest')
        row=source_binding(plan,work,name,watched,expected,expected)
        require(row['Changes']==[],'vendor body must remain byte-for-byte unchanged')
        rows.append(row)
    vendor_blocks={k.split('/u_ddr3_test_h',1)[1]:v for k,v in blocks.items() if '/u_ddr3_test_h' in k}
    fingerprint=hashlib.sha256(json.dumps(vendor_blocks,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    require(len(vendor_blocks)==121 and fingerprint==DDR_PARAMETERS_SHA,
            'actual vendor instance parameters differ from reviewed configuration')
    top=compact((work/'compiled'/build.TOP).read_text(encoding='utf-8-sig'))
    require(len(re.findall(r'\bddr3_test\b',uncomment((work/'compiled'/build.TOP).read_text())))==1
            and top.count('ddr3_testu_ddr3_test_h(')==1,'DDR wrapper instance has overrides or another instance')
    protected=[]
    for name,line,counter,old,new in REDUCTIONS[3:]:
        bound=next(r for r in rows if r['Source']==name)
        text=(work/'compiled'/name).read_text(encoding='utf-8-sig')
        require(text.startswith('`pragma protect begin_protected') and '`pragma protect data_block' in text,
                'expected P1735 protected vendor source differs')
        pattern=r'Removed register node (\S+) that is stuck at constant 0\.'
        zeros=[{'Line':i,'Text':s,'Node':re.search(pattern,s)[1]}for i,s in enumerate(compile_text.splitlines(),1)
            if re.search(pattern,s) and (('/mcdq_dcp_buf/cnt[' in s) if counter=='cnt' else ('/ddrphy_data_slice_wrcal/delay_cnt[' in s))]
        prefix='u_ddr3_test_h/'
        if counter=='cnt':
            expected={prefix+'u_ips_ddrc_top/mcdq_dcp_top/mcdq_dcp_buf/cnt[6]'}
        else:
            expected={prefix+'u_ddrphy_top/ddrphy_slice_top/i_dqs_group['+str(group)+
                '].ddrphy_data_slice/ddrphy_data_slice_wrcal/delay_cnt['+str(bit)+']'
                for group in range(4) for bit in (2,3)}
        require(len(zeros)==len(expected) and {r['Node']for r in zeros}==expected,
                'vendor compiler constant-zero node inventory differs')
        protected.append({'SourceBinding':bound,'Source':name,'Line':line,'Accumulator':counter,
            'OriginalBits':old,'ReducedBits':new,'EncryptedSource':True,
            'IndependentSourceRangeProof':False,'OriginalAssignmentsAndUsesVisible':False,
            'OriginalInternalRangeEnumerated':False,'ReachableMaximum':None,
            'LimitedDiagnosticAcceptance':True,'AcceptanceBasis':VENDOR_BASIS,
            'ReportedConstantZeroNodes':zeros,'CompilerZeroReportsAreIndependentRTLProof':False})
    return {'CheckedManifest':ref(base_path),'IDFAndExpandedFiles':rows,'FileCount':75,
        'EveryVendorOriginalAndCompiledByteMatchesCheckedManifest':True,
        'ActualElaboratedParameterBlocks':vendor_blocks,'ParameterBlockCount':121,
        'ParameterBlockSHA256':fingerprint,'TopDDRWrapperHasNoParameterOverrides':True,
        'IndependentProtectedSourceRangeProof':False},protected


def warning_inventory(work,plan):
    prefix=build.paths.alias_path(build.ROOT,plan['RepoAlias'],work);result={}
    for path in sorted(work.rglob('*.log')):
        rows=Counter(line.strip().replace(prefix,'@BUILD@')for line in path.read_text(encoding='gb18030',errors='strict').splitlines()
            if line.lstrip().startswith('W:'))
        if rows:result[path.relative_to(work).as_posix()]=dict(sorted(rows.items()))
    return result


def code(line):
    m=re.match(r'W: ([A-Za-z]+-\d+):',line)
    return m[1]if m else 'Unnumbered'


def table_facts(work):
    rows=[]
    for source,width in (('rtl/experimental/ms7200_1080p30_rearm_ctl.v',14),('rtl/experimental/ms7210_checked_ctl.v',13)):
        text=(work/'compiled'/source).read_text(encoding='utf-8-sig');flat=compact(text)
        addresses=[int(x,16)for x in re.findall(r"\d+'d\d+\s*:\s*cmd_data\s*=\s*\{16'h([0-9a-fA-F]+)\s*,",text)]
        require(addresses and max(addresses)<1<<width,'configuration address high-bit proof differs')
        assignments=re.findall(r'cmd_iic<=([^;]+);',flat)
        require(assignments and all(x in ('0',"24'd0",'cmd_data(cmd_index)')for x in assignments),'configuration table assignment differs')
        rows.append({'Source':ref(work/'compiled'/source),'Rows':len(addresses),'MaximumAddress':max(addresses),
            'RequiredBits':width,'AddressUpperZeroBits':list(range(width,16))})
    return rows


def rgb565_buffer_contract(engine,writer):
    """The new elastic register loses precisely the writer's eight RGB LSBs."""
    e,w=compact(engine),compact(writer)
    require(e.count('buffer_rgb')==4 and all(e.count(s)==1 for s in (
        'reg[23:0]buffer_rgb,buffer_tag;', 'buffer_rgb<=0;',
        "buffer_rgb<=result_masked?24'd0:result_rgb;", '.in_rgb(buffer_rgb)')),
        'elastic RGB buffer has another assignment or consumer')
    require(w.count('in_rgb')==4 and w.count(
        'wire[15:0]pixel={in_rgb[23:19],in_rgb[15:10],in_rgb[7:3]};')==1,
        'writer RGB565 quantization contract differs')
    kept=list(range(3,8))+list(range(10,16))+list(range(19,24))
    dropped=sorted(set(range(24))-set(kept))
    return {'WriterRGB565RetainedInputBits':kept,'ElasticBufferUnusedInputBits':dropped,
        'ElasticBufferOnlyConsumerIsRGB565Writer':True,'RemovedBitsArePixelQuantization':True,
        'RemovedBitsClassifiedAsMetadata':False}


def source_facts(work,plan):
    generator=importlib.import_module('generate_hdmi_fisheye_profile');cfg=generator.config()
    bound,inputs=build.fisheye_profile_binding(plan['FisheyeProfile']['Profile']['Path'])
    cache_name=build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe']
    cache_facts,cache_inputs=protocol.directfill_contract.review(build.ROOT/cache_name)
    for source,digest in cache_inputs.items():
        require(source not in inputs or inputs[source]==digest,'conflicting direct-fill source evidence')
        inputs[source]=digest
    compiled_cache=work/'compiled'/cache_name
    require(sha(compiled_cache)==protocol.directfill_contract.SOURCE_SHA256,
            'source warning facts must bind the unchanged reviewed compiled direct-fill cache')
    inputs[str(compiled_cache)]=sha(compiled_cache)
    require(bound==plan['FisheyeProfile'],'build-bound profile rederivation differs')
    lut=cfg['LUTQ30'];delta=lut[1:]-lut[:-1]
    base_bits={i:int((int(lut[0])>>i)&1)for i in range(32)if all(((int(x)>>i)&1)==((int(lut[0])>>i)&1)for x in lut[:-1])}
    delta_bits={i:int((int(delta[0])>>i)&1)for i in range(32)if all(((int(x)>>i)&1)==((int(delta[0])>>i)&1)for x in delta)}
    mapper=compact((work/'compiled'/build.MAPPER).read_text(encoding='utf-8-sig'))
    require(mapper.count('if(cfg_valid&&cfg_ready)beginconfigured<=1;corrected<=cfg_corrected;end')==1 and
        mapper.count('assigncfg_ready=!rst&&!(|valid);')==1 and
        mapper.count('corrected?result_x:identity_x[22]')==1 and mapper.count('corrected?result_y:identity_y[22]')==1,
        'frame-drained mode lock or exact identity path changed')
    require(mapper.count('identity_x[0]<=in_u;identity_y[0]<=in_v;')==1 and
        mapper.count('identity_x[i]<=identity_x[i-1];identity_y[i]<=identity_y[i-1];')==1,
        'identity pipeline changed')
    engine=compact((work/'compiled'/build.REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8']).read_text(encoding='utf-8-sig'))
    require('wireuse_tiles=cfg_corrected;'in engine and 'tiled_mode<=use_tiles;'in engine and
        '.frame_tiled(use_tiles)'in engine and 'if(!tiled_mode)'in engine and 'column==WIDTH-1'in engine and 'row<=row+'in engine and
        "u={3'b0,column,8'b0}"in engine and "v={3'b0,row,8'b0}"in engine,
        'frame-locked corrected tile8/raw raster integer-coordinate input contract changed')
    writer=(work/'compiled/rtl/experimental/ddr_adaptive_result_writer_dualstripe.v').read_text(encoding='utf-8-sig')
    quantization=rgb565_buffer_contract(engine,writer)
    tile_contracts={role:protocol.contract(role,(work/'compiled'/protocol.CONTRACTS[role]['Source']).read_text(encoding='utf-8-sig'))
        for role in ('Bank','Engine','Writer')}
    inputs[str(protocol.SELF)]=sha(protocol.SELF)
    uart=compact((work/'compiled'/build.STATUS_UART).read_text(encoding='utf-8-sig'))
    period=re.findall(r'parameter(?:integer)?(?:CLOCK_HZ|PERIOD_CYCLES)=([^,\)]+)',uart)
    return {'CurrentCProfile':bound,'DirectFillCacheSourceContract':cache_facts,'MapperModeLockedOnlyWhenDrained':True,'CorrectedTile8RawRasterModeFrameLocked':True,'IdentityQ8PipelineExact':True,
        'NativeXIntegerRange':[0,1919],'NativeYIntegerRange':[0,1079],
        'IntegerCoordinateAlwaysZeroBits':{'Q8X':list(range(8))+list(range(19,24)),
            'Q8Y':list(range(8))+list(range(19,24))},
        'ROMBaseConstantBits':{str(k):v for k,v in base_bits.items()},'ROMDeltaConstantBits':{str(k):v for k,v in delta_bits.items()},
        'ROMSourceWordCount':1024,'ROMSourceValueMinMax':[int(lut.min()),int(lut.max())],
        'ElasticRGB565Quantization':quantization,'Tile8WholeSourceContracts':tile_contracts,
        'DualStripeMemorySource':{'Banks':2,'RowsPerBank':8,'Width':1920,'PixelBits':16,
            'PixelsPerBank':15360,'TotalSourceBits':491520,'MemoryAndReadDataHaveNoReset':True,
            'OnlyValidatedFullStripeReadAndLastSynchronousReturnReleasesBank':True,
            'SourceContractDoesNotProveActualNativeMemoryModeOrReset':True},
        'TableExactHeaderBound':True,'UARTParameterExpressions':period,
        'NewMappingDataCleanupClassifiedAsMetadata':False,
        'PostSynthesisROMAndMapperFunctionalGraphAcceptanceStillRequired':True},inputs


def body_class(line):
    """Finite exact bodies are additionally SHA-pinned by the build inventory.

    These classes state the diagnostic scope; no class grants a path exception,
    memory mode, reset alias, pad waiver or source-to-netlist equivalence.
    """
    if line.startswith('W: Adm-4021:'):
        require(re.fullmatch(r"W: Adm-4021: The attribute '\.name' of object '[^']+' is overwritten by new value\.",line),
            'non-name native attribute overwrite requires explicit new review')
        return 'CompilerLogicalNameMetadataOnly'
    if code(line)in ('Timing-4086','Timing-4087'):return 'UnacceptedExternalPortACAndExactPinInventory'
    if code(line)=='ConstraintEditor-4040':return 'CheckedSharePinLocationNativeElectricalStillMandatory'
    if line.startswith('W: Unable to honor max fanout constraint for ')or re.fullmatch(
        r"W: syn_maxfan of lutcarry \S+ is more than 10000 on net \S+, but wasn't replicated\.",line):
        return 'UnmetFanoutOptimizationNativeAllTenTimingStillMandatory'
    if line in ('W: Sdm-2008: The attribute named async_reg is not legal, then it has no effect, ignore its value.',
        'W: Sdm-2008: The attribute named ram_style is not legal, then it has no effect, ignore its value.'):
        return 'IgnoredSourceAttributeCurrentNativeCDCAndRAMProofRequired'
    if '/compiled/'+build.IP+'/'in line or "'u_ddr3_test_h/"in line or 'inst u_ddr3_test_h/'in line:
        require(code(line)in ('Verilog-2057','Verilog-2006','Verilog-2064','Verilog-2019','Verilog-2039','Verilog-2023',
            'Sdm-2000','Adm-4000','Public-4008','Unnumbered'),'unreviewed vendor compiler diagnostic kind')
        return 'ExactUnchangedOfficialVendorIPLimitedCompilerDisposition'
    if code(line)=='Sdm-2000':return 'ExactReadableCounterRangeOrConstantConfigurationTable'
    if code(line)=='Adm-4000':return 'FrozenSourceConstantPropagationNotUnusedPixelMetadata'
    m=re.fullmatch(r"W: Public-4008: Instance '([^']+)' of '([^']+)' unit is dangling and will be cleaned\.",line)
    require(m is not None,'unreviewed source warning body: '+line)
    name,primitive=m.groups()
    if name.startswith('hdmi_configuration/'):
        return 'RetainedRearmTableConstantsAndUnconnectedDiagnosticHistory'
    if name=='view_control/toggle_pulse':return 'UnconnectedViewPulseObservationModeRequestStillBusiness'
    if name.startswith('system/bank_core/engine/buffer_rgb['):
        require(re.fullmatch(r'system/bank_core/engine/buffer_rgb\[(0|1|2|8|9|16|17|18)\]',name),
            'elastic buffer lost a retained RGB565 input bit')
        return 'ExactElasticBufferEightRGB565QuantizationLSBs'
    if re.fullmatch(r'board_fault\[(3|4|6|7)\]',name):return 'ClosedBoardFaultCodeConstantBits'
    if 'reset_sync'in name or name.endswith('core_reset_sync[1:0]')or name.endswith('sys_reset[1:0]'):
        return 'DuplicateLocalReleaseChainCurrentNativeGuardAliasProofRequired'
    if name.startswith('status_uart/'):
        return 'AtomicFixedStatusPacketAndBaudCounterConstantPropagation'
    if name.startswith('ainst_vf_system/')or re.search(r'/N\d+/pr\[48:0\]$',name):
        return 'CompilerDSPPartialProductUnusedPrimitiveRegisterOutput'
    if '/core/mapper/'in name:
        if '/radial_rom/'in name or '/base_delay['in name:return 'ExhaustiveGeneratedRadialROMConstantBit'
        if '/identity_x['in name or '/identity_y['in name:return 'BoundedIntegerRasterCoordinateIdentityPipelineConstantBit'
        require(any('/'+family+'/'in name for family in ('normalize_x','normalize_y','square_x','square_y','interpolate',
            'distort_x','distort_y','source_x','source_y')),'unreviewed mapper functional cleanup: '+name)
        return 'ExactFixedPointRoundingUnusedLowProductBits'
    require(name.startswith('system/'),'unknown functional source hierarchy: '+name)
    if '/sampler/interpolation/'in name or '/sampler/cache/inner/fast_pixel['in name:
        return 'RetainedRGB565ExpansionInterpolationAndQuantizationSlice'
    if 'base['in name or '/destination['in name or '/completed_base['in name or '/reader_base['in name:
        return 'FourFixedAlignedFrameBankAddressConstantBit'
    if name.endswith(('/source_crc[31:0]','/source_pixels[31:0]','/accepted_pixels[31:0]','/completed_frames[31:0]',
        '/mismatches[31:0]','/underflows[31:0]'))or any(token in name for token in ('dropped_frames','overflow_frames','no_grant_',
            'last_drop_fault','end_fault','/bursts','/source_commit','/active_process_id','/peak_fifo_used')):
        return 'UnconnectedPrivateDiagnosticCounterOrStatusHistory'
    return 'FiniteReviewedCheckedPipelineParameterConstantOrPrivateUnusedIntermediate'


def bind_simulation_receipts(inventory,plan,watched):
    specs={'MapperSimulation':('run_hdmi_camera_fisheye_mapper_sim',(build.MAPPER,build.ROM,build.PROFILE_HEADER,build.RADIAL_HEADER)),
        'SystemSmallSimulation':('run_hdmi_camera_fisheye_tile8df8_system_sim',(build.SAMPLER,build.MAPPER,build.ROM,build.PROFILE_HEADER,build.RADIAL_HEADER,
            build.REQUIRED_MODULES['ddr_remap_sample_scatter4'],build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe'],
            build.REQUIRED_MODULES['ddr_read_arbiter'],
            build.REQUIRED_MODULES['hdmi_camera_fisheye_system'],build.REQUIRED_MODULES['hdmi_camera_fisheye_input_link'],
            build.REQUIRED_MODULES['hdmi_camera_fisheye_bank'],build.REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8'],
            build.REQUIRED_MODULES['ddr_adaptive_result_writer_dualstripe'])),
        'IOSimulation':('run_hdmi_camera_fisheye_io_sim',(build.QUANTIZER,build.STATUS_UART,build.UART))}
    require(set(inventory['Simulations'])==set(specs),'three independent current source simulations required')
    summaries={}
    for kind,(name,names)in specs.items():
        provider=importlib.import_module(name);record=inventory['Simulations'][kind]
        require(Path(provider.__file__).resolve()==SELF.with_name(name+'.py')and set(record)=={'Path','SHA256'}and
            sha(record['Path'])==record['SHA256'],'simulation provider/receipt reference changed')
        value,inputs=provider.verify(record['Path']);require(value['Passed']is True and value['HardwareAccessed']is False,'actual source simulation failed')
        for source in names:
            original=str((build.ROOT/source).resolve());actual=value['SourceSHA256'].get(source)if kind=='SystemSmallSimulation'else value['SourceSHA256'].get(original)
            require(actual==plan['InputSHA256'][original],'warning evidence compiled different current source: '+source)
        if kind=='MapperSimulation':require(value['Mode']=='native'and value['Summary']['CorrectedCoordinates']==2073600,'full native coordinate RTL oracle required')
        if kind=='SystemSmallSimulation':require(value['Mode']=='small'and value['Summary']['frame_mode_latches']==2 and
            value['CandidateEngine']==build.REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8'] and
            value['CandidateWriter']==build.REQUIRED_MODULES['ddr_adaptive_result_writer_dualstripe'] and
            value['CorrectedCoordinatesTiled8x8'] is True and value['RawCoordinatesRaster'] is True,
            'real frame-locked tile8/raw two-mode small system required')
        if kind=='IOSimulation':require(value['ActualUARTPinDecodePassed']is True and value['ActualQuantizerAll256ValuesAndTimingPassed']is True,'actual quantizer/status wire proof required')
        for path,h in inputs.items():add(watched,path,h)
        add(watched,provider.__file__);summaries[kind]={'Receipt':record,'Passed':True,'Scope':value.get('Limits',kind)}
    return summaries


def derive(build_plan):
    build_plan=Path(build_plan).resolve();work=build.work_path(build_plan.parent);plan=build.validate(build_plan)
    receipt=build.verify_execution(work/'execution-result.json');watched={}
    require(INVENTORY_SHA is not None and sha(INVENTORY)==INVENTORY_SHA,'actual tile8 warning inventory is pending or changed');inventory=read(INVENTORY)
    require(inventory.get('Schema')=='hdmi-camera-fisheye-tile8df8-warning-inventory-v1'and inventory['Target']==build.TARGET and
        inventory['BuildPlan']==ref(build_plan)and inventory['SourceBuildReceipt']==ref(work/'execution-result.json'),
        'warning inventory identifies another completed source build')
    expected_sources=[{k:r[k]for k in ('Source','OriginalSHA256','CompiledSHA256')}for r in plan['CompiledInputs']]
    require(inventory['CompiledSources']==expected_sources,'source warning compiled closure differs')
    actual=warning_inventory(work,plan);require(actual==inventory['WarningBodiesByLog'],'unknown/missing/different warning body/count')
    unique={body for rows in actual.values()for body in rows};classes={body:body_class(body)for body in sorted(unique)}
    require(classes==inventory['BodyClasses']and len(unique)==inventory['UniqueBodies'],'warning semantic/body inventory differs')
    counts=Counter()
    for rows in actual.values():
        for body,n in rows.items():counts[code(body)]+=n
    require(dict(counts)==inventory['Counts'],'exact warning multiplicity differs')
    for group in ('InputSHA256','PreparedSHA256'):
        for path,h in plan[group].items():add(watched,path,h)
    # Five exact critical reductions, repeated only by the four original logs.
    expected=[]
    prefix=build.paths.alias_path(build.ROOT,plan['RepoAlias'],work)
    for source,line,name,old,new in REDUCTIONS:
        expected.append(f'C: Sdm-3003: [{prefix}/compiled/{source}(line number: {line})] Reduce accumulator {name} size from {old} to {new}. If this is not intended behavior, please drive {name} with valid values.')
    require(Counter(receipt['Diagnostics'])==Counter(log+': '+body for log in ('compile/run.log','flow.log','run.log','stdout.log')for body in expected),
        'unknown/missing/current critical source diagnostic')
    text=(work/'compile/run.log').read_text(encoding='gb18030',errors='strict');blocks=parameters(text)
    wanted={build.TARGET:{'INPUT_TIMING_CONFIGURED':1,'RX_VS_ACTIVE_LEVEL':1,'RX_DE_ACTIVE_LEVEL':1,
        'CFG_SETTLE_CYCLES':2700000,'PCLK_STALE_REF_CYCLES':2700000},
        build.TARGET+'/hdmi_configuration':{'CLK_FRE':10000000,'IIC_FREQ':400000,'TIMEOUT_CYCLES':100000},
        build.TARGET+'/hdmi_configuration/driver':{'CLK_FRE':10000000,'IIC_FREQ':400000,'T_WR':1,
            'ADDR_BYTE':2,'LEN_WIDTH':3,'DATA_BYTE':1,'TIMEOUT_CYCLES':100000}}
    require(all(integer_parameters(blocks.get(k,[]))==v for k,v in wanted.items()),'actual readable counter parameters differ')
    proofs=[]
    for name,spec in PUBLIC.items():
        source=source_binding(plan,work,spec['Source'],watched)
        checked=counter_contract((work/'compiled'/spec['Source']).read_text(encoding='utf-8-sig'),name)
        proofs.append({'Accumulator':name,'SourceBinding':source,**checked,
            **dict(enumerate_bound(spec['Maximum'],spec['Old'],spec['New'])),'IndependentSourceRangeProof':True})
    vendor,protected=vendor_basis(plan,work,blocks,text,watched)
    facts,inputs=source_facts(work,plan)
    for p,h in inputs.items():add(watched,p,h)
    require(facts==inventory['SourceFacts'],'current source semantic facts changed')
    evidence=bind_simulation_receipts(inventory,plan,watched)
    for path,h in receipt['NativeLogSHA256'].items():add(watched,work/path,h)
    for p in (SELF,Path(build.__file__),build_plan,work/'execution-result.json',INVENTORY,Path(sys.executable).resolve()):add(watched,p)
    require(all(sha(p)==h for p,h in watched.items()),'warning source/runtime evidence drift')
    value={'Schema':SCHEMA,'Target':build.TARGET,'Passed':True,'SourceDiagnosticReviewPassed':True,
        'BuildPlan':ref(build_plan),'SourceBuildReceipt':ref(work/'execution-result.json'),'Inventory':ref(INVENTORY),
        'Counts':dict(sorted(counts.items())),'ReviewedWarningBodiesByLog':actual,'BodyClasses':classes,
        'ReadableCounterProofs':proofs,'ProtectedVendorCounterDispositions':protected,'VendorIPBinding':vendor,
        'ReadableIndependentSourceRangeProofCount':3,'ProtectedLimitedAcceptanceCount':2,'AllFiveIndependentSourceRangeProof':False,
        'SourceFacts':facts,'CommandTableFacts':table_facts(work),'IndependentSimulationEvidence':evidence,
        'SourceDiagnostics':receipt['Diagnostics'],'DiagnosticsCleared':False,'OriginalDiagnosticsUnmodified':True,
        'UnknownWarningBodiesAccepted':False,'NewPixelDataCleanupClassifiedAsMetadata':False,
        'AdditionalTimingExceptionsAuthorized':False,'SourceToNativeFormalEquivalenceClaimed':False,
        'NativeDDRResetCDCROMPinTimingAndRuntimeFaultAcceptanceRemainIndependent':True,
        'TimingAccepted':False,'HardwareReleaseAllowed':False,'HardwareAccessed':False,'ExternalACAccepted':False,
        'InputSHA256':dict(sorted(watched.items()))}
    return value,{Path(p):h for p,h in watched.items()}


def verify(path):
    path=Path(path).resolve();saved=read(path);require(saved.get('Schema')==SCHEMA and saved.get('Target')==build.TARGET,'fisheye warning review required')
    current,watched=derive(saved['BuildPlan']['Path']);require(saved==current,'fisheye warning review changed');watched[path]=sha(path);return saved,watched


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build-plan',type=Path);p.add_argument('--output',type=Path);p.add_argument('--verify',type=Path);a=p.parse_args()
    if a.verify:v,w=verify(a.verify)
    else:
        require(a.build_plan and a.output,'build-plan/output required');v,w=derive(a.build_plan);build.write(a.output,v)
    print(json.dumps({'Passed':v['Passed'],'SourceDiagnosticReviewPassed':v['SourceDiagnosticReviewPassed'],'Counts':v['Counts'],'Watched':len(w)}));return 0


if __name__=='__main__':raise SystemExit(main())

