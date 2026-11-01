"""Reset effects must preserve data timing, native constraints and sibling routes."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import audit_raw_camera_reset_effect as audit


def entry(identifier, instance, pin, direction, context='context'):
    return {'ContextSHA256':context, 'Instance':instance,
            'Tree':['CDBENTRY', ['CDBID',identifier], ['FILEID','1'], ['LINENUM','1'],
                    ['TYPE',direction], ['PINNAME',pin]]}


def constraints():
    old = {'NonConstraintNonRouteSHA256':'unchanged',
           'CDB':['CDB', ['FN','base.fdc'], ['IODLY',['CDBID','1000']]],
           'Entries':[entry('1000','input','D','3')]}
    new = copy.deepcopy(old)
    new['CDB'].append(['FP',['FID','1'],['LN','1'],['CDBID','1001'],['SU','1'],['HD','1'],['EXCPTFEA','264437760']])
    new['Entries'] += [entry('1001','source','CLK','1'),entry('1001','sink','RS','3')]
    return old, new, [{'Source':'source/CLK','Targets':['sink/RS']}]


class ConstraintTests(unittest.TestCase):
    def test_exact_scoped_addition(self):
        result = audit.compare_constraints(*constraints())
        self.assertEqual(result['AddedSourceEndpointPairs'], 1)

    def test_missing_scope_rejected(self):
        old,new,queries = constraints(); new['Entries'].pop()
        with self.assertRaisesRegex(ValueError, 'missing endpoints'):
            audit.compare_constraints(old,new,queries)

    def test_extra_data_endpoint_rejected(self):
        old,new,queries = constraints();new['Entries'].append(entry('1001','pixel','D','3'))
        with self.assertRaisesRegex(ValueError, 'differs from proved'):
            audit.compare_constraints(old,new,queries)

    def test_moved_existing_reference_rejected(self):
        old,new,queries = constraints();new['Entries'][0]['Instance']='other'
        with self.assertRaisesRegex(ValueError, 'moved, changed or removed'):
            audit.compare_constraints(old,new,queries)

    def test_changed_existing_clock_constraint_rejected(self):
        old,new,queries = constraints();new['CDB'][2].append(['MIN','999'])
        with self.assertRaisesRegex(ValueError, 'constraint changed or removed'):
            audit.compare_constraints(old,new,queries)

    def test_unbounded_false_path_rejected(self):
        old,new,queries = constraints();new['CDB'][-1].append(['THROUGH','any'])
        with self.assertRaisesRegex(ValueError, 'exact scoped false-path'):
            audit.compare_constraints(old,new,queries)

    def test_id_collision_rejected(self):
        old,new,queries = constraints();new['CDB'][-1][3][1]='1000'
        with self.assertRaisesRegex(ValueError, 'reuses a prior'):
            audit.compare_constraints(old,new,queries)

    def test_semantic_change_rejected(self):
        old,new,queries = constraints();new['NonConstraintNonRouteSHA256']='changed'
        with self.assertRaisesRegex(ValueError, 'functional/placement'):
            audit.compare_constraints(old,new,queries)


def path(corner,kind,delta=0):
    slack = 5 + (-delta if kind == 'setup' else delta)
    return {'Source':'cam_data[2] (port)','Endpoint':'receiver/D',
            'LaunchClock':'camera_pclk','CaptureClock':'camera_pclk',
            'LaunchEdge':'rising','CaptureEdge':'rising','Corner':corner,'Kind':kind,'SlackNS':slack,
            '_Lines':[
                'Startpoint  : cam_data[2] (port)\n', 'Endpoint : receiver/D\n',
                ' Clock camera_pclk (rising edge) 0.000 0.000 r\n',
                ' Input external delay 0.000 0.000 f\n',
                ' IOLHR_16_294/DI_TO_CLK td 0.500 0.500 f buffer/O\n',
                f' net (fanout=4) {1+delta:.3f} {1.5+delta:.3f} nt_cam_data[2]\n',
                ' CLMA_243_420/M3 f receiver/D\n',
                f' Data arrival time {1.5+delta:.3f} Logic Levels: 2\n',
                f' Logic: 0.500ns(33.333%), Route: {1+delta:.3f}ns(66.667%)\n',
                ' Capture Clock Delay : 3.796\n', ' Data required time 6.500\n',
                f' Data arrival time {1.5+delta:.3f}\n', f' Slack (MET) {slack:.3f}\n']}


class TargetPathTests(unittest.TestCase):
    def fixture(self):
        old = [path(c,k) for c in ('slow','fast') for k in ('setup','hold')]
        new = [path(c,k,1.2) for c in ('slow','fast') for k in ('setup','hold')]
        targets = [{'Source':'cam_data[2] (port)','Endpoint':'receiver/D',
                    'PhysicalRepairCandidate':{'Net':'nt_cam_data[2]'}}]
        return old,new,targets

    def test_port_path_only_terminal_delay_changes(self):
        result = audit.compare_target_records(*self.fixture())
        self.assertTrue(result[0]['AllFourChecksMet'])

    def test_camera_budget_change_rejected(self):
        old,new,targets = self.fixture();new[0]['_Lines'][3]=' Input external delay 0.500 0.500 f\n'
        with self.assertRaisesRegex(ValueError, 'beyond the requested'):
            audit.compare_target_records(old,new,targets)

    def test_capture_clock_change_rejected(self):
        old,new,targets = self.fixture();new[0]['_Lines'][9]=' Capture Clock Delay : 3.000\n'
        with self.assertRaisesRegex(ValueError, 'beyond the requested'):
            audit.compare_target_records(old,new,targets)

    def test_wrong_slack_delta_rejected(self):
        old,new,targets = self.fixture();new[0]['_Lines'][-1]=' Slack (MET) 9.000\n'
        with self.assertRaisesRegex(ValueError, 'beyond the requested'):
            audit.compare_target_records(old,new,targets)

    def test_missing_corner_rejected(self):
        old,new,targets = self.fixture();new.pop()
        with self.assertRaisesRegex(ValueError, 'multiplicity'):
            audit.compare_target_records(old,new,targets)


class TimingInventoryTests(unittest.TestCase):
    def fixture(self):
        row = {'TotalChecks':10,'FailingChecks':0,'WorstSlackNS':1.0,'TotalNegativeSlackNS':0}
        before = {(c,k):{('data','data'):dict(row)} for c in ('slow','fast') for k in audit.native.KINDS}
        groups = []
        for corner in ('slow','fast'):
            groups.append({'Corner':corner,'LaunchClock':'startup','CaptureClock':'reset',
                           'Complete':True,'ObservedLogicalChecks':1})
            for kind in ('recovery','removal'):
                before[(corner,kind)][('startup','reset')] = {**row,'TotalChecks':1}
        after = copy.deepcopy(before)
        for corner in ('slow','fast'):
            for kind in ('recovery','removal'):del after[(corner,kind)][('startup','reset')]
        return before,after,{'Groups':groups},{('data','data')}

    def test_only_proved_reset_counts_disappear(self):
        summary,_ = audit.compare_timing(*self.fixture())
        self.assertEqual(summary['slow_recovery']['RemovedResetChecks'],1)

    def test_removed_data_check_rejected(self):
        before,after,inventory,pairs = self.fixture()
        after[('slow','hold')][('data','data')]['TotalChecks'] -= 1
        with self.assertRaisesRegex(ValueError, 'checks removed'):
            audit.compare_timing(before,after,inventory,pairs)

    def test_remaining_hold_failure_rejected(self):
        before,after,inventory,pairs = self.fixture()
        after[('fast','hold')][('data','data')]['FailingChecks'] = 1
        with self.assertRaisesRegex(ValueError, 'remaining native timing failure'):
            audit.compare_timing(before,after,inventory,pairs)


if __name__ == '__main__':unittest.main()
