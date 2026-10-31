import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_camera_vga_route_reset_scope as scope


def inputs():
    before={'NetAnnotations':{'_N101':'route','_N188':'route2','other':'unchanged'},
            'TargetRoutes':{'_N101':['driver','waypoint','load']},
            'TargetConnectivity':{'_N101':['source','sink']},
            'ExcludedBlockSHA256':{'CDB':'original constraints'}}
    after=copy.deepcopy(before);after['ExcludedBlockSHA256']['CDB']='new constraints'
    plain={'NonConstraintNonRouteSHA256':'same semantic tokens',
           'ConstraintPinReferences':[{'SHA256':'base-ref','Tokens':['(',')']}]}
    updated=copy.deepcopy(plain);updated['ConstraintPinReferences'].append({'SHA256':'reset-ref','Tokens':['(',')']})
    return before,after,plain,updated


def test_records_constraint_delta_without_approval():
    report=scope.verify(*inputs())
    assert report['CDBChanged'] is True
    assert report['ConstraintPinReferenceAdded']=={'reset-ref':1}
    assert report['ConstraintScopeAccepted'] is False


@pytest.mark.parametrize('mutation,reason',[('route','route inventory'),('tree','target tree'),
    ('connectivity','connectivity'),('placement','semantic tokens')])
def test_rejects_every_nonconstraint_change(mutation,reason):
    b,a,bs,cs=inputs()
    if mutation=='route':a['NetAnnotations']['other']='rerouted'
    elif mutation=='tree':a['TargetRoutes']['_N101']=['different']
    elif mutation=='connectivity':a['TargetConnectivity']['_N101']=['different']
    else:cs['NonConstraintNonRouteSHA256']='changed'
    with pytest.raises(ValueError,match=reason):scope.verify(b,a,bs,cs)
