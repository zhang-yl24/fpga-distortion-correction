from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_raw_reset_fast_inspect as fast
import camera720_raw_reset_fast_effect as effect

class AuthorityTests(unittest.TestCase):
    def value(self):
        return {'Schema':fast.AUTHORITY_SCHEMA,'Target':fast.prep.TARGET,'FullVerificationCompleted':True,
            'ValidationMethod':{'Function':'camera720_raw_reset_apply.bind_completed',
              'Path':str(fast.physical.SELF),'SHA256':fast.sha(fast.physical.SELF)},
            'Producer':fast.reference(fast.SELF),'EDAExecuted':False,'HardwareAccessed':False,
            'HardwareReleaseAllowed':False,'TimingAccepted':False}

    def test_exact_validator_and_false_authority_required(self):
        fast.authority_shape(self.value())
        for key,value in [('FullVerificationCompleted',False),('Schema','old'),
                          ('Target','camera720_transport_top'),('TimingAccepted',True),
                          ('HardwareReleaseAllowed',True)]:
            data=self.value();data[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):fast.authority_shape(data)

    def test_validator_bytes_and_function_identity_cannot_drift(self):
        for key,value in [('SHA256','0'*64),('Function','another.binder')]:
            data=self.value();data['ValidationMethod'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):fast.authority_shape(data)

    def test_source_authority_cannot_use_another_producer(self):
        data=self.value();data['Producer']['SHA256']='0'*64
        with self.assertRaises(ValueError):fast.authority_shape(data)

    def test_fresh_report_has_no_mutation(self):
        text=fast.render('report','',fast.prep.WORK,fast.prep.WORK/'fixture')
        self.assertEqual(text.count(fast.INIT),1)
        for bad in ('save_adif','set_false_path','manual_route','unroute','gen_bitstream'):
            self.assertNotIn(bad,text)

    def test_new_completion_marker_cannot_be_injected(self):
        with self.assertRaisesRegex(ValueError,'reserved'):
            fast.render('query','',fast.prep.WORK,fast.prep.WORK,'puts {'+fast.MARKER+'}')

    def test_fast_effect_never_accepts_old_target(self):
        with self.assertRaisesRegex(ValueError,'current720'):
            effect.graph('module camera720_transport_top(input a); endmodule')

    def test_fast_effect_requires_exact_routes_and_nonconstraint_tokens(self):
        before={'NetAnnotations':{'net0':'a'},'TargetConnectivity':{},'RouteCount':1}
        scope={'NonConstraintNonRouteSHA256':'x'}
        changed={'NetAnnotations':{'net0':'b'},'TargetConnectivity':{},'RouteCount':1}
        with self.assertRaises(ValueError):effect.semantics.compare_routes(before,changed,scope,scope)
        with self.assertRaises(ValueError):effect.semantics.compare_routes(before,before,scope,{'NonConstraintNonRouteSHA256':'changed'})

if __name__=='__main__':unittest.main()
