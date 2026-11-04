"""New fisheye DDR/profile/sim authority and explicit volatile SRAM boundaries."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import mock
import pytest
sys.path.insert(0,str(Path('D:\\GravityLRT\\thu\\semester_4.5\\FPGAchina\\fpga-distortion-correction\\distortion')/'tools'))
import hdmi_camera_fisheye_tile8df8v2_bitstream as bit
import hdmi_camera_fisheye_tile8df8v2_program as program


def proof():
    return {'Schema':bit.PROOF_SCHEMA,'Target':bit.TARGET,**{name:True for name in (
        'Passed','STAAllTenPassed','NativeWarningsReviewed','SourceDiagnosticReviewPassed','NetlistEquivalent',
        'AllFFPlacementsEquivalent','RoutesUnchanged','ResetAccepted','SourceSamplingIsolatedVerified',
        'VendorDDRClockResetAccepted','FrameBoundaryViewSelectionAccepted','FisheyeProfileAccepted','UserCDCAccepted')},
        'Pins':{'DeclaredTopPorts':144,'NativeRoutedPorts':144,'NativeActivePorts':144,'UnusedPads':[],
            'NativeElectricalParametersVerified':True},
        'DataCDC':{'InterstageTimingAccepted':True,'Missing':[],'Violations':[]},
        'NativeAcceptance':{'ActualDDRGraphReviewed':True},'SourcePartitions':{'CurrentGraphBound':True}}


@pytest.mark.parametrize('name',['Passed','STAAllTenPassed','NativeWarningsReviewed','SourceDiagnosticReviewPassed','NetlistEquivalent',
    'AllFFPlacementsEquivalent','RoutesUnchanged','ResetAccepted','SourceSamplingIsolatedVerified','VendorDDRClockResetAccepted',
    'FrameBoundaryViewSelectionAccepted','FisheyeProfileAccepted','UserCDCAccepted'])
def test_each_native_ddr_mode_profile_or_interstage_requirement_is_mandatory(name):
    value=proof();bit.physical_flags(value);value[name]=False
    with pytest.raises(ValueError):bit.physical_flags(value)


@pytest.mark.parametrize('mutation',['old_target','old_schema','wrong_route_count','missing_active','unused_rgb',
    'unreviewed_unused','wrong_unused_count','cdc_missing','cdc_violation','no_interstage','no_partitions','no_native'])
def test_actual144_pin_ddr_and_user_cdc_evidence_cannot_be_inherited(mutation):
    value=proof()
    if mutation=='old_target':value['Target']='hdmi_camera_snapshot_top'
    elif mutation=='old_schema':value['Schema']='hdmi-camera-snapshot-final-physical-proof-v1'
    elif mutation=='wrong_route_count':value['Pins']['NativeRoutedPorts']=142
    elif mutation=='missing_active':del value['Pins']['NativeActivePorts']
    elif mutation=='unused_rgb':value['Pins'].update(NativeActivePorts=143,UnusedPads=['r_in[0]'],UnusedPadDispositionsAccepted=True,
        UnusedPadDispositions=[{'Port':'r_in[0]','Passed':True}])
    elif mutation=='unreviewed_unused':value['Pins'].update(NativeActivePorts=143,UnusedPads=['clk_n'])
    elif mutation=='wrong_unused_count':value['Pins']['UnusedPads']=['clk_n']
    elif mutation=='cdc_missing':value['DataCDC']['Missing']=['held-mode launch']
    elif mutation=='cdc_violation':value['DataCDC']['Violations']=['bad source Q']
    elif mutation=='no_interstage':value['DataCDC']['InterstageTimingAccepted']=False
    elif mutation=='no_partitions':value['SourcePartitions']={}
    else:value['NativeAcceptance']={}
    with pytest.raises(ValueError):bit.physical_flags(value)


def test_all144_actual_ports_required_even_if_an_unused_ddr_pin_is_labelled_accepted():
    value=proof();value['Pins'].update(NativeActivePorts=143,UnusedPads=['clk_n'],UnusedPadDispositionsAccepted=True,
        UnusedPadDispositions=[{'Port':'clk_n','Passed':True}])
    with pytest.raises(ValueError):bit.physical_flags(value)


def test_only_exact_new_request_roles_and_real_native_alias_are_accepted():
    assert bit.FIELDS=={'Schema','Target','PhysicalProof','MapperSimulation','SystemSimulation','IOSimulation','Profile'}
    assert bit.TARGET=='hdmi_camera_fisheye_top'and bit.EXPECTED_BIT_BYTES==3791112
    assert bit.native_work(bit.WORK/'bit-a').startswith('P:/distortion/work/hdmi-camera-fisheye-tile8df8-20261103-a/')
    with pytest.raises(ValueError):bit.build.paths.alias_format('P:')


def test_fresh_runtime_gate_never_uses_the_preparation_authority_cache(tmp_path,monkeypatch):
    def validate(work,*,fresh_authority=False):
        assert fresh_authority is True
        raise ValueError('full fresh authority checked')
    monkeypatch.setattr(bit,'validate',validate)
    with pytest.raises(ValueError,match='full fresh'):bit.gate(tmp_path)


def test_fresh_sta_keeps_all_three_complete_comparisons(tmp_path,monkeypatch):
    provider=SimpleNamespace(compare_fresh_sta=mock.Mock(return_value={k:True for k in (
        'STAAllTenPassed','ClockAndSummaryIdentityPreserved','AllExceptionPathsPreserved')}))
    monkeypatch.setattr(bit,'physical_provider',lambda:provider)
    for _ in range(2):bit.compare_fresh({'Proof':{}},tmp_path/'r',tmp_path/'e')
    assert provider.compare_fresh_sta.call_count==2
    provider.compare_fresh_sta.return_value['AllExceptionPathsPreserved']=False
    with pytest.raises(ValueError):bit.compare_fresh({'Proof':{}},tmp_path/'r',tmp_path/'e')


def test_tcl_fresh_sta_uncached_cpu_gate_then_explicit_unused_bitgen(tmp_path,monkeypatch):
    monkeypatch.setattr(bit,'context_prefix',lambda path:'frozen context\n')
    monkeypatch.setattr(bit,'native_work',lambda path:'P:/fisheye/'+Path(path).name)
    value=bit.render({'BuildPlan':tmp_path/'plan','FinalADFSHA256':'a'*64},tmp_path/'bit-a')
    assert value.index('report_timing ')<value.index('--gate ')<value.index('gen_bit_stream ')
    assert '-max_path 10000 -nworst 4 -report_exception TRUE'in value
    assert '-unused_io_status UNUSED'in value and 'P:/fisheye/audited-final.adf'in value


def test_current_C_profile_rederives_and_matches_both_actual_header_hashes():
    profile,inputs=bit.build.fisheye_profile_binding()
    plan={'FisheyeProfile':profile,'InputSHA256':{str((bit.ROOT/n).resolve()):bit.sha(bit.ROOT/n)
        for n in (bit.build.PROFILE_HEADER,bit.build.RADIAL_HEADER)}}
    watched={};assert bit.bind_profile(bit.build.FISHEYE_PROFILE,plan,watched)==profile
    assert profile['FullGridError']['NativeCoordinatesChecked']==2073600 and len(watched)>=6
    plan['InputSHA256'][str((bit.ROOT/bit.build.RADIAL_HEADER).resolve())]='0'*64
    with pytest.raises(ValueError):bit.bind_profile(bit.build.FISHEYE_PROFILE,plan,{})


def test_same_board_existing_camera_receipt_is_read_only_not_new_target_approval():
    watched={};value=program.bind_prior_camera(program.PRIOR_CAMERA_RECEIPT,watched)
    assert value==bit.ref(program.PRIOR_CAMERA_RECEIPT)and len(watched)>=7
    assert program.read(program.PRIOR_CAMERA_RECEIPT)['source_kind']=='physical_hdmi_camera'


def test_program_has_only_scan_volatile_scripts_and_explicit_session_gates(tmp_path):
    scripts=program.scripts(tmp_path/'fisheye.sbit')
    assert set(scripts)=={'scan','program'}and all('flash'not in v.lower()for v in scripts.values())
    program.execution_authorization(True,True,90)
    for values in [(False,True,90),(True,False,90),(True,True,float('nan')),(True,True,301)]:
        with pytest.raises(ValueError):program.execution_authorization(*values)
    source=Path(program.__file__).read_text()
    assert 'PGHRAW'not in source and "'UARTPrecheckRequired':False"in source


def test_previous_snapshot_camera_success_cannot_be_spliced_to_another_receipt(tmp_path,monkeypatch):
    value=program.read(program.PRIOR_CAMERA_RECEIPT);value=copy.deepcopy(value);value['passed']=False
    path=tmp_path/'bad.json';path.write_text(json.dumps(value))
    with pytest.raises(ValueError):program.bind_prior_camera(path,{})


@pytest.fixture
def simulations(tmp_path,monkeypatch):
    root=tmp_path/'repo/distortion';root.mkdir(parents=True);monkeypatch.setattr(bit,'ROOT',root)
    names={bit.build.MAPPER,bit.build.ROM,bit.build.SAMPLER,bit.build.PROFILE_HEADER,bit.build.RADIAL_HEADER,
        bit.build.VIEW_CONTROL,bit.build.QUANTIZER,bit.build.STATUS_UART,bit.build.UART,'rtl/mul32_pipe.v',
        *[bit.build.REQUIRED_MODULES[n]for n in ('hdmi_camera_fisheye_system','hdmi_camera_fisheye_bank',
            'hdmi_camera_fisheye_engine_tile8','hdmi_camera_fisheye_core','hdmi_camera_fisheye_input_link',
            'ddr_neighbour_cache_scatter16_rowpipe','ddr_remap_sample_scatter4','ddr_read_arbiter',
            'ddr_adaptive_result_writer_dualstripe')]}
    for name in names:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('executed '+name)
    inputs={str((root/n).resolve()):bit.sha(root/n)for n in names}
    compiled=[{'Source':n,'OriginalSHA256':inputs[str(root/n)],'CompiledPath':str(root/n),
        'CompiledSHA256':inputs[str(root/n)]}for n in names]
    plan={'InputSHA256':inputs,'CompiledInputs':compiled,'PreparedSHA256':dict(inputs)}
    common={'Passed':True,'HardwareAccessed':False,'PDSAccessed':False,'SourceDrift':[]}
    values={'MapperSimulation':{**common,'Mode':'native','SmallGate':{'Path':'small','SHA256':'a'*64},
        'ActualMapperROMAndMultipliersExecuted':True,'SourceSHA256':dict(inputs),
        'Summary':{'CorrectedCoordinates':2073600,'ExactIdentityCoordinates':4096,'DomainCoordinates':1024,
            'TotalCoordinatesMatched':2078720,'InitiationInterval':1,'PipelineEnabledStages':23},
        'FullNativeCPUError':{'NativeCoordinatesChecked':2073600,'ArithmeticMaskedCoordinates':0,'Passed':True,
            'FixedVsOpenCVMaxNativePixels':.0064}},
        'SystemSimulation':{**common,'Mode':'native','SmallGate':{'Path':'small','SHA256':'a'*64},'FunctionalPassed':True,
            'InputClockHz':148500000,'OutputClockHz':74250000,'SystemClockHz':125000000,
            'ActualPixelSamplerInstantiated':True,'InputDDRPreloaded':False,'RealOutputAsyncFIFO':True,'ActualDERGBScanned':True,
            'SourceSHA256':{n:inputs[str(root/n)]for n in names},
            'Summary':{'frames_input':2,'frames_committed':2,'frames_processed':2,'frames_published':2,'frames_unique_scanned':2,
                'unique_scanned_pixels':4147200,'key_toggles':3,'mode_changes_while_processing':3,'frame_mode_latches':2,
                'output_underflows':0,'output_crc_mismatches':0,'dropped_frames':0,'overflow_frames':0,'no_free_frames':0,'final_drain':True},
            'DirectFillCache':True,'CacheIndexBits':8,'ScatterCyclesPerFill':0,'CacheRAMWriteCyclesPerFill':8,'CandidateCache':bit.build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe'],
            'CandidateArbiter':bit.build.REQUIRED_MODULES['ddr_read_arbiter'],
            'CandidateEngine':bit.build.REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8'],
            'CandidateWriter':bit.build.REQUIRED_MODULES['ddr_adaptive_result_writer_dualstripe'],
            'CorrectedCoordinatesTiled8x8':True,'RawCoordinatesRaster':True,
            'Frames':[{'id':1,'fills':'31110','scatter_cycles':'0','cache_ram_write_cycles':'248880','cache_fill_valid_commits':'31110'},{'id':2,'fills':'16200','scatter_cycles':'0','cache_ram_write_cycles':'129600','cache_fill_valid_commits':'16200'}],'Fixture':{'Frames':[{'Corrected':True},{'Corrected':False,'ChangedPixels':0}]}},
        'IOSimulation':{**common,'SourceSHA256':dict(inputs),'ActualUARTPinDecodePassed':True,
            'ActualQuantizerAll256ValuesAndTimingPassed':True,'AtomicSnapshotUnaffectedByLaterCounterAndFaultChanges':True,
            'Bytes':96,'BitCycles':1085}}
    paths={};providers={}
    for kind,value in values.items():
        path=root/'work'/kind/'simulation.json';path.parent.mkdir(parents=True);path.write_text(json.dumps(value));paths[kind]=path
        provider=root/'tools'/(kind+'.py');provider.parent.mkdir(exist_ok=True);provider.write_text('strict actual verifier fixture')
        providers[kind]=SimpleNamespace(__file__=str(provider),verify=mock.Mock(side_effect=lambda path,value=value:(
            copy.deepcopy(value),{path:bit.sha(path)})))
    providers['SystemSimulation'].BENCH='testbench.sv'
    providers['SystemSimulation'].closure=lambda:(tuple(names),(),(),{})
    monkeypatch.setattr(bit,'simulation_provider',lambda kind:providers[kind])
    return SimpleNamespace(root=root,plan=plan,values=values,paths=paths,providers=providers)


@pytest.mark.parametrize('kind',list(bit.SIMULATIONS))
def test_each_distinct_source_bound_simulation_is_reverified_and_watched(simulations,kind):
    a=simulations;watched={};value=bit.bind_simulation(kind,a.paths[kind],a.plan,watched)
    a.providers[kind].verify.assert_called_once_with(a.paths[kind])
    assert value==a.values[kind]and str(a.paths[kind])in watched
    assert str(Path(a.providers[kind].__file__))in watched


def test_c_system_simulation_must_bind_new_local_reset_link(simulations):
    a=simulations;name=bit.build.REQUIRED_MODULES['hdmi_camera_fisheye_input_link']
    a.values['SystemSimulation']['SourceSHA256'][name]='0'*64
    a.paths['SystemSimulation'].write_text(json.dumps(a.values['SystemSimulation']))
    with pytest.raises(ValueError,match='different build-plan'):bit.bind_simulation('SystemSimulation',a.paths['SystemSimulation'],a.plan,{})


def test_c_authorities_use_c_build_native_and_system_provider():
    assert bit.build.__name__=='hdmi_camera_fisheye_tile8df8_build'
    assert bit.native.__name__=='hdmi_camera_fisheye_tile8df8v2_scoped_native'
    assert bit.SIMULATIONS['SystemSimulation']=='run_hdmi_camera_fisheye_tile8df8_system_sim'
    assert program.bit is bit


@pytest.mark.parametrize('mutation',[
    'old_engine','old_writer','missing_engine','missing_writer','corrected_raster','raw_tiled',
    'bank_source','writer_source','engine_source','bank_compiled','writer_compiled',
    'engine_unprepared','missing_bank_snapshot','other_production_snapshot'])
def test_tile8_new_roles_and_every_executed_production_snapshot_are_bound(simulations,mutation):
    a=simulations;v=a.values['SystemSimulation'];modules=bit.build.REQUIRED_MODULES
    bank=modules['hdmi_camera_fisheye_bank'];writer=modules['ddr_adaptive_result_writer_dualstripe'];engine=modules['hdmi_camera_fisheye_engine_tile8']
    if mutation=='old_engine':v['CandidateEngine']='rtl/experimental/hdmi_camera_fisheye_engine.v'
    elif mutation=='old_writer':v['CandidateWriter']='rtl/experimental/ddr_adaptive_result_writer.v'
    elif mutation=='missing_engine':del v['CandidateEngine']
    elif mutation=='missing_writer':del v['CandidateWriter']
    elif mutation=='corrected_raster':v['CorrectedCoordinatesTiled8x8']=False
    elif mutation=='raw_tiled':v['RawCoordinatesRaster']=False
    elif mutation.endswith('_source'):
        name={'bank_source':bank,'writer_source':writer,'engine_source':engine}[mutation]
        v['SourceSHA256'][name]='0'*64
    elif mutation.endswith('_compiled'):
        name=bank if mutation=='bank_compiled'else writer
        a.plan['CompiledInputs'][next(i for i,r in enumerate(a.plan['CompiledInputs'])if r['Source']==name)]['CompiledSHA256']='0'*64
    elif mutation=='engine_unprepared':del a.plan['PreparedSHA256'][str(a.root/engine)]
    elif mutation=='missing_bank_snapshot':a.plan['CompiledInputs']=[r for r in a.plan['CompiledInputs']if r['Source']!=bank]
    else:
        name=bit.build.UART
        # This role is beyond the original short list, but the executed
        # provider closure includes it and therefore must still bind exactly.
        a.plan['CompiledInputs']=[r for r in a.plan['CompiledInputs']if r['Source']!=name]
    a.paths['SystemSimulation'].write_text(json.dumps(v))
    with pytest.raises(ValueError):bit.bind_simulation('SystemSimulation',a.paths['SystemSimulation'],a.plan,{})


@pytest.mark.parametrize('mutation',[
    'fill32_count','missing_fill_count','old_candidate_cache','missing_candidate_cache',
    'first_frame_fill32','second_frame_fill32','missing_frame','cache_source_drift',
    'sampler_source_drift','unbound_cache_source','unbound_sampler_source'])
def test_old_or_unbound_cache_evidence_cannot_be_used_for_fill8(simulations,mutation):
    a=simulations;v=a.values['SystemSimulation']
    cache=bit.build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe']
    sampler=bit.build.REQUIRED_MODULES['ddr_remap_sample_scatter4']
    if mutation=='fill32_count':v['ScatterCyclesPerFill']=32
    elif mutation=='missing_fill_count':del v['ScatterCyclesPerFill']
    elif mutation=='old_candidate_cache':v['CandidateCache']='rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v'
    elif mutation=='missing_candidate_cache':del v['CandidateCache']
    elif mutation=='first_frame_fill32':v['Frames'][0]['scatter_cycles']=str(32*int(v['Frames'][0]['fills']))
    elif mutation=='second_frame_fill32':v['Frames'][1]['scatter_cycles']=str(32*int(v['Frames'][1]['fills']))
    elif mutation=='missing_frame':v['Frames'].pop()
    elif mutation=='cache_source_drift':v['SourceSHA256'][cache]='0'*64
    elif mutation=='sampler_source_drift':v['SourceSHA256'][sampler]='0'*64
    elif mutation=='unbound_cache_source':del a.plan['InputSHA256'][str(a.root/cache)]
    elif mutation=='unbound_sampler_source':del a.plan['InputSHA256'][str(a.root/sampler)]
    a.paths['SystemSimulation'].write_text(json.dumps(v))
    with pytest.raises(ValueError):bit.bind_simulation('SystemSimulation',a.paths['SystemSimulation'],a.plan,{})


def test_old_c_physical_proof_schema_is_not_fill8_authority():
    value=proof();value['Schema']='hdmi-camera-fisheye-final-physical-proof-v1'
    with pytest.raises(ValueError):bit.physical_flags(value)


@pytest.mark.parametrize('mutation', ['missing_identity', 'old_identity', 'changed_source', 'unbound_source'])
def test_r2_arbiter_evidence_is_mandatory(simulations, mutation):
    a = simulations
    value = a.values['SystemSimulation']
    arbiter = bit.build.REQUIRED_MODULES['ddr_read_arbiter']
    if mutation == 'missing_identity':
        del value['CandidateArbiter']
    elif mutation == 'old_identity':
        value['CandidateArbiter'] = 'rtl/ddr_read_arbiter.v'
    elif mutation == 'changed_source':
        value['SourceSHA256'][arbiter] = '0' * 64
    else:
        del a.plan['InputSHA256'][str(a.root / arbiter)]
    a.paths['SystemSimulation'].write_text(json.dumps(value))
    with pytest.raises(ValueError):
        bit.bind_simulation('SystemSimulation', a.paths['SystemSimulation'], a.plan, {})


@pytest.mark.parametrize('kind,mutation',[
    ('MapperSimulation','short_native'),('MapperSimulation','no_identity'),('MapperSimulation','error_gate'),
    ('MapperSimulation','other_source'),('MapperSimulation','no_small'),('SystemSimulation','no_scan'),
    ('SystemSimulation','preloaded'),('SystemSimulation','no_final_drain'),('SystemSimulation','mode_midframe'),
    ('SystemSimulation','identity_modified'),('SystemSimulation','other_source'),('IOSimulation','no_quantizer'),
    ('IOSimulation','byte_model'),('IOSimulation','wrong_divisor'),('IOSimulation','other_source')])
def test_nominal_pass_cannot_replace_actual_mapper_modes_scan_io_or_current_bytes(simulations,kind,mutation):
    a=simulations;v=a.values[kind]
    if mutation=='short_native':v['Summary']['CorrectedCoordinates']=512
    elif mutation=='no_identity':v['Summary']['ExactIdentityCoordinates']=0
    elif mutation=='error_gate':v['FullNativeCPUError']['FixedVsOpenCVMaxNativePixels']=.126
    elif mutation=='no_small':v['SmallGate']=None
    elif mutation=='no_scan':v['ActualDERGBScanned']=False
    elif mutation=='preloaded':v['InputDDRPreloaded']=True
    elif mutation=='no_final_drain':v['Summary']['final_drain']=False
    elif mutation=='mode_midframe':v['Summary']['frame_mode_latches']=3
    elif mutation=='identity_modified':v['Fixture']['Frames'][1]['ChangedPixels']=1
    elif mutation=='no_quantizer':v['ActualQuantizerAll256ValuesAndTimingPassed']=False
    elif mutation=='byte_model':v['ActualUARTPinDecodePassed']=False
    elif mutation=='wrong_divisor':v['BitCycles']=1086
    else:
        source=bit.build.MAPPER if kind!='IOSimulation'else bit.build.UART
        v['SourceSHA256'][source if kind=='SystemSimulation'else str(a.root/source)]='0'*64
    a.paths[kind].write_text(json.dumps(v))
    with pytest.raises(ValueError):bit.bind_simulation(kind,a.paths[kind],a.plan,{})


def test_complete_request_binds_all_providers_profile_and_cache_watches_every_receipt(simulations,monkeypatch):
    a=simulations;work=a.root/'work/fisheye';work.mkdir()
    monkeypatch.setattr(bit,'WORK',work);monkeypatch.setattr(bit.build,'ROOT',a.root);monkeypatch.setattr(bit.build,'WORK',work)
    monkeypatch.setattr(bit,'_AUTHORITY_CACHE',{})
    def file(name,data):
        path=work/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(data);return path
    build_plan=file('build-b/plan.json','{}');pds=file('pds/pds_shell.exe','unexecuted PDS fixture')
    compiled=file('build-b/compiled/selected.v','configured source')
    a.plan.update(Command=[str(pds)],Pins={'PinInventory':{str(i):{}for i in range(144)}})
    a.plan['PreparedSHA256'][str(compiled)]=bit.sha(compiled)
    adf=file('physical/final.adf','actual final ADF fixture');report=file('physical/final.rtr','ten-table fixture')
    exceptions=file('physical/exceptions.rtr','exact launch triplets');core=file('physical/core','current complete core')
    proof_path=file('final-proof.json','{}');physical=proof();physical.update(BuildPlan=bit.ref(build_plan),
        FinalADF=bit.ref(adf),FreshSTAReport=bit.ref(report),FreshSTAExceptions=bit.ref(exceptions),InputSHA256={str(core):bit.sha(core)})
    proof_path.write_text(json.dumps(physical));provider_file=file('tools/final.py','strict physical provider fixture')
    provider=SimpleNamespace(__file__=str(provider_file),verify=mock.Mock(side_effect=lambda path:(
        copy.deepcopy(physical),{core:bit.sha(core),proof_path:bit.sha(proof_path)})))
    monkeypatch.setattr(bit,'physical_provider',lambda:provider)
    monkeypatch.setattr(bit.build,'validate',lambda path:copy.deepcopy(a.plan))
    profile=file('profile/profile.json','source-bound profile fixture')
    profile_binder=mock.Mock(side_effect=lambda path,plan,watched:{'Profile':bit.ref(path)})
    monkeypatch.setattr(bit,'bind_profile',profile_binder)
    sustained_path=file('sustained/simulation.json','actual independent contention fixture')
    def sustained_bind(plan,watched):
        bit.add(watched,sustained_path)
        return {'Passed':True,'IndependentSustainedFixture':True}
    sustained_binder=mock.Mock(side_effect=sustained_bind)
    monkeypatch.setattr(bit,'bind_sustained',sustained_binder)
    request=file('bit-request.json',json.dumps({'Schema':bit.REQUEST_SCHEMA,'Target':bit.TARGET,
        'PhysicalProof':bit.ref(proof_path),'Profile':bit.ref(profile),**{k:bit.ref(p)for k,p in a.paths.items()}}))
    context=bit.audit_request(request)
    assert context['FinalADF']==adf and set(context['Simulations'])==set(bit.SIMULATIONS)
    assert str(profile)in context['Watched']and str(core)in context['Watched']
    assert context['SustainedSimulation']=={'Passed':True,'IndependentSustainedFixture':True}
    assert str(sustained_path)in context['Watched']
    sustained_binder.assert_called_once_with(a.plan,context['Watched'])
    for kind,path in a.paths.items():a.providers[kind].verify.assert_called_once_with(path)
    bit.audit_request(request);assert provider.verify.call_count==1
    bit.audit_request(request,use_cache=False);assert provider.verify.call_count==2
    a.paths['IOSimulation'].write_text('post-verification mutated wire receipt')
    with pytest.raises(ValueError,match='authority input drift'):bit.audit_request(request)
