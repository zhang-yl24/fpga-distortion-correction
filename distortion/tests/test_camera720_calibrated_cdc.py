"""Focused current-target CDC query and diagnostic coverage checks; CPU only."""
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_calibrated_cdc as current


def mapping(source='src/CLK',output='src/L5Q',endpoint='dst/I2',sc='camera_pclk',dc='board27'):
    return {'SourceNativeClockPin':source,'SourceNativeOutputPin':output,'NativeBoundaries':[{'Endpoint':endpoint}],
            'SourceClock':sc,'DestinationClock':dc}


def constraints():
    return {'RelevantStatements':[
        {'Line':9,'Text':'set_max_delay -datapath_only -from [get_clocks {camera_pclk}] -to [get_clocks {board27}] 8'},
        {'Line':10,'Text':'set_min_delay -from [get_clocks {camera_pclk}] -to [get_clocks {board27}] 0'}],
        'PeriodsNS':{'camera_pclk':20.833,'board27':37.037}}


class CurrentCDCTests(unittest.TestCase):
    def test_current_constraints_preserve_crossing_suppression_and_normal_hold(self):
        queries=current.make_queries([mapping(),mapping(source='other/CLK',output='other/L6Q',sc='board27')],constraints())
        cross=next(q for q in queries if 'SourceClock' in q)
        normal=next(q for q in queries if 'Clock' in q)
        self.assertEqual(cross['CheckKinds'],['max-delay'])
        self.assertTrue(cross['HoldAnalysisSuppressed']);self.assertTrue(cross['MinDelayNotAccepted'])
        self.assertEqual(cross['EffectiveMaximum']['Line'],9)
        self.assertEqual(normal['CheckKinds'],['setup','hold']);self.assertFalse(normal['HoldAnalysisSuppressed'])

    def test_unconstrained_crossing_and_conflicting_merged_domain_fail(self):
        with self.assertRaises(ValueError):current.make_queries([mapping(sc='unbound')],constraints())
        with self.assertRaises(ValueError):current.make_queries([mapping(),mapping(sc='board27')],constraints())

    def test_packed_launches_remain_distinct_and_missing_only(self):
        queries=current.make_queries([mapping(),mapping(output='src/L6Q'),mapping(endpoint='other/I3')],constraints())
        missing=[{**q,'Corner':'slow','Kind':'max-delay'} for q in queries[:2]]
        result=current.groups(queries,missing)
        self.assertEqual(sum(len(g['ExpectedIdentities']) for g in result),2)
        for g in result:
            self.assertEqual({r['LaunchOutput'] for r in g['ExpectedIdentities']},{g['LaunchOutput']})
            self.assertEqual({r['Source'] for r in g['ExpectedIdentities']},{g['Source']})
            self.assertIn('-through {'+g['LaunchOutput']+'}',g['Command'])

    def test_duplicate_missing_corners_do_not_repeat_command(self):
        queries=current.make_queries([mapping()],constraints())
        result=current.groups(queries,[queries[0],queries[0]])
        self.assertEqual(len(result),1)
        self.assertEqual(len(result[0]['ExpectedIdentities']),1)

    def test_endpoint_and_context_limits(self):
        queries=current.make_queries([mapping(endpoint=f'dst[{i}]/I2') for i in range(130)],constraints())
        result=current.groups(queries,queries)
        self.assertEqual([len(g['Endpoints']) for g in result],[128,2])
        self.assertEqual(len(current.bodies(result,1)),2)
        for invalid in (0,9,True):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):current.bodies(result,invalid)

    def test_unknown_missing_identity_and_unsafe_pin_fail(self):
        queries=current.make_queries([mapping()],constraints())
        with self.assertRaises(ValueError):current.groups(queries,[{**queries[0],'Endpoint':'unknown/I4'}])
        with self.assertRaises(ValueError):current.make_queries([mapping(endpoint='bad};exec')],constraints())

    def test_current_report_header_cannot_be_old_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.rtr'
            path.write_text('| Version : 2023.2-SP3 <build 154097>\n| Design : camera720_transport_top\n',encoding='ascii')
            with self.assertRaises(ValueError):current.collect([], [path])
            path.write_text('| Version : 2023.2-SP3 <build 154097>\n| Design : camera720_calibrated_top\n',encoding='ascii')
            with patch.object(current.timing.native,'blocks',return_value=[]):
                self.assertEqual(current.collect([],[path]),([],[],[]))

    def test_missing_coverage_never_becomes_pass(self):
        queries=current.make_queries([mapping()],constraints())
        summary=current.timing.coverage(queries,[],[])
        self.assertEqual(summary['ExpectedCases'],2)
        self.assertFalse(summary['EnumeratedPathsTimingPassed'])

    def test_only_source_locations_are_removed_and_other_bytes_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a',Path(tmp)/'b'
            keep=b'(NET n\r\n  (CONNECT (PORTREF I0 (INSTREF source)))\r\n)\r\n'
            a.write_bytes(keep.replace(b'(NET n\r\n',b'(NET n\r\n  (FILEID 25 )\r\n  (LINENUM 19 )\r\n'))
            value=current.normalize_source_locations(a,b)
            self.assertEqual(b.read_bytes(),keep)
            self.assertEqual(value['RemovedSourceMetadataCounts'],{'FILEID':1,'LINENUM':1})
            self.assertTrue(value['AllOtherBytesCopiedExactly'])

    def test_source_metadata_cannot_hide_connection(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'a',Path(tmp)/'b'
            a.write_bytes(b'(FILEID 25 (CONNECT (PORTREF I0)))\n')
            with self.assertRaises(ValueError):current.normalize_source_locations(a,b)


if __name__=='__main__':unittest.main()
