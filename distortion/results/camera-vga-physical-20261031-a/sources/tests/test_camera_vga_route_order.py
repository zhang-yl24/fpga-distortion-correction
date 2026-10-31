import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_camera_vga_route_order as order


def inputs():
    before={'ExcludedBlockSHA256':{'CDB':'identical'},'TargetConnectivity':{'n':['s','d']},
            'NetAnnotations':{'n':'before','other':'unchanged'}}
    after=copy.deepcopy(before);after['NetAnnotations']['n']='after'
    normalized={'OrderedNonRouteSemanticSHA256':'identical semantics','CDBRawTextSHA256':'identical text'}
    return before,after,normalized,copy.deepcopy(normalized)


def test_accept_order_only_change():
    assert order.validate(*inputs(),{'n'})['CDBRawTextIdentical'] is True


@pytest.mark.parametrize('mutation,reason',[('entry','sibling order'),('raw_cdb','raw CDB'),
    ('cdb_tokens','constraint block'),('route','scope differs')])
def test_reject_content_change_after_order_normalization(mutation,reason):
    b,a,bo,ao=inputs()
    if mutation=='entry':ao['OrderedNonRouteSemanticSHA256']='entry changed or moved'
    elif mutation=='raw_cdb':ao['CDBRawTextSHA256']='waiver'
    elif mutation=='cdb_tokens':a['ExcludedBlockSHA256']['CDB']='waiver'
    else:a['NetAnnotations']['other']='rerouted'
    with pytest.raises(ValueError,match=reason):order.validate(b,a,bo,ao,{'n'})


def sample_dump(path,first=(1,2),second=(),changed=None):
    text=['(ADIF "output.txt"','  (TIMESTAMP "time")','  (ATTR_FN "source.v")']
    for parent,entries in [('parentA',first),('parentB',second)]:
        text.append('  (NODE '+parent)
        for number in entries:
            text.extend(['    (CDBENTRY',f'      (CDBID {number})',
                         f'      (TYPE {changed if changed is not None and number==1 else 4})','    )'])
        text.append('  )')
    for number in range(1001):
        text.extend([f'  (NETANNOTATE (NETREF n{number})','  )'])
    text.extend(['  (CDB','    (CONSTRAINT exact)','  )','  (FILETABLE','  )',')'])
    path.write_text('\n'.join(text)+'\n')


def test_actual_parser_only_sorts_same_parent_siblings(tmp_path):
    baseline=tmp_path/'base.txt';reordered=tmp_path/'reordered.txt';moved=tmp_path/'moved.txt';changed=tmp_path/'changed.txt'
    sample_dump(baseline);sample_dump(reordered,first=(2,1))
    sample_dump(moved,first=(1,),second=(2,));sample_dump(changed,changed=5)
    values=[order.ordered_semantics(p)['OrderedNonRouteSemanticSHA256']
            for p in (baseline,reordered,moved,changed)]
    assert values[0]==values[1]
    assert values[0]!=values[2]
    assert values[0]!=values[3]
