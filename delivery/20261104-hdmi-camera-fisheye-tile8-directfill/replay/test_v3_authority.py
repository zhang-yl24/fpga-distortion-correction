"""Synthetic finite authority metadata tests; no release or hardware evidence."""
from copy import deepcopy
import pytest
import v3_authority as v


def fragment():
    def ref(name):return {'Path':'D:/LOCAL_UNIT_FRAGMENT/'+name,'SHA256':'a'*64}
    names={'ProviderManifest','RootSourceReview','PrewarmWrapper','ReleaseGO','PrewarmAuthority','ReleaseDriver',
           'ReleaseInputManifest','RequestSnapshot','RequestComparison','ActualRequest',*v.FIVE_ROLES}
    refs={name:ref(name) for name in names}
    request={'Schema':v.PREFIX+'bitstream-request-v1','Target':v.TARGET,**{k:refs[k] for k in v.FIVE_ROLES}}
    bit={'Schema':v.PREFIX+'bitstream-plan-v1','Target':v.TARGET,'Request':refs['ActualRequest'],
         **{k:refs[k] for k in v.FIVE_ROLES}}
    go={'Schema':v.PREFIX+'physical-to-release-go-v1','ProviderRevision':v.REVISION,
        **{k:True for k in v.GO_FLAGS},**{k:refs[k] for k in v.FIVE_ROLES},
        'ProviderSourceManifest':refs['ProviderManifest'],'SelectedReleaseInputManifest':refs['ReleaseInputManifest']}
    warm={'Schema':v.PREFIX+'release-authority-prewarm-v1','Passed':True,'InputDrift':[],
          'RequestExclusiveCreatedByWrapper':True,'FreshRuntimeGateStillRequired':True,
          **{k:False for k in v.WARM_FALSE},'ExactRequest':request,'ProviderSourceManifest':refs['ProviderManifest'],
          'ReviewedWrapperManifest':refs['PrewarmWrapper'],'ActualSelectedFourRoleManifest':refs['ReleaseInputManifest'],
          'FrozenReleaseDriver':refs['ReleaseDriver'],'RequestSnapshot':refs['RequestSnapshot'],
          'RequestPath':refs['ActualRequest']['Path'],'RequestSHA256':'a'*64}
    transition={'Schema':v.PREFIX+'release-prewarm-authorized-transition-v1','Passed':True,'PrivateCacheAccessed':False,
        **{k:True for k in v.TRANSITION_FLAGS},'RootReleaseGo':refs['ReleaseGO'],'PrewarmReceipt':refs['PrewarmAuthority'],
        'ExpectedRealRequestSHA256':'a'*64,'FrozenReleaseDriver':refs['ReleaseDriver'],
        'RequestComparison':refs['RequestComparison']}
    return bit,go,warm,transition,refs


def test_finite_v3_metadata_fragment_passes_without_granting_source_authority(monkeypatch):
    facts=v.check_release_metadata(*fragment())
    assert facts['ReleaseFamily']=='tile8df8v3' and facts['OldV2AcceptanceInherited'] is False
    monkeypatch.setattr(v,'PROVIDER_SHA256',None)
    with pytest.raises(ValueError,match='not frozen'):v.pins_ready()


@pytest.mark.parametrize('which',range(4))
def test_crossfamily_v2_schema_is_rejected(which):
    args=fragment();args[which]['Schema']=args[which]['Schema'].replace('tile8df8v3','tile8df8v2')
    with pytest.raises(ValueError):v.check_release_metadata(*args)


@pytest.mark.parametrize('name',v.GO_FLAGS)
def test_every_v3_go_authority_flag_is_required(name):
    args=fragment();args[1][name]=False
    with pytest.raises(ValueError):v.check_release_metadata(*args)


@pytest.mark.parametrize('name',v.WARM_FALSE)
def test_prewarm_cannot_use_cache_patch_provider_or_grant_release(name):
    args=fragment();args[2][name]=True
    with pytest.raises(ValueError):v.check_release_metadata(*args)


@pytest.mark.parametrize('name',v.TRANSITION_FLAGS)
def test_every_transition_flag_is_required(name):
    args=fragment();args[3][name]=False
    with pytest.raises(ValueError):v.check_release_metadata(*args)


@pytest.mark.parametrize('name',v.FIVE_ROLES)
@pytest.mark.parametrize('side',['bit','go','request'])
def test_exact_five_roles_cannot_mix_runs_or_v2_identity(name,side):
    args=fragment();index={'bit':0,'go':1}.get(side)
    record=args[index] if index is not None else args[2]['ExactRequest']
    record[name]={'Path':'D:/OLD_OR_DIAGNOSTIC/'+name,'SHA256':'b'*64}
    with pytest.raises(ValueError):v.check_release_metadata(*args)


@pytest.mark.parametrize('which,key',[(0,'Request'),(1,'ProviderSourceManifest'),(1,'SelectedReleaseInputManifest'),
    (2,'ProviderSourceManifest'),(2,'ReviewedWrapperManifest'),(2,'ActualSelectedFourRoleManifest'),(2,'FrozenReleaseDriver'),
    (2,'RequestSnapshot'),(3,'RootReleaseGo'),(3,'PrewarmReceipt'),(3,'FrozenReleaseDriver'),(3,'RequestComparison')])
def test_each_explicit_authority_reference_is_bound(which,key):
    args=fragment();args[which][key]={'Path':'D:/another-attempt/'+key,'SHA256':'b'*64}
    with pytest.raises(ValueError):v.check_release_metadata(*args)


@pytest.mark.parametrize('mutation',['revision','target','drift','request_extra','request_schema','request_path',
                                    'requestsha','transition_sha','transition_private','missing_ref','partial_ref'])
def test_other_metadata_mutations_rejected(mutation):
    args=fragment()
    if mutation=='revision':args[1]['ProviderRevision']='tile8df8v2-bounded-b'
    elif mutation=='target':args[0]['Target']='another_top'
    elif mutation=='drift':args[2]['InputDrift']=['changed']
    elif mutation=='request_extra':args[2]['ExactRequest']['UseCache']=True
    elif mutation=='request_schema':args[2]['ExactRequest']['Schema']='diagnostic-only'
    elif mutation=='request_path':args[2]['RequestPath']='D:/OLD/bit-request-v2-a.json'
    elif mutation=='requestsha':args[2]['RequestSHA256']='b'*64
    elif mutation=='transition_sha':args[3]['ExpectedRealRequestSHA256']='b'*64
    elif mutation=='transition_private':args[3]['PrivateCacheAccessed']=True
    elif mutation=='missing_ref':args[4].pop('RootSourceReview')
    else:args[4]['RootSourceReview']={'Path':'missing sha'}
    with pytest.raises(ValueError):v.check_release_metadata(*args)


def test_unfrozen_final_pins_are_not_inherited_from_v2(monkeypatch):
    for key in ('PROVIDER_SHA256','ROOT_REVIEW_SHA256','WRAPPER_SHA256'):monkeypatch.setattr(v,key,None)
    refs=fragment()[4]
    with pytest.raises(ValueError,match='not frozen'):
        v.check_source_freeze(refs['ProviderManifest'],refs['RootSourceReview'],refs['PrewarmWrapper'],
                              refs['ProviderManifest'],refs['RootSourceReview'])


@pytest.mark.parametrize('wrong_index',range(5))
def test_new_pins_and_both_original_provenance_refs_are_all_required(monkeypatch,wrong_index):
    monkeypatch.setattr(v,'PROVIDER_SHA256','1'*64);monkeypatch.setattr(v,'ROOT_REVIEW_SHA256','2'*64)
    monkeypatch.setattr(v,'WRAPPER_SHA256','3'*64)
    hashes=['1'*64,'2'*64,'3'*64,v.ORIGINAL_PROVIDER_SHA256,v.ORIGINAL_ROOT_REVIEW_SHA256]
    refs=[{'Path':'D:/LOCAL_UNIT_FRAGMENT/'+str(i),'SHA256':h} for i,h in enumerate(hashes)]
    assert v.check_source_freeze(*refs)['NewV3AndOriginalProvenanceBothRequired']
    refs[wrong_index]['SHA256']='0'*64
    with pytest.raises(ValueError):v.check_source_freeze(*refs)
